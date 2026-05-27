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
MLFLOW_API_URL = os.environ.get("MLFLOW_API_URL", "https://mlflow.redhat-ods-applications.svc:8443")
MLFLOW_EXTERNAL_URL = os.environ.get(
    "MLFLOW_EXTERNAL_URL",
    "https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow",
)
MLFLOW_WORKSPACE = os.environ.get("MLFLOW_WORKSPACE", "data-strat-poc")
MLFLOW_EXPERIMENT_NAME = os.environ.get("MLFLOW_EXPERIMENT_NAME", "underwriter-chat-v2")
MARQUEZ_NAMESPACE = os.environ.get("MARQUEZ_NAMESPACE", "data-strat-poc")

SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"

router = APIRouter(prefix="/api/v1/provenance", tags=["provenance"])

_http_client: Optional[httpx.AsyncClient] = None


def _get_sa_token() -> str:
    """Read the ServiceAccount token for MLflow auth."""
    try:
        return open(SA_TOKEN_PATH).read().strip()
    except FileNotFoundError:
        token = os.environ.get("MLFLOW_TRACKING_TOKEN", "")
        if token:
            return token
        logger.warning("No SA token found — MLflow calls will be unauthenticated")
        return ""


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=10.0, verify=False)
    return _http_client


def _mlflow_headers() -> dict:
    """Build auth + workspace headers for RHOAI MLflow."""
    headers = {"X-Mlflow-Workspace": MLFLOW_WORKSPACE}
    token = _get_sa_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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


class ChunkDetail(BaseModel):
    doc_id: str
    chunk_index: int
    pipeline_run_id: str
    score: float
    text_preview: str
    section_path: str = ""
    page_numbers: str = ""


class TraceSummary(BaseModel):
    trace_id: str
    timestamp: str
    question: str
    answer_preview: str
    collection: str
    chunks: list[ChunkDetail]
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


async def _get_mlflow_experiment_id() -> str:
    """Resolve the experiment ID for the underwriter-chat experiment."""
    client = _get_client()
    try:
        resp = await client.post(
            f"{MLFLOW_API_URL}/api/2.0/mlflow/experiments/search",
            json={"max_results": 50},
            headers=_mlflow_headers(),
        )
        resp.raise_for_status()
        for exp in resp.json().get("experiments", []):
            if exp.get("name") == MLFLOW_EXPERIMENT_NAME:
                return exp["experiment_id"]
    except Exception as e:
        logger.warning(f"MLflow experiment search failed: {e}")
    return ""


async def _search_mlflow_traces(
    max_results: int = 20,
) -> list[dict]:
    """Search MLflow traces. Returns trace metadata."""
    client = _get_client()
    try:
        exp_id = await _get_mlflow_experiment_id()
        if not exp_id:
            logger.warning("Could not resolve MLflow experiment ID")
            return []

        resp = await client.get(
            f"{MLFLOW_API_URL}/api/2.0/mlflow/traces",
            params={"experiment_ids": exp_id, "max_results": max_results},
            headers=_mlflow_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("traces", [])
    except Exception as e:
        logger.warning(f"MLflow trace search failed: {e}")
        return []


async def _get_mlflow_trace(trace_id: str) -> Optional[dict]:
    """Fetch a single trace by filtering the list endpoint (RHOAI MLflow lacks GET /traces/{id})."""
    client = _get_client()
    try:
        exp_id = await _get_mlflow_experiment_id()
        if not exp_id:
            return None

        resp = await client.get(
            f"{MLFLOW_API_URL}/api/2.0/mlflow/traces",
            params={"experiment_ids": exp_id, "request_ids": trace_id},
            headers=_mlflow_headers(),
        )
        resp.raise_for_status()
        traces = resp.json().get("traces", [])
        for t in traces:
            if t.get("request_id") == trace_id:
                return t
        return None
    except Exception as e:
        logger.warning(f"MLflow trace fetch failed for {trace_id}: {e}")
        return None


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

    Returns trace metadata from MLflow enriched with Registry document links.
    """
    trace = await _get_mlflow_trace(trace_id)
    if not trace:
        raise HTTPException(404, f"Trace {trace_id} not found in MLflow")

    summary = _extract_trace_summary(trace)

    # Enrich with Registry document metadata for cited doc_ids
    doc_details = []
    if summary and summary.doc_ids_cited:
        from .db import SessionLocal, DocumentRow
        db = SessionLocal()
        try:
            for doc_id in summary.doc_ids_cited:
                doc = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
                if doc:
                    doc_details.append({
                        "doc_id": doc.doc_id,
                        "name": doc.name,
                        "source_url": doc.source_url,
                        "document_type": doc.document_type,
                        "line_of_business": doc.line_of_business,
                        "jurisdiction": doc.jurisdiction,
                    })
        finally:
            db.close()

    return {
        "trace_id": trace_id,
        "timestamp": str(trace.get("timestamp_ms", "")),
        "status": trace.get("status", ""),
        "execution_time_ms": trace.get("execution_time_ms"),
        "question": summary.question if summary else "",
        "answer_preview": summary.answer_preview if summary else "",
        "collection": summary.collection if summary else "",
        "doc_ids_cited": summary.doc_ids_cited if summary else [],
        "chunks": [c.model_dump() for c in summary.chunks] if summary else [],
        "documents": doc_details,
        "mlflow_url": f"{MLFLOW_EXTERNAL_URL}/#/experiments/{trace.get('experiment_id', '')}/traces?startTime=ALL&workspace={MLFLOW_WORKSPACE}&selectedEvaluationId={trace_id}",
    }


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


@router.get("/traces")
async def list_traces():
    """List recent query traces from MLflow."""
    raw_traces = await _search_mlflow_traces(max_results=50)
    summaries = []
    for trace in raw_traces:
        summary = _extract_trace_summary(trace)
        if summary:
            summaries.append(summary)
    return {"traces": summaries, "total": len(summaries)}


def _extract_trace_summary(trace: dict, doc_id_filter: str = "") -> Optional[TraceSummary]:
    """Extract a TraceSummary from an MLflow trace list response."""
    try:
        import json as _json

        trace_id = trace.get("request_id", "")
        timestamp = str(trace.get("timestamp_ms", ""))
        status = trace.get("status", "")

        question = ""
        answer_preview = ""
        metadata_dict = {}
        for meta in trace.get("request_metadata", []):
            metadata_dict[meta.get("key", "")] = meta.get("value", "")

        # Extract question from traceInputs
        try:
            inputs = _json.loads(metadata_dict.get("mlflow.traceInputs", "{}"))
            msgs = inputs.get("messages", [])
            if msgs:
                question = msgs[0].get("content", "")[:200]
        except (_json.JSONDecodeError, TypeError, IndexError):
            pass

        # Extract answer from traceOutputs — last AI message
        try:
            outputs = _json.loads(metadata_dict.get("mlflow.traceOutputs", "{}"))
            msgs = outputs.get("messages", [])
            for msg in reversed(msgs):
                msg_type = msg.get("type", "")
                content = msg.get("content", "")
                if msg_type in ("ai", "AIMessage") and content:
                    answer_preview = content[:500]
                    break
        except (_json.JSONDecodeError, TypeError, IndexError):
            pass

        # Extract tags (doc_ids_cited, collection_queried)
        tags = {}
        for tag in trace.get("tags", []):
            tags[tag.get("key", "")] = tag.get("value", "")

        doc_ids_cited = [d for d in tags.get("doc_ids_cited", "").split(",") if d]
        collection = tags.get("collection_queried", "")

        # Answer from tag (not truncated) takes priority over traceOutputs (truncated)
        if not answer_preview and tags.get("answer_preview"):
            answer_preview = tags["answer_preview"]

        # If no tags, try to extract collection from the traceOutputs (retrieve step)
        if not collection and not doc_ids_cited:
            try:
                outputs = _json.loads(metadata_dict.get("mlflow.traceOutputs", "{}"))
                msgs = outputs.get("messages", [])
                for msg in msgs:
                    content = msg.get("content", "")
                    if "retrieved_chunks" in str(outputs):
                        rc = outputs.get("retrieved_chunks", "")
                        if isinstance(rc, str) and rc.startswith("{"):
                            parsed_rc = _json.loads(rc)
                            collection = parsed_rc.get("collection", "")
                            doc_ids_cited = list(set(
                                c.get("doc_id", "") for c in parsed_rc.get("chunks", []) if c.get("doc_id")
                            ))
            except (_json.JSONDecodeError, TypeError):
                pass

        # Parse chunk details from tag
        chunks = []
        chunks_json = tags.get("chunks_detail", "")
        if chunks_json:
            try:
                for c in _json.loads(chunks_json):
                    chunks.append(ChunkDetail(
                        doc_id=c.get("doc_id", ""),
                        chunk_index=c.get("chunk_index", 0),
                        pipeline_run_id=c.get("pipeline_run_id", ""),
                        score=c.get("score", 0),
                        text_preview=c.get("text_preview", ""),
                        section_path=c.get("section_path", ""),
                        page_numbers=c.get("page_numbers", ""),
                    ))
                if not doc_ids_cited:
                    doc_ids_cited = list(set(c.doc_id for c in chunks))
            except (_json.JSONDecodeError, TypeError):
                pass

        if doc_id_filter and doc_id_filter not in doc_ids_cited:
            return None

        return TraceSummary(
            trace_id=trace_id,
            timestamp=timestamp,
            question=question,
            answer_preview=answer_preview,
            collection=collection,
            chunks=chunks,
            doc_ids_cited=doc_ids_cited,
        )
    except Exception as e:
        logger.warning(f"Failed to extract trace summary: {e}")
        return None
