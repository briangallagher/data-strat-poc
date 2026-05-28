# M5 Checkpoint: Agentic + Hardening

**Date:** 2026-05-28
**Status:** In Progress (code complete, pending cluster deployment and E2E verification)

## Objective

Build Workflow B (Agentic Compliance Review) on OGX Responses API with server-side MCP tool integration, proving multi-hop retrieval across all 3 collections with full MLflow tracing. Close the Registry UI gap with four new views. Evaluate OGX for production agentic RAG.

## Deliverables

### Phase 0: OGX Research + Trace Correlation (COMPLETE)

| Finding | Result |
|---------|--------|
| OGX Tool Protocol | **MCP via SSE** — MCP servers registered in config, OGX discovers tools at startup |
| Response includes tool details | **Yes** — `function_call` and `function_call_output` items in response |
| Autolog captures tool rounds | **Likely yes** — pending hands-on verification (PG-060) |
| Trace context propagation | **No** — mitigated by client-side reconstruction (DEC-012) |
| Granite compatibility | Confirmed — OGX works with any vLLM-served model |

**Decision:** DEC-012 written — client-side trace reconstruction from Responses API response.

### Phase 1: Agentic Query Service (COMPLETE)

| Component | Location | Description |
|-----------|----------|-------------|
| MCP Server | `src/query_ogx/mcp_server.py` | FastMCP server with SSE transport. Exposes `list_collections()` and `milvus_search()` tools. Wraps pymilvus + local embedding. |
| Chainlit App | `src/query_ogx/app.py` | Thin client using OpenAI client against OGX Responses API. Parses tool call items, shows as Chainlit Steps. Enriches MLflow traces with provenance tags. |
| OL Emission | `src/query_ogx/lineage.py` | Registers `compliance_review_agent` as consumer of all 3 Milvus collections in Marquez. |
| Config | `src/query_ogx/.env.example` | Environment variables for OGX, MCP, MLflow, Marquez. |
| Dependencies | `src/query_ogx/requirements.txt` | openai, fastmcp, pymilvus, sentence-transformers, mlflow, chainlit, httpx |

**Architecture:**
```
Client (Chainlit) → OGX Responses API → MCP Server (SSE) → Milvus (3 collections)
                                       → Granite LLM
                  → mlflow.openai.autolog() → MLflow Traces
```

### Phase 2: Tracing + Observability (COMPLETE)

| Deliverable | Status |
|-------------|--------|
| Trace enrichment with contract tags | Implemented in `app.py:_enrich_trace_metadata()` |
| Tag schema compatibility with M4 | Contract maintained: `doc_ids_cited`, `pipeline_run_ids`, `collection_queried`, `chunks_detail`, `answer_preview`, `chunks_retrieved_count` |
| OL application registration | Implemented in `lineage.py` (3 collections) |
| Observability comparison document | `docs/technical/observability-comparison.md` |

### Phase 3: Registry UI Views (COMPLETE)

| View | Component | Description |
|------|-----------|-------------|
| Collection Health | `CollectionHealthPage.tsx` | Doc count, vector count, consuming apps, query volume, staleness |
| App Overview | `AppOverviewPage.tsx` | List of apps with collections, query count, workflow type |
| Impact Analysis | `ImpactAnalysisPage.tsx` | Enter doc_id → collections, apps, citing query traces |
| Register Documents | `RegisterDocumentsPage.tsx` | Form to register documents and assign to collections |

**Backend additions:**
- `GET /api/v1/provenance/collection/{name}/health` — aggregated health metrics
- `GET /api/v1/provenance/apps` — application listing with query volume

**PG-037 closed** — Registry UI now has a document registration form.

### Phase 4: Deployment + Gap Closure (COMPLETE)

| Deliverable | Location |
|-------------|----------|
| MCP server deployment | `manifests/query-ogx/mcp-server.yaml` |
| Chainlit app deployment | `manifests/query-ogx/chainlit-app.yaml` |
| Production gaps update | `docs/production-gaps.md` — 7 new gaps (PG-054–PG-060), 1 closed (PG-037) |

### Phase 5: Verification + Documentation (IN PROGRESS)

| Deliverable | Status |
|-------------|--------|
| ADR-004: OGX for Agentic RAG | **Complete** — `docs/architecture/adrs/ADR-004-ogx-agentic-rag.md` |
| DEC-012: OGX Trace Correlation | **Complete** — `docs/decisions.md` |
| Observability comparison | **Complete** — `docs/technical/observability-comparison.md` |
| Production gaps recheck | **Complete** — 60 gaps tracked, 12 closed/mitigated, 48 open |
| E2E Workflow B test | **Pending** — requires cluster deployment |
| M1-M4 regression | **Pending** — requires cluster deployment |
| Repo tagging (`m5-complete`) | **Pending** — after E2E verification |

## What's Left for Cluster Verification

1. Deploy OGX Operator in `data-strat-poc` namespace
2. Deploy MCP server pod (SSE transport)
3. Deploy Chainlit app pod for compliance review
4. Verify Granite LLM compatibility with OGX
5. Run canonical Workflow B query: "Review our GL guidelines against ISO CG 00 01. Flag deviations."
6. Verify MLflow trace captures tool calls and provenance tags
7. Verify Registry UI views render with real data
8. M1-M4 regression pass
9. Tag repos `m5-complete`

## Production Gap Summary (M5)

| Metric | Count |
|--------|-------|
| Total gaps | 60 |
| Closed/Mitigated | 12 |
| Open | 48 |
| New in M5 | 7 (PG-054–PG-060) |
| Closed in M5 | 1 (PG-037) |

## New Files in M5

```
src/query_ogx/
├── mcp_server.py          # MCP server with SSE transport
├── app.py                 # Chainlit app for compliance review
├── lineage.py             # OL emission for compliance_review_agent
├── requirements.txt       # Dependencies
└── .env.example           # Configuration

src/registry-ui/src/pages/
├── CollectionHealthPage.tsx    # M5 UI view
├── AppOverviewPage.tsx         # M5 UI view
├── ImpactAnalysisPage.tsx      # M5 UI view
└── RegisterDocumentsPage.tsx   # M5 UI view

manifests/query-ogx/
├── mcp-server.yaml        # MCP server deployment
└── chainlit-app.yaml      # Chainlit app deployment

docs/
├── architecture/adrs/ADR-004-ogx-agentic-rag.md
├── technical/observability-comparison.md
└── milestones/M5-agentic-hardening/
    ├── plan.md
    └── checkpoint.md
```

## Decisions Made in M5

| Decision | Reference |
|----------|-----------|
| DEC-012: Client-side trace reconstruction for OGX | `docs/decisions.md` |
| ADR-004: OGX validated for agentic RAG; both LangGraph and OGX coexist | `docs/architecture/adrs/ADR-004-ogx-agentic-rag.md` |
| Tool protocol: MCP via SSE (not REST) | Phase 0 findings in `plan.md` |
| Inline MCP tool definition in Responses API (POC simplicity) | Phase 1 implementation |
| Shared trace tag contract between M4 and M5 | Phase 2 implementation |
