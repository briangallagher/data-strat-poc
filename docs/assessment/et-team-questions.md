# Questions for the ET (Waterford) Team — Lineage Architecture

**Date:** 2026-05-28
**Context:** Our Data Strategy POC v2 forked and adapted the ET team's lineage work into [`rhoai-lineage`](https://github.com/bgallagher-rh/rhoai-lineage). We've since built a full RAG pipeline on RHOAI with end-to-end lineage from source documents through ingest to query-time answer provenance. Several architectural questions came up during the build that we'd love the ET team's perspective on.

**Goal:** Compare approaches, identify gaps, and explore collaboration on a shared lineage library for RHOAI.

---

## 1. Understanding Your Approach

We restructured the original `openlineage-oai` and `openlineage-sdk` code into `rhoai-lineage` — a single installable package with KFP, MLflow, and manual SDK adapters, plus naming convention helpers. Before we diverge further, we want to make sure we understand the original intent.

**Q1.1 — Original scope of the MLflow-Marquez bridge.**
The `OpenLineageTrackingStore` intercepts MLflow tracking operations (create_run, log_param, log_metric, set_tag, log_input, update_run_info) and emits corresponding OL events to Marquez. Was this designed primarily for **ML training runs** (the classic experiment tracking use case), or did you envision it covering inference/serving scenarios too?

**Q1.2 — Bridge evolution.**
The bridge wraps a delegate store and has a clean adapter pattern (`ToolAdapter` ABC, `MLflowAdapter`). Was the plan to add more adapters beyond MLflow and KFP? For example, a Ray adapter, or a generic "notebook" adapter for ad-hoc work?

**Q1.3 — Relationship to MLflow's own OpenLineage integration.**
MLflow has had an experimental `mlflow.openlineage` integration since ~2.15. Did you evaluate that? If so, what was missing that led to building the custom tracking store wrapper instead?

**Q1.4 — Dataset Registry integration.**
The `OLClient` in `sdk/client.py` has a `dataset()` method that resolves datasets from a registry by name. Was there a Dataset Registry service behind this, or was it aspirational? We built a [Document Registry](../../src/registry/) with provenance federation — curious if you had similar plans.

---

## 2. Request-Time Tracking

This is the critical architectural question we ran into and the one we'd most value your perspective on.

### What we found

When we moved from ingest-time lineage (M1–M3) to query-time lineage (M4), we hit a fundamental mismatch between what Marquez models and what RAG query provenance requires:

- **Marquez** models **datasets and jobs** — it's a batch/pipeline world. An OL event says "job X consumed dataset A and produced dataset B."
- **MLflow traces** model **per-request execution** — each trace is one query with exact spans, inputs, outputs, retrieved chunks, similarity scores, and cited doc_ids.

The Data Strategy proposal's "Event 3: Query/Retrieval" (an OL event to Marquez with the query as a `rag_query` job) doesn't work for per-request provenance. Every query would be a new run of the same job against the same Milvus collection. Marquez would show "the collection was queried" — but not *which specific chunks were retrieved for which specific question*.

The two core provenance questions we needed to answer:

1. **"Which chunks/documents answered this question?"** — requires per-request granularity. Marquez doesn't model at request level.
2. **"Which questions were answered using this document?"** — requires reverse lookup across query traces by doc_id. Marquez has no concept of searching across job runs by facet values.

### What we built (DEC-009)

A **two-layer lineage architecture**:

| Layer | Technology | Scope | Granularity |
|-------|-----------|-------|-------------|
| Ingest lineage | Marquez (OpenLineage events) | Pipeline-time: how data got into Milvus | Dataset-level, batch |
| Query lineage | MLflow traces (`mlflow.langchain.autolog()`) | Query-time: what happened when a question was asked | Request-level, per-span |
| Bridge | `pipeline_run_id` on every Milvus vector | Links query traces back to ingest lineage | Per-vector metadata |
| Graph completion | Application-level OL event (`src/query/lineage.py`) | Registers consuming apps in Marquez | One event per app, not per query |

The application-level OL emission (`emit_application_registration()`) emits a single COMPLETE event on startup that registers `underwriter_chat` as a downstream consumer of `milvus://underwriting_guidelines`. This completes the Marquez graph without flooding it with per-query events.

### Questions

**Q2.1 — Did you encounter this same limitation?**
When the ET team explored lineage beyond training pipelines — inference, serving, or any per-request scenario — did you run into the same tension between Marquez's job/dataset model and request-level granularity?

**Q2.2 — MLflow traces vs MLflow runs.**
The `OpenLineageTrackingStore` intercepts MLflow *tracking store* operations (runs, params, metrics, tags). It doesn't intercept MLflow *trace* operations (the GenAI tracing API: `mlflow.start_span()`, `mlflow.langchain.autolog()`, etc.). Did you consider extending the bridge to intercept trace operations? Or was the tracing API not yet available when you built this?

**Q2.3 — Two-layer split.**
Does the two-layer architecture (Marquez for batch/pipeline, MLflow traces for request-level) make sense to you? Or do you see a path to making Marquez work for per-request lineage (e.g., custom facets, different modelling)?

**Q2.4 — OpenLineage's suitability for request-level events.**
More broadly — do you think OpenLineage (the spec, not just Marquez) is the right model for request-level lineage events? The spec is fundamentally job-and-dataset-oriented. We've seen discussions in the OL community about "streaming lineage" but nothing concrete for per-request RAG provenance.

**Q2.5 — Application-level OL emission.**
We emit a one-time OL event per consuming application (not per query) to complete the Marquez graph. The app (`underwriter_chat`) becomes a job node with Milvus collections as inputs. Did you consider this pattern? Does it feel right, or would you model it differently?

---

## 3. Technical Details

### MLflow Bridge Internals

**Q3.1 — Workspace header injection.**
Our POC uses a `http_request` monkeypatch to inject the `X-Mlflow-Workspace` header required by the RHOAI MLflow Operator (`src/query/mlflow_config.py`, `configure_mlflow()`). We noticed the ET bridge's `OpenLineageTrackingStore` wraps the delegate store directly — does it work with the RHOAI MLflow Operator's REST store out of the box? Or did you need a similar header injection approach?

**Q3.2 — Delegate store creation.**
The bridge's `_create_delegate_store()` manually dispatches on URI scheme (http → RestStore, postgresql → SqlAlchemyStore, etc.). In your experience, did this cover all the store types you needed? The RHOAI MLflow Operator uses a REST store behind a route — any gotchas with TLS or auth when wrapping it?

**Q3.3 — Thread safety.**
The `RunState` accumulation uses a `threading.Lock` — was this needed because MLflow's client can log from multiple threads? Did you see any concurrency issues in practice?

### Custom Facets

**Q3.4 — Facet standardisation.**
The bridge emits several custom facets:
- `mlflow_run` (experiment ID, name, params, metrics, tags)
- `mlflow_dataset` (source, source type, digest, context)
- `mlflow_model` (artifact path, flavors, signature)
- `parent` run facet linking MLflow runs to KFP pipeline runs

Are these standardised across the ET team's work, or POC-specific? Have you proposed any of these to the OpenLineage community as standard ML facets?

**Q3.5 — Parent run facet reliability.**
The `_build_parent_run_facet()` reads `KFP_RUN_ID` and `KFP_PIPELINE_NAME` from env vars to link MLflow runs to KFP runs. In our experience, these env vars aren't always reliably set in KFP v2 (depends on how the DSPA injects them). Did you find this worked consistently? We ended up using `pipeline_run_id` as an explicit parameter passed through the pipeline.

### Naming & Identity

**Q3.6 — Dataset URI conventions.**
We adopted the `naming.py` helpers (DEC-014) and extended them for our domain (S3, Milvus, Feast, MLflow model, Postgres). The `normalise_namespace()` function (e.g., `postgresql://` → `postgres://`) was critical for getting Marquez graph connections to work. Were there other normalisation rules you discovered that we should add?

**Q3.7 — `URIDatasetSource`.**
The custom `URIDatasetSource` in `mlflow/dataset_source.py` lets you pass arbitrary URIs to `mlflow.data.from_pandas()` for lineage. Clever pattern — did you find any issues with MLflow's Dataset API when using custom sources? We haven't adopted this yet but it would clean up our ingest pipeline's MLflow logging.

---

## 4. Collaboration Opportunities

**Q4.1 — Extending `rhoai-lineage` for query-time trace emission.**
The library currently covers KFP components (ingest-time) and MLflow runs (training-time). Could it be extended to support query-time lineage? For example, a `QueryAdapter` that wraps MLflow's tracing API to automatically enrich traces with provenance metadata (doc_ids, pipeline_run_ids, collection names) and optionally emit the application-level OL event to Marquez.

**Q4.2 — Application-level OL emission pattern.**
Our `src/query/lineage.py` (`emit_application_registration()`) is a standalone function — not integrated into `rhoai-lineage`. It probably should be. Would the ET team be interested in contributing this pattern back into the library? The idea: any RHOAI application (chat bot, agent, notebook) can register itself as a Marquez consumer with one call.

**Q4.3 — Registry provenance federation.**
Our Registry backend (`src/registry/provenance.py`) federates across MLflow, Marquez, and its own database to answer provenance questions. The endpoints:
- `GET /provenance/document/{doc_id}` — "everything about this document"
- `GET /provenance/trace/{trace_id}` — "everything about this query"
- `GET /provenance/collection/{name}` — "everything about this collection"

Could this federation pattern be generalised into a standalone service that any RHOAI deployment could use? Or is it too tightly coupled to our specific schema?

**Q4.4 — Shared `rhoai-lineage` ownership.**
We're maintaining a fork. If the library is useful to others beyond our POC, would the ET team be interested in co-maintaining it? Or is the original `openlineage-oai` still actively developed?

---

## 5. Your Opinion on Our Approach

Here's a brief summary of what we built, and we'd genuinely like your take on whether the architecture holds up.

### Our system (Data Strategy POC v2)

An enterprise RAG pipeline for P&C insurance underwriting on RHOAI. Five pillars:

1. **Ingest pipeline** (KFP v2): parse PDFs → chunk → embed (Granite Embedding 125M) → Milvus. Three collections (underwriting guidelines, ISO forms, regulatory bulletins).
2. **Lineage** (Marquez + `rhoai-lineage`): every pipeline step emits OL events. Full graph from source documents through S3 to Milvus collections.
3. **Document Registry** (FastAPI + PostgreSQL + PatternFly UI): document identity, collection membership, source metadata.
4. **Query layer** (LangGraph + MCP + Chainlit): deterministic RAG with `mlflow.langchain.autolog()` for full trace capture. Application-level OL for Marquez graph completion.
5. **Provenance portal** (Registry UI): federated views — document provenance, query trace detail, trace list — bridging MLflow traces and Marquez ingest lineage via `pipeline_run_id`.

The key architectural decision (DEC-009) is the two-layer split: Marquez for pipeline-time lineage (batch, dataset-level), MLflow traces for query-time provenance (request-level, per-question).

### Questions

**Q5.1 — Does the two-layer architecture make sense?**
Given your experience building the MLflow-Marquez bridge, does the split between Marquez (ingest) and MLflow traces (query) feel like the right architecture? Or would you push harder to keep everything in Marquez?

**Q5.2 — What would you do differently?**
With hindsight, if you were building this system from scratch today, what would you change about the lineage approach? Anything you tried that didn't work, or paths you explored that we should learn from?

**Q5.3 — Anything we're missing?**
We're focused on answer provenance (which documents answered this question) and document impact (which queries used this document). Are there other lineage questions in the enterprise ML/RAG space that we should be thinking about?

**Q5.4 — Production concerns.**
The `OpenLineageTrackingStore` is impressively careful about not breaking ML training — emission failures are warnings, not exceptions, and the lock-based state accumulation is robust. What production issues did you encounter that shaped these design choices? We want to make sure `rhoai-lineage` inherits that production-mindedness.

---

## Next Steps

We'd love to set up a call to walk through both codebases and discuss these questions. We can demo:
- The full ingest → lineage → query → provenance chain running on RHOAI
- The Registry provenance portal federating across MLflow, Marquez, and Registry
- The `rhoai-lineage` library in action (KFP context manager, manual SDK, naming helpers)

Let us know what works for your team's schedule.
