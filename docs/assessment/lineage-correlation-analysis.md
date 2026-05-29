# Lineage Correlation: Three-Perspective Analysis

**Date:** 2026-05-29
**Purpose:** Frame the cross-system correlation challenge for today's discussion between the Data Strategy team, the POC team (Brian), and the ET team (lineage POC builders).
**Status:** Working document for meeting prep

---

## 1. How the Data Strategy Frames the Lineage Challenge

### The Proposed Model

The Data Strategy proposal (Scenario B, Pillar 4) frames all lineage as OpenLineage events flowing to Marquez. It defines three events covering the full lifecycle:

| Event | Scope | OL Job | Input Dataset | Output Dataset |
|-------|-------|--------|---------------|----------------|
| Event 1: Document Ingestion | Source → staging | `document_ingestion_pipeline` | `sharepoint://policy-library/` | `s3://staging/documents/batch_*` |
| Event 2: Document Processing | Staging → vectors | `docling_processing_pipeline` | `s3://staging/documents/batch_*` | `milvus://underwriting_guidelines/` |
| Event 3: Query/Retrieval | Vectors → answer | `rag_query` | `milvus://underwriting_guidelines/` | `response_text` |

The proposal explicitly acknowledges Event 3 as a gap:

> "Event 3 (query-level lineage) requires custom instrumentation at the application level; neither the Responses API nor Milvus emits OpenLineage events natively."

The proposed resolution is "custom OpenLineage facets for RAG query events" — implying query lineage should flow to Marquez alongside ingest lineage.

### Specific Correlation Challenges Identified

The proposal's feasibility analysis (`pillar-4-lineage-governance.md`) is sharper about the difficulty:

1. **Zero OpenLineage emitters exist in RHOAI** — "No RHOAI component currently emits OpenLineage events; adoption requires upstream work in every participating component"
2. **Cross-component identity correlation** — "how to link a Feast feature set to an MLflow run to a DSP pipeline to a Model Registry entry has no defined key scheme"
3. **No lineage aggregation backend shipped** — Marquez would be a new component requiring productization

The feasibility document rates this pillar as **"indeterminate"** and calls for splitting it into three workstreams: lineage collection, lineage aggregation, and governance policy enforcement.

### Where the Proposal Acknowledges Gaps

1. No OOTB OpenLineage integration with RayData/Docling — "must be instrumented manually"
2. Marquez not integrated into RHOAI — "must deploy and manage separately"
3. No query/response audit logging — neither Responses API nor Milvus produces OL events
4. No document lifecycle governance at platform level
5. No lineage UI in RHOAI for RAG workflows

### What the Proposal Does NOT Address

- **Per-request granularity**: The `rag_query` event implies one OL run per query, but doesn't address how Marquez would handle thousands of runs of the same job against the same dataset — or how you'd search across them
- **Reverse lookup**: "Which questions were answered using this document?" requires searching across all query runs by facet values — Marquez has no such capability
- **Application-level consumption**: The lineage graph ends at Milvus. No concept of downstream consuming applications appearing in the graph
- **The bridge key**: No explicit `pipeline_run_id` or equivalent mechanism to join ingest-time lineage to query-time provenance

---

## 2. How the ET Team Solved It

### Architecture Overview

The ET team (Waterford) built `openlineage-oai` — restructured by us into `rhoai-lineage`. It provides three adapters for emitting OpenLineage events:

| Adapter | Mechanism | Scope |
|---------|-----------|-------|
| **KFP context manager** (`kfp_lineage`) | Wraps KFP component code; emits START/COMPLETE/FAIL per step | Pipeline-time ingest lineage |
| **MLflow tracking store** (`OpenLineageTrackingStore`) | Intercepts all MLflow API calls; emits OL events as side-effects | Training-time experiment lineage |
| **Manual SDK** (`OLClient`) | Fire-and-forget or tracked lifecycle events | Ad-hoc / any-time lineage |

### The Parent Run Facet — How MLflow Links to KFP

The `_build_parent_run_facet()` method in the tracking store reads environment variables to correlate:

```python
run_id = os.environ.get("OPENLINEAGE_PARENT_RUN_ID") or os.environ.get("KFP_RUN_ID", "")
job_name = os.environ.get("OPENLINEAGE_PARENT_JOB_NAME") or os.environ.get("KFP_PIPELINE_NAME", "")
```

This creates a ParentRunFacet in the OL event linking the MLflow run (child) to the KFP pipeline run (parent). The hierarchy in Marquez becomes: `Pipeline Run → Component Step → MLflow Experiment Run`.

Similarly, `kfp/facets.py` has `build_parent_run_facet()` that reads `KFP_RUN_ID` and `KFP_PIPELINE_NAME` to link individual KFP component runs to the pipeline run.

The KFP context manager also propagates context downward:
```python
os.environ["OPENLINEAGE_PARENT_RUN_ID"] = self._run_id
os.environ["OPENLINEAGE_PARENT_JOB_NAME"] = self._job_name
```

This means if an MLflow run starts *inside* a KFP component (common for training steps), the tracking store picks up the parent context and emits a linked event.

### The Tracking Store Bridge — What It Actually Correlates

The `OpenLineageTrackingStore` intercepts these MLflow operations and emits corresponding OL events:

| MLflow Operation | OL Event | What It Captures |
|-----------------|----------|------------------|
| `create_run()` | START | Experiment ID, run name, parent run facet (KFP link) |
| `log_param()` / `log_metric()` | *(accumulated)* | Params and metrics stored in RunState |
| `set_tag("mlflow.log-model.history")` | Dataset CREATE | Model artifact registered as output dataset with flavors, signature |
| `log_input()` | Dataset CREATE | Input datasets with schema, source URI, context (training/validation) |
| `update_run_info(FINISHED)` | COMPLETE | Full `mlflow_run` facet (all params, metrics, filtered tags), all inputs/outputs |
| `update_run_info(FAILED)` | FAIL | Error message from tags |

The bridge creates a **Marquez node per MLflow run** with the training datasets as inputs and model artifacts as outputs. If the run happened inside a KFP pipeline, the parent facet links it to the pipeline DAG.

### Custom Facets for Correlation

The ET team defined three custom facets:

1. **`mlflow_run`** — experiment ID, name, params, metrics, non-system tags. Allows finding the MLflow UI entry from the Marquez graph.
2. **`mlflow_dataset`** — source URI, source type, digest, context (training/validation). Maps MLflow's dataset API to OL's dataset model.
3. **`mlflow_model`** — artifact path, flavors, signature. Registers model outputs in Marquez.

Plus standard facets: `ParentRunFacet` (KFP link), `SchemaDatasetFacet` (column types), `ErrorMessageRunFacet`.

### What They DID NOT Solve

1. **No query/inference-time lineage at all.** The tracking store intercepts MLflow *runs* (training/experiment operations). It does not intercept MLflow *traces* (the GenAI tracing API: `mlflow.start_span()`, autolog for LangChain/OpenAI). The tracing API didn't exist when this was built.

2. **No per-request provenance.** Everything is batch-oriented — one OL event per pipeline run or training run. The concept of "which chunks answered this specific question" is entirely out of scope.

3. **No application-level registration.** No mechanism to declare a consuming application (chatbot, agent) as a Marquez job that reads from a dataset.

4. **No naming convention enforcement.** Dataset namespaces/names are ad-hoc. The POC added `naming.py` with `normalise_namespace()` specifically because the ET code produced disconnected Marquez graphs when URI schemes didn't match.

5. **Env var reliability.** The parent run facet depends on `KFP_RUN_ID` being set in the pod environment. In KFP v2 on RHOAI, this isn't reliably injected by the DSPA — the POC moved to explicit `pipeline_run_id` parameter passing instead.

---

## 3. How We Solved It in the POC

### The Two-Layer Architecture (DEC-009)

The fundamental insight: **Marquez and MLflow serve different provenance needs at different granularities.**

| Layer | Technology | What It Answers | Granularity | When Emitted |
|-------|-----------|-----------------|-------------|--------------|
| **Pipeline-time** | OpenLineage → Marquez (via `rhoai-lineage`) | "How did this data get into Milvus?" | Dataset-level, batch | During ingest pipeline execution |
| **Query-time** | MLflow traces (`autolog()`) | "What happened when this question was asked?" | Per-request, per-span | During every query |
| **Bridge** | `pipeline_run_id` metadata on Milvus vectors | Joins the two layers | Per-vector | Stamped at ingest, retrieved at query |
| **Graph completion** | Application-level OL event | "What apps consume this data?" | Per-application, one-time | On app startup |

### `pipeline_run_id` as the Bridge Key

Every vector in Milvus carries `pipeline_run_id` as metadata. At query time, the retrieval results include this field. The MLflow trace captures it as a span attribute. This creates the join:

```
MLflow trace span → retrieved chunk → pipeline_run_id → Marquez ingest run → source document
```

A compliance officer asking "where did this answer come from?" follows:
1. Open the query trace (MLflow) — see which chunks were retrieved
2. Each chunk has `pipeline_run_id` — click through to the Marquez ingest graph
3. The Marquez graph shows source → S3 staging → Milvus collection

### Application-Level OL Emission for Graph Completion

Without downstream consumers, the Marquez graph is a dead end — data flows into Milvus and disappears. The POC's `lineage.py` emits a single COMPLETE event per application on startup:

```python
# Models the app as an OL "job" consuming Milvus collections
event = {
    "eventType": "COMPLETE",
    "job": {"namespace": "data-strat-poc", "name": "underwriter_chat"},
    "inputs": [{"namespace": "milvus://...", "name": "underwriting_guidelines"}],
}
```

Both `underwriter_chat` (M4, deterministic) and `compliance_review_agent` (M5, agentic) are registered. The Marquez graph now reads: source → acquire → parse → embed → Milvus → application.

### Client-Side Trace Reconstruction for OGX (DEC-012)

OGX (Responses API) owns the agent loop — it calls MCP tools autonomously. The correlation challenge: OGX doesn't propagate OTel `traceparent` to MCP servers, so there's no distributed trace.

Solution: client-side reconstruction from the response. The Responses API response includes full `function_call` and `function_call_output` items. After the response completes, the client (`query_ogx/app.py`) parses these and enriches the MLflow trace:

```python
tags = {
    "doc_ids_cited": ",".join(sorted(doc_ids)),
    "pipeline_run_ids": ",".join(sorted(pipeline_run_ids)),
    "collection_queried": ",".join(sorted(collections)),
    "chunks_retrieved_count": str(total_chunks),
    "chunks_detail": json.dumps(all_chunks),
}
mlflow.update_current_trace(tags=tags)
```

`mlflow.openai.autolog()` captures the LLM interactions; the enrichment adds the provenance metadata that makes the trace useful for audit.

### What We Found Doesn't Work

1. **Marquez for per-request provenance** — Every query would be a run of the `rag_query` job against the same dataset. Marquez would accumulate thousands of runs with no way to search them by facet values. The UI becomes unusable. The data model is wrong: Marquez models *datasets transforming into other datasets*, not *requests against a dataset*.

2. **OGX for lineage emission** — OGX Vector I/O is a lineage black box. No OL events, no observability into which embedding model was used, no metadata passthrough guarantees. Direct Milvus writes (the upstream `pipelines-components` pattern) give full control over what metadata lands on each vector.

3. **Environment variable propagation for parent run facets** — `KFP_RUN_ID` isn't reliably set in KFP v2 pods on RHOAI. Explicit `pipeline_run_id` parameter passing (through the KFP DAG) is more reliable than environment variable discovery.

4. **Single-system lineage** — Neither Marquez alone nor MLflow alone can answer all provenance questions. The two-layer split is essential because the granularities are fundamentally different (batch/dataset vs request/span).

---

## 4. The Correlation Gap That Remains

### Cross-System Identity — Still Fragile

The `pipeline_run_id` bridge works but is a custom convention, not a platform feature. If anyone builds a pipeline that doesn't stamp `pipeline_run_id` on vectors, the join breaks silently. There's no platform-level enforcement that ingest pipelines must propagate correlation keys.

### Document Lifecycle Across Re-Ingest

When a document is re-processed (new pipeline run), its vectors get a new `pipeline_run_id`. Historical queries that cited the old vectors now point to a pipeline run that produced since-deleted vectors. The Registry tracks document identity (`doc_id` persists across re-ingestion), but the Marquez lineage graph for the old pipeline run becomes an orphan. No system automatically reconciles "this document was re-processed; here's the new lineage."

### OGX Trace Context Propagation

OGX doesn't propagate `traceparent` headers to MCP tool servers (confirmed in M5). This means:
- The MCP server's internal processing (Milvus queries, embedding calls) is invisible to the MLflow trace
- If the MCP server encounters errors not reflected in the response, the client never knows
- True distributed tracing across OGX → MCP → Milvus requires OGX to implement W3C Trace Context propagation

### Inference-Time Model Lineage

None of the three approaches connect the LLM generation step back to the model's training lineage. We know *which model* generated the answer (from the trace), but not *what that model was trained on*. For full audit, a regulator might ask: "The model that generated this answer — what was it trained on, and was that training data appropriate?" This requires joining:
- MLflow trace → model name/version → Model Registry → training run → training data lineage

This chain is theoretically possible but not built in any of the three approaches.

### Marquez Graph Staleness

Application-level OL events are emitted once (on startup). If a collection is dropped, or a new collection is added, the Marquez graph doesn't automatically update. There's no heartbeat or reconciliation mechanism. The graph represents "what was true at last registration" not "what is true now."

### Multi-Collection Query Correlation

The agentic RAG agent (M5) queries multiple collections in a single user request. The MLflow trace captures all tool calls and results, but correlating back through Marquez means following multiple `pipeline_run_id` values to multiple distinct ingest lineage graphs. The "provenance of this answer" becomes a forest, not a tree. No system provides a unified view of multi-collection query provenance as a single coherent lineage.

---

## 5. Discussion Framing for Today's Meeting

### Question 1: Should the Data Strategy Proposal Adopt the Two-Layer Model?

The proposal currently frames all lineage as OpenLineage events to Marquez (Events 1, 2, 3). The POC proved that Event 3 doesn't work as specified — Marquez can't model per-request provenance. The ET team's code also doesn't address query-time at all.

**For the Data Strategy team:** Does it make sense to update Pillar 4 to formally specify a two-layer architecture (Marquez for pipeline-time, MLflow traces for query-time, `pipeline_run_id` as the bridge)? This would be an architectural correction, not a rejection — the five-pillar model still holds, but Pillar 4's implementation is more nuanced than a single lineage backend.

**Concrete decision:** Replace "Event 3: Query/Retrieval" with a specification of the two-layer split and the bridge key requirement.

### Question 2: Who Owns the Correlation Key Contract?

`pipeline_run_id` works as the bridge between ingest-time (Marquez) and query-time (MLflow) lineage. But it's currently a convention maintained in POC code — not a platform-level requirement.

**For ET team:** In your production vision, where does this correlation key get enforced? Should `rhoai-lineage` enforce that all pipeline components stamp a `pipeline_run_id`? Should the DSPA inject it automatically? Should it be part of the OpenLineage facet spec that RHOAI proposes upstream?

**Concrete decision:** Define ownership and enforcement mechanism for the `pipeline_run_id` contract — library-level, platform-level, or spec-level.

### Question 3: What's the Path for OGX Trace Context Propagation?

OGX doesn't propagate W3C Trace Context (`traceparent`) to MCP tool servers. This forces client-side trace reconstruction from the response — which works but loses visibility into tool execution internals. For production audit requirements (State DOI regulatory compliance), is "the response told us what tools were called" sufficient? Or do we need true distributed tracing through the OGX → MCP → Milvus chain?

**For all three teams:** Is this an OGX roadmap item (add `traceparent` propagation to MCP calls)? Or is client-side reconstruction architecturally acceptable for enterprise deployments?

**Concrete decision:** File (or validate existing) requirement for OGX trace context propagation; determine if it's a blocker for production lineage.

### Question 4: Should `rhoai-lineage` Become a Shared Library Across All Three Efforts?

Three pieces of lineage code exist:
- The ET team's original `openlineage-oai` and `openlineage-sdk`
- The POC's fork as `rhoai-lineage` (extended with naming conventions, DEC-014)
- Whatever the Data Strategy team envisions for the canonical RHOAI lineage integration

**For ET team:** Is the original code still actively maintained? Would you co-maintain `rhoai-lineage` if it gained a `QueryAdapter` for MLflow trace enrichment and the application-level registration pattern?

**For the Data Strategy team:** Should the Data Strategy proposal reference a specific library for OpenLineage emission, or keep it technology-neutral?

**Concrete decision:** Single shared library vs. independent implementations; ownership model.

### Question 5: What Does "Production-Grade Lineage" Actually Require Beyond What We've Built?

The POC has end-to-end correlation working across five milestones. The ET team has production-hardened emission (non-blocking, thread-safe, warning-only failures). The Data Strategy proposal identifies the strategic requirements (audit, compliance, impact analysis).

**For all three teams:** Enumerate the top 3 gaps between current state and production:
- Is it auth (Marquez has none — PG-001)?
- Is it scale (thousands of MLflow traces per day)?  
- Is it reconciliation (stale Marquez graphs)?
- Is it governance enforcement (who can query what)?
- Is it the inference-time model lineage chain?

**Concrete decision:** Prioritised gap list for the next phase of work, with owners assigned.

---

## Appendix: Key References

| Source | Location | Relevant Section |
|--------|----------|-----------------|
| Data Strategy Scenario B | `DataStrategy/data-strategy-proposal/scenarios/scenario-b-*/` | Pillar 4 — OpenLineage event model, gap analysis |
| Data Strategy Pillar 4 Feasibility | `DataStrategy/data-strategy-proposal/feasibility/pillar-4-lineage-governance.md` | Cross-component identity, aggregation problem, recommended decomposition |
| ET team tracking store | `rhoai-lineage/src/rhoai_lineage/mlflow/tracking_store.py` | `_build_parent_run_facet()`, `create_run()`, `update_run_info()` |
| ET team KFP adapter | `rhoai-lineage/src/rhoai_lineage/kfp/lineage.py` | `kfp_lineage` context manager, `build_parent_run_facet()` |
| POC DEC-009 | `data-strat-poc/docs/decisions.md` | Two-layer lineage architecture |
| POC DEC-012 | `data-strat-poc/docs/decisions.md` | OGX trace correlation strategy |
| POC ADR-003 | `data-strat-poc/docs/architecture/adrs/ADR-003-ogx-role.md` | Lineage implications of direct Milvus writes |
| POC ADR-004 | `data-strat-poc/docs/architecture/adrs/ADR-004-lineage-architecture.md` | rhoai-lineage as library, bridge OFF, pipeline_run_id as key |
| POC application-level OL | `data-strat-poc/src/query/lineage.py` | `emit_application_registration()` |
| POC OGX trace enrichment | `data-strat-poc/src/query_ogx/app.py` | `_enrich_trace_metadata()` |
| POC feedback to proposal | `data-strat-poc/docs/assessment/data-strategy-feedback.md` | Finding 1 (lineage model), Finding 4 (app-level consumption) |
| POC questions for ET team | `data-strat-poc/docs/assessment/et-team-questions.md` | Section 2 (request-time tracking), Section 4 (collaboration) |
