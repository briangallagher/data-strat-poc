# Feedback to Data Strategy Proposal: Findings from the Enterprise RAG POC

**Date:** 2026-05-28
**Author:** Brian Gallagher, AIP Kubeflow-DevX
**POC:** Data Strategy POC — P&C Underwriting Knowledge Assistant (Scenario B)
**POC Status:** M4 Complete (Deterministic RAG operational), M5 Planned (Agentic RAG)
**Audience:** Data Strategy team (Jonathan Zarecki, Francisco Arceo, Paul McCarthy)

---

## Purpose

This document presents seven findings from the Data Strategy POC that have implications for the Data Strategy proposal. Each finding identifies a gap or correction in the current proposal, provides evidence from the POC (referencing specific decisions, ADRs, and production gaps), and offers a concrete recommendation for updating the proposal.

The POC validates the five-pillar architecture overall — it works for enterprise RAG without a feature store and without Feast. These findings are refinements, not objections. They represent places where building a working system revealed requirements the proposal's top-down framing missed.

---

## Summary Table

| # | Finding | Proposal Impact | Pillar(s) | POC Reference |
|---|---------|----------------|-----------|---------------|
| 1 | Pillar 4 lineage model is wrong for RAG query provenance | **Architectural correction** — two-layer lineage needed | P4 | DEC-009 |
| 2 | Document Registry should be a first-class platform component | **New capability** — not in current proposal | P1, P4 | M3, DEC-011 |
| 3 | OGX's value is narrower than the spec implies | **Scoping correction** — distinguish deterministic vs agentic RAG | P2, P3 | ADR-003, DEC-010 |
| 4 | No concept of application-level consumption in lineage | **Gap** — Marquez graph incomplete without downstream consumers | P4 | DEC-009 (graph completion) |
| 5 | Document source connectivity gap is understated | **Underweight** — needs standalone capability framing | P1 | PG-010, Connector ABC |
| 6 | Pillar 5 underspecifies provenance UX | **Missing deliverable** — provenance portal needed | P5 | DEC-011 |
| 7 | Embedding model alignment isn't addressed | **Missing concern** — silent retrieval degradation risk | P2, P3 | ADR-003 (consequences), PG-018 |

---

## Detailed Findings

### Finding 1: Pillar 4 Lineage Model Is Wrong for RAG Query Provenance

**Proposal position:** Pillar 4 frames all lineage as OpenLineage events emitted to Marquez, including query/retrieval (the spec's "Event 3: Query/Retrieval"). The implied resolution for the acknowledged gap ("neither the Responses API nor Milvus emits OpenLineage events natively") is custom OpenLineage facets for RAG query events flowing to Marquez alongside ingest lineage.

**What the POC found:** Marquez cannot model per-request provenance. Marquez models datasets and jobs — it tracks that a collection was queried, but not which specific chunks answered which specific question. Two core provenance questions are unanswerable in Marquez:

1. *"Which chunks/documents answered this question?"* — requires per-request granularity (this query → these 5 chunks → these doc_ids). Marquez has no request concept.
2. *"Which questions were answered using this document?"* — requires reverse lookup across all queries where a given `doc_id` appeared. Marquez has no concept of searching across job runs by facet values.

MLflow traces are purpose-built for this: each trace is one request with the exact chunks retrieved, similarity scores, doc_ids, and pipeline_run_ids captured as span attributes. MLflow's trace search API supports filtering by custom attributes for the reverse lookup.

**Evidence:** DEC-009 documents the full analysis and decision. The POC implemented the two-layer architecture across M2–M4 and verified end-to-end answer provenance (Chain 1): MLflow trace → retrieved chunks (doc_id, pipeline_run_id) → Registry (source_url, metadata) → Marquez (ingest lineage graph). A compliance officer can trace any AI-generated answer back to its source documents without touching Marquez's query API.

**Recommendation:** Replace "Event 3: Query/Retrieval" in the Pillar 4 lineage model with a two-layer architecture:

| Layer | Tool | Scope | Granularity |
|-------|------|-------|-------------|
| Pipeline-time lineage | OpenLineage → Marquez | Data pipeline: source → parse → embed → store | Dataset/batch level |
| Query-time lineage | MLflow traces | RAG query: question → retrieval → generation → answer | Per-request level |
| Bridge | `pipeline_run_id` | Stamped on every vector at ingest; retrieved at query time; joins the two layers | Per-vector |

This is not a minor framing change. It is a fundamental architectural correction: Marquez and MLflow serve different provenance needs at different granularities, and the bridge between them (`pipeline_run_id`) must be a first-class design element in the proposal.

---

### Finding 2: Document Registry Should Be a First-Class Platform Component

**Proposal position:** The proposal treats document metadata as application-level. Pillar 1's "Phase 1: Document Ingestion" describes a single pipeline phase where documents are ingested with metadata tagging. There is no concept of persistent document identity separate from the vector store.

**What the POC found:** Documents need stable identity (`doc_id`) that persists across pipeline re-runs, source URL changes, and multi-collection membership. The POC built a Document Registry (FastAPI + PostgreSQL) that owns:

- **Stable identity:** `doc_id` persists when a document's source URL changes or when the pipeline is re-run. Milvus metadata alone cannot provide this — vectors are deleted and re-created on each ingest run.
- **Collection membership:** Many-to-many relationship between documents and collections. A single regulatory bulletin may belong to both `regulatory_bulletins` and `underwriting_guidelines`.
- **Content hashing:** `content_hash` enables future incremental processing (PG-006) — skip unchanged documents on re-ingest.
- **Provenance federation:** The Registry became the natural home for the provenance portal (DEC-011) because it already owns document identity — the entry point for all provenance questions.

The proposal's assumption that document identity lives in Milvus metadata breaks down in practice. Vectors are ephemeral (re-created on each pipeline run); document identity must be persistent.

**Evidence:** M3 built the Registry with `doc_id` persistence, content hashing, collection membership, and a `supersede` API. DEC-011 extended it into the provenance portal. The separation of concerns — Register (identity) → Build Collection (curation) → Pipeline Run (execution) — directly contradicts the proposal's single-phase ingestion model.

**Recommendation:** Add "Document Registry" as a named platform capability in Pillar 1. Define it as the component that:

1. Owns persistent document identity across pipeline runs and source URL changes
2. Manages document-to-collection membership (many-to-many)
3. Tracks content versions and supersession history
4. Serves as the entry point for provenance queries (see Finding 6)

Position it between P1 (connectors) and P2 (compute) in the architecture diagram. It mediates document identity, collection membership, and pipeline triggering.

---

### Finding 3: OGX's Value Is Narrower Than the Spec Implies

**Proposal position:** The spec positions OGX for both the ingest path (Vector I/O for embedding + storage) and the query path (Responses API for retrieval + generation). Pillar 2 lists OGX as a compute engine for prototyping, and Pillar 3 frames OGX Responses API as the data abstraction layer for RAG.

**What the POC found:** OGX's value is real but narrower than the proposal implies. Three specific issues emerged:

1. **Ingest path — OGX Vector I/O is a lineage blind spot.** OGX emits no OpenLineage events. Embedding and Milvus insertion happen in a single opaque API call with no observability into which model was used, batch sizes, retries, or transformations. Direct Milvus writes (the Ray team's upstream pattern) make every step observable and lineage-emittable. (ADR-003, Lineage Implications section)

2. **Deterministic RAG — LangGraph + MLflow provides superior observability.** For single-collection, deterministic retrieval (Workflow A), LangGraph with `mlflow.langchain.autolog()` captures the full trace tree automatically — every tool call, every retrieved chunk with doc_id and score, every LLM generation. OGX Responses API provides no native tracing; achieving equivalent observability requires wrapping OGX calls in custom MLflow spans. (DEC-010, options analysis)

3. **Agentic RAG — this is OGX's actual sweet spot.** OGX's differentiator is multi-tool orchestration and agent loops for multi-hop retrieval across multiple collections. This is Workflow B (compliance review agent), not Workflow A (guideline lookup). The POC reserves OGX evaluation for M5 where this value is clearest.

**Evidence:** ADR-003 documents the full ingest-path analysis (six lineage concerns compared across direct writes vs OGX Vector I/O). DEC-010 documents the query-path evaluation (three options compared on observability, developer experience, and alignment with Pillar 4 requirements).

**Recommendation:** Distinguish two RAG patterns in the proposal and position OGX accordingly:

| Pattern | Characteristics | Recommended Stack | OGX Role |
|---------|----------------|-------------------|----------|
| Deterministic RAG | Single collection, controlled retrieval, cited answers | LangGraph/LangChain + MCP + MLflow autolog | Not required |
| Agentic RAG | Multi-collection, multi-hop, autonomous reasoning | OGX Responses API | Core orchestrator |

Remove OGX Vector I/O from the recommended ingest path until it supports OpenLineage emission. For ingest, recommend direct writes with explicit embedding and metadata stamping — the pattern already merged upstream in `pipelines-components`.

---

### Finding 4: No Concept of Application-Level Consumption in Lineage

**Proposal position:** Pillar 4's lineage model describes the data flow from source through processing to storage (Milvus). The lineage graph ends at the vector store. There is no description of how consuming applications (chat agents, compliance tools, reporting dashboards) appear in the lineage graph.

**What the POC found:** Without downstream consumers in Marquez, the lineage graph is incomplete — data flows into Milvus and disappears. A compliance officer looking at the Marquez graph sees "documents were processed into vectors" but not "these vectors are consumed by the underwriter chat agent and the compliance review agent."

The POC solved this with application-level OpenLineage events: each consuming application (e.g., `underwriter_chat`) is modelled as an OL job with Milvus collections as inputs. This event is emitted once per application (on startup or first query), not per-request. It completes the Marquez graph from source documents through ingest to application consumption, while per-query detail stays in MLflow traces (Finding 1).

**Evidence:** DEC-009 (Marquez graph completion section). The POC registered `underwriter_chat` as an OL job consuming `milvus://underwriting_guidelines`, closing the visual gap in the Marquez lineage graph.

**Recommendation:** Add an "application-level consumption" pattern to Pillar 4. Each application that queries a vector store should emit a lightweight OpenLineage event declaring its input datasets (Milvus collections). This is a one-time emission per application, not per-request. Include this as a standard pattern in the lineage architecture alongside pipeline-time events.

---

### Finding 5: Document Source Connectivity Gap Is Understated

**Proposal position:** The spec lists connector gaps under RFE-001 (RHAIRFE-847) as a sub-item of the centralized external connection auth decision. The 22-connector gap vs Databricks is mentioned, but the work required to actually connect to document sources is treated as a configuration concern.

**What the POC found:** Building even one production-quality connector required significant effort that the proposal underestimates:

- **Connector abstraction:** The POC designed and built a Connector ABC (abstract base class) with a `fetch_to_staging()` contract, error handling, and credential management. This didn't exist — the proposal assumes connectors can be plugged in but doesn't describe the contract they must satisfy.
- **Discovery workflow:** Before documents can be ingested, they must be discovered and registered. The POC built a discovery workflow (scan source → register documents → curate into collections → trigger pipeline) that the proposal's "Phase 1: Document Ingestion" conflates into a single step.
- **Source abstraction:** Different source systems have fundamentally different access patterns (S3 list + get, SharePoint Graph API with pagination, Confluence REST API with space/page hierarchy). The connector abstraction must handle these differences while presenting a uniform interface to the pipeline.
- **Credential management:** Each source system requires different credential types (S3: access key + secret, SharePoint: OAuth2 client credentials, Confluence: API token). The POC used per-pipeline configuration; production needs the centralized credential registry the proposal describes but hasn't scoped.

Only the S3 connector was built to production quality. SharePoint and Confluence remain mock-only (PG-010).

**Evidence:** PG-010 (mock connectors only). The POC's connector abstraction, discovery workflow, and source-to-staging pipeline represent meaningful engineering that the proposal's RFE-001 sub-item treatment doesn't reflect.

**Recommendation:** Elevate document source connectivity from a sub-item of RFE-001 to a standalone Pillar 1 capability gap. Define:

1. A connector contract (interface/ABC) that all source connectors must implement
2. A discovery workflow separate from the ingest pipeline (discover → register → curate → ingest)
3. A credential registry integrated with the connector contract
4. A prioritised connector roadmap based on customer demand (the 10–15 connectors identified in the workshop)

This is not a configuration task — it is a significant engineering investment that should be planned and resourced accordingly.

---

### Finding 6: Pillar 5 Underspecifies Provenance UX

**Proposal position:** Pillar 5 mentions dashboards and a "Data Hub UI" for unified discovery. The gap table notes "no compliance/audit dashboard" but doesn't describe what such a dashboard would show or how a user would navigate from an AI-generated answer back to the source documents that informed it.

**What the POC found:** The provenance UX is not a dashboard — it is a portal that federates multiple backend systems. The POC built this as the Registry UI (DEC-011) with three views:

1. **Document Provenance:** From any document → collections it belongs to, consuming applications, recent queries that cited it, ingest pipeline runs that processed it, original source URL. Entry point: "What happened with this document?"
2. **Query Trace Detail:** From any query → the question asked, the answer generated, every chunk retrieved (with text preview), source documents (linked to Document Provenance), pipeline run that produced the vectors (linked to Marquez). Entry point: "What informed this answer?"
3. **Query Trace List:** Recent queries across all applications, filterable by collection, doc_id, and date range. Entry point: "What queries are being run?"

The portal federates MLflow (query traces), Marquez (ingest lineage), and the Document Registry (document identity and collections) through a single UI. Users never need to open Marquez, MLflow, or a terminal. Deep links to those systems are available for engineers who want the underlying detail.

**Evidence:** DEC-011 documents the full evaluation (three options compared) and implementation. The Registry UI is deployed and verified — a compliance officer can navigate from a document to the queries that cited it to the pipeline that ingested it to the original source, all without leaving the portal.

**Recommendation:** Add "Provenance Portal" as a named Pillar 5 deliverable. Define it as a federated UI that answers three provenance questions:

| Question | Data Sources | User |
|----------|-------------|------|
| "What informed this AI answer?" | MLflow traces + Registry + Marquez | Compliance officer, auditor |
| "What happened with this document?" | Registry + Marquez + MLflow (reverse lookup) | Document owner, compliance officer |
| "What queries are being run against our data?" | MLflow traces + Registry | Operations, security |

This is distinct from the "Data Hub UI" (which is about data asset discovery). The provenance portal is about traceability and audit — a Pillar 4 concern surfaced through a Pillar 5 interface.

---

### Finding 7: Embedding Model Alignment Isn't Addressed

**Proposal position:** The proposal does not discuss embedding model alignment between ingest-time and query-time. Pillar 2 mentions RHOAI model serving for embeddings and Pillar 3 describes vector search, but neither addresses what happens when ingest and query use different embedding models or model versions.

**What the POC found:** Ingest-time and query-time embedding models must produce vectors in the same embedding space, or retrieval silently degrades. There is no error — cosine similarity still returns results, but the results are semantically wrong because the vector spaces don't align. This is a pernicious failure mode because it is invisible to the user and to monitoring.

The POC encountered this directly:

- **PG-018:** RHOAI 3.4's vLLM lacks `--task=embedding`, so the POC could not use a KServe InferenceService for embeddings. The mitigation was local `sentence-transformers` using the same model (Granite Embedding 125M EN) for both ingest and query. This works but is fragile — if someone changes the ingest model without updating the query path (or vice versa), retrieval degrades silently.
- **ADR-003 consequences:** The decision to split OGX from ingest (direct writes) while reserving it for query explicitly calls out: "Must ensure the embedding model used in the ingest pipeline matches what OGX uses at query time. If they differ, retrieval quality degrades."
- **Multi-collection complication:** With three collections potentially ingested at different times, model version drift across collections is a real risk. Re-embedding an entire collection is expensive; knowing which collections use which model version is essential.

**Evidence:** PG-018 (embedding ISVC limitation), ADR-003 (consequences section), DEC-010 (consequences: "Embedding model alignment still critical").

**Recommendation:** Add embedding model alignment as a named platform concern in the proposal. Specifically:

1. **Model version tracking:** Every collection should record the embedding model name and version used at ingest time (the POC stores this as pipeline metadata, but it should be a platform-level concern).
2. **Alignment validation:** At query time, the platform should verify that the query embedding model matches the collection's ingest embedding model. If they differ, warn or block rather than returning silently degraded results.
3. **Re-embedding support:** When a model version changes, the platform should support re-embedding existing collections with the new model. This connects to incremental processing (PG-006) — re-embedding is a bulk reprocessing operation.
4. **PG-018 as a platform gap:** Until RHOAI model serving supports `--task=embedding`, the proposal's assumption that "RHOAI model serving for embeddings" is available is incorrect. Call this out as a known limitation with a target resolution (RHOAI 3.5+).

---

## Cross-Cutting Observations

### The Five-Pillar Model Works

Despite the seven findings above, the POC validates the five-pillar architecture as the right framing for enterprise data + AI. All five pillars were exercised for a knowledge retrieval workload with zero predictive AI, no feature engineering, and no Feast. The pillar model is technology-neutral and applies beyond the training/serving scenarios the proposal emphasises.

### The Proposal Is Top-Down; the POC Is Bottom-Up

Most of these findings arise from the difference between designing an architecture (top-down) and building a working system (bottom-up). The proposal correctly identifies the capabilities needed at each pillar. What it underspecifies is the connective tissue: how lineage actually flows across layers (Finding 1), what owns document identity (Finding 2), where provenance questions are answered (Finding 6), and what happens when components at different layers use incompatible configurations (Finding 7). These are integration concerns that only surface when you build the full stack.

### RAG Is a Valid Scenario B Without Feast

The proposal's scenarios lean heavily toward feature-store-centric workloads. The POC demonstrates that Scenario B (knowledge retrieval) exercises all five pillars without Feast. This is significant for field teams: customers doing RAG — arguably the most common enterprise AI pattern today — can use the full data strategy architecture. The proposal should call this out explicitly.

---

## Appendix: POC Reference Index

| Reference | Type | Location |
|-----------|------|----------|
| DEC-009: Two-layer lineage | Decision | `docs/decisions.md` |
| DEC-010: LangGraph for deterministic RAG | Decision | `docs/decisions.md` |
| DEC-011: Registry as provenance portal | Decision | `docs/decisions.md` |
| ADR-003: OGX role in the system | ADR | `docs/architecture/adrs/ADR-003-ogx-role.md` |
| PG-006: No incremental processing | Production gap | `docs/production-gaps.md` |
| PG-010: Mock connectors only | Production gap | `docs/production-gaps.md` |
| PG-018: Embedding ISVC limitation | Production gap | `docs/production-gaps.md` |
| PG-026: Document lifecycle not exercised | Production gap | `docs/production-gaps.md` |
| Scenario B Assessment | Assessment | `docs/assessment/scenario-b-assessment.md` |
| RHAIRFE-847: OOTB connectors | Jira RFE | `https://redhat.atlassian.net/browse/RHAIRFE-847` |
| RHAIRFE-929: Credential handling | Jira RFE | `https://redhat.atlassian.net/browse/RHAIRFE-929` |
