"""Provenance federation endpoints — bridges Registry, MLflow, and Marquez."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MARQUEZ_API_URL = os.environ.get("MARQUEZ_API_URL", "http://marquez:5000")
MLFLOW_API_URL = os.environ.get("MLFLOW_API_URL", "http://mlflow-ui-redhat-ods-applications.apps.dev.aip-ft.rh-ods.com")
MARQUEZ_NAMESPACE = os.environ.get("MARQUEZ_NAMESPACE", "data-strat-poc")

router = APIRouter(prefix="/api/v1/provenance", tags=["provenance"])

_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0, verify=False)
    return _http_client


# --- Response Models ---


class MarquezLink(BaseModel):
    job_name: str
    run_id: str
    namespace: str
    url: str


class TraceChunk(BaseModel):
    doc_id: str
    chunk_index: int
    pipeline_run_id: str
    text_preview: str
    score: float


class TraceSummary(BaseModel):
    trace_id: str
    timestamp: str
    question: str
    answer_preview: str
    collection: str
    chunks: list[TraceChunk]
    doc_ids_cited: list[str]


class DocumentProvenance(BaseModel):
    doc_id: str
    name: str
    source_url: str
    collections: list[str]
    pipeline_run_ids: list[str]
    marquez_links: list[MarquezLink]
    recent_query_traces: list[TraceSummary]


class CollectionProvenance(BaseModel):
    collection_name: str
    document_count: int
    downstream_apps: list[str]
    query_count: int
    marquez_jobs: list[MarquezLink]


# --- Marquez Helpers ---


async def _get_marquez_jobs(namespace: str = MARQUEZ_NAMESPACE) -> list[dict]:
    """Fetch all jobs from Marquez for the given namespace."""
    client = _get_client()
    try:
        resp = await client.get(f"{MARQUEZ_API_URL}/api/v1/namespaces/{namespace}/jobs", params={"limit": 100})
        resp.raise_for_status()
        return resp.json().get("jobs", [])
    except Exception as e:
        logger.warning(f"Marquez jobs fetch failed: {e}")
        return []


async def _get_marquez_lineage(dataset_name: str, namespace: str) -> dict:
    """Fetch lineage graph for a dataset from Marquez."""
    client = _get_client()
    try:
        node_id = f"dataset:{namespace}:{dataset_name}"
        resp = await client.get(f"{MARQUEZ_API_URL}/api/v1/lineage", params={"nodeId": node_id, "depth": 5})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Marquez lineage fetch failed for {dataset_name}: {e}")
        return {}


async def _get_marquez_runs_for_job(job_name: str, namespace: str = MARQUEZ_NAMESPACE) -> list[dict]:
    """Fetch runs for a specific Marquez job."""
    client = _get_client()
    try:
        resp = await client.get(
            f"{MARQUEZ_API_URL}/api/v1/namespaces/{namespace}/jobs/{job_name}/runs",
            params={"limit": 10},
        )
        resp.raise_for_status()
        return resp.json().get("runs", [])
    except Exception as e:
        logger.warning(f"Marquez runs fetch failed for {job_name}: {e}")
        return []


# --- MLflow Helpers ---


async def _search_mlflow_traces(
    experiment_name: str = "underwriter-chat",
    filter_string: str = "",
    max_results: int = 20,
) -> list[dict]:
    """Search MLflow traces. Returns trace metadata."""
    client = _get_client()
    try:
        resp = await client.post(
            f"{MLFLOW_API_URL}/api/2.0/mlflow/traces/search",
            json={
                "experiment_names": [experiment_name],
                "filter": filter_string,
                "max_results": max_results,
            },
        )
        resp.raise_for_status()
        return resp.json().get("traces", [])
    except Exception as e:
        logger.warning(f"MLflow trace search failed: {e}")
        return []


async def _get_mlflow_trace(trace_id: str) -> dict:
    """Fetch a single MLflow trace with full span details."""
    client = _get_client()
    try:
        resp = await client.get(f"{MLFLOW_API_URL}/api/2.0/mlflow/traces/{trace_id}")
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"MLflow trace fetch failed for {trace_id}: {e}")
        return {}


# --- Provenance Endpoints ---


@router.get("/document/{doc_id}", response_model=DocumentProvenance)
async def get_document_provenance(doc_id: str):
    """
    Federated provenance for a document.

    Combines: Registry metadata + Marquez ingest lineage + MLflow query traces.
    """
    from .db import SessionLocal, DocumentRow

    db = SessionLocal()
    try:
        doc_row = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
        if not doc_row:
            raise HTTPException(404, f"Document {doc_id} not found in registry")

        collections = [link.collection.name for link in doc_row.collection_links if link.collection]

        pipeline_run_ids = []
        for link in doc_row.collection_links:
            if link.last_pipeline_run:
                pipeline_run_ids.append(link.last_pipeline_run)

        marquez_links = []
        for coll_name in collections:
            job_name = f"acquire_documents/{coll_name}"
            runs = await _get_marquez_runs_for_job(job_name)
            for run in runs[:3]:
                marquez_links.append(MarquezLink(
                    job_name=job_name,
                    run_id=run.get("id", ""),
                    namespace=MARQUEZ_NAMESPACE,
                    url=f"{MARQUEZ_API_URL}/lineage/{MARQUEZ_NAMESPACE}/{job_name}",
                ))

        traces = await _search_mlflow_traces()
        recent_traces = []
        for trace in traces[:10]:
            trace_summary = _extract_trace_summary(trace, doc_id_filter=doc_id)
            if trace_summary:
                recent_traces.append(trace_summary)

        return DocumentProvenance(
            doc_id=doc_id,
            name=doc_row.name,
            source_url=doc_row.source_url,
            collections=collections,
            pipeline_run_ids=pipeline_run_ids,
            marquez_links=marquez_links,
            recent_query_traces=recent_traces,
        )
    finally:
        db.close()


@router.get("/trace/{trace_id}")
async def get_trace_provenance(trace_id: str):
    """
    Federated provenance for a query trace.

    Returns MLflow trace detail enriched with Registry document metadata
    and Marquez lineage links.
    """
    trace = await _get_mlflow_trace(trace_id)
    if not trace:
        raise HTTPException(404, f"Trace {trace_id} not found in MLflow")

    return trace


@router.get("/collection/{collection_name}", response_model=CollectionProvenance)
async def get_collection_provenance(collection_name: str):
    """
    Federated provenance for a collection.

    Combines: Registry membership + Marquez downstream apps + MLflow query volume.
    """
    from .db import SessionLocal, CollectionRow

    db = SessionLocal()
    try:
        coll_row = db.query(CollectionRow).filter(CollectionRow.name == collection_name).first()
        if not coll_row:
            raise HTTPException(404, f"Collection {collection_name} not found")

        doc_count = len(coll_row.document_links)

        jobs = await _get_marquez_jobs()
        downstream_apps = []
        marquez_jobs = []
        for job in jobs:
            job_inputs = job.get("inputs", [])
            for inp in job_inputs:
                if collection_name in inp.get("name", ""):
                    downstream_apps.append(job["name"])
                    marquez_jobs.append(MarquezLink(
                        job_name=job["name"],
                        run_id="",
                        namespace=job.get("namespace", MARQUEZ_NAMESPACE),
                        url=f"{MARQUEZ_API_URL}/lineage/{MARQUEZ_NAMESPACE}/{job['name']}",
                    ))

        traces = await _search_mlflow_traces()
        query_count = len(traces)

        return CollectionProvenance(
            collection_name=collection_name,
            document_count=doc_count,
            downstream_apps=downstream_apps,
            query_count=query_count,
            marquez_jobs=marquez_jobs,
        )
    finally:
        db.close()


def _extract_trace_summary(trace: dict, doc_id_filter: str = "") -> Optional[TraceSummary]:
    """Extract a TraceSummary from an MLflow trace response, optionally filtering by doc_id."""
    try:
        trace_id = trace.get("info", {}).get("request_id", "")
        timestamp = trace.get("info", {}).get("timestamp_ms", "")

        spans = trace.get("data", {}).get("spans", [])
        question = ""
        answer_preview = ""
        chunks = []
        collection = ""

        for span in spans:
            span_name = span.get("name", "")
            attributes = span.get("attributes", {})

            if "input" in attributes and not question:
                question = str(attributes.get("input", ""))[:200]
            if "output" in attributes and span_name != "milvus_search":
                answer_preview = str(attributes.get("output", ""))[:300]

        doc_ids_cited = list(set(c.doc_id for c in chunks))

        if doc_id_filter and doc_id_filter not in doc_ids_cited:
            return None

        return TraceSummary(
            trace_id=trace_id,
            timestamp=str(timestamp),
            question=question,
            answer_preview=answer_preview,
            collection=collection,
            chunks=chunks,
            doc_ids_cited=doc_ids_cited,
        )
    except Exception as e:
        logger.warning(f"Failed to extract trace summary: {e}")
        return None
