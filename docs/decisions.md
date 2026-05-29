# Decision Log

High-level decisions made during the project. For significant architectural decisions with detailed context and alternatives analysis, use [ADRs](architecture/adrs/).

---

## Template

```
### DEC-NNN: Title
**Date:** YYYY-MM-DD
**Milestone:** M<N>
**Status:** Proposed | Decided | Superseded by DEC-NNN

**Context:** What prompted the decision.

**Decision:** What was decided.

**Consequences:** What follows — trade-offs, follow-up work, risks accepted.
```

---

## Decisions

### DEC-001: Self-contained documentation in code repo
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** The initial approach split planning documentation across work-knowledge and the code repo. This created context-switching overhead and made it harder for new contributors to find things.

**Decision:** All documentation lives in `data-strat-poc` — architecture, technical, functional, UX, operations, milestones. The work-knowledge repo tracks this as a project entry but doesn't host the planning docs.

**Consequences:** Single source of truth. Documentation ships with the code. Trade-off: no cross-project knowledge aggregation in work-knowledge (mitigated by linking from projects/index.md).

### DEC-002: Production-grade from day one with explicit gap tracking
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** The initial approach built quickly and deferred production concerns (auth, RBAC, TLS, error handling). Gaps were discovered but not systematically tracked, making it hard to assess production readiness.

**Decision:** Enterprise standard is the default expectation. Every deviation is logged in `production-gaps.md` with: what the gap is, why it exists, what production-grade looks like, and the path to close it. Updated at every milestone checkpoint.

**Consequences:** Slower initial velocity but clearer production readiness posture. Nothing is silently accepted. Gap register serves as a backlog for hardening work.

### DEC-003: E2E verification at every milestone
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** Previous iterations built features sequentially without re-verifying previous phases. Regressions were discovered late.

**Decision:** Every milestone includes an E2E verification gate. New capabilities are verified (small scale first, then scaled up) and all previous milestone capabilities are re-verified. Milestone checkpoint documents record verification evidence.

**Consequences:** Higher confidence in system integrity at each stage. Additional verification effort per milestone. Forces clean, repeatable deployment.

### DEC-004: Multi-level documentation structure
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** The initial approach had flat docs/ with no clear separation between architecture, operations, and user-facing content. Finding the right document required knowing the project well.

**Decision:** Six documentation tiers: Architecture (ADRs, system overview), Technical (component deep dives), Functional (use cases, requirements), User Experience (personas, journeys), Operations (prerequisites, runbooks, getting started), Milestones (plans, checkpoints). Conventions in `doc-standards.md`.

**Consequences:** Clear navigation for different audiences. Template overhead for new docs. Technical writer skill automates enforcement.

### DEC-005: Namespace prefix convention (`data-strat-`)
**Date:** 2026-05-23
**Milestone:** M0
**Status:** Decided

**Context:** Multiple namespaces will be created on the cluster as the project grows (core workloads, MLflow, Marquez, connectors, etc.). It needs to be immediately obvious which namespaces belong to this project when looking at `oc get namespaces`.

**Decision:** All OpenShift namespaces created by this project must be prefixed with `data-strat-`. The primary namespace is `data-strat-poc`. Additional namespaces (if needed for isolation) follow the pattern `data-strat-<component>` (e.g. `data-strat-mlflow`, `data-strat-lineage`).

**Consequences:** Easy identification of project resources at a glance. Simplifies cleanup (`oc get ns | grep data-strat-`). Consistent with the repo name. All manifests, getting-started docs, runbooks, and scripts must use this prefix — never hardcode a namespace without it.

### DEC-006: Git tagging convention for milestones and phases
**Date:** 2026-05-25
**Milestone:** M1
**Status:** Decided

**Context:** The project spans multiple repos (`data-strat-poc` for docs/manifests and `pipelines-components` fork for component code). When a milestone or phase is verified, we need a way to recreate that exact state across all repos — for rollback, comparison, or onboarding.

**Decision:** Use lightweight git tags with the pattern `m<N>-p<P>` (e.g., `m1-p0`, `m1-p2`, `m1-complete`) applied simultaneously to all project repos at each verified checkpoint. Tags are permanent and never moved.

**Consequences:** Any checkpoint can be recreated by checking out the same tag across all repos. Enables rollback after broken changes. Makes it easy to diff between phases (`git diff m1-p1..m1-p2`). Requires discipline to tag all repos together — a missed tag on one repo breaks the contract.

### DEC-007: Data-chain-only ingest pipeline for M1–M3
**Date:** 2026-05-25
**Milestone:** M1
**Status:** Decided

**Context:** The full `rag_multistep_pipeline` includes both a data chain (parse → ingest) and a model chain (download LLM → deploy). For M1–M3 the focus is on the data pipeline — parsing, chunking, embedding, and vector storage. Model deployment (LLM + optional embedding service) is only needed from M4 onward when the query layer lands. Running unnecessary model deployment steps wastes GPU resources and adds failure modes during early milestones.

**Decision:** Split into two pipeline files in `pipelines-components`:
- `ingest_pipeline.py` — data-chain-only: `parse_and_chunk` → `ingest_to_milvus`. No model deployment parameters, no If/Else branching for embedding deployment. Used for M1–M3.
- `pipeline.py` — full multi-step pipeline with both chains. Retained for M4+ when LLM deployment is needed.

Both pipelines are exported from the same package. The compiled YAML for the ingest pipeline is `rag_ingest_pipeline.yaml`.

**Consequences:** Simpler pipeline for early milestones — fewer parameters, no GPU requirements, faster runs. The full pipeline remains available and tested. When M4 starts, the team switches back to `rag_multistep_pipeline` (or extends the ingest pipeline with query steps).

### DEC-008: Multi-collection architecture for Scenario B
**Date:** 2026-05-25
**Milestone:** M2 (captured for M3 execution)
**Status:** Decided

**Context:** Scenario B specifies three document collections for the P&C underwriting knowledge assistant, each serving different personas and query patterns. M1-M2 used a single `underwriting_guidelines` collection with all 11 test PDFs mixed together. The compliance review agent (UC-003) requires multi-hop retrieval across all three collections.

**Decision:** Run the ingest pipeline **separately per collection** with different parameters:

| Pipeline Run | Collection | Input Documents | Category |
|-------------|------------|-----------------|----------|
| Run 1 | `underwriting_guidelines` | Company guidelines by LOB | Per-LOB (commercial_property, workers_comp, etc.) |
| Run 2 | `iso_forms` | ISO/ACORD standard forms | Per form series |
| Run 3 | `regulatory_bulletins` | State DOI bulletins, NAIC guidance | Per jurisdiction |

Each run gets its own `pipeline_run_id`, lineage graph, and MLflow experiment run. The collections share the same schema (ADR-002) but contain different document types.

At M3, connectors route documents from different sources to the appropriate collection. At M4, OGX queries across all three collections for the compliance review agent.

**Consequences:** The pipeline already supports this -- `collection_name` is a parameter. No code changes needed. M3 must implement: (a) corpus organisation by collection, (b) per-collection pipeline runs, (c) per-document metadata from manifests (PG-020). The compliance review agent (M5) depends on all three collections being populated.

### DEC-009: Two-layer lineage — Marquez for ingest, MLflow for query
**Date:** 2026-05-27
**Milestone:** M4
**Status:** Decided

**Context:** The Data Strategy Scenario B proposal (Pillar 4, OpenLineage event model) frames query-time lineage as an OpenLineage Event 3 emitted to Marquez — a `rag_query` job with Milvus as input dataset and the response as output. While the proposal correctly identifies that "neither the Responses API nor Milvus emits OpenLineage events natively" (Gap), the proposed resolution ("custom OpenLineage facets for RAG query events") implies query lineage should flow to Marquez alongside ingest lineage.

This doesn't work. Marquez models **datasets and jobs** (batch/pipeline world), not individual requests. Every query would be a run of the `rag_query` job against the same Milvus collection — Marquez would show "the collection was queried" but not which specific chunks were retrieved for which specific question. To answer the two core provenance questions:

1. **"Which chunks/documents answered this question?"** — requires per-request granularity (this query → these 5 chunks → these doc_ids). Marquez doesn't model at request level.
2. **"Which questions were answered using this document?"** — requires reverse lookup across all queries where a given `doc_id` appeared in retrieved chunks. Marquez has no concept of searching across job runs by facet values.

MLflow traces are purpose-built for this: each trace is one request with exact chunks, scores, doc_ids, and pipeline_run_ids as span attributes. MLflow's trace search API supports filtering by custom attributes for the reverse lookup.

**Decision:** Query-time lineage goes to MLflow as traces, not to Marquez as OpenLineage events.

- **Marquez (ingest-time):** OpenLineage events for the data pipeline. Answers "how did this data get into Milvus?" Dataset-level, batch-oriented. Already built in M2/M3. No changes in M4.
- **MLflow (query-time):** Traces for each RAG query. Answers "what happened when this question was asked?" Request-level, span-oriented. New in M4.
- **Bridge:** `pipeline_run_id` on every Milvus vector. Retrieved at query time, attached to MLflow trace spans, used to join back to the Marquez ingest graph.

This is a deliberate divergence from the Data Strategy proposal's Pillar 4 framing. The proposal's gap identification is correct (no OOTB query lineage), but its implied resolution (OL events to Marquez) is the wrong tool for request-level provenance. The two-layer split is the architecturally sound approach.

**Marquez graph completion:** To close the visual gap in Marquez (ingest pipeline produces Milvus collections but nothing consumes them), emit a lightweight application-level OL event per consuming application. Each application (e.g., `underwriter_chat`, `compliance_review_agent`) is modelled as an OL job with Milvus collections as inputs. This is emitted once (on startup or first query), not per-request. It completes the Marquez graph from source documents through ingest to application consumption, while keeping per-query detail in MLflow traces.

**Consequences:** The Data Strategy proposal should be updated to reflect a two-layer lineage architecture for RAG scenarios: OpenLineage/Marquez for pipeline-time and application-level consumption (batch, dataset-level), MLflow traces for query-time (request-level, per-question provenance). This is a gap in the proposal — it describes Pillar 4 primarily in pipeline/OpenLineage terms and doesn't account for the request-level observability that RAG query provenance requires. The POC proves the correct pattern.

### DEC-010: LangGraph + MLflow for M4 deterministic RAG; OGX reserved for M5 agentic RAG
**Date:** 2026-05-27
**Milestone:** M4
**Status:** Decided (amends ADR-003 scope)

**Context:** ADR-003 reserved OGX Responses API for the query path. The question for M4 is whether to use OGX for deterministic RAG (Workflow A) or defer OGX to M5's agentic RAG (Workflow B) and use a more observable stack for M4.

Three options evaluated:

| Option | Stack | Tracing | Pros | Cons |
|--------|-------|---------|------|------|
| A: OGX Responses API | OGX orchestrates retrieval + generation via custom function tools | No native tracing; must wrap OGX calls in custom MLflow spans | Proves OGX Pillar 3 value; aligns with Scenario B spec | Black box for observability; Dev Preview; query audit requires significant custom instrumentation |
| B: LangGraph + MCP + MLflow | LangGraph agent, MCP server for Milvus search, Chainlit UI | `mlflow.langchain.autolog()` gives full span tree automatically | Full observability OOTB; proven pattern (demo_mlflow_agent_tracing); inner/outer loop eval framework; Chainlit provides chat UI | Doesn't prove OGX query-path value in M4 |
| C: Hybrid (OGX + MLflow wrapper) | OGX for retrieval + generation, MLflow spans wrapping OGX calls | Partial — outer spans only, OGX internals still opaque | Gets both OGX proof point and some MLflow tracing | Most complex; double abstraction; fights OGX's orchestration model |

**Decision:** Option B for M4. LangGraph + MCP + MLflow autolog + Chainlit for deterministic RAG. OGX reserved for M5 agentic RAG.

- **M4 (Deterministic RAG / Workflow A):** LangGraph agent with an MCP tool server wrapping Milvus search (pymilvus). `mlflow.langchain.autolog()` captures the full trace tree (LLM reasoning, tool calls with retrieved chunk IDs/doc_ids/pipeline_run_ids, generation). Chainlit provides the chat UI. Queries `underwriting_guidelines` collection.
- **M5 (Agentic RAG / Workflow B):** Evaluate OGX Responses API for multi-hop retrieval across all 3 collections. OGX's multi-tool orchestration and agent loop are its differentiator — agentic RAG is where that value is clearest. Compare observability with M4's LangGraph approach.

**Rationale:** The Scenario B spec's value isn't in which specific query orchestrator we use — it's in proving the five-pillar architecture works for enterprise RAG. MLflow autolog tracing gives a dramatically better Pillar 4 (lineage & governance) story than OGX would, because the full span tree — including which chunks were retrieved and which doc_ids were cited — is captured automatically. OGX's strength is agent orchestration (multi-tool, multi-hop), which is M5's Workflow B, not M4's single-collection deterministic retrieval.

ADR-003's decision ("reserve OGX for the query path") remains valid in spirit — OGX is still the query-path technology to evaluate. The amendment is *when*: M5 (agentic, where OGX's value is highest) rather than M4 (deterministic, where observability matters most).

**Consequences:**
- M4 depends on LangGraph, LangChain MCP adapters, MLflow tracing, Chainlit — not OGX. OGX deployment deferred to M5.
- Embedding model alignment still critical: query-time embedding must match ingest-time (Granite Embedding 125M).
- LLM serving required for M4 (generation). Deploy Granite or equivalent via vLLM/KServe.
- The demo_mlflow_agent_tracing repo serves as a reference architecture for the M4 implementation.
- M5 becomes the OGX evaluation milestone — direct comparison of LangGraph (M4) vs OGX (M5) observability and developer experience.

### DEC-011: Registry UI as unified provenance portal
**Date:** 2026-05-27
**Milestone:** M4
**Status:** Decided

**Context:** Post-M3, answering provenance questions requires navigating four systems: Registry (document identity, collections), Marquez (ingest lineage graph), MLflow (query traces), and Milvus (vector-level queries via pymilvus). Each has its own interface, authentication, and mental model. Simple questions like "what documents answered this query?" or "what apps use this document?" require a user to know which system to go to and how to join the results across systems.

The UX assessment (Gap 1) identified this as the highest-impact gap. Three options were evaluated:

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A: Extend Registry UI | Registry becomes the provenance portal, federating MLflow + Marquez + Registry APIs server-side | Lowest incremental effort; Registry already has document identity (the natural entry point); PatternFly UI already deployed | Couples Registry to MLflow/Marquez APIs; needs error handling when backends unavailable |
| B: Dedicated provenance app | Separate service with its own UI federating all backends | Clean separation; could serve multiple projects | Significant build/maintain cost; premature for a PoC |
| C: Status quo (multi-tool) | Users navigate Marquez, MLflow, Registry, and CLI as needed | No additional build | Unusable for non-developers; blocks compliance/audit use case; limits demo impact |

**Decision:** Option A. The Registry UI becomes the single pane of glass for all provenance questions.

The Registry backend gains federation endpoints that call MLflow API (trace search, trace detail), Marquez API (lineage graph, job runs), and its own database. The frontend gains three views:

- **Document Provenance:** from any document → collections, consuming apps, recent queries that cited it, ingest pipeline runs, source URL
- **Query Trace Detail:** from any query → question, answer, retrieved chunks (with text), source documents (linked), pipeline run (linked to Marquez)
- **Query Trace List:** recent queries across all apps, filterable by collection, doc_id, date range

Users never need to open Marquez, MLflow, or a terminal. Deep links to those systems are available for engineers who want the underlying detail.

**Consequences:** The Registry evolves from a document metadata store to a provenance portal. Its backend now depends on MLflow and Marquez APIs being reachable. Need graceful degradation when backends are down (show what's available, flag what's unavailable). M5 adds Collection Health, App Overview, and Impact Analysis views when more apps exist.

### DEC-012: OGX Trace Correlation Strategy
**Date:** 2026-05-28
**Milestone:** M5
**Status:** Accepted (verified — autolog captures tool call rounds as child spans)

**Context:** M5 builds the agentic compliance review agent on OGX Responses API with server-side Tool Runtime. OGX owns the agent loop: the client sends one request and gets a final response. Tools (MCP servers) are called by OGX during the loop, not by our code. This creates a trace correlation problem — how do we build a single MLflow trace that captures the client request, OGX's tool calls, and the tool results?

Phase 0b investigated four questions:

| # | Question | Finding |
|---|----------|---------|
| Q1 | Does the Responses API response include tool call details? | **Yes** — response contains `function_call` and `function_call_output` items with tool names, arguments, and results |
| Q2 | Does `mlflow.openai.autolog()` capture tool call rounds? | **Likely yes, pending verification** — Responses API is OpenAI-compatible; autolog should parse tool call items into child spans |
| Q3 | Does OGX propagate trace context to MCP tool calls? | **No** — OGX has `forward_headers` for auth but no OpenTelemetry `traceparent` propagation to MCP servers |
| Q4 | What protocol does OGX use for custom tools? | **MCP via SSE** — MCP servers registered in run.yaml or programmatically; OGX connects via SSE, discovers tools at startup |

**Decision:** Client-side trace reconstruction from the Responses API response.

Since Q1=Yes (response includes full tool call details), the client can reconstruct the entire agent interaction from the response output items. The strategy:

1. **Client-side:** `mlflow.openai.autolog()` captures the Responses API call. If autolog parses tool call rounds into child spans (Q2), we get the full trace automatically. If not, we parse `function_call` and `function_call_output` items from the response and create manual child spans.

2. **Trace enrichment:** After the response completes, extract search metadata from `function_call_output` items (which contain the MCP tool results with doc_ids, pipeline_run_ids, chunks). Tag the trace with the contract schema: `doc_ids_cited`, `pipeline_run_ids`, `collection_queried`, `chunks_detail`, `answer_preview`, `chunks_retrieved_count`.

3. **Tool service spans are not needed for core tracing.** Since the client gets the full tool call details in the response, the tool service (MCP server) doesn't need to emit its own MLflow spans for trace completeness. The MCP server is a pure compute service — OGX calls it, gets results, includes them in the response. All provenance data flows through the client.

This is analogous to how M4's `mlflow.langchain.autolog()` captures LangGraph tool calls without the MCP server needing its own MLflow instrumentation.

**Consequences:** Simpler architecture — tool service stays clean (no MLflow dependency). All tracing happens client-side. Trade-off: if OGX encounters errors during tool calls that aren't reflected in the response, the client won't see them. Acceptable for POC; revisit if tool reliability is an issue.

### DEC-013: Model Selection — Hermes-3-Llama-3.1-70B-FP8
**Date:** 2026-05-28
**Milestone:** M5
**Status:** Accepted

**Context:** M4/M5 require an LLM that produces structured `tool_calls` responses (JSON function calls) when given tool definitions and `tool_choice=auto`. The initial model — IBM Granite 3.3 8B Instruct — was tested but generated conversational text describing tool use ("I will search the database for...") rather than actual function call JSON. This is a fundamental blocker for both deterministic and agentic RAG workflows.

Options evaluated:

| Model | Size | Tool Calling | Access | Storage | GPU |
|-------|------|-------------|--------|---------|-----|
| Granite 3.3 8B Instruct | 16GB | Broken in vLLM | Open | Fits emptyDir | 1x A100 |
| Llama 3.1 70B Instruct | 140GB | Native (llama3_json parser) | Gated (HF token) | Too large for emptyDir or PVC on IBM VPC | 2x A100 |
| Hermes-3-Llama-3.1-70B-FP8 | ~70GB | Native (hermes parser) | Ungated | Fits emptyDir (80Gi) | 1x A100-80GB |
| Llama 3.1 70B AWQ | ~35GB | Native | Gated | Fits emptyDir | 1x A100 |

**Decision:** Use `NousResearch/Hermes-3-Llama-3.1-70B-FP8` for the POC.

Rationale:
1. **Ungated** — no HuggingFace token required, simplifying deployment
2. **FP8 quantized** — fits in ~70GB ephemeral storage on a single A100-80GB GPU
3. **Native tool calling** — vLLM's `--tool-call-parser=hermes` produces correct structured function calls
4. **Quality** — 70B parameter model provides high-quality synthesis and multi-hop reasoning
5. **Raw Deployment** — deployed as a Kubernetes Deployment (not KServe InferenceService) to bypass KServe storage initializer limitations with large models

**Consequences:** The system now depends on A100-80GB GPU availability. Model download takes 5-10 minutes on first pod start. The raw Deployment approach means no KServe autoscaling or canary features — acceptable for POC. Granite 8B remains an option for low-resource environments if tool calling support improves.
