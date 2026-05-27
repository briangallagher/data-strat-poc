"""MCP server wrapping Milvus vector search for the underwriting knowledge base."""

import logging
import os
from typing import Optional

from fastmcp import FastMCP
from pymilvus import MilvusClient
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MILVUS_URI = os.environ.get("MILVUS_URI", "http://localhost:19530")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "ibm-granite/granite-embedding-125m-english")
DEFAULT_COLLECTION = os.environ.get("DEFAULT_COLLECTION", "underwriting_guidelines")
DEFAULT_TOP_K = int(os.environ.get("DEFAULT_TOP_K", "10"))

_embedding_model: Optional[SentenceTransformer] = None
_milvus_client: Optional[MilvusClient] = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


def get_milvus_client() -> MilvusClient:
    global _milvus_client
    if _milvus_client is None:
        logger.info(f"Connecting to Milvus: {MILVUS_URI}")
        _milvus_client = MilvusClient(uri=MILVUS_URI)
    return _milvus_client


mcp = FastMCP("Underwriting Knowledge Base")


class ChunkResult(BaseModel):
    """A single retrieved chunk with full metadata."""
    doc_id: str
    chunk_index: int
    pipeline_run_id: str
    text: str
    score: float
    category: str
    subcategory: str
    document_date: str
    section_path: str
    page_numbers: str


class SearchResult(BaseModel):
    """Result of a Milvus vector search."""
    status: str
    collection: str
    query: str
    total_results: int
    chunks: list[ChunkResult]


@mcp.tool
def milvus_search(
    query: str,
    collection: str = DEFAULT_COLLECTION,
    top_k: int = DEFAULT_TOP_K,
    category_filter: str = "",
    subcategory_filter: str = "",
) -> SearchResult:
    """
    Search the underwriting knowledge base using semantic similarity.

    Returns document chunks ranked by relevance, with full metadata
    including doc_id, pipeline_run_id, and source text for citation.

    Args:
        query: Natural language question to search for.
        collection: Milvus collection to search. One of: underwriting_guidelines,
                    regulatory_bulletins, iso_forms.
        top_k: Number of results to return. Defaults to 10.
        category_filter: Filter by document category (e.g., "commercial_property").
        subcategory_filter: Filter by subcategory (e.g., "circular_letter").
    """
    logger.info(f"Search: query={query!r}, collection={collection}, top_k={top_k}")

    try:
        model = get_embedding_model()
        client = get_milvus_client()

        query_embedding = model.encode(query).tolist()

        filter_expr = ""
        conditions = []
        if category_filter:
            conditions.append(f'category == "{category_filter}"')
        if subcategory_filter:
            conditions.append(f'subcategory == "{subcategory_filter}"')
        if conditions:
            filter_expr = " and ".join(conditions)

        search_params = {"metric_type": "COSINE", "params": {"ef": 64}}

        results = client.search(
            collection_name=collection,
            data=[query_embedding],
            limit=top_k,
            output_fields=[
                "source_document_id", "pipeline_run_id", "chunk_index",
                "text", "category", "subcategory", "document_date",
                "section_path", "page_numbers",
            ],
            search_params=search_params,
            filter=filter_expr if filter_expr else None,
        )

        chunks = []
        for hit in results[0]:
            entity = hit["entity"]
            chunks.append(ChunkResult(
                doc_id=entity.get("source_document_id", ""),
                chunk_index=entity.get("chunk_index", 0),
                pipeline_run_id=entity.get("pipeline_run_id", ""),
                text=entity.get("text", ""),
                score=round(hit["distance"], 4),
                category=entity.get("category", ""),
                subcategory=entity.get("subcategory", ""),
                document_date=entity.get("document_date", ""),
                section_path=entity.get("section_path", ""),
                page_numbers=entity.get("page_numbers", ""),
            ))

        logger.info(f"Found {len(chunks)} results from {collection}")

        return SearchResult(
            status="success",
            collection=collection,
            query=query,
            total_results=len(chunks),
            chunks=chunks,
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return SearchResult(
            status="error",
            collection=collection,
            query=query,
            total_results=0,
            chunks=[],
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    mcp.run(show_banner=False)
