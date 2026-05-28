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
MLFLOW_EXPERIMENT_NAMES = [
    s.strip() for s in os.environ.get(
        "MLFLOW_EXPERIMENT_NAMES",
        os.environ.get("MLFLOW_EXPERIMENT_NAME", "compliance-review-agent,underwriter-chat-v3"),
    ).split(",") if s.strip()
]
MARQUEZ_NAMESPACE = os.environ.get("MARQUEZ_NAMESPACE", "data-strat-poc")
MARQUEZ_WEB_URL = os.environ.get(
    "MARQUEZ_WEB_URL",
    "https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com",
)

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


async def _get_mlflow_experiment_ids() -> list[str]:
    """Resolve experiment IDs for all configured experiment names."""
    client = _get_client()
    try:
        resp = await client.post(
            f"{MLFLOW_API_URL}/api/2.0/mlflow/experiments/search",
            json={"max_results": 50},
            headers=_mlflow_headers(),
        )
        resp.raise_for_status()
        ids = []
        for exp in resp.json().get("experiments", []):
            if exp.get("name") in MLFLOW_EXPERIMENT_NAMES:
                ids.append(exp["experiment_id"])
        return ids
    except Exception as e:
        logger.warning(f"MLflow experiment search failed: {e}")
    return []


async def _search_mlflow_traces(
    max_results: int = 20,
) -> list[dict]:
    """Search MLflow traces across all configured experiments."""
    client = _get_client()
    exp_ids = await _get_mlflow_experiment_ids()
    if not exp_ids:
        logger.warning("Could not resolve any MLflow experiment IDs")
        return []

    all_traces: list[dict] = []
    for exp_id in exp_ids:
        try:
            resp = await client.get(
                f"{MLFLOW_API_URL}/api/2.0/mlflow/traces",
                params={"experiment_ids": exp_id, "max_results": max_results},
                headers=_mlflow_headers(),
            )
            resp.raise_for_status()
            all_traces.extend(resp.json().get("traces", []))
        except Exception as e:
            logger.warning(f"MLflow trace search failed for experiment {exp_id}: {e}")

    all_traces.sort(key=lambda t: t.get("timestamp_ms", 0), reverse=True)
    return all_traces[:max_results]


async def _get_mlflow_trace(trace_id: str) -> Optional[dict]:
    """Fetch a single trace by searching across all configured experiments."""
    client = _get_client()
    exp_ids = await _get_mlflow_experiment_ids()
    if not exp_ids:
        return None

    for exp_id in exp_ids:
        try:
            resp = await client.get(
                f"{MLFLOW_API_URL}/api/2.0/mlflow/traces",
                params={"experiment_ids": exp_id, "request_ids": trace_id},
                headers=_mlflow_headers(),
            )
            resp.raise_for_status()
            for t in resp.json().get("traces", []):
                if t.get("request_id") == trace_id:
                    return t
        except Exception as e:
            logger.warning(f"MLflow trace fetch failed for {trace_id} in experiment {exp_id}: {e}")
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


@router.get("/links")
async def get_external_links():
    """Return external tool URLs for the UI sidebar."""
    return {
        "marquez_web": MARQUEZ_WEB_URL,
        "marquez_api": MARQUEZ_API_URL,
        "mlflow": MLFLOW_EXTERNAL_URL,
        "marquez_lineage": f"{MARQUEZ_WEB_URL}/lineage/{MARQUEZ_NAMESPACE}",
    }


# --- M5: Collection Health, Apps, Impact Analysis ---


class CollectionHealth(BaseModel):
    collection_name: str
    document_count: int
    vector_count: int
    consuming_apps: list[str]
    query_count: int
    last_ingest: Optional[str]
    staleness_days: Optional[int]
    marquez_jobs: list[MarquezLink]


class AppInfo(BaseModel):
    app_name: str
    collections: list[str]
    query_count: int
    last_query: Optional[str]
    workflow_type: str


@router.get("/collection/{collection_name}/health", response_model=CollectionHealth)
async def get_collection_health(collection_name: str):
    """Aggregated health metrics for a collection.

    Combines: Registry (doc count, last ingest), Marquez (consuming apps),
    MLflow (query volume).
    """
    from datetime import datetime as dt
    from .db import SessionLocal, CollectionRow, CollectionDocumentRow

    db = SessionLocal()
    try:
        coll = db.query(CollectionRow).filter(CollectionRow.name == collection_name).first()
        if not coll:
            raise HTTPException(404, f"Collection {collection_name} not found")

        links = db.query(CollectionDocumentRow).filter(
            CollectionDocumentRow.collection_id == coll.id
        ).all()
        doc_count = len(links)

        total_vectors = sum(link.vector_count or 0 for link in links)

        last_ingest = None
        last_ingest_dt = None
        for link in links:
            if link.last_ingested:
                if last_ingest_dt is None or link.last_ingested > last_ingest_dt:
                    last_ingest_dt = link.last_ingested
        if last_ingest_dt:
            last_ingest = last_ingest_dt.isoformat()

        staleness_days = None
        if last_ingest_dt:
            staleness_days = (dt.now(last_ingest_dt.tzinfo or None) - last_ingest_dt).days

        jobs = await _get_marquez_jobs()
        consuming_apps = []
        marquez_jobs = []
        for job in jobs:
            job_inputs = job.get("inputs", [])
            for inp in job_inputs:
                if collection_name in inp.get("name", ""):
                    app_name = job["name"]
                    if app_name not in consuming_apps:
                        consuming_apps.append(app_name)
                    marquez_jobs.append(MarquezLink(
                        job_name=app_name,
                        run_id="",
                        namespace=job.get("namespace", MARQUEZ_NAMESPACE),
                        url=f"{MARQUEZ_API_URL}/lineage/{MARQUEZ_NAMESPACE}/{app_name}",
                    ))

        traces = await _search_mlflow_traces()
        query_count = 0
        for trace in traces:
            tags = {t.get("key", ""): t.get("value", "") for t in trace.get("tags", [])}
            queried_colls = tags.get("collection_queried", "")
            if collection_name in queried_colls:
                query_count += 1

        return CollectionHealth(
            collection_name=collection_name,
            document_count=doc_count,
            vector_count=total_vectors,
            consuming_apps=consuming_apps,
            query_count=query_count,
            last_ingest=last_ingest,
            staleness_days=staleness_days,
            marquez_jobs=marquez_jobs,
        )
    finally:
        db.close()


@router.get("/apps", response_model=list[AppInfo])
async def list_apps():
    """List all registered applications with their collection consumption and query metrics.

    Applications are Marquez jobs of type APPLICATION that consume Milvus collections.
    Query counts and workflow types come from MLflow traces.
    """
    jobs = await _get_marquez_jobs()

    app_map: dict[str, AppInfo] = {}
    for job in jobs:
        job_type = job.get("facets", {}).get("jobType", {}).get("jobType", "")
        if job_type != "APPLICATION":
            continue

        app_name = job["name"]
        collections = []
        for inp in job.get("inputs", []):
            input_name = inp.get("name", "")
            if input_name:
                collections.append(input_name)

        app_map[app_name] = AppInfo(
            app_name=app_name,
            collections=collections,
            query_count=0,
            last_query=None,
            workflow_type="unknown",
        )

    traces = await _search_mlflow_traces(max_results=100)
    for trace in traces:
        tags = {t.get("key", ""): t.get("value", "") for t in trace.get("tags", [])}
        trace_app = tags.get("app_name", "")
        if trace_app and trace_app in app_map:
            app_map[trace_app].query_count += 1
            ts = str(trace.get("timestamp_ms", ""))
            if ts and (app_map[trace_app].last_query is None or ts > app_map[trace_app].last_query):
                app_map[trace_app].last_query = ts
            wf = tags.get("workflow", "")
            if wf:
                app_map[trace_app].workflow_type = wf

    if not app_map:
        known_apps = [
            AppInfo(
                app_name="underwriter_chat",
                collections=["underwriting_guidelines"],
                query_count=len([
                    t for t in traces
                    if any(tag.get("value") == "underwriter_chat"
                           for tag in t.get("tags", [])
                           if tag.get("key") == "app_name")
                ]),
                last_query=None,
                workflow_type="deterministic",
            ),
            AppInfo(
                app_name="compliance_review_agent",
                collections=["underwriting_guidelines", "iso_forms", "regulatory_bulletins"],
                query_count=len([
                    t for t in traces
                    if any(tag.get("value") == "compliance_review_agent"
                           for tag in t.get("tags", [])
                           if tag.get("key") == "app_name")
                ]),
                last_query=None,
                workflow_type="agentic",
            ),
        ]
        return known_apps

    return list(app_map.values())


def _extract_trace_summary(trace: dict, doc_id_filter: str = "") -> Optional[TraceSummary]:
    """Extract a TraceSummary from an MLflow trace list response.

    Handles two formats:
    - Tag-based: deterministic RAG traces with collection_queried, doc_ids_cited, etc.
    - OpenAI chat completion: agentic traces with choices[].message.content and tool_calls.
    """
    try:
        import json as _json
        import re as _re

        trace_id = trace.get("request_id", "")
        timestamp = str(trace.get("timestamp_ms", ""))

        question = ""
        answer_preview = ""
        metadata_dict = {}
        for meta in trace.get("request_metadata", []):
            metadata_dict[meta.get("key", "")] = meta.get("value", "")

        # --- Question: find the last user/human message in traceInputs ---
        inputs_raw = metadata_dict.get("mlflow.traceInputs", "{}")
        try:
            inputs = _json.loads(inputs_raw)
            msgs = inputs.get("messages", [])
            for msg in reversed(msgs):
                role = msg.get("role", "")
                msg_type = msg.get("type", "")
                if role == "user" or msg_type == "human":
                    question = msg.get("content", "")[:200]
                    break
        except (_json.JSONDecodeError, TypeError, IndexError):
            m = _re.search(r'"content":\s*"([^"]{10,})', inputs_raw)
            if m:
                question = m.group(1)[:200]

        # --- Answer: handle both chat completion and message-list formats ---
        # MLflow truncates traceOutputs to 250 chars, so also try regex fallback
        outputs_raw = metadata_dict.get("mlflow.traceOutputs", "{}")
        try:
            outputs = _json.loads(outputs_raw)
            # OpenAI chat completion format: choices[].message.content
            if "choices" in outputs:
                for choice in outputs["choices"]:
                    content = choice.get("message", {}).get("content", "")
                    if content:
                        answer_preview = content[:500]
                        break
            # LangChain/agent format: messages[].content where type=ai
            elif "messages" in outputs:
                for msg in reversed(outputs.get("messages", [])):
                    msg_type = msg.get("type", "")
                    content = msg.get("content", "")
                    if msg_type in ("ai", "AIMessage") and content:
                        answer_preview = content[:500]
                        break
        except (_json.JSONDecodeError, TypeError, IndexError):
            # Truncated JSON — extract content after "content": "
            m = _re.search(r'"content":\s*"(.+)', outputs_raw)
            if m:
                raw_answer = m.group(1)
                if raw_answer.endswith('...'):
                    raw_answer = raw_answer[:-3] + "..."
                answer_preview = raw_answer[:500]

        # --- Tags ---
        tags = {}
        for tag in trace.get("tags", []):
            tags[tag.get("key", "")] = tag.get("value", "")

        doc_ids_cited = [d for d in tags.get("doc_ids_cited", "").split(",") if d]
        collection = tags.get("collection_queried", "")

        if not answer_preview and tags.get("answer_preview"):
            answer_preview = tags["answer_preview"]

        # --- Collection from tool_calls in traceInputs or traceOutputs ---
        if not collection:
            collection = _extract_collection_from_raw(inputs_raw, outputs_raw)

        # --- Fallback: collection from retrieved_chunks in outputs ---
        if not collection and not doc_ids_cited:
            try:
                outputs = _json.loads(outputs_raw)
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

        # --- Chunk details from tag ---
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


def _extract_collection_from_raw(inputs_raw: str, outputs_raw: str) -> str:
    """Extract collection name from trace JSON, trying multiple strategies.

    1. Look for "collection": "..." in tool_call arguments
    2. Look for known collection names mentioned in the user's question text
    """
    import re as _re

    # Strategy 1: JSON key match
    for raw in (inputs_raw, outputs_raw):
        m = _re.search(r'"collection":\s*"([^"]+)"', raw)
        if m:
            val = m.group(1)
            if val not in ("", "messages", "tools"):
                return val

    # Strategy 2: known collection names in text (MLflow truncates to 250 chars)
    combined = inputs_raw + outputs_raw
    known_collections = [
        "underwriting_guidelines",
        "iso_forms",
        "regulatory_bulletins",
        "claims_procedures",
    ]
    for coll in known_collections:
        if coll in combined:
            return coll

    return ""
