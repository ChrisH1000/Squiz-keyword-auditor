"""RAG-based keyword retriever for validation and citations.

This module provides a small helper class around a Chroma-style
vector store to retrieve documentation snippets relevant to
Squiz Matrix keywords and to determine if a keyword is valid
based on the retrieved documentation.

The implementation avoids changing the vector store API and
keeps the validation logic local so it can be tuned without
rebuilding the index.
"""

import logging
from typing import List, Dict
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class KeywordRetriever:
    """Retrieves documentation snippets for keyword validation.

    Responsibilities:
    - Build search queries adapted to keyword families (globals/frontend/common)
    - Retrieve top-k similar document chunks from the vector store
    - Apply a multi-check validation routine to decide if a keyword
      is present/valid in the documentation
    - Format citation metadata for reporting
    """

    def __init__(self, vector_store, k: int = 3):
        """Initialize retriever.

        Args:
            vector_store: Chroma-like vector store instance that implements
                          similarity_search(query, k=...) -> List[Document]
            k: Number of neighbors to retrieve per query
        """
        self.vector_store = vector_store
        self.k = k

    def validate_keywords(self, keywords: List[Dict]) -> List[Dict]:
        """Validate a list of extracted keywords using RAG lookups.

        Each keyword is queried against the vector store using a
        short, family-aware search query. The retrieved documents are
        then passed to _is_keyword_valid which runs several heuristics
        to determine validity.

        Args:
            keywords: List of keyword dicts. Each dict is expected to
                      contain at least a "normalized" key.

        Returns:
            A new list of keyword dicts extended with "valid" (bool)
            and "citations" (list) keys for reporting.
        """
        validated = []

        for keyword in keywords:
            normalized = keyword["normalized"]

            # Extract the base keyword (strip surrounding % and any modifiers
            # like :123 or ^modifier). This base is used to choose which
            # documentation chapter to query and for matching checks.
            keyword_base = normalized.strip('%').split(':')[0].split('^')[0]

            # Construct query based on keyword prefix to bias retrieval
            # toward the most relevant documentation chapter. Using a
            # family-specific term (e.g., "global keywords") helps the
            # vector search return chunks from the intended page.
            if keyword_base.startswith('globals_'):
                query = f"global keywords {keyword_base} example"
            elif keyword_base.startswith('frontend_'):
                query = f"frontend asset keywords {keyword_base}"
            else:
                query = f"common keywords {keyword_base} example"

            # Retrieve top-k similar chunks
            docs = self._retrieve(query)

            # Run validation heuristics against the retrieved docs
            is_valid = self._is_keyword_valid(normalized, docs)

            # Prepare citation metadata for reporting
            citations = self._format_citations(docs)

            keyword_result = {
                **keyword,
                "valid": is_valid,
                "citations": citations,
            }
            validated.append(keyword_result)

        return validated

    def _retrieve(self, query: str) -> List[Document]:
        """Retrieve relevant documents from the vector store.

        This helper wraps the underlying vector store call and logs the
        result. It returns an empty list on error so callers can handle
        missing docs gracefully.
        """
        try:
            docs = self.vector_store.similarity_search(query, k=self.k)
            logger.debug(f"Retrieved {len(docs)} documents for: {query}")
            return docs
        except Exception as e:
            # Log and return empty list on retrieval failure
            logger.error(f"Retrieval failed for {query}: {e}")
            return []

    def _is_keyword_valid(self, normalized_keyword: str, docs: List[Document]) -> bool:
        """Determine if a normalized keyword is present/valid in docs.

        The validation applies multiple heuristics because the vector
        search sometimes returns nearby context (headers/intros) rather
        than the explicit keyword table. The checks are ordered from
        strictest to loosest:

        1. Exact keyword pattern with percent signs (e.g. %asset_name%)
        2. Plain text match of the base keyword
        3. Underscore -> space variant (human readable)
        4. Template-style prefix matching (e.g. %prefix_<something>% patterns)
        5. Family occurrence heuristics (if the doc contains several
           %asset_ or %globals_ entries it's likely the correct page)

        Args:
            normalized_keyword: Keyword including % and optional modifiers
            docs: Retrieved Document objects to inspect

        Returns:
            True if any heuristic indicates the keyword is valid
        """
        if not docs:
            return False

        # Base keyword used for matching checks (strip % and modifiers)
        keyword_base = normalized_keyword.strip('%').split(':')[0].split('^')[0]

        for doc in docs:
            # Lower-case the content for case-insensitive matching
            content = doc.page_content.lower()
            keyword_lower = keyword_base.lower()

            # Check 1: exact keyword patterns commonly present in docs
            if (
                f'%{keyword_lower}%' in content
                or f'%{keyword_lower}:' in content
                or f'%{keyword_lower}^' in content
            ):
                return True

            # Check 2: plain appearance of the base keyword (looser)
            if keyword_lower in content:
                return True

            # Check 3: underscore-to-space variation (human readable tables)
            if keyword_lower.replace('_', ' ') in content:
                return True

            # Check 4: template-style prefix matching. This handles
            # patterns like %globals_asset_attribute_<attribute>% which
            # may be documented with a placeholder rather than an exact name.
            parts = keyword_lower.split('_')
            for i in range(len(parts), 1, -1):
                prefix = '_'.join(parts[:i])
                # Look for placeholders that start with prefix_ < or prefix_<
                if f'%{prefix}_<' in content or f'%{prefix}_ <' in content:
                    return True
                if f'{prefix}_<' in content:
                    return True

            # Check 5: family heuristics — if a doc contains many entries
            # from the same family it's likely the correct keyword page.
            if keyword_lower.startswith('asset_') and '%asset_' in content:
                asset_keyword_count = content.count('%asset_')
                if asset_keyword_count >= 3:
                    return True

            if keyword_lower.startswith('globals_') and '%globals_' in content:
                globals_keyword_count = content.count('%globals_')
                if globals_keyword_count >= 3:
                    return True

            if keyword_lower.startswith('frontend_') and '%frontend_' in content:
                frontend_keyword_count = content.count('%frontend_')
                if frontend_keyword_count >= 2:
                    return True

        # No heuristic matched — treat as invalid or missing
        return False

    def _format_citations(self, docs: List[Document]) -> List[Dict]:
        """Format retrieved documents into a small citation dict.

        Each citation contains a rank (1..k), a title, URL and a short
        snippet to display in reports.
        """
        citations = []

        for i, doc in enumerate(docs, 1):
            citation = {
                "rank": i,
                "title": doc.metadata.get("title", "Unknown"),
                "url": doc.metadata.get("source", ""),
                "snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
            }
            citations.append(citation)

        return citations

    def get_keyword_documentation(self, keyword: str) -> str:
        """Return combined documentation text for a keyword.

        This helper is useful for debugging and for generating a
        human-readable explanation of where a keyword is documented.
        """
        query = f"keyword {keyword} usage examples syntax"
        docs = self._retrieve(query)

        if not docs:
            return f"No documentation found for {keyword}"

        # Concatenate the top documents into a single string with titles
        doc_text = "\n\n".join([
            f"From {doc.metadata.get('title', 'Unknown')}:\n{doc.page_content}"
            for doc in docs
        ])

        return doc_text
