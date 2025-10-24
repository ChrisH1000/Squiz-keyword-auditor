"""Split documents and create vector embeddings."""

import logging
from pathlib import Path
from typing import List, Dict, Union
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

logger = logging.getLogger(__name__)


class VectorStoreBuilder:
    """Builds and manages the vector store for documentation."""

    def __init__(
        self,
        persist_dir: Union[str, Path],
        embedding_model: str = "bge-small",
        chunk_size: int = 1200,
        chunk_overlap: int = 120,
    ):
        """Initialize vector store builder.

        Args:
            persist_dir: Directory to persist the vector store
            embedding_model: Ollama embedding model name
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        # Initialize embeddings
        logger.info(f"Initializing Ollama embeddings with model: {embedding_model}")
        self.embeddings = OllamaEmbeddings(model=embedding_model)

        self.vector_store = None

    def build(self, docs: List[Dict[str, str]], rebuild: bool = False) -> Chroma:
        """Build vector store from documents.

        Args:
            docs: List of document dicts with 'text', 'url', 'title'
            rebuild: If True, rebuild even if exists

        Returns:
            Chroma vector store
        """
        collection_name = "squiz_docs"

        # Check if vector store exists
        if not rebuild and self._vector_store_exists():
            logger.info("Loading existing vector store")
            self.vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(self.persist_dir),
            )
            return self.vector_store

        # Create LangChain Documents
        logger.info(f"Processing {len(docs)} documents")
        langchain_docs = []

        for doc in docs:
            langchain_docs.append(
                Document(
                    page_content=doc["text"],
                    metadata={
                        "source": doc["url"],
                        "title": doc.get("title", ""),
                    }
                )
            )

        # Split documents
        logger.info("Splitting documents into chunks")
        splits = self.text_splitter.split_documents(langchain_docs)
        logger.info(f"Created {len(splits)} chunks")

        # Create vector store
        logger.info("Creating vector store and generating embeddings...")
        self.vector_store = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            collection_name=collection_name,
            persist_directory=str(self.persist_dir),
        )

        logger.info(f"Vector store created with {len(splits)} chunks")
        return self.vector_store

    def get_vector_store(self) -> Chroma:
        """Get the vector store instance.

        Returns:
            Chroma vector store
        """
        if self.vector_store is None:
            collection_name = "squiz_docs"
            self.vector_store = Chroma(
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(self.persist_dir),
            )
        return self.vector_store

    def _vector_store_exists(self) -> bool:
        """Check if vector store already exists.

        Returns:
            True if exists, False otherwise
        """
        chroma_file = self.persist_dir / "chroma.sqlite3"
        return chroma_file.exists()

    def search(self, query: str, k: int = 3) -> List[Document]:
        """Search the vector store.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of relevant documents
        """
        if self.vector_store is None:
            self.vector_store = self.get_vector_store()

        return self.vector_store.similarity_search(query, k=k)
