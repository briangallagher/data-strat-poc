# M4 Checkpoint: Query Layer (Deterministic RAG)

**Date:** 2026-05-27
**Status:** Complete (local verification; cluster deployment pending)

## What Was Built

### Phase 0: Query Infrastructure
- Granite 3.3 8B Instruct deployed via vLLM InferenceService (KServe) on A100 GPU
  - `--enable-auto-tool-choice --tool-call-parser=hermes` for function calling
  - Model: `ibm-granite/granite-3.3-8b-instruct` (16GB, bf16)
  - Endpoint: `http://granite-llm-predictor.data-strat-poc.svc.cluster.local/v1`
- Embedding ISVC blocked by PG-018 (RHOAI 3.4 vLLM v0.18.0 lacks `--task=embedding`)
  - Fallback: local `sentence-transformers` with `ibm-granite/granite-embedding-125m-english` in MCP server
- Milvus verified: 363 vectors, 10 docs (ug-001 to ug-010), `pipeline_run_id` on every vector
- ServingRuntime + ISVC manifests: `manifests/model-serving/`

### Phase 1: Deterministic RAG Service (Workflow A)
- **MCP server** (`src/query/mcp_server.py`): wraps pymilvus search with local embedding. Tool: `milvus_search(query, collection, filters, top_k)`. Returns `ChunkResult` objects with doc_id, pipeline_run_id, chunk_index, text, score, category, subcategory, document_date, section_path, page_numbers.
- **LangGraph agent** (`src/query/agent.py`): ReAct agent with underwriting system prompt. Grounded to knowledge base (must search before answering, cite sources by doc_id). Temperature 0 for deterministic responses.
- **Chainlit app** (`src/query/app.py`): Chat UI with streaming, tool call visualization, trace metadata enrichment. `mlflow.langchain.autolog()` for automatic trace capture.
- **E2E verified**: Asked "Does our commercial property form cover flood damage for a property in a high-risk flood zone?" → received cited answer referencing [ug-003] → full 7-span MLflow trace captured.

### Phase 2: Query Audit + Provenance Bridge
- **Trace enrichment**: After each query, extract doc_ids and pipeline_run_ids from tool outputs and set as searchable trace tags (`doc_ids_cited`, `pipeline_run_ids`, `collection_queried`, `chunks_retrieved_count`).
- **Application-level OL emission** (`src/query/lineage.py`): Emits OL COMPLETE event registering `underwriter_chat` as a downstream consumer of `milvus://underwriting_guidelines` in Marquez. Verified: job appears in Marquez API with correct input dataset.
- **Registry federation backend** (`src/registry/provenance.py`): Three endpoints mounted on existing Registry app:
  - `GET /api/v1/provenance/document/{doc_id}` — federated: Registry + MLflow + Marquez
  - `GET /api/v1/provenance/trace/{trace_id}` — federated: MLflow + Registry
  - `GET /api/v1/provenance/collection/{name}` — federated: Registry + Marquez + MLflow
- **MLflow trace search API validated**: endpoint exists on cluster MLflow (`GET /api/2.0/mlflow/traces?experiment_ids=<id>`), requires SA token + workspace header.

### Phase 3: Unified Provenance Portal
- **Three new Registry UI pages** (PatternFly 6, React, TypeScript):
  - **QueryTracesPage**: list recent query traces with timestamp, question, collection, docs cited
  - **TraceDetailPage**: full trace provenance — question, answer, execution spans (expandable), cited doc_ids (linked), pipeline_run_ids, collection, duration
  - **DocumentProvenancePage**: full document provenance — identity, collections, ingest pipeline runs, Marquez lineage links, query traces that cited this document
- **Navigation**: "Queries" added to sidebar nav; "View Full Provenance →" link on DocumentDetailPage
- **UI header**: updated to "M4 Query"
- **TypeScript compiles clean**, production bundle built (460KB JS, 1.1MB CSS gzipped to 139KB + 96KB)

## Decisions Made

| Decision | Summary |
|----------|---------|
| [DEC-009](../../decisions.md) | Two-layer lineage: Marquez for ingest (dataset-level), MLflow traces for query (request-level). Application-level OL emission for graph completion. Diverges from Data Strategy proposal's Pillar 4 framing. |
| [DEC-010](../../decisions.md) | LangGraph + MCP + MLflow autolog for M4 deterministic RAG. OGX reserved for M5 agentic RAG. Amends ADR-003 scope. |
| [DEC-011](../../decisions.md) | Registry UI as unified provenance portal, federating MLflow + Marquez + Registry APIs. |

## Verification Results

| Test | Result | Evidence |
|------|--------|----------|
| Granite LLM serving | **PASS** | `curl /v1/chat/completions` returns coherent response; `granite-llm` model listed |
| Milvus queryable | **PASS** | 363 vectors, 10 docs, `pipeline_run_id` on every vector |
| MCP server → Milvus search | **PASS** | `milvus_search` returns ChunkResult with doc_id, pipeline_run_id, text, score |
| LangGraph agent E2E | **PASS** | Flood coverage question → cited answer referencing [ug-003] |
| MLflow trace capture | **PASS** | 7 spans captured per query (LangGraph → agent → call_model → RunnableSequence → Prompt → ChatOpenAI → should_continue) |
| Marquez app registration | **PASS** | `underwriter_chat` job with `milvus://underwriting_guidelines` input visible in Marquez API |
| Registry UI build | **PASS** | TypeScript compiles clean; production bundle built |

## Production Gaps Identified

See [production-gaps.md](../../production-gaps.md) for the full register. M4 added PG-042 through PG-053.

| ID | Gap | Status |
|----|-----|--------|
| PG-047 | LLM occasionally skipped tool call (ReAct agent) | **Closed** — Restructured to deterministic RAG graph (retrieve → generate) |
| PG-018 | Embedding ISVC blocked (RHOAI 3.4 vLLM lacks `--task=embedding`) | Mitigated — using local sentence-transformers; re-evaluate on RHOAI 3.5+ |
| PG-019 | Embedding model downloads per startup | Open — MCP server downloads Granite Embedding 125M on each restart |
| PG-009 | No query/response audit logging | **Closed** — MLflow autolog captures full traces with doc_ids, pipeline_run_ids |
| PG-048 | RHOAI MLflow lacks trace delete API | Open — upstream feature request |
| PG-049 | MLflow `traceOutputs` metadata truncated at 250 chars | Open — upstream bug |
| PG-050 | Chainlit incompatible with Python 3.14 (asyncio) | Open — pin to Python 3.12/3.13 |
| PG-051 | MLflow workspace header requires monkeypatch (`mlflow_config.py`) | Mitigated |
| PG-052 | Port-forward instability for local dev | Open — deploy on cluster to resolve |
| PG-053 | Query service not yet deployed on cluster | Open — M5 deployment task |

## Cluster State After M4

| Component | Pods | Status | Endpoint |
|-----------|------|--------|----------|
| DSPA (KFP v2) | 6 ds-pipeline-* pods | Running | Route: ds-pipeline-dspa |
| MinIO | 1 pod | Running | minio-service:9000 |
| Milvus | 3 pods (standalone, etcd, minio) | Running | milvus:19530 |
| Marquez PostgreSQL | 1 pod | Running | marquez-db:5432 |
| Marquez API | 1 pod | Running | marquez:5000 (route exposed) |
| Marquez Web UI | 1 pod | Running | marquez-web:3000 (route exposed) |
| MLflow | Cluster-wide (redhat-ods-applications) | Running | mlflow.redhat-ods-applications.svc:8443 |
| Document Registry | 1 pod (FastAPI + nginx UI) | Running | doc-registry:8080 (route exposed) |
| **Granite LLM (NEW)** | 1 pod (vLLM on A100) | Running | granite-llm-predictor:8080 |
| **Query Service (NEW)** | Not yet deployed | Local only | src/query/ |

## Files Created/Modified

### New files
| File | Purpose |
|------|---------|
| `src/query/mcp_server.py` | MCP server wrapping Milvus vector search |
| `src/query/agent.py` | LangGraph ReAct agent with underwriting system prompt |
| `src/query/app.py` | Chainlit chat UI with streaming and trace enrichment |
| `src/query/lineage.py` | Application-level OL emission to Marquez |
| `src/query/test_e2e.py` | E2E test script |
| `src/query/requirements.txt` | Python dependencies |
| `src/query/.env.example` | Environment variable template |
| `src/registry/provenance.py` | Federation endpoints (Marquez + MLflow + Registry) |
| `src/registry-ui/src/pages/QueryTracesPage.tsx` | Query traces list view |
| `src/registry-ui/src/pages/TraceDetailPage.tsx` | Trace detail provenance view |
| `src/registry-ui/src/pages/DocumentProvenancePage.tsx` | Document provenance view |
| `manifests/model-serving/serving-runtime.yaml` | vLLM CUDA ServingRuntime |
| `manifests/model-serving/granite-llm-isvc.yaml` | Granite LLM InferenceService |
| `manifests/model-serving/granite-embedding-isvc.yaml` | Embedding ISVC (blocked, documented) |
| `docs/milestones/M4-query/plan.md` | M4 plan |
| `docs/milestones/M4-query/checkpoint.md` | This file |

### Modified files
| File | Change |
|------|--------|
| `docs/decisions.md` | Added DEC-009, DEC-010, DEC-011 |
| `docs/milestones/README.md` | Updated M4/M5 status and descriptions |
| `src/registry/app.py` | Mounted provenance router, bumped to v0.2.0 |
| `src/registry-ui/src/App.tsx` | Added Queries nav, trace routes, header update |
| `src/registry-ui/src/api.ts` | Added provenance types and API methods |
| `src/registry-ui/src/pages/DocumentDetailPage.tsx` | Added "View Full Provenance" link |

## How to Resume for M5

1. M4 query service runs locally with port-forwards to cluster (Milvus, LLM, Marquez)
2. Next step: deploy query service on cluster (pod + route)
3. Wire MLflow traces to cluster MLflow (SA token + workspace header)
4. M5 scope: OGX for agentic RAG (Workflow B), multi-hop across all 3 collections, RBAC
5. Key repos unchanged: pipeline components stable, rhoai-lineage may need minor additions for M5 OL emission
