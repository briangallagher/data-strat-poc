# M5 Checkpoint: Agentic + Hardening

**Date:** 2026-05-28
**Status:** Complete

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

### Phase 5: Verification + Documentation (COMPLETE)

| Deliverable | Status |
|-------------|--------|
| ADR-004: OGX for Agentic RAG | **Complete** — `docs/architecture/adrs/ADR-004-ogx-agentic-rag.md` |
| DEC-012: OGX Trace Correlation | **Complete** — `docs/decisions.md` |
| Observability comparison | **Complete** — `docs/technical/observability-comparison.md` |
| Production gaps recheck | **Complete** — 60 gaps tracked, 12 closed/mitigated, 48 open |
| E2E Workflow B test | **Complete** — Hermes-3-Llama-3.1-70B-FP8 via vLLM, 4 tool calls across 3 collections, synthesized compliance review |
| M1-M4 regression | **Complete** — all components operational |
| Repo tagging (`m5-complete`) | **Complete** |

### Phase 6: Model Upgrade + Registry Hardening (COMPLETE)

| Deliverable | Detail |
|-------------|--------|
| Model upgrade | Granite 3.3 8B → Hermes-3-Llama-3.1-70B-FP8 (NousResearch, ungated, FP8 quantized, fits 1x A100-80GB) |
| Granite 3.3 8B retired | Confirmed unsupported for vLLM tool calling; Hermes provides native structured `tool_calls` with `tool_choice=auto` |
| Deployment mode | Raw Kubernetes Deployment (bypassing KServe storage initializer limitations) |
| Registry trace extraction | Fixed to handle both OpenAI chat completion format (agentic) and LangChain format (deterministic) |
| Multi-experiment search | Registry now searches across multiple MLflow experiments (`compliance-review-agent` + `underwriter-chat-v3`) |
| Apps discovery | From MLflow trace tags (not just Marquez APPLICATION jobs) |
| Observability links | Marquez and MLflow external links added to registry UI sidebar |
| Marquez lineage | `compliance_review_agent` registered as APPLICATION consuming all 3 Milvus collections with correct dataset namespace |
| Full E2E lineage graph | source docs → acquire → parse_and_chunk → ingest_to_milvus → Milvus collections → application |
| MLflow traces | 4 clean traces: 3 deterministic (one per collection) + 1 agentic (multi-collection) |
| PG-060 closed | MLflow auth resolved |
| Cluster cleanup | Stale Granite ISVC, completed docling Jobs, stuck PVCs removed |

## Cluster Verification (COMPLETE)

All items verified on cluster:

- [x] Deploy OGX Operator in `data-strat-poc` namespace
- [x] Deploy MCP server pod (SSE transport)
- [x] Deploy Chainlit app pod for compliance review
- [x] Model serving via vLLM (Hermes-3-Llama-3.1-70B-FP8, raw Deployment)
- [x] Run canonical Workflow B query — 4 tool calls across 3 collections, synthesized compliance review
- [x] MLflow trace captures tool calls and provenance tags (4 clean traces)
- [x] Registry UI views render with real data
- [x] M1-M4 regression pass
- [x] Tag repos `m5-complete`

## Production Gap Summary (M5)

| Metric | Count |
|--------|-------|
| Total gaps | 60 |
| Closed/Mitigated | 13 |
| Open | 47 |
| New in M5 | 7 (PG-054–PG-060) |
| Closed in M5 | 2 (PG-037, PG-060) |

## New Files in M5

```
src/query_ogx/
├── mcp_server.py          # MCP server with SSE transport
├── app.py                 # Chainlit app for compliance review
├── lineage.py             # OL emission for compliance_review_agent
├── requirements.txt       # Dependencies
└── .env.example           # Configuration

src/registry/
└── provenance.py              # Updated: multi-experiment search, dual trace extraction

src/registry-ui/src/
├── App.tsx                    # Updated: observability links in sidebar
├── api.ts                     # Updated: links endpoint
└── pages/
    ├── CollectionHealthPage.tsx    # M5 UI view
    ├── AppOverviewPage.tsx         # M5 UI view
    ├── ImpactAnalysisPage.tsx      # M5 UI view
    └── RegisterDocumentsPage.tsx   # M5 UI view

manifests/query-ogx/
├── mcp-server.yaml            # MCP server deployment
├── chainlit-app.yaml          # Chainlit app deployment
└── hermes-70b-fp8-vllm.yaml  # Hermes model vLLM deployment

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
| Model selection: Hermes-3-Llama-3.1-70B-FP8 for tool calling quality | Phase 6 findings |
