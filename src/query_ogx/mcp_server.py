"""MCP server wrapping Milvus vector search for multi-collection knowledge base.

Serves tools to OGX via SSE transport. OGX discovers and registers tools at startup,
then calls them server-side during the Responses API agent loop.

Unlike M4's mcp_server.py (stdio transport, single collection focus), this server:
- Uses SSE transport for OGX integration
- Exposes a list_collections tool for agent discovery
- Supports all 3 collections for multi-hop retrieval (Workflow B)
"""

import json
import logging
import os
from typing import Optional

from fastmcp import FastMCP
from pymilvus import MilvusClient
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MILVUS_URI = os.environ.get("MILVUS_URI", "http://localhost:19530")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "ibm-granite/granite-embedding-125m-english")
DEFAULT_TOP_K = int(os.environ.get("DEFAULT_TOP_K", "10"))
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))

COLLECTIONS = {
    "underwriting_guidelines": (
        "Commercial property and liability underwriting guidelines. Contains referral thresholds, "
        "coverage forms, exclusions, pricing tiers, and risk assessment criteria. "
        "Use when the query asks about underwriting rules, coverage limits, or referral requirements."
    ),
    "iso_forms": (
        "ISO standardized insurance forms and policy language. Contains forms like CG 00 01 "
        "(Commercial General Liability), CP 00 10 (Building and Personal Property), and their "
        "endorsements. Use when the query references specific form numbers or standard policy language."
    ),
    "regulatory_bulletins": (
        "State Department of Insurance regulatory bulletins and circular letters. Contains "
        "compliance requirements, rate filing mandates, and regulatory updates by jurisdiction. "
        "Use when the query involves regulatory compliance, state-specific rules, or DOI directives."
    ),
}

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


class CollectionInfo(BaseModel):
    name: str
    description: str
    fields: list[str] = Field(
        default_factory=lambda: [
            "category", "subcategory", "document_date", "section_path", "page_numbers"
        ]
    )


class ChunkResult(BaseModel):
    """A single retrieved chunk with full provenance metadata."""
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
    """Result of a Milvus vector search with provenance metadata."""
    status: str
    collection: str
    query: str
    total_results: int
    chunks: list[ChunkResult]


@mcp.tool
def list_collections() -> list[CollectionInfo]:
    """List available document collections in the underwriting knowledge base.

    Returns collection names and descriptions. Call this first to understand
    what knowledge sources are available before searching.
    """
    return [
        CollectionInfo(name=name, description=desc)
        for name, desc in COLLECTIONS.items()
    ]


@mcp.tool
def milvus_search(
    query: str,
    collection: str,
    top_k: int = DEFAULT_TOP_K,
    category_filter: str = "",
    subcategory_filter: str = "",
) -> SearchResult:
    """Search a document collection using semantic similarity.

    Returns document chunks ranked by relevance, with full metadata
    including doc_id, pipeline_run_id, and source text for citation.
    The agent can call this multiple times with different collections
    to cross-reference information across knowledge sources.

    Args:
        query: Natural language question to search for.
        collection: Collection to search. Must be one of: underwriting_guidelines,
                    iso_forms, regulatory_bulletins. Call list_collections() first
                    to see available options.
        top_k: Number of results to return (1-50). Defaults to 10.
        category_filter: Optional filter by document category.
        subcategory_filter: Optional filter by subcategory.
    """
    if collection not in COLLECTIONS:
        return SearchResult(
            status=f"error: unknown collection '{collection}'. Use list_collections() to see available options.",
            collection=collection,
            query=query,
            total_results=0,
            chunks=[],
        )

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
            status=f"error: {e}",
            collection=collection,
            query=query,
            total_results=0,
            chunks=[],
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    logger.info(f"Starting MCP server on {MCP_HOST}:{MCP_PORT} (SSE transport)")
    logger.info(f"Collections: {list(COLLECTIONS.keys())}")
    mcp.run(transport="sse", host=MCP_HOST, port=MCP_PORT)
