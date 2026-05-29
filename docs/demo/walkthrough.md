# Data Strategy POC — Walkthrough

> A working enterprise RAG system built against the Data Strategy Scenario B spec.
> P&C underwriting knowledge assistant on RHOAI. Solo build, 7 days, M0–M5.

---

## 1. Context

The Data Strategy proposes five pillars for enterprise data + AI on RHOAI:

| Pillar | Capability | Scenario B Component |
|--------|-----------|---------------------|
| P1 | Data Ingestion & Connectivity | Document connectors, Registry |
| P2 | Compute Engine Strategy | KFP + RayData + Docling |
| P3 | Data Abstraction Layer | Milvus vector search, LangGraph, OGX |
| P4 | Orchestration, Lineage & Governance | Marquez (ingest), MLflow traces (query) |
| P5 | Unified Data & AI Experience | Registry provenance portal, Chainlit |

Scenario B is the **non-Feast proof point** — pure knowledge retrieval, no ML training, no feature store. Two workflows:

- **Workflow A (Deterministic RAG):** Underwriter asks a question → retrieve from one collection → cited answer
- **Workflow B (Agentic Compliance Review):** Compliance officer → agent retrieves across 3 collections → structured report

**What's not in scope:** RBAC / access control (PG-008), production connectors beyond S3 (PG-010), Unity Catalog, incremental processing, credential registry.

> Reference: [Scenario B spec](https://github.com/briangallagher/DataStrategy) — show the architecture diagram, note P1–P5 annotations.

---

## 2. The Document Registry

> **Open:** [Document Registry UI](https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

### Show: Document list

- 20 documents with stable `doc_id` (e.g., `ug-001`, `rb-003`)
- Each has: source URL, content hash, line of business, jurisdiction, effective date, document type
- `doc_id` is persistent — survives pipeline re-runs, source URL changes, collection reassignment

### Show: Register Documents page

- Form: source URL, document type, LOB, jurisdiction, effective date
- This is how new documents enter the system — registered first, then assigned to collections, then processed

### Key point

Milvus vectors are ephemeral — deleted and re-created every pipeline run. Document identity must live somewhere persistent. The Scenario B spec assumed metadata lives in Milvus; it can't.

**Future direction:** This catalog/identity role could be served by Unity Catalog or OpenMetadata. The POC proves the need; the technology is open.

---

## 3. Collections

> **Stay in:** [Document Registry UI](https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

### Show: The three collections

| Collection | Docs | What's in it | Who queries it |
|------------|------|-------------|----------------|
| `underwriting_guidelines` | 10 | Company guidelines by LOB (commercial property, GL, workers comp, etc.) | Underwriters (Workflow A) |
| `iso_forms` | 5 | ISO/ACORD standard forms (CG 00 01, CP 00 10, etc.) | Compliance review (Workflow B) |
| `regulatory_bulletins` | 5 | State DOI bulletins, NAIC guidance | Compliance review (Workflow B) |

**Why three?** Different document types, different personas, different query patterns. An underwriter only needs guidelines. A compliance officer cross-references all three. Separate collections enable targeted retrieval — the agent decides which to search.

### The modelling chain

```
Documents  →  Collection  →  Milvus Collection  →  Application(s)
 (identity)    (curation)     (physical storage)    (consumer)
```

- A **Collection** is a curation decision: "these documents should be queryable together"
- A **Milvus collection** is the physical storage (1:1 with Collection)
- An **Application** (`underwriter_chat`, `compliance_review_agent`) consumes one or more collections
- Documents can belong to multiple collections (many-to-many)

> **Discussion:** Is this the right abstraction? Should Collections be a platform-level concept in the Data Strategy?

---

## 4. The Ingest Pipeline

> **Open:** [KFP Dashboard](https://ds-pipeline-dspa-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

### Show: A completed pipeline run

One pipeline run per collection. Three steps:

```
acquire_documents  →  parse_and_chunk  →  ingest_to_milvus
    │                      │                    │
    ├─ Registry query      ├─ RayData workers   ├─ Granite Embedding 125M
    ├─ S3 fetch            ├─ Docling parsing   ├─ pymilvus writes
    ├─ Manifest write      ├─ Per-doc metadata  ├─ 10-field schema
    └─ OL events → Marquez └─ OL events         └─ OL events
```

- Show the DAG visualisation
- Show run parameters: `collection_name`, `pipeline_run_id`, `marquez_url`
- Show step logs / artifacts

### How OpenLineage works without native RayData/Docling support

RayData and Docling have **no OpenLineage integration**. Emission happens at the **orchestrator level** (KFP component driver), not inside Ray workers or Docling.

The pattern: each KFP component submits its work (e.g., a RayJob for parse_and_chunk), waits for completion, then **retroactively emits** OL events declaring what was consumed and produced:

```python
with kfp_lineage(
    f"parse_and_chunk/{collection_name}",
    inputs=[s3_input_dataset],
    outputs=[s3_output_dataset],
    run_facets={"pipelineRunId": pipeline_run_id},
):
    pass  # work already done — START/COMPLETE fire back-to-back
```

The `kfp_lineage` context manager comes from **`rhoai-lineage`** — this is the key piece we reused from the ET (Waterford) team's work. Docling is represented in the Marquez graph as the parse job node, but Docling itself emits nothing. Ray workers emit nothing. The orchestrator declares the logical datasets (S3 paths, Milvus collections) and the lineage graph is built from those declarations.

### What we reused from the ET team

`rhoai-lineage` is a fork-and-adapt of the ET team's `openlineage-oai` + `openlineage-sdk`:

| Reused | Not reused |
|--------|-----------|
| KFP adapter (`kfp_lineage` context manager) | **Lineage operator** (Go/kubebuilder) — deferred |
| Core emitter (HTTP transport to Marquez) | **AgentCard CRD** — operator-only |
| MLflow tracking store wrapper (`OpenLineageTrackingStore`) | **Dataset registry** — we built our own |
| Naming conventions / URI normalisation | **Pod annotations** (`lineage-enabled`, etc.) |
| SDK client (`OLClient`, `emit_job()`) | **Feast / Spark integrations** — N/A for Scenario B |
| Config (env-based, ConfigMap pattern) | **MLflow bridge always-on** — we keep it OFF by default |

**What we added:** DEC-014 naming helpers (`s3_dataset()`, `milvus_dataset()`), `pipelineRunId` custom run facet for Milvus↔Marquez correlation, single-package structure.

The ET team's **lineage operator** (watches pods for `ai.platform/*` annotations, creates lineage from CRDs) was not needed — the KFP adapter handles pipeline-time emission, and query-time lineage goes to MLflow traces, not through the operator.

### What lands on every Milvus vector

`doc_id`, `pipeline_run_id`, `line_of_business`, `jurisdiction`, `effective_date`, `document_type`, `section_path`, `page_numbers`, chunk text, embedding — 10-field schema (ADR-002).

`pipeline_run_id` is the bridge between the two lineage layers. It connects query-time traces back to the ingest pipeline.

---

## 5. What the Pipeline Produced

### Marquez: ingest lineage graph

> **Open:** [Marquez Web UI](https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

Show the full lineage graph:

```
Source docs → acquire_documents → S3 staging → parse_and_chunk → ingest_to_milvus → Milvus collection
                                                                                          │
                                                                          ┌────────────────┤
                                                                          ▼                ▼
                                                                  underwriter_chat   compliance_review_agent
```

- Source documents as input datasets
- Pipeline steps as jobs
- Milvus collections as output datasets
- **Downstream consumers** as application nodes — these complete the graph

Marquez answers: **"How did this data get into Milvus?"**

### MLflow: pipeline experiment runs

> **Open:** [MLflow UI](https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments)

- Each collection ingest logged as an MLflow run with params and metrics
- Standard experiment tracking — not traces yet (traces come at query time)

---

## 6. Live Query: Deterministic RAG (Workflow A)

> **Open:** Chainlit UI for `underwriter_chat`

**Ask:** *"Does our commercial property form cover flood damage for a property in a high-risk flood zone?"*

- Cited answer referencing `[ug-003]` with section and page
- Tool call visualisation: MCP `milvus_search` → `underwriting_guidelines` collection → retrieved chunks

### Stack

```
User → Chainlit → LangGraph agent → MCP server → pymilvus → Milvus
                       │                              (local embedding)
                       └─ mlflow.langchain.autolog() → MLflow traces
```

**Why LangGraph, not OGX?** For deterministic RAG, `mlflow.langchain.autolog()` captures the full trace tree automatically. OGX has no native tracing — you'd need to build it yourself. OGX's value is agentic orchestration, not single-collection retrieval (DEC-010).

---

## 7. Live Query: Agentic Compliance Review (Workflow B)

> **Open:** [Compliance Review UI](https://compliance-review-ui-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

**Ask:** *"Compare our general liability exclusion language with the ISO CG 00 01 standard. Flag material deviations."*

- Agent makes **multiple tool calls** across `underwriting_guidelines`, `iso_forms`, `regulatory_bulletins`
- Structured compliance review with citations from all three collections

### Stack

```
User → Chainlit → OGX Responses API → MCP server (SSE) → pymilvus → Milvus (3 collections)
                       │                                    (local embedding)
                       ├─ Hermes-3-Llama-3.1-70B-FP8 (vLLM, 1x A100-80GB)
                       └─ mlflow.openai.autolog() → MLflow traces
```

**OGX's role:** Orchestrates the agent loop — client sends one request, OGX autonomously plans tool calls, executes via MCP, synthesizes the answer. This is where OGX adds value.

**Model:** Granite 3.3 8B couldn't produce structured `tool_calls`. Hermes 70B FP8 (ungated, FP8 quantized) provides native tool calling via vLLM `--tool-call-parser=hermes`.

**Trace note:** OGX doesn't propagate trace context to MCP tools. We reconstruct traces client-side from the response — the Responses API includes full tool call details (DEC-012).

---

## 8. Query-Time Tracing

> **Open:** [MLflow UI](https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments)

### Show: A query trace

- Full span tree for the query we just ran
- Workflow A: autolog captures everything (LangGraph → agent → tool call → retrieval → generation)
- Workflow B: autolog captures Responses API call + tool call rounds as child spans
- Trace tags: `doc_ids_cited`, `pipeline_run_ids`, `collection_queried`, `chunks_retrieved_count`, `answer_preview`

### The key point

**Nothing was captured in Marquez for the query.** Marquez knows the collections exist and which apps consume them. But it doesn't know which chunks answered which question. That's MLflow's job.

### Two-layer lineage (DEC-009)

| Layer | Tool | Answers | Granularity |
|-------|------|---------|-------------|
| **Ingest-time** | Marquez (OpenLineage) | How did this data get into Milvus? | Dataset / batch |
| **Query-time** | MLflow traces | What happened when this question was asked? | Per-request / per-span |
| **Bridge** | `pipeline_run_id` | Links the two layers | Per-vector metadata |

The Scenario B spec proposed OL events to Marquez for every query ("Event 3"). This doesn't work — Marquez models datasets and jobs, not individual requests. The two-layer split is the architecturally correct approach.

> **Discussion (ET team):** Did you hit this same limitation? Is there a path to making Marquez work for per-request lineage, or is the split the right answer?

### Solving the correlation problem

The Data Strategy proposal identifies **cross-component identity correlation** as the hardest unsolved problem for end-to-end lineage (Pillar 4 feasibility doc):

> *"How does an MLflow run ID map to a DSP execution ID? How does a Model Registry model version map to the MLflow model that produced it? Today, these mappings are manual (users copy-paste IDs between systems) or non-existent."*

The proposal rated this as **research-grade, not engineering** — "no defined key scheme" across components.

The POC solved this with a single key: **`pipeline_run_id`**.

```
KFP run                →  pipeline_run_id as run parameter
Marquez OL events      →  pipeline_run_id as custom run facet
MLflow experiment run  →  pipeline_run_id as run tag
Every Milvus vector    →  pipeline_run_id as metadata field
MLflow query traces    →  pipeline_run_ids extracted from retrieved chunks
Registry provenance    →  pipeline_run_id joins all views
```

One UUID, generated once per pipeline execution, flows through every system. At query time, the retrieved chunks carry their `pipeline_run_id`, which links the MLflow trace back to the exact Marquez ingest graph and KFP run. The Registry UI uses this to federate across all three systems.

This isn't the full cross-component correlation the proposal envisions (which includes Feast feature sets, Model Registry versions, TrustyAI). But for the RAG scenario, `pipeline_run_id` as the correlation key is sufficient and proven.

---

## 9. Provenance Portal

> **Open:** [Document Registry UI](https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

The Registry federates MLflow + Marquez + its own database. Users answer provenance questions without opening the underlying systems.

### Walk the chain:

1. **Queries** → find the query we just ran
2. **Trace Detail** → question, answer, tool calls, chunks with doc_ids and scores, `pipeline_run_id`
3. **Click a doc_id** → Document Provenance: identity, collections, pipeline runs, source URL, other queries that cited it
4. **Collection Health** → doc count, vector count, consuming apps, query volume
5. **App Overview** → the two apps with their collections and query counts
6. **Impact Analysis** → enter a doc_id → affected collections, apps, queries

### Sidebar deep links

- [Marquez](https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com) — raw ingest lineage graph
- [MLflow](https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments) — raw trace spans

**End-to-end chain:** Answer → chunks (doc_ids, pipeline_run_ids) → Registry (source_url, metadata) → Marquez (ingest graph) → source document.

**Future direction:** This provenance portal role could evolve toward Unity Catalog (if it gains lineage federation) or OpenMetadata (richer lineage UI, built-in auth).

---

## 10. Against the Data Strategy: What's Proven, What Needs Work

The Data Strategy proposal and its research docs identify specific challenges and gaps. Here's where each stands after the POC.

### Proven — works

| Challenge (from DataStrategy repo) | How the POC solved it |
|------------------------------------|----------------------|
| **No OL emitters in RHOAI** — zero components emit OpenLineage natively | `rhoai-lineage` library: KFP adapter emits from orchestrator level; naming helpers ensure graph connectivity |
| **No lineage aggregation backend** — Marquez not integrated | Marquez deployed on OpenShift (API + Web UI), receiving OL events from pipeline components |
| **Cross-component identity correlation** — no defined key scheme | `pipeline_run_id` as single correlation key across KFP, Marquez, MLflow, Milvus, Registry |
| **No query/response audit logging** — neither Responses API nor Milvus emits events | MLflow traces with autolog (`langchain` for Workflow A, `openai` for Workflow B); structured tags for search |
| **MLflow-to-OpenLineage bridge needed** — MLflow doesn't emit OL | Bridge built (ET team's `OpenLineageTrackingStore`), kept OFF by default; direct OL emission is cleaner for pipeline-time |
| **No RAG lineage UI** — Feast UI is feature-store-scoped | Registry provenance portal federates MLflow + Marquez + Registry |
| **RayData/Docling have no OL** — manual instrumentation required | Orchestrator-level emission via `kfp_lineage`; Docling invisible to Marquez except as declared I/O |
| **Event 3 (query lineage) needs custom instrumentation** | Solved — but differently than proposed. Two-layer architecture (MLflow traces, not OL to Marquez) |

### Needs work / discussion

| Challenge | Status | What's needed |
|-----------|--------|---------------|
| **Marquez has no auth** | Open (PG-001) | OAuth proxy sidecar; multi-tenant access |
| **Marquez maintenance risk** — 18-month release gap, single maintainer | Not addressed | Evaluate OpenMetadata as alternative |
| **Full cross-platform correlation** (Feast → MLflow → Model Registry → TrustyAI) | Solved for RAG only (`pipeline_run_id`) | Broader key scheme needed for Scenario A/C |
| **Lineage operator for agent-level tracking** | Deferred (PG-023) | ET team's operator not needed for pipeline/query lineage; revisit for production agent monitoring |
| **Unity Catalog integration** | Not in scope | Deploy OSS; evaluate overlap with Registry + Marquez |
| **OpenMetadata evaluation** | Not in scope | Richer UI, built-in auth — candidate to replace Marquez |
| **Document lifecycle governance** (exercised) | Partial — API exists, not exercised in pipeline | Supersede a doc, re-run pipeline, verify old vectors removed |
| **OGX as OL producer** — OGX emits no lineage events | Confirmed as a gap (ADR-003) | Upstream feature request; or keep OGX out of the lineage-critical path |
| **Embedding model alignment** — no platform-level tracking | Implicit (same model used) | Platform needs model version tracking + alignment validation |

---

## 11. Summary

### What the POC proves

1. **Five-pillar architecture works for enterprise RAG** — no feature store needed
2. **Two-layer lineage** is the correct pattern for RAG governance
3. **End-to-end answer provenance** is achievable — regulatory audit trail from answer to source document
4. **Document identity needs a dedicated registry** — Milvus metadata is not persistent enough
5. **OGX's value is real but scoped** — agentic orchestration (Workflow B) yes; deterministic RAG and ingest no
6. **Federated provenance portal** is feasible — users don't need to know the underlying systems
7. **Cross-component correlation is solvable** — `pipeline_run_id` as a single key works for RAG

### What's not covered

| Gap | Future Direction | Ref |
|-----|------------------|-----|
| RBAC / access control | Per-role document and collection permissions | PG-008 |
| Production connectors (SharePoint, Confluence) | Connector ABC exists; real implementations are product-level | PG-010 |
| Unity Catalog | Deploy OSS on OpenShift; evaluate overlap with Registry + Marquez | Spec P5 |
| OpenMetadata | Evaluate as Marquez replacement (richer UI, built-in auth) | — |
| Hybrid search (vector + keyword) | Milvus 2.4+ supports | PG-007 |
| Incremental processing | `content_hash` tracked; pipeline needs delta logic | PG-006 |
| Embedding ISVC on RHOAI | vLLM 3.4 lacks `--task=embedding`; re-evaluate on 3.5+ | PG-018 |

Full assessment: [scenario-b-assessment.md](../assessment/scenario-b-assessment.md) — 14 of 29 capabilities fully demonstrated, 9 partial, 6 not addressed. 60 production gaps tracked: [production-gaps.md](../production-gaps.md)

---

## 12. Findings for the Data Strategy Proposal

Seven findings → full detail: [data-strategy-feedback.md](../assessment/data-strategy-feedback.md)

| # | Finding | Pillar | Impact |
|---|---------|--------|--------|
| 1 | **Lineage model needs two layers** — Marquez for pipeline-time, MLflow traces for query-time | P4 | Architectural correction |
| 2 | **Document Registry should be a platform component** — persistent identity, not Milvus metadata | P1 | New capability |
| 3 | **OGX scope is narrower than spec implies** — agentic yes, deterministic RAG and ingest no | P2/P3 | Scoping correction |
| 4 | **Add application-level consumption to lineage** — downstream consumers complete the Marquez graph | P4 | Gap |
| 5 | **Elevate document source connectivity** — not a sub-item of RFE-001, it's major engineering | P1 | Underweight |
| 6 | **Add provenance portal as P5 deliverable** — federated traceability UI distinct from "Data Hub UI" | P5 | Missing deliverable |
| 7 | **Embedding model alignment is a platform concern** — silent retrieval degradation if models differ | P2/P3 | Missing concern |

---

## 13. Questions for the ET Team

Priority items — full set: [et-team-questions.md](../assessment/et-team-questions.md)

- **Request-time lineage:** Did you hit the Marquez per-request limitation? Does the two-layer split make sense?
- **MLflow bridge:** Your `OpenLineageTrackingStore` intercepts MLflow *runs* but not *traces*. Extend it, or two-layer?
- **Application OL emission:** One event per consuming app to complete the Marquez graph — sound pattern?
- **`rhoai-lineage`:** We forked your code. Co-maintain?

---

## 14. Discussion

- **Is Marquez needed long-term?** Could MLflow experiment tracking cover ingest runs too? Or does the visual DAG justify a second system?
- **Collection ↔ Application modelling:** Should Collections be a platform concept?
- **OGX production path:** Dev Preview blocks adoption — timeline?
- **Unity Catalog vs OpenMetadata:** Which is the right long-term home for catalog + identity + lineage?
- **Lineage ownership:** ET team, platform team, or shared?

---

## Links

| System | URL |
|--------|-----|
| Document Registry UI | https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Compliance Review UI | https://compliance-review-ui-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Marquez Web UI | https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Marquez API | https://marquez-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| MLflow UI (RHOAI) | https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments |
| KFP Dashboard | https://ds-pipeline-dspa-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Data Strategy Repo | https://github.com/briangallagher/DataStrategy |

## References

| Document | Path |
|----------|------|
| Scenario B spec | `DataStrategy/.../scenario-b-underwriting-knowledge.md` |
| Scenario B assessment | `docs/assessment/scenario-b-assessment.md` |
| Data Strategy feedback (7 findings) | `docs/assessment/data-strategy-feedback.md` |
| ET team questions | `docs/assessment/et-team-questions.md` |
| Production gaps (60 tracked) | `docs/production-gaps.md` |
| Decision log (DEC-001–013) | `docs/decisions.md` |
| Milestones (M0–M5) | `docs/milestones/README.md` |
| Domain glossary | `CONTEXT.md` |
