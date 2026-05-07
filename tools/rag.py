"""RAG retriever for log-based context.

Loads the ChromaDB vector store and retrieves relevant log entries
to enrich LLM prompts in Steps 4 and 5 with root-cause context.
"""

from __future__ import annotations

import logging
import os

from langchain_community.vectorstores import Chroma
from langchain_openai import AzureOpenAIEmbeddings

logger = logging.getLogger(__name__)
rag_logger = logging.getLogger("observer_advisor.rag")

VECTORSTORE_DIR = os.path.join(os.path.dirname(__file__), "..", "vectorstore", "chroma_logs")
COLLECTION_NAME = "observer_logs"


def _get_embeddings() -> AzureOpenAIEmbeddings:
    return AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    )


def _get_vectorstore() -> Chroma:
    return Chroma(
        persist_directory=VECTORSTORE_DIR,
        embedding_function=_get_embeddings(),
        collection_name=COLLECTION_NAME,
    )


def retrieve_logs(query: str, application: str, k: int = 5) -> str:
    """Retrieve relevant log entries from ChromaDB.

    Args:
        query: Semantic search query (e.g. detection evidence text).
        application: Filter logs by application name (e.g. "ASCM").
        k: Number of results to return.

    Returns:
        Formatted string of retrieved log entries, ready for prompt injection.
        Returns empty string if retrieval fails or no results found.
    """
    try:
        rag_logger.info(f"Query app={application} k={k} q='{query[:80]}...'")
        vectorstore = _get_vectorstore()
        results = vectorstore.similarity_search(
            query,
            k=k,
            filter={"application": application},
        )

        if not results:
            rag_logger.info(f"No logs found for app={application}")
            logger.info(f"No logs found for query='{query[:50]}...' app={application}")
            return ""

        lines = []
        for doc in results:
            meta = doc.metadata
            lines.append(
                f"[{meta.get('timestamp', '?')}] [{meta.get('severity', '?')}] "
                f"({meta.get('job_name', '?')}) {doc.page_content}"
            )

        rag_logger.info(f"Retrieved {len(results)} log entries for {application}")
        rag_logger.debug(f"Results for {application}:\n" + "\n".join(
            f"  - [{r.metadata.get('severity')}] {r.page_content[:100]}" for r in results
        ))
        logger.info(f"Retrieved {len(results)} log entries for {application}")
        return "\n\n".join(lines)

    except Exception as e:
        rag_logger.error(f"RAG retrieval failed for {application}: {e}")
        logger.warning(f"RAG retrieval failed (continuing without): {e}")
        return ""
