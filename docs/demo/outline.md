# Data Strategy POC — Demo Walkthrough

**What this is:** A working enterprise RAG system built against the Data Strategy's Scenario B spec — P&C underwriting knowledge assistant on RHOAI. Five pillars, 6 milestones, 20 documents, 3 collections, 2 query workflows, 60 production gaps tracked.

**Audiences:** Teammates, Data Strategy author, ET (Waterford) lineage team.

---

## 1. Context: Scenario B and the Five Pillars

The Data Strategy proposes a five-pillar architecture for enterprise data + AI on RHOAI. Scenario B is the non-Feast proof point: pure knowledge retrieval, no ML training, no feature store.

Two workflows:
- **Workflow A (Deterministic RAG):** Underwriter asks a question → retrieve from one collection → cited answer
- **Workflow B (Agentic Compliance Review):** Compliance officer asks for cross-reference review → agent retrieves across 3 collections → structured report

> Show the Scenario B architecture diagram from the spec. Note the five pillar annotations (P1–P5). The rest of the demo walks through what we actually built against this spec.

**What's not in scope for this POC:**
- No RBAC or access control — no per-document permissions, no role-based filtering at query time (PG-008). In production, a compliance officer sees different documents than a junior underwriter. We haven't modelled that.
- No production connectors — S3/MinIO only; no SharePoint, Confluence, or DMS (PG-010)
- No Unity Catalog, no credential registry, no incremental processing

These are called out throughout and summarised at the end.

**Repo:** [github.com/briangallagher/DataStrategy](https://github.com/briangallagher/DataStrategy) — `scenarios/scenario-b-underwriting-knowledge/`

---

## 2. The Document Registry: Identity and Registration

> Open: [Document Registry UI](https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

Before any pipeline runs, documents need stable identity. The Registry owns document identity — a `doc_id` that persists across pipeline re-runs, source URL changes, and collection reassignment.

- Show the **document list** — 20 documents with `doc_id` (e.g., `ug-001`), source URL, content hash, metadata
- Show the **Register Documents** page — this is how new documents would enter the system (form fields: source URL, document type, line of business, jurisdiction, effective date)
- Each document has: `doc_id`, `source_url`, `line_of_business`, `jurisdiction`, `effective_date`, `document_type`, `content_hash`

`doc_id` is stable. If the source file moves in S3 or SharePoint, the identity doesn't break. Milvus vectors are ephemeral — deleted and re-created on every pipeline run — so document identity can't live there.

**This wasn't in the Scenario B spec.** The spec assumes document metadata is tagged at ingestion time and lives in Milvus. We found that doesn't work — you need a persistent registry that owns identity separately from the vector store. This is **Finding 2** in our feedback to the proposal.

**Alternatives to explore:** The Registry covers the catalog/identity concern. In production, this role could potentially be filled by **Unity Catalog** (three-level namespace, lineage tracking, access control) or **OpenMetadata** (richer UI, built-in auth). Both are future evaluation items — the POC proves the *need* for this capability; the specific technology is open.

---

## 3. Collections: Curation and the Modelling Question

> Stay in: [Document Registry UI](https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

Documents are assigned to **Collections**. Show the three existing collections:

| Collection | Documents | Purpose |
|------------|-----------|---------|
| `underwriting_guidelines` | 10 docs | Company underwriting guidelines by LOB (commercial property, workers comp, GL, etc.) |
| `iso_forms` | 5 docs | ISO/ACORD standard forms (CG 00 01, CP 00 10, etc.) |
| `regulatory_bulletins` | 5 docs | State DOI bulletins, NAIC guidance, regulatory circulars |

**Why three separate collections?** They serve different personas and query patterns. An underwriter asking about flood coverage only needs `underwriting_guidelines`. A compliance officer comparing company guidelines against ISO standards needs to cross-reference `underwriting_guidelines` and `iso_forms`. A regulatory review pulls from all three. Separate collections enable targeted retrieval — the agent decides which collection(s) to search based on the question.

Each Collection maps 1:1 to a Milvus collection and is the unit of pipeline execution — one pipeline run per collection. A document can belong to multiple collections (many-to-many).

**The modelling question:**

```
Documents → Collection → Milvus Collection → Application(s)
```

- **Collection** = the curation decision ("these documents should be queryable together")
- **Milvus collection** = the physical vector storage
- **Application** = a consuming service (e.g., `underwriter_chat`, `compliance_review_agent`) that queries one or more collections

> Discussion: Is this the right abstraction? The spec doesn't distinguish between "a set of documents I want to query" and "the vector store that holds them." We found the separation matters — curating which documents belong together is a human/domain decision, separate from how they're stored and who queries them.

**Mapping to Scenario B:** This covers the **catalog and connector** piece (P1). Not covered: RBAC on collections or documents, production connectors beyond S3, credential management.

---

## 4. The Ingest Pipeline: A Previous Run

> Open: [KFP Dashboard](https://ds-pipeline-dspa-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

Show a **completed pipeline run** for one of the three collections. The pipeline has three steps:

1. **`acquire_documents`** — queries the Registry for collection members, fetches files from S3 staging, writes a manifest, emits OpenLineage events to Marquez
2. **`parse_and_chunk`** — RayData + Docling: layout-aware parsing (97.9% table accuracy), structure-aware chunking, per-document metadata from manifest
3. **`ingest_to_milvus`** — embeds chunks (Granite Embedding 125M via local sentence-transformers), writes vectors to Milvus with full metadata

- Show the run parameters: `collection_name`, `pipeline_run_id`, `marquez_url`
- Show the DAG visualisation and step logs

Each step emits **OpenLineage events** to Marquez via `rhoai-lineage` (forked from the ET team's work).

**Key metadata stamped on every vector:** `doc_id`, `pipeline_run_id`, `line_of_business`, `jurisdiction`, `effective_date`, `document_type`, `section_path`, `page_numbers` — 10-field Milvus schema (ADR-002).

The `pipeline_run_id` is the critical piece — it bridges ingest-time lineage (Marquez) and query-time lineage (MLflow). More on this shortly.

---

## 5. What the Pipeline Produced: Marquez and MLflow

### Marquez: the ingest lineage graph

> Open: [Marquez Web UI](https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

- Show the full lineage graph: source documents → `acquire_documents` → S3 staging → `parse_and_chunk` → `ingest_to_milvus` → Milvus collection
- Show the **downstream consumers**: `underwriter_chat` and `compliance_review_agent` appear as application nodes consuming the Milvus collections
- This is the complete graph — from source files through pipeline to consuming applications

Marquez answers: **"How did this data get into Milvus?"** Dataset-level, batch-oriented, pipeline-time.

### MLflow: experiment tracking for pipeline runs

> Open: [MLflow UI](https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments)

- Show the pipeline experiment runs — each collection ingest is logged as an MLflow run with params and metrics
- This is standard experiment tracking, not traces (traces come at query time — next section)

---

## 6. Querying: Live Demo

### Workflow A — Deterministic RAG

> Open: Chainlit UI for `underwriter_chat`

Ask: *"Does our commercial property form cover flood damage for a property in a high-risk flood zone?"*

- Cited answer referencing `[ug-003]` with section and page
- Tool call visualisation — the MCP `milvus_search` call and retrieved chunks

**Stack:** LangGraph + MCP server (wraps pymilvus with local embedding) + Chainlit + `mlflow.langchain.autolog()`

**Why LangGraph, not OGX?** (DEC-010) For deterministic RAG, `mlflow.langchain.autolog()` captures the full trace tree automatically — every tool call, every chunk with doc_id and score, every LLM generation. OGX provides no native tracing. OGX's value is agentic orchestration, not single-collection retrieval.

### Workflow B — Agentic Compliance Review

> Open: [Compliance Review UI](https://compliance-review-ui-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

Ask: *"Compare our general liability exclusion language with the ISO CG 00 01 standard. Flag material deviations."*

- Agent makes **multiple tool calls** across different collections
- Structured compliance review output with cited sources from all three collections

**Stack:** OGX Responses API + MCP server (SSE) + Hermes-3-Llama-3.1-70B-FP8

**OGX's role:** OGX orchestrates the agent loop — the client sends one request, OGX autonomously plans and executes tool calls via MCP, synthesizes the answer. This is where OGX adds real value.

**Model note:** Granite 3.3 8B couldn't produce structured `tool_calls`. Hermes 70B FP8 (NousResearch, ungated, FP8 quantized) provides native tool calling via vLLM `--tool-call-parser=hermes`. Fits on 1x A100-80GB.

---

## 7. Query-Time Tracing: MLflow

> Open: [MLflow UI](https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments)

- Show the **trace** for the query we just ran — the full span tree
- **Workflow A:** `mlflow.langchain.autolog()` captures everything automatically
- **Workflow B:** `mlflow.openai.autolog()` captures the Responses API call; tool call rounds appear as child spans; trace enriched client-side with provenance tags (DEC-012 — client-side reconstruction because OGX doesn't propagate trace context to MCP tools)
- Show the trace tags: `doc_ids_cited`, `pipeline_run_ids`, `collection_queried`, `chunks_retrieved_count`, `answer_preview`

**The key point:** Nothing was captured in Marquez for the query. Marquez knows the collections exist and which apps consume them, but it doesn't know which specific chunks answered which specific question. That's MLflow's job.

This is the **two-layer lineage architecture** (DEC-009):

| Layer | Tool | Answers | Granularity |
|-------|------|---------|-------------|
| Ingest-time | Marquez (OpenLineage) | "How did this data get into Milvus?" | Dataset / batch |
| Query-time | MLflow traces | "What happened when this question was asked?" | Per-request / per-span |
| Bridge | `pipeline_run_id` | Links the two layers | Per-vector metadata |

The Scenario B spec proposed **Event 3** — an OL event to Marquez for every query. This doesn't work. Marquez models datasets and jobs, not individual requests. It would show "the collection was queried" but not which chunks or documents were involved. The two-layer split is the architecturally correct approach.

> Discussion (ET team): Did you hit this same limitation? Does the two-layer split make sense, or is there a path to making Marquez work for per-request lineage?

---

## 8. Provenance Portal: Back to the Registry

> Open: [Document Registry UI](https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com)

The Registry UI federates MLflow, Marquez, and its own database so users never need to open the underlying systems directly.

### Walk the provenance chain:

1. **Queries view** — find the query we just ran in the trace list
2. **Trace Detail** — question, answer, tool calls, retrieved chunks with doc_ids and scores, `pipeline_run_id` for each chunk
3. **Click a cited doc_id** → Document Provenance: identity, collections, pipeline runs, source URL, other queries that cited this document
4. **Collection Health** — doc count, vector count, consuming apps, query volume
5. **App Overview** — `underwriter_chat` and `compliance_review_agent` with collections and query counts
6. **Impact Analysis** — enter a doc_id → which collections, apps, and queries would be affected if this document changes

### Sidebar links to underlying systems:
- [Marquez](https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com) for the raw ingest lineage graph
- [MLflow](https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments) for the raw trace spans

**End-to-end chain:** Answer → chunks (doc_ids, pipeline_run_ids) → Registry (source_url, metadata) → Marquez (ingest graph) → source document. A compliance officer can trace any AI-generated answer back to its source without leaving the portal.

**Alternatives:** The provenance portal role could be served by **Unity Catalog** (if it gains lineage federation capabilities) or **OpenMetadata** (richer lineage UI, built-in auth). The POC proves the need; the implementation could evolve. The spec's Pillar 5 mentions a "Data Hub UI" but doesn't define what provenance navigation looks like — this is **Finding 6**.

---

## 9. What the POC Proves

1. The **five-pillar architecture works for enterprise RAG** without a feature store
2. **Two-layer lineage** is the correct architecture for RAG governance
3. **Answer provenance is achievable end-to-end** — regulatory audit trail from answer to source document
4. **Document identity requires a dedicated registry** — Milvus metadata alone is not persistent enough
5. **OGX's value is real but scoped** — agentic orchestration yes, deterministic RAG and ingest no
6. **A federated provenance portal is feasible** — users don't need to know Marquez or MLflow exist

---

## 10. What's Not Covered

| Gap | Why | Future Direction | Ref |
|-----|-----|------------------|-----|
| **RBAC / access control** | No per-document or per-collection permissions | Application-level filtering by user role; Milvus partition-key isolation | PG-008 |
| **Production connectors** (SharePoint, Confluence) | S3/MinIO only — real connectors need OAuth, pagination, credential management | Connector ABC exists; real implementations are product-level work | PG-010 |
| **Unity Catalog** | Not deployed | Deploy OSS on OpenShift; evaluate overlap with Registry (identity, catalog) and Marquez (lineage visualisation) | Spec P5 |
| **Hybrid search** (vector + keyword) | Dense-only — legal terminology like "additional insured" benefits from keyword matching | Milvus 2.4+ supports; implement dual-vector schema | PG-007 |
| **Incremental processing** | Full re-ingest per run | Registry tracks `content_hash`; pipeline needs delta logic | PG-006 |
| **Embedding ISVC** | RHOAI 3.4 vLLM lacks `--task=embedding` | Re-evaluate on RHOAI 3.5+; local sentence-transformers works but is fragile | PG-018 |
| **OpenMetadata** | Not evaluated | Richer lineage UI + built-in auth — could replace or supplement Marquez | Spec P4 |

Full assessment: [scenario-b-assessment.md](../assessment/scenario-b-assessment.md) — 14 fully demonstrated, 9 partial, 6 not addressed out of 29 Scenario B capabilities.

60 production gaps tracked, 12 closed/mitigated, 48 open: [production-gaps.md](../production-gaps.md)

---

## 11. Findings for the Data Strategy Proposal

Seven findings that should feed back. Full detail: [data-strategy-feedback.md](../assessment/data-strategy-feedback.md)

1. **Pillar 4 lineage model needs two layers** — Marquez for pipeline-time, MLflow traces for query-time. The spec's "Event 3" doesn't work for per-request provenance.
2. **Document Registry should be a platform component** — persistent identity separate from the vector store. Could be a new service, could be Unity Catalog — but the capability is needed.
3. **OGX scope is narrower than the spec implies** — agentic orchestration yes (Workflow B); deterministic RAG no (LangGraph + MLflow is better); ingest no (lineage blind spot).
4. **Add application-level consumption to lineage** — without downstream consumer nodes, the Marquez graph ends at Milvus and data disappears.
5. **Elevate document source connectivity** — not a sub-item of RFE-001. Building even one connector requires a contract (ABC), discovery workflow, credential management. Major engineering.
6. **Add provenance portal as a Pillar 5 deliverable** — federated traceability UI. Distinct from the "Data Hub UI" (discovery). Could be Unity Catalog, OpenMetadata, or a custom portal.
7. **Embedding model alignment is a platform concern** — if ingest and query use different embedding models, retrieval silently degrades. No error, just wrong answers.

---

## 12. Questions for the ET Team

Priority questions — full set in [et-team-questions.md](../assessment/et-team-questions.md)

- **Request-time lineage:** Did you hit the same Marquez limitation? Does the two-layer split make sense?
- **MLflow-Marquez bridge:** Your `OpenLineageTrackingStore` intercepts MLflow *runs* but not *traces* (GenAI tracing API). Could it be extended, or is the two-layer approach cleaner?
- **Application-level OL emission:** One OL event per consuming app to complete the Marquez graph. Sound?
- **`rhoai-lineage` co-maintenance:** We forked your code into a standalone package. Should we co-own?

---

## 13. Open Discussion

- **Is Marquez needed long-term?** Could MLflow experiment tracking model ingest runs too? Or does the visual DAG justify the second system?
- **Collection ↔ Application modelling:** Is the Registry's abstraction the right model? Should Collections be a platform concept?
- **OGX production path:** Dev Preview blocks production adoption. Timeline?
- **Unity Catalog / OpenMetadata:** Which is the right long-term home for catalog + identity + lineage visualisation?
- **Who owns lineage going forward?** ET team, platform team, shared?

---

## Live System Links

| System | URL |
|--------|-----|
| Document Registry UI | https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Compliance Review UI | https://compliance-review-ui-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Marquez Web UI | https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Marquez API | https://marquez-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| MLflow UI (RHOAI) | https://rh-ai.apps.dev.aip-ft.rh-ods.com/mlflow/#/experiments |
| KFP Dashboard | https://ds-pipeline-dspa-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Data Strategy Repo | https://github.com/briangallagher/DataStrategy |

## Reference Documents

| Document | Path |
|----------|------|
| Scenario B spec | `DataStrategy/.../scenario-b-underwriting-knowledge.md` |
| Scenario B assessment (pillar-by-pillar) | `docs/assessment/scenario-b-assessment.md` |
| Data Strategy feedback (7 findings) | `docs/assessment/data-strategy-feedback.md` |
| ET team questions | `docs/assessment/et-team-questions.md` |
| Production gap register (60 gaps) | `docs/production-gaps.md` |
| Decision log (DEC-001–013) | `docs/decisions.md` |
| Milestone status | `docs/milestones/README.md` |
| CONTEXT.md (domain glossary) | `CONTEXT.md` |
