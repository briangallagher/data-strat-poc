# M5 Plan: Agentic + Hardening

**Date:** 2026-05-28
**Status:** Planning
**Depends on:** M4 (complete)

## Objective

Build Workflow B (Agentic Compliance Review) on OGX Responses API with server-side Tool Runtime, proving multi-hop retrieval across all 3 collections with full MLflow tracing. The Registry UI becomes the unified provenance portal federating all query and ingest data. This is the ADR-003 evaluation milestone — OGX proves (or disproves) its value for agentic RAG on RHOAI.

After M5, the system goes from "knowledge assistant" to "multi-application platform" with two independent query services (deterministic + agentic), full answer provenance across both, and operational UI views.

## Decisions Locked In

| Decision | Reference |
|----------|-----------|
| Agentic retrieval proof is the headline — prove multi-hop with full tracing; compliance report format is secondary | This plan |
| Build on OGX Responses API with server-side Tool Runtime — independent from M4's LangGraph stack | ADR-003; DEC-010 |
| MLflow tracing is non-negotiable — investigate autolog, fall back to manual spans if needed | DEC-009 |
| RBAC (PG-008) deferred to M6 | This plan |
| Inner/outer loop evals deferred to M6 | This plan |
| Four UI views in scope: Collection Health, App Overview, Impact Analysis, Register Documents | This plan |
| OGX evaluation captured as a full ADR | This plan |

## Architecture

### M4 vs M5

```
M4 (Deterministic RAG):
  User → Chainlit → LangGraph Agent → MCP Server → Milvus (underwriting_guidelines)
                                     → Granite LLM
                  → mlflow.langchain.autolog() → MLflow Traces

M5 (Agentic RAG):
  User → Chainlit → OGX Responses API → Tool Runtime → Tool Service → Milvus (all 3 collections)
                                       → Granite LLM
                  → autolog or manual spans → MLflow Traces
                    Tool Service → spans → MLflow Traces
```

**Key structural difference:** M4's LangGraph agent follows a fixed retrieve-then-generate graph — the application controls retrieval. M5's OGX agent has an autonomous loop — it decides which tools to call, how many times, and in what order. OGX handles the entire agent loop server-side via Tool Runtime. The client sends one request and gets the final answer.

### Server-side MCP Tool Execution

```
Client (Chainlit) ──request──→ OGX Responses API
                                    │
                                    ├── LLM reasoning (Granite)
                                    ├── Tool call → MCP (SSE) → mcp_server.py → Milvus
                                    ├── Tool call → MCP (SSE) → mcp_server.py → Milvus
                                    ├── LLM synthesis
                                    │
                  ←──response──── (includes function_call + function_call_output items)
```

OGX connects to the MCP server via SSE, discovers `list_collections` and `milvus_search` tools, and calls them server-side during the agent loop. The response includes all intermediate tool calls and results as output items.

## Phases

### Phase 0: OGX Infrastructure + Observability Investigation

Deploy OGX and verify the Responses API works with server-side Tool Runtime and the existing Granite LLM. Resolve the **critical design question** of how MLflow traces are captured when OGX owns the agent loop.

**Phase 0 is a go/no-go gate for the rest of M5.**

#### 0a: OGX Deployment

| Task | Details | Verification |
|------|---------|--------------|
| Deploy OGX Operator | `data-strat-poc` namespace (or `data-strat-ogx` per DEC-005) | Operator running, LlamaStackDistribution CR accepted |
| Configure LLM backend | Point OGX at existing Granite vLLM ISVC (`granite-llm-predictor`) | OGX can generate responses via Granite |
| Register test tool | Simple tool via Tool Runtime (`/v1/tool-runtime`) | OGX calls tool server-side during agent loop |
| Verify E2E | Responses API accepts prompt + tool definitions, calls tool, returns answer | `curl` test passes |

#### 0b: Trace Correlation Investigation (Critical)

With server-side Tool Runtime, OGX owns the agent loop. The client sends a request and gets a response. The tool service is called by OGX, not by our code. This creates a trace correlation problem: **how do we build a single MLflow trace that spans the client request, the OGX agent loop, and the tool service executions?**

Investigate four questions:

| # | Question | Why It Matters |
|---|----------|----------------|
| Q1 | Does the Responses API response include tool call details (tool name, inputs, outputs)? | If yes, client can reconstruct the full trace |
| Q2 | Does `mlflow.openai.autolog()` capture tool call rounds from the response? | If yes, tracing is zero-effort (like M4) |
| Q3 | Does OGX propagate trace context (OpenTelemetry `traceparent`, request ID) to tool service calls? | If yes, tool service spans can correlate to client trace |
| Q4 | What protocol does OGX Tool Runtime use to call external tools (HTTP, gRPC, MCP, OGX-specific)? | Determines tool service implementation |

**Possible outcomes:**

| Q1 (response has tool details) | Q2 (autolog captures them) | Q3 (trace context propagated) | Strategy |
|---|---|---|---|
| Yes | Yes | -- | Best case: autolog handles everything. Add trace enrichment tags only. |
| Yes | No | -- | Client-side reconstruction: parse tool details from response, create manual child spans. |
| No | -- | Yes | Tool-side tracing: tool service emits spans correlated to the client trace via propagated context. |
| No | -- | No | Hardest case: tool service emits standalone spans keyed by a query ID we inject. Client and tool spans joined post-hoc. |

**Output:** Document findings as **DEC-012: OGX Trace Correlation Strategy** in `docs/decisions.md`.

#### 0c: Exit Criteria

- OGX Responses API works with a Tool Runtime tool, backed by Granite LLM
- Q1, Q2, Q3, Q4 answered with evidence
- DEC-012 written — tracing strategy decided
- **Go/no-go:** If OGX + Granite doesn't work, Tool Runtime is too immature, or trace correlation is impossible — stop and discuss before proceeding to Phase 1

### Phase 1: Agentic RAG Service (Workflow B on OGX)

Build the agentic query service as an independent, production-grade **Application** (`compliance_review_agent`). This is `src/query_ogx/` — completely independent from M4's `src/query/`. The search logic (pymilvus, embedding) can be shared as a library concern, but the query service architecture is OGX-native.

**Tool design decision:** One parameterised `milvus_search(query, collection, filters, top_k)` tool (agent selects collection) vs three named tools (`search_guidelines`, `search_forms`, `search_bulletins`). Three named tools with semantic descriptions may help the agent make better routing decisions, but one tool with a collection parameter is simpler. Evaluate during implementation.

| Task | Details |
|------|---------|
| **MCP server** | `src/query_ogx/mcp_server.py` — FastMCP server with SSE transport. Exposes `list_collections()` and `milvus_search(query, collection, ...)` tools. Wraps pymilvus search with local embedding. Returns ChunkResult objects with full provenance metadata. Deployed as a pod with SSE endpoint. |
| **OGX tool registration** | Inline MCP tool in Responses API request (`type: "mcp"`, `server_url: http://mcp-server:8000/sse`). OGX discovers tools via MCP protocol at call time. |
| **Chainlit app** | `src/query_ogx/app.py` — thin client calling OGX Responses API via OpenAI client. Parses `function_call` and `function_call_output` items from response to show tool calls as Chainlit Steps. |
| **Multi-hop verification** | Test with canonical Workflow B query: "Review our GL guidelines against ISO CG 00 01. Flag deviations." Agent should search 2+ collections. |

**Exit criteria:** Ask the canonical Workflow B question, OGX autonomously searches 2+ collections via server-side tool calls, cross-references results, produces coherent cited answer. Client never executes a tool.

### Phase 2: MLflow Tracing + Observability

Implement the tracing strategy decided in DEC-012 (Phase 0b).

**Two tracing surfaces:**

1. **Client-side (Chainlit → OGX):** What autolog captures from the OpenAI client's perspective.
2. **Tool service side (OGX → tool_service):** Spans emitted by the tool service during each search.

**Trace structure target:**

```
Root Span: "Compliance Review Query"
├── metadata: user_id, app_name, timestamp
│
├── Child Span: "OGX Agent Loop"
│   ├── input: user question + tool definitions
│   │
│   ├── Child Span: "Tool Call 1: search_guidelines"
│   │   ├── input: query, collection, filters
│   │   └── output: chunks with doc_ids, pipeline_run_ids, scores
│   │
│   ├── Child Span: "Tool Call 2: search_forms"
│   │   ├── input: query, collection, filters
│   │   └── output: chunks with doc_ids, pipeline_run_ids, scores
│   │
│   ├── Child Span: "Tool Call 3: search_bulletins" (if agent decides)
│   │   ├── input: query, collection, filters
│   │   └── output: chunks with doc_ids, pipeline_run_ids, scores
│   │
│   └── output: synthesized answer with citations
│
└── Custom Tags: doc_ids_cited, pipeline_run_ids, collections_queried, chunks_count
```

**Trace tag schema compatibility (contract):** M5 trace enrichment MUST use the same tag names and formats as M4: `doc_ids_cited`, `pipeline_run_ids`, `collection_queried`, `chunks_detail`, `answer_preview`, `chunks_retrieved_count`. The Registry provenance endpoints (`src/registry/provenance.py`) parse these tags to power the provenance portal. If M5 traces use different names, the portal breaks for M5 queries. Treat this as a contract.

| Task | Details |
|------|---------|
| **Tracing implementation** | Per DEC-012 strategy (autolog, manual spans, or hybrid) |
| **Trace enrichment** | Tag each trace with contract tags after query completes |
| **Application-level OL emission** | Emit OL event registering `compliance_review_agent` as consumer of all 3 Milvus collections in Marquez |
| **Observability comparison** | Document: what M4 autolog captures vs M5 OGX tracing. Where are the gaps? What's in OGX's black box? |

**Exit criteria:** Given any M5 trace ID, the provenance portal shows: question, tool calls (with collections and chunks), answer, doc_ids cited, pipeline_run_ids for the Marquez bridge. Comparison document written.

### Phase 3: Registry UI Views

Four new views in the PatternFly 6 Registry UI (`src/registry-ui/`).

| View | Page Component | What It Shows | Data Sources |
|------|----------------|---------------|--------------|
| **Collection Health** | `CollectionHealthPage.tsx` | Document count, vector count, consuming apps, query volume, last ingest, staleness | Registry + Milvus + Marquez + MLflow |
| **App Overview** | `AppOverviewPage.tsx` | List of apps, collections each consumes, query count, last query | Marquez jobs + MLflow traces |
| **Impact Analysis** | `ImpactAnalysisPage.tsx` | Enter doc_id → collections, consuming apps, query traces that cited it | `/provenance/document/{doc_id}` |
| **Register Documents** | `RegisterDocumentsPage.tsx` | Form: source_url, name, metadata, target collection. Two sections: Document Identity (Registering) and Collection Assignment (Building) | Registry API |

**Backend additions:**

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/collections/{name}/health` | Aggregates Registry + Milvus + Marquez + MLflow stats |
| `GET /api/v1/apps` | Lists application jobs from Marquez with query volume from MLflow |

**Exit criteria:** All four views render with real data. Compliance officer can register a document, check collection health, see apps and their collections, run impact analysis.

### Phase 4: Gap Closure + Deployment

| Task | Details |
|------|---------|
| Deploy M4 query service on cluster | Pod + route for Chainlit + LangGraph (local-only per M4 checkpoint) |
| Deploy M5 query service on cluster | Pod + route for Chainlit + OGX agent + tool service pod |
| Wire MLflow to cluster | SA token + workspace header (pattern established, not deployed) |
| Close PG-019 | Pre-cache embedding model on PVC (downloads per startup) |
| Assess PG-047 for OGX | Does OGX reliably call tools, or does it skip like Granite did with LangGraph? Document. |

**Production gaps:** Log new gaps as discovered during each phase (per DEC-002). Close what we can.

### Phase 5: Verification + Documentation

| Task | Details |
|------|---------|
| E2E Workflow B test | 3 distinct compliance review questions across different LOBs. Verify multi-hop + cross-referencing + tracing. |
| Regression | M1 (ingest), M2 (lineage), M3 (registry + connectors), M4 (deterministic RAG) |
| ADR: OGX for Agentic RAG | Full ADR: orchestration quality, observability, DX, production readiness, comparison with M4 LangGraph. Recommends path forward. Updates ADR-003 status. |
| Production gaps recheck | Full pass over `production-gaps.md` — add M4 gaps never logged, verify M5 gaps captured, update statuses |
| Checkpoint | M5 checkpoint document with verification evidence |
| Tag repos | `m5-complete` across all repos |

## What M5 Does NOT Include

| Deferred | Why |
|----------|-----|
| RBAC (PG-008) | Orthogonal to agentic headline; deferred to M6 |
| Inner/outer loop evals | Valuable but separate concern; eval framework deferred to M6 |
| Polished compliance report format | Headline is agentic proof, not report formatting |
| Feedback collection (thumbs up/down) | Chainlit supports it, not in M5 scope |
| Hybrid search (PG-007) | Infrastructure change; evaluate separately |
| Real connectors (PG-010) | Mock connectors sufficient for POC |
| Embedding ISVC (PG-018) | Blocked by RHOAI 3.4; local sentence-transformers works |

## Phase 0 Research Findings

Research conducted before coding (documented here for decision traceability):

| Question | Finding | Evidence |
|----------|---------|----------|
| **Q4: Tool protocol** | **MCP via SSE** — OGX uses Model Context Protocol. MCP servers are registered in run.yaml or programmatically. OGX connects via SSE, discovers tools at startup, routes tool calls during the agent loop. | rh-ai-quickstart/llama-stack-mcp-server, llamastack.github.io/docs, Red Hat Developer article |
| **Q1: Response includes tool details** | **Yes** — Responses API returns `OpenAIResponseObject` with intermediate `function_call` and `function_call_output` items. Client can see every step. | llamastack.github.io/docs/api-openai/responses-flow, Red Hat Developer article |
| **Q2: Autolog captures tool rounds** | **Likely yes, needs verification** — Since Responses API is OpenAI-compatible, `mlflow.openai.autolog()` should capture tool call rounds. Requires hands-on testing. | Inference from OpenAI client compatibility |
| **Q3: Trace context propagation** | **Partial** — OGX has `forward_headers` and `mcp_headers` for auth, but no explicit OpenTelemetry `traceparent` propagation. Tool service spans may be orphaned. | llamastack/llama-stack#5152, PR#5257 |

**Architectural implication:** The tool service is an **MCP server with SSE transport**, not a REST API. M4 already has an MCP server (`mcp_server.py`) using FastMCP/stdio. M5 adapts this to SSE transport for OGX. The `rh-ai-quickstart/llama-stack-mcp-server` repo demonstrates this exact pattern.

**Registration options:**
1. Declarative in `run.yaml` (production)
2. Programmatic via `client.toolgroups.register()` (development)
3. Inline in each Responses API request as `type: "mcp"` tool (simplest for POC)

M5 uses inline MCP tools (option 3) for POC simplicity.

## Open Questions (Remaining)

1. **Autolog verification** — Does `mlflow.openai.autolog()` actually capture Responses API tool call rounds as child spans? Needs hands-on test with OGX.
2. **Trace correlation** — Without OpenTelemetry propagation, tool service spans are orphaned. Can we use the inline MCP response to reconstruct the full trace client-side instead?
3. **Embedding model** — Does the tool service need its own local embedding model, or can OGX's built-in embedding be used?

## References

| Source | Location |
|--------|----------|
| OGX knowledge doc | `work-knowledge/knowledge/rhoai/ogx/ogx.md` |
| Scenario B (Workflow B walkthrough) | `DataStrategy/.../scenario-b-underwriting-knowledge.md` §6 |
| ADR-003 (OGX role) | `docs/architecture/adrs/ADR-003-ogx-role.md` |
| DEC-009 (two-layer lineage) | `docs/decisions.md` |
| DEC-010 (LangGraph for M4, OGX for M5) | `docs/decisions.md` |
| DEC-011 (Registry as provenance portal) | `docs/decisions.md` |
| M4 checkpoint | `docs/milestones/M4-query/checkpoint.md` |
| MLflow agent tracing demo | `~/dev/workspaces/mlflow/demo_mlflow_agent_tracing` |
| RHOAI Llama Stack docs | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_llama_stack/ |
| OGX Responses API deep dive | https://developers.redhat.com/articles/2025/08/20/your-agent-your-rules-deep-dive-responses-api-llama-stack |
