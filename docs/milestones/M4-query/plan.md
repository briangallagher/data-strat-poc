# M4 Plan: Query Layer (Deterministic RAG)

**Date:** 2026-05-27
**Status:** Planning
**Depends on:** M3 (complete)

## Objective

Add the query layer so users can ask questions against ingested documents and get cited, traceable answers. M4 delivers **Workflow A (Deterministic RAG)** — querying `underwriting_guidelines` — with full answer provenance via MLflow tracing.

After M4, the system goes from "data pipeline" to "knowledge assistant." For the first time, a user asks a question and gets a grounded answer with source citations, and every step is traceable from answer back to source document.

## Key Decisions

| Decision | Choice | Reference |
|----------|--------|-----------|
| Query orchestration | LangGraph + MCP + MLflow autolog (not OGX) | [DEC-010](../../decisions.md) |
| Query-time lineage | MLflow traces, not Marquez OL events | [DEC-009](../../decisions.md) |
| Chat UI | Chainlit | DEC-010 |
| Initial collection scope | `underwriting_guidelines` (extend to all 3 after verification) | — |
| OGX | Deferred to M5 (agentic RAG) | DEC-010; amends [ADR-003](../../architecture/adrs/ADR-003-ogx-role.md) |
| Unified provenance | Registry UI as single pane of glass, federating MLflow + Marquez + Registry | [DEC-011](../../decisions.md) |

## Architecture

```
User (Browser)
    │
    │ WebSocket
    ▼
┌──────────────┐
│  Chainlit    │  Chat UI (app.py)
│  Frontend    │
└──────┬───────┘
       │ astream()
       ▼
┌──────────────┐       ┌──────────────────┐
│  LangGraph   │──────→│  LLM Service     │
│  Agent       │  chat │  (vLLM / Granite) │
│              │  comp │                  │
│  ┌────────┐  │       └──────────────────┘
│  │ MCP    │  │
│  │ Client │  │       ┌──────────────────┐
│  └───┬────┘  │       │  Milvus          │
│      │       │       │  (underwriting_  │
└──────┼───────┘       │   guidelines)    │
       │ stdio         └────────┬─────────┘
       ▼                        │
┌──────────────┐    pymilvus    │
│  MCP Server  │────────────────┘
│  (milvus     │
│   search)    │       ┌──────────────────┐
│              │──────→│  Embedding ISVC  │
└──────────────┘ embed │  (Granite 125M   │
                 query │   via vLLM)      │
       │               └──────────────────┘
       │
       │ mlflow.langchain.autolog()
       ▼
┌──────────────┐       ┌──────────────────┐
│  MLflow      │──────→│  Marquez         │
│  (traces)    │ join  │  (ingest lineage)│
│              │ via   │                  │
│  query-time  │ p_r_id│  pipeline-time   │
└──────────────┘       └──────────────────┘
```

### Trace Structure (per query)

```
Root Span: "RAG Query"
├── metadata: user_id, collection, timestamp
│
├── Child Span: "LLM Reasoning" (tool selection)
│   └── prompt: system + user question + tool definitions
│
├── Child Span: "Tool Call: milvus_search"
│   ├── input: query text, collection, filters, top_k
│   └── output: retrieved chunks with:
│       ├── doc_id (e.g., ug-003)
│       ├── chunk_index
│       ├── pipeline_run_id (bridge to Marquez)
│       ├── text content
│       ├── similarity score
│       └── metadata (LOB, jurisdiction, effective_date)
│
└── Child Span: "LLM Generation" (cited answer)
    ├── prompt: user question + retrieved context
    └── output: answer with source citations
```

### Answer Provenance (Chain 1)

```
MLflow trace
  → retrieved chunk (doc_id: ug-003, pipeline_run_id: abc-123)
    → Registry: GET /documents/ug-003 → source_url, metadata, collections
    → Marquez: GET /lineage?pipeline_run_id=abc-123 → full ingest graph
```

Both directions answered:
- **Forward:** "Which documents answered this question?" → MLflow trace → chunk doc_ids → Registry
- **Reverse:** "Which questions were answered by this document?" → MLflow trace search API, filter by doc_id in span attributes

### Marquez Graph Completion (Application-Level OL)

Emit a lightweight OpenLineage event per application (not per query) to show downstream consumption of Milvus collections in the Marquez graph. Each application is a distinct OL job:

```
source docs → acquire → S3 → parse → milvus://underwriting_guidelines → underwriter_chat (M4)
source docs → acquire → S3 → parse → milvus://regulatory_bulletins   → compliance_review_agent (M5)
source docs → acquire → S3 → parse → milvus://iso_forms              → compliance_review_agent (M5)
                                                                      → forms_lookup (M5)
```

This completes the Marquez graph from source documents through ingest to application consumption. Modelled at the application level — not per-query — to keep the graph clean and stable. Per-query detail (which chunks, which documents, which questions) lives in MLflow traces (DEC-009).

For M4: one job node (`underwriter_chat`) with `milvus://underwriting_guidelines` as input. Run events emitted on application startup or first query, not per-request. M5 adds `compliance_review_agent` and `forms_lookup` spanning all 3 collections.

## Phases

### Phase 0: Query Infrastructure

Deploy the services needed to run queries. No application code yet.

| Task | Details | Verification |
|------|---------|--------------|
| Deploy LLM serving | Granite via vLLM InferenceService (KServe). Deploy in `data-strat-poc` namespace. | `curl /v1/chat/completions` returns a response |
| ~~Deploy embedding InferenceService~~ | **Blocked by PG-018:** RHOAI 3.4 vLLM (v0.18.0) does not support `--task=embedding`. Fallback: local `sentence-transformers` in MCP server process (same model: `ibm-granite/granite-embedding-125m-english`). PG-019 remains open. | Verify MCP server embeds queries correctly; dimension matches Milvus schema |
| Verify Milvus queryable | pymilvus search against `underwriting_guidelines` from within namespace | Top-k results returned with all metadata fields |
| Verify pipeline_run_id on vectors | Confirm every vector in `underwriting_guidelines` carries `pipeline_run_id` | pymilvus query with output_fields including `pipeline_run_id` |

**Exit criteria:** LLM, embedding, and Milvus all reachable; test search returns vectors with metadata.

### Phase 1: Deterministic RAG Service (Workflow A)

Build the query service following the `demo_mlflow_agent_tracing` pattern.

| Task | Details |
|------|---------|
| **MCP server** | `src/query/mcp_server.py` — wraps pymilvus search. Tool: `milvus_search(query, collection, filters, top_k)`. Embeds the query, runs ANN search, returns chunks with all metadata (doc_id, chunk_index, pipeline_run_id, text, score, LOB, jurisdiction, effective_date). |
| **LangGraph agent** | `src/query/agent.py` — system prompt grounds the agent to the knowledge base. Single tool: milvus_search. Temperature 0 for deterministic responses. Must cite source documents in every answer. |
| **Chainlit app** | `src/query/app.py` — chat UI with streaming. Tool call steps visible in UI. User auth (basic or OAuth). |
| **MLflow autolog** | `mlflow.langchain.autolog()` — one-liner, captures full trace tree automatically. |
| **System prompt** | Grounded to underwriting domain. Must search before answering. Must cite doc_id + section. Must refuse questions not covered by the knowledge base. |
| **Metadata filtering** | MCP server supports filters: `line_of_business`, `document_type`, `jurisdiction`, `effective_date`. Agent can use filters based on the question (e.g., "California" → `jurisdiction=CA`). |
| **Response format** | Answer with inline citations: doc_id, section, page number. Sources list at the end. Matches Workflow A format from Scenario B. |

**Key reference:** `demo_mlflow_agent_tracing` repo — same architecture (LangGraph + MCP + Chainlit + MLflow), adapted from ChromaDB to Milvus.

**Exit criteria:** Ask "Does our commercial property form cover flood damage in Zone X?" → get cited answer → see full trace in MLflow UI with chunk-level detail.

### Phase 2: Query Audit + Provenance Bridge

Connect query traces to ingest lineage. Close PG-009.

| Task | Details |
|------|---------|
| **Validate MLflow trace search API** | Early validation: confirm MLflow's `search_traces` API can filter traces by doc_id and collection name within span attributes — server-side, not client-side filtering. This is the foundation for the reverse lookup ("which queries cited this document?"). If MLflow doesn't support deep span attribute search, we'll need a lightweight query log table in the Registry database as a fallback. Validate before building the provenance portal. |
| **Enrich MCP search results** | Include `pipeline_run_id` and `doc_id` in every returned chunk. These are already on the vectors — just ensure they surface in the tool output span. |
| **Custom trace metadata** | Add to each trace: `collection_queried`, `chunks_retrieved_count`, `docs_cited` (list of doc_ids), `pipeline_run_ids` (list of unique IDs from retrieved chunks). |
| **Registry provenance endpoint** | `GET /provenance/query` — accepts a list of doc_ids and pipeline_run_ids, returns: document metadata (from Registry), Marquez lineage links (constructed URLs), full Chain 1 for each cited document. |
| **Verify Chain 1 E2E** | From an MLflow trace: extract pipeline_run_id → query Marquez API → confirm full ingest lineage graph → extract doc_id → query Registry → confirm source_url and metadata. |
| **Application-level OL emission** | On query service startup (or first query), emit an OL event: `Job: underwriter_chat`, `Input: milvus://underwriting_guidelines`. Uses `rhoai-lineage` emitter directly. Creates the downstream consumption edge in Marquez. One event per application, not per query. |
| **Verify Marquez graph** | Confirm `underwriter_chat` appears downstream of `milvus://underwriting_guidelines` in Marquez Web UI. Full graph: source docs → ingest pipeline → Milvus → underwriter_chat. |

**Exit criteria:** Given any MLflow trace ID, programmatically reconstruct the full chain from answer → chunks → pipeline_run → source documents. Marquez graph shows the query application consuming the Milvus collection.

### Phase 3: Unified Provenance Portal

The Registry UI becomes the **single pane of glass** for all provenance questions. It federates across three backends (Registry API, MLflow API, Marquez API) so users never need to know those systems exist. Closes UX Gaps 1 ("no unified provenance UI") and 3 ("no query-time tracing").

**Principle:** The user enters through a document, a query, a collection, or an app — and can navigate to any related artifact without leaving the Registry UI. Deep links to Marquez graph or MLflow trace detail are available for engineers, but every provenance question is answerable in the portal.

#### Backend: Registry Federation Layer

| Task | Details |
|------|---------|
| **MLflow API integration** | Registry backend calls MLflow trace search API. Fetch recent traces, search by doc_id in span attributes, retrieve trace detail (spans, inputs, outputs). |
| **Marquez API integration** | Registry backend calls Marquez API. Fetch lineage graph for a pipeline_run_id, fetch job run history for applications, resolve dataset relationships. |
| **`/provenance/document/{doc_id}`** | Federated endpoint: combines Registry metadata + MLflow traces citing this doc + Marquez ingest lineage for this doc's pipeline runs + apps consuming its collections. Single call, unified response. |
| **`/provenance/trace/{trace_id}`** | Federated endpoint: MLflow trace detail + Registry document metadata for each cited doc_id + Marquez lineage links for each pipeline_run_id. |
| **`/provenance/collection/{name}`** | Federated endpoint: Registry collection membership + Milvus vector count + Marquez downstream apps + MLflow query volume (trace count). |

#### Frontend: Provenance Views (M4 Scope)

| View | Entry Point | What It Shows | Data Sources |
|------|-------------|---------------|--------------|
| **Document Provenance** | Click any document in existing list | Collections, consuming apps, recent queries that cited it, ingest pipeline runs, source URL, full Chain 1 | Registry + MLflow + Marquez |
| **Query Trace Detail** | Click any trace from a trace list or document page | Question asked, answer generated, chunks retrieved (text preview, similarity scores), source documents (linked), pipeline run (linked to Marquez), app name | MLflow + Registry + Marquez |
| **Query Trace List** | New nav item: "Queries" | Recent query traces across all apps. Timestamp, question (truncated), docs cited, collection queried, app. Filterable by collection, doc_id, date range. | MLflow |

#### Frontend: Provenance Views (Deferred to M5)

These views are valuable but not essential for M4's core "answer provenance" goal:

| View | What It Shows | Why Deferred |
|------|---------------|--------------|
| **Collection Health** | Document count, vector count, consuming apps, query volume, staleness, last ingest | Useful for ops, not core to answer provenance |
| **App Overview** | List of apps, which collections each consumes, query count, last query, health | Only one app in M4; becomes relevant when M5 adds 2 more |
| **Impact Analysis** | "If I update/remove this document, which apps and queries are affected?" | Requires both forward and reverse lookups working; M5 polish |

#### Deploy

| Task | Details |
|------|---------|
| **Deploy Chainlit** | Deploy Chainlit app as a pod in the namespace with a route. |
| **Registry UI updated** | Redeploy Registry with new provenance pages. |

**Exit criteria:** A compliance officer opens the Registry UI, clicks a document, sees which queries cited it and which apps use it. Clicks a query, sees the full chain from answer → chunks → source documents. Never opens Marquez, MLflow, or a terminal.

### Phase 4: Verification + Documentation

| Task | Details |
|------|---------|
| **E2E Workflow A test** | Ask 3 distinct underwriting questions → verify cited answers → verify traces in MLflow → verify Chain 1 via Registry UI |
| **Regression** | Re-verify M1 (ingest), M2 (lineage), M3 (registry + connectors) |
| **Extend to all collections** | After `underwriting_guidelines` is verified, extend MCP server to support `regulatory_bulletins` and `iso_forms`. Verify cross-collection queries work (agent selects correct collection based on question). |
| **ADRs** | ADR for query service architecture (if beyond DEC-009/010 scope) |
| **Production gaps** | Log new PGs discovered during M4 |
| **Checkpoint** | M4 checkpoint document with verification evidence |
| **Tag repos** | `m4-complete` across all repos |

## New Infrastructure (M4)

| Component | What | Where |
|-----------|------|-------|
| LLM serving | Granite via vLLM InferenceService (KServe) | `data-strat-poc` namespace |
| Embedding | Local `sentence-transformers` in MCP server (PG-018 blocks ISVC) | Bundled in query service pod; PG-019 remains open |
| Query service | Chainlit + LangGraph + MCP server | `src/query/` in repo; deployed as pod |

**Registry changes:** New federation endpoints (`/provenance/*`) calling MLflow + Marquez APIs. New UI pages (Document Provenance, Query Trace Detail, Query Trace List). Existing Registry functionality unchanged.

**No changes to:** Marquez, Milvus, ingest pipeline, existing MLflow.

## Production Gaps (Expected)

| ID | Gap | Notes |
|----|-----|-------|
| PG-042+ | No auth on Chainlit beyond basic | OAuth proxy or OIDC needed for production |
| PG-043+ | Single LLM instance, no HA | Scaling/failover for vLLM serving |
| PG-044+ | No rate limiting on query service | Protect LLM from abuse |
| PG-045+ | No response caching | Repeated identical queries hit LLM each time |
| PG-046+ | No guardrails/safety filters | LLM can be prompted outside underwriting domain |
| PG-047 | ~~LLM occasionally skips tool call~~ | **Resolved:** Restructured from ReAct agent (LLM decides) to deterministic RAG graph (application always retrieves first). Retrieve → Generate pipeline — no LLM decision on whether to search. |

## What M4 Does NOT Include

| Deferred to M5 | Why |
|----------------|-----|
| Agentic RAG (Workflow B) | Multi-hop retrieval across all 3 collections — M5 headline |
| OGX Responses API evaluation | OGX's value is agent orchestration, not deterministic RAG (DEC-010) |
| Document-level RBAC at query time | PG-008 — requires Milvus partition-key or application-level filtering |
| Inner/outer loop evals | MLflow eval framework from the demo — valuable but not core to M4 provenance |
| Feedback collection (thumbs up/down) | Chainlit supports it (see demo app.py), but not in M4 scope |

## Open Items Resolved During Planning

| Item | Resolution |
|------|------------|
| LLM for generation | Granite via vLLM InferenceService (KServe) |
| Embedding at query time | Local `sentence-transformers` in MCP server (PG-018 blocks vLLM ISVC for embeddings). Same model: `ibm-granite/granite-embedding-125m-english`. PG-019 remains open. |
| Two UIs (Chainlit + Registry) | Acceptable for M4. Chainlit for asking questions, Registry for investigating provenance. M5+ could embed chat in Registry UI. |
| MLflow trace search by span attributes | Validate early in Phase 2. Ideal: MLflow API supports server-side filtering by doc_id in span attributes. Fallback: lightweight query log table in Registry database. |
| Phase 3 scope | Full scope in M4 — not constrained by timeline. |

## References

| Source | Location |
|--------|----------|
| MLflow agent tracing demo | `~/dev/workspaces/mlflow/demo_mlflow_agent_tracing` |
| Scenario B (Workflow A walkthrough) | `DataStrategy/.../scenario-b-underwriting-knowledge.md` §6 |
| ADR-003 (OGX role) | `docs/architecture/adrs/ADR-003-ogx-role.md` |
| DEC-009 (two-layer lineage) | `docs/decisions.md` |
| DEC-010 (LangGraph for M4) | `docs/decisions.md` |
| UX assessment (Gap 3) | `docs/user-experience/ux-assessment.md` |
| Lineage questions (unanswered) | `docs/user-experience/lineage-questions.md` |
| M3 checkpoint (cluster state) | `docs/milestones/M3-connectors/checkpoint.md` |
