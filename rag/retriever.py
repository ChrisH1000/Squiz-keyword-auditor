"""RAG-based keyword retriever for validation and citations."""

import logging
from typing import List, Dict
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class KeywordRetriever:
    """Retrieves documentation snippets for keyword validation."""

    def __init__(self, vector_store, k: int = 3):
        """Initialize retriever.

        Args:
            vector_store: Chroma vector store instance
            k: Number of neighbors to retrieve
        """
        self.vector_store = vector_store
        self.k = k

    def validate_keywords(self, keywords: List[Dict]) -> List[Dict]:
        """Validate keywords using RAG lookups.

        Args:
            keywords: List of keyword dicts from KeywordExtractor

        Returns:
            List of keywords with validation results and citations
        """
        validated = []

        for keyword in keywords:
            normalized = keyword["normalized"]
            keyword_base = normalized.strip('%').split(':')[0].split('^')[0]

            # Construct query based on keyword prefix to find the right documentation page
            if keyword_base.startswith('globals_'):
                query = f"global keywords {keyword_base} example"
            elif keyword_base.startswith('frontend_'):
                query = f"frontend asset keywords {keyword_base}"
            else:
                query = f"common keywords {keyword_base} example"

            docs = self._retrieve(query)

            # Determine if valid based on retrieval results
            is_valid = self._is_keyword_valid(normalized, docs)

            # Format citations
            citations = self._format_citations(docs)

            keyword_result = {
                **keyword,
                "valid": is_valid,
                "citations": citations,
            }
            validated.append(keyword_result)

        return validated

    def _retrieve(self, query: str) -> List[Document]:
        """Retrieve relevant documents.

        Args:
            query: Search query

        Returns:
            List of relevant documents
        """
        try:
            docs = self.vector_store.similarity_search(query, k=self.k)
            logger.debug(f"Retrieved {len(docs)} documents for: {query}")
            return docs
        except Exception as e:
            logger.error(f"Retrieval failed for {query}: {e}")
            return []

    def _is_keyword_valid(self, normalized_keyword: str, docs: List[Document]) -> bool:
        """Determine if keyword is valid based on retrieved docs.

        Args:
            normalized_keyword: Normalized keyword string
            docs: Retrieved documents

        Returns:
            True if valid, False otherwise
        """
        if not docs:
            return False

        # Extract keyword base by stripping % and splitting on : and ^
        keyword_base = normalized_keyword.strip('%').split(':')[0].split('^')[0]

        for doc in docs:
            content = doc.page_content.lower()
            keyword_lower = keyword_base.lower()

            # Check 1: keyword with percentage signs (most common in docs)
            if f'%{keyword_lower}%' in content or f'%{keyword_lower}:' in content or f'%{keyword_lower}^' in content:
                return True

            # Check 2: exact match without % signs
            if keyword_lower in content:
                return True

            # Check 3: pattern match with spaces (e.g., asset_name -> asset name)
            if keyword_lower.replace('_', ' ') in content:
                return True

            # Check 4: Pattern template matching (e.g., %globals_asset_attribute_alt% matches %globals_asset_attribute_<attribute>%)
            # Extract prefix patterns by progressively removing suffix parts
            parts = keyword_lower.split('_')
            for i in range(len(parts), 1, -1):
                prefix = '_'.join(parts[:i])
                # Check for template patterns like %prefix_<something>%
                if f'%{prefix}_<' in content or f'%{prefix}_ <' in content:
                    return True
                # Also check for the prefix with common variations
                if f'{prefix}_<' in content:
                    return True

            # Check 5: Common keyword prefixes that indicate validity
            # asset_* keywords
            if keyword_lower.startswith('asset_') and '%asset_' in content:
                # Make sure it's a common asset keyword by checking for multiple asset_ keywords
                asset_keyword_count = content.count('%asset_')
                if asset_keyword_count >= 3:  # Likely a valid asset keyword page
                    return True

            # globals_* keywords
            if keyword_lower.startswith('globals_') and '%globals_' in content:
                globals_keyword_count = content.count('%globals_')
                if globals_keyword_count >= 3:  # Likely a valid globals keyword page
                    return True

            # frontend_* keywords
            if keyword_lower.startswith('frontend_') and '%frontend_' in content:
                frontend_keyword_count = content.count('%frontend_')
                if frontend_keyword_count >= 2:  # Likely a valid frontend keyword page
                    return True

        # If no match in top docs, likely invalid or deprecated
        return False

    def _format_citations(self, docs: List[Document]) -> List[Dict]:
        """Format retrieved documents as citations.

        Args:
            docs: Retrieved documents

        Returns:
            List of citation dicts
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
        """Get full documentation for a keyword.

        Args:
            keyword: Keyword to document

        Returns:
            Documentation text
        """
        query = f"keyword {keyword} usage examples syntax"
        docs = self._retrieve(query)

        if not docs:
            return f"No documentation found for {keyword}"

        # Combine top results
        doc_text = "\n\n".join([
            f"From {doc.metadata.get('title', 'Unknown')}:\n{doc.page_content}"
            for doc in docs
        ])

        return doc_text
