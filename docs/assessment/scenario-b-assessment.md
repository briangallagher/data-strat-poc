# Scenario B Assessment: POC vs Data Strategy Proposal

**Date:** 2026-05-28
**POC Status:** M4 Complete, M5 Planned
**Assessed Against:** Scenario B — P&C Underwriting Knowledge Assistant on RHOAI (May 2026 draft)

---

## Executive Summary

The POC has delivered a working enterprise RAG system across milestones M1–M4 that validates the five-pillar Data Strategy architecture for knowledge retrieval workloads. Of the 29 capabilities specified across the five pillars in Scenario B, the POC **fully demonstrates** 14, **partially demonstrates** 9, and **has not yet addressed** 6 (most deferred to M5). The POC also identified 3 architectural insights the proposal missed — most significantly, the two-layer lineage model (DEC-009) that separates pipeline-time lineage (Marquez/OpenLineage) from query-time lineage (MLflow traces).

Workflow A (Deterministic RAG) is **fully operational** with cited answers and end-to-end provenance. Workflow B (Agentic RAG) is **planned for M5** with architectural foundations in place.

---

## 1. Pillar-by-Pillar Assessment

### P1: Data Ingestion & Connectivity

#### What Scenario B Requires

- Connect to diverse document sources (SharePoint, DMS, S3/MinIO, Confluence, regulatory portals)
- Track document versions with superseded-date management
- Manage credentials centrally per source system
- Support incremental ingestion (only new/changed documents)
- Handle format diversity (PDF, DOCX, HTML, XML)
- Tag documents with rich metadata (source_system, document_type, line_of_business, effective_date, jurisdiction, confidentiality)

#### What the POC Delivers

| Capability | POC Status | Component |
|-----------|-----------|-----------|
| S3/MinIO access | **Delivered** | `acquire_documents` fetches from MinIO staging |
| Document format support | **Delivered** | Docling processes PDF, DOCX, HTML (11 real PDFs including 6.9MB FEMA manual) |
| Rich metadata tagging | **Delivered** | 10-field Milvus schema (ADR-002) with LOB, jurisdiction, effective_date, document_type |
| Document version tracking (metadata) | **Partial** | `effective_date` and `superseded_date` in schema; supersede API in registry; not exercised in pipeline (PG-026) |
| Document Registry with stable identity | **Delivered** | FastAPI + PostgreSQL with `doc_id` persistence across source URL changes, content hashing, many-to-many collection membership |
| Per-document metadata in pipeline | **Delivered** | Manifest-driven `parse_and_chunk` (PG-020 closed in M3) |
| Connector abstraction | **Delivered** | Connector ABC with `fetch_to_staging()`; S3 connector built |
| SharePoint/Confluence connectors | **Not delivered** | Mock connectors only (PG-010) |
| Centralized credential management | **Not delivered** | Per-pipeline config; no connection registry |
| Incremental ingestion | **Not delivered** | Full re-ingest per run; `content_hash` tracked but not used for delta processing (PG-006) |

#### Assessment: **Partially Met**

The POC significantly exceeds the proposal's expectations in one area: the Document Registry (not in Scenario B spec at all) provides stable identity, many-to-many collection membership, and a separation of concerns (Register → Build → Acquire) that the spec's "Phase 1: Document Ingestion" conflates into a single step. The spec's gap around "no document version tracking at platform level" is partially addressed by the registry's `supersede` API and content hashing.

However, the core P1 gaps remain: no production connectors beyond S3, no incremental processing, no credential registry. These are acknowledged as out-of-scope for the POC (M5+ or product-level work).

---

### P2: Compute Engine Strategy

#### What Scenario B Requires

- CPU-intensive parsing via Docling (layout detection, table extraction, OCR)
- GPU-intensive embedding via RayData with heterogeneous compute
- Scheduled re-processing via KFP recurring runs
- Streaming execution: CPU parsing chained to GPU embedding with backpressure
- RHOAI model serving for embedding models

#### What the POC Delivers

| Capability | POC Status | Component |
|-----------|-----------|-----------|
| KFP pipeline orchestration | **Delivered** | DSPA with 6 ds-pipeline pods; compiled YAML for both ingest-only and full pipelines |
| KubeRay on RHOAI | **Delivered** | RayData workers for distributed document processing |
| RayData + Docling parsing | **Delivered** | 20 docs, 363 vectors, ~7 min E2E; 97.9% table accuracy inherited from Docling |
| Heterogeneous compute (CPU + GPU) | **Delivered** | CPU parsing nodes + GPU embedding nodes in RayData |
| Multi-collection orchestration | **Delivered** | `run-multi-collection.py` triggers per-collection pipeline runs (DEC-008) |
| RHOAI model serving for LLM | **Delivered** | Granite 3.3 8B via vLLM on A100 (KServe InferenceService) |
| Embedding via InferenceService | **Blocked** | PG-018: RHOAI 3.4 vLLM lacks `--task=embedding`; using local sentence-transformers |
| Scheduled re-processing | **Not demonstrated** | Pipeline is manually triggered; KFP recurring runs not configured |
| Managed document processing template | **Not delivered** | Build-your-own pipeline from components |

#### Assessment: **Fully Met** (core compute), **Partially Met** (operational scheduling)

The POC proves the RayData + Docling compute story end-to-end. The pipeline processes real insurance documents (including complex multi-page PDFs) into vectors with full metadata. The only significant gap is PG-018 (embedding ISVC), which is a platform limitation mitigated by local sentence-transformers using the same model (Granite Embedding 125M). Scheduled re-processing is technically trivial (KFP recurring runs are a configuration, not code) but not demonstrated.

---

### P3: Data Abstraction Layer

#### What Scenario B Requires

- Semantic search via Milvus vector database (HNSW, cosine similarity)
- Metadata filtering (LOB, document_type, jurisdiction, effective_date)
- Source attribution (document, section, page number in every answer)
- Deterministic RAG (Workflow A): application controls retrieval, LLM generates cited answer
- Agentic RAG (Workflow B): agent autonomously performs multi-hop retrieval across collections
- OGX Responses API as the abstraction layer (or custom tool calling against Milvus)
- Access control: restricted documents filtered by user role

#### What the POC Delivers

| Capability | POC Status | Component |
|-----------|-----------|-----------|
| Milvus vector search (HNSW, cosine) | **Delivered** | 3 collections deployed; HNSW index; cosine similarity |
| Metadata filtering | **Delivered** | MCP server supports filters on `line_of_business`, `document_type`, `jurisdiction`, `effective_date` |
| Source attribution (cited answers) | **Delivered** | Agent cites doc_id + section in every answer; MLflow traces capture chunk-level detail |
| Deterministic RAG (Workflow A) | **Delivered** | LangGraph agent + MCP server + Chainlit UI + MLflow autolog (DEC-010) |
| Multi-collection retrieval | **Partial** | MCP server queries `underwriting_guidelines`; extension to all 3 collections verified in plan but deferred to M4 Phase 4 / M5 |
| Agentic RAG (Workflow B) | **Not delivered** | Deferred to M5 (OGX Responses API evaluation) |
| Hybrid search (vector + keyword) | **Not delivered** | Dense-only search (PG-007) |
| Document-level RBAC | **Not delivered** | No per-document access control (PG-008) |
| OGX Responses API | **Deferred** | DEC-010 chose LangGraph for M4; OGX reserved for M5 agentic RAG |

#### Assessment: **Partially Met**

Workflow A is fully operational with cited answers, but the spec's expectation of OGX as the abstraction layer is deliberately diverged from (DEC-010). The POC argues this is the correct trade-off: LangGraph + MCP gives dramatically better observability (mlflow.langchain.autolog() captures full span tree) while OGX's strength — agent orchestration for multi-hop reasoning — is better evaluated in M5's agentic workflow.

The key missing pieces are Workflow B (agentic, multi-hop, M5), hybrid search (PG-007), and RBAC (PG-008).

---

### P4: Orchestration, Lineage & Governance

#### What Scenario B Requires

- Document provenance: trace any answer back through chunks → pipeline run → source document
- Query audit trail: log who asked, what was retrieved, what was generated, what was cited
- Document lifecycle tracking: versions, superseded documents, effective dates
- Impact analysis: identify affected documents/answers when a source changes
- OpenLineage events at three stages: ingestion, processing, query/retrieval
- Marquez as lineage backend

#### What the POC Delivers

| Capability | POC Status | Component |
|-----------|-----------|-----------|
| Pipeline-time lineage (OL → Marquez) | **Delivered** | `rhoai-lineage` library emits OL events from `parse_and_chunk` and `ingest_to_milvus`; Marquez records full graph |
| Per-document lineage in Marquez | **Delivered** | `acquire_documents` emits per-doc InputDataset nodes; per-doc metadata in facets |
| Query audit trail (MLflow traces) | **Delivered** | Every query captured as 7-span MLflow trace with chunks, doc_ids, pipeline_run_ids, scores |
| Cross-system correlation | **Delivered** | `pipeline_run_id` on every vector bridges MLflow traces → Marquez ingest graph |
| Application-level graph completion | **Delivered** | `underwriter_chat` registered as OL job consuming `milvus://underwriting_guidelines` |
| Answer provenance (Chain 1) | **Delivered** | MLflow trace → chunk doc_ids → Registry → Marquez (full chain verified) |
| Unified provenance portal | **Delivered** | Registry UI federates MLflow + Marquez + Registry APIs (DEC-011) |
| Document lifecycle governance | **Partial** | Registry tracks versions; `supersede` API exists; not exercised in pipeline (PG-026) |
| Impact analysis | **Not delivered** | Foundations exist (reverse lookup via MLflow trace search) but no UI; deferred to M5 |
| PII governance | **Not delivered** | No document sanitization during ingestion |

#### Assessment: **Fully Met** (architecture), exceeds spec in key areas

This is the POC's strongest pillar. The two-layer lineage architecture (DEC-009) is a **significant architectural contribution** that the Scenario B spec missed. The spec proposed OpenLineage Event 3 for query lineage, pushing per-query data to Marquez. The POC demonstrates why this doesn't work (Marquez models datasets and jobs, not individual requests) and delivers the correct pattern: MLflow traces for request-level provenance, Marquez for pipeline-level lineage, `pipeline_run_id` as the bridge.

The unified provenance portal (DEC-011) also exceeds the spec — Scenario B listed "no compliance/audit dashboard" as a P5 gap; the POC delivers it as a federated UI in the Registry.

---

### P5: Unified Data & AI Experience

#### What Scenario B Requires

- RHOAI Dashboard as unified entry point
- Chat UI for the knowledge assistant
- Compliance/audit dashboard for officers
- Document pipeline monitoring (embedding freshness, staleness)
- Unity Catalog for data catalog and governance
- Milvus Attu UI for vector management

#### What the POC Delivers

| Capability | POC Status | Component |
|-----------|-----------|-----------|
| Chat UI for knowledge assistant | **Delivered** | Chainlit with streaming, tool call visualization, trace metadata |
| Compliance/provenance views | **Delivered** | Registry UI: QueryTracesPage, TraceDetailPage, DocumentProvenancePage |
| Document/collection browsing | **Delivered** | Registry UI: document list, detail, collection management |
| Pipeline monitoring | **Partial** | KFP dashboard tracks runs; no embedding freshness or staleness alerts |
| Unity Catalog integration | **Not delivered** | Not in scope for POC |
| Milvus Attu UI | **Not deployed** | Available but not part of deployed stack |
| RHOAI Dashboard integration | **Not applicable** | POC uses custom UIs; RHOAI Dashboard is the platform entry point |

#### Assessment: **Partially Met**

The POC delivers a working chat UI (Chainlit) and a provenance portal (Registry UI) that together address the spec's "no chat UI" and "no compliance/audit dashboard" gaps. However, Unity Catalog (the spec's recommended data catalog solution) is not in scope. The POC's Registry fills some of Unity Catalog's functions (document identity, collection browsing, metadata management) but doesn't address cross-platform catalog, lineage visualization, or AI asset management.

---

## 2. Workflow Assessment

### Workflow A: Deterministic RAG (Underwriting Guideline Lookup)

**Status: Fully Operational**

| Spec Requirement | POC Implementation | Gap |
|-----------------|-------------------|-----|
| User asks a question via chat | Chainlit WebSocket chat UI | None |
| Responses API invokes milvus_search | LangGraph agent invokes MCP tool `milvus_search` (DEC-010 divergence) | Architectural difference, not a gap — same outcome |
| Semantic search with metadata filtering | pymilvus ANN search with scalar filters (LOB, jurisdiction, etc.) | None |
| Retrieve top-k relevant chunks | MCP server returns ChunkResult with all metadata | None |
| Generate cited answer with source doc + page | Agent generates answer citing doc_id + section; sources listed | None |
| Audit logging (user, timestamp, query, chunks, response) | MLflow trace captures full span tree; trace tags: doc_ids_cited, pipeline_run_ids, collection_queried | None |

**Verification evidence:** Asked "Does our commercial property form cover flood damage for a property in a high-risk flood zone?" → received cited answer referencing [ug-003] → full 7-span MLflow trace captured → Chain 1 verified from answer through to source document.

**Key divergence:** The spec uses OGX Responses API; the POC uses LangGraph + MCP. The outcome is identical (cited answer with source attribution), but the POC's approach gives dramatically better observability via MLflow autolog. This validates DEC-010's rationale.

### Workflow B: Agentic Compliance Review

**Status: Planned (M5)**

| Spec Requirement | POC Readiness | Gap |
|-----------------|---------------|-----|
| Agent decomposes complex request into sub-tasks | Not built | M5: OGX evaluation for agent orchestration |
| Multi-hop retrieval across 3 collections | **Foundation ready:** all 3 collections populated, MCP server supports collection parameter | Agent loop not built |
| Cross-reference across document types | **Foundation ready:** collections have distinct doc types with metadata | Cross-referencing logic not built |
| Structured compliance report output | Not built | M5 scope |
| Full audit trail of agent reasoning chain | **Partial:** MLflow trace structure supports nested spans; LangGraph already captures tool calls | Need OGX-specific tracing or extended LangGraph multi-hop |

**Assessment:** The infrastructure for Workflow B is in place (3 collections, metadata filtering, MCP tooling, MLflow tracing, provenance bridge). What's missing is the agentic orchestration layer that autonomously plans and executes multi-hop retrieval. M5 will evaluate OGX Responses API for this — its multi-tool orchestration and agent loop are its differentiator for this use case.

---

## 3. Gap Summary Table

### Gaps Closed by the POC (spec identified as gaps, POC addressed)

| Spec Gap | How POC Closed | Component/Decision |
|----------|---------------|-------------------|
| No query/response audit logging | MLflow traces with full span tree; per-query tags (doc_ids_cited, pipeline_run_ids) | M4 Phase 2, DEC-009 |
| No compliance/audit dashboard | Registry UI provenance views (QueryTracesPage, TraceDetailPage, DocumentProvenancePage) | M4 Phase 3, DEC-011 |
| No OpenLineage integration with RayData/Docling | `rhoai-lineage` library emits OL events from pipeline components | M2, ADR-004 |
| Marquez not integrated into RHOAI | Marquez deployed and integrated (API + Web UI, route exposed) | M2 |
| No chat UI for knowledge assistant | Chainlit deployed with streaming and tool visualization | M4 Phase 1 |
| No document version tracking at platform level | Document Registry with `content_hash`, `supersede` API, `effective_date`/`superseded_date` | M3 |
| No OOTB OpenLineage integration | `rhoai-lineage` library abstracts OL emission; naming conventions enforced | M2, ADR-004 |
| Pipeline-level metadata only | Per-document metadata via manifest (PG-020 closed) | M3 Phase 2 |

### Gaps the POC Identified That the Spec Missed

| POC Discovery | Why the Spec Missed It | Decision/Reference |
|--------------|----------------------|-------------------|
| **Two-layer lineage (ingest vs query)** | Spec framed all lineage as OpenLineage events to Marquez (Event 1–3). Doesn't account for request-level granularity that RAG query provenance requires. Marquez models datasets/jobs, not individual requests. | DEC-009 |
| **Document Registry as a first-class concern** | Spec assumes documents are tagged with metadata at ingestion time but has no concept of a persistent registry that owns document identity across pipeline runs and source URL changes. | M3, CONTEXT.md (doc_id vs source_url distinction) |
| **Separation of Discovery from Ingest** | Spec conflates "Document Ingestion" (Phase 1) as one pipeline phase. POC separates: Discovery (scan source systems, register), Building (curate collections), Ingest (fetch + process). These are distinct concerns with different triggers and responsibilities. | ADR-010, ADR-012, collection-lifecycle.md |
| **OGX opacity for lineage** | Spec assumes OGX for both ingest and query. OGX emits no OpenLineage events and provides no observability into embedding/write operations — a lineage blind spot for production governance. | ADR-003 (Lineage Implications section) |
| **Application-level vs per-query OL emission** | Spec's "Event 3" implies per-query OL events. POC proves this is wrong granularity — emit one OL event per application (graph completion), query detail in MLflow. | DEC-009 (Marquez graph completion) |
| **Embedding ISVC gap on RHOAI 3.4** | Spec assumes "RHOAI model serving for embeddings" exists. In practice, vLLM in RHOAI 3.4 doesn't support `--task=embedding`. | PG-018 |

### Gaps Remaining (spec and POC both acknowledge, not yet closed)

| Gap | Spec Section | POC ID | Priority for M5 |
|-----|-------------|--------|-----------------|
| No SharePoint/Confluence connectors | P1 Gap table | PG-010 | Low (product-level, not POC) |
| No incremental processing | P1 Gap table | PG-006 | Medium (foundations in registry) |
| No hybrid search (vector + keyword) | P3 Gap table | PG-007 | Medium (Milvus 2.4+ supports) |
| No document-level RBAC | P3 Gap table | PG-008 | High (M5 scope) |
| Agentic RAG (Workflow B) | P3 "OGX Dev Preview" | M5 scope | **Critical** (M5 headline) |
| No PII governance for document content | P4 Gap table | Not tracked | Low (application-level concern) |
| Unity Catalog integration | P5 Gap table | Not in scope | Low (external deployment, future) |
| No document pipeline monitoring (freshness, staleness) | P5 Gap table | Not tracked | Medium |
| Document lifecycle governance (exercised) | P4 Gap table | PG-026 | Medium |
| Impact analysis UI | P4 implied | M5 deferred view | Medium |

### Deliberate Divergences (POC chose differently from the spec, with rationale)

| Spec Expectation | POC Choice | Rationale | Reference |
|-----------------|-----------|-----------|-----------|
| OGX Responses API for all query modes | LangGraph + MCP for deterministic RAG (M4); OGX reserved for agentic RAG (M5) | OGX's strength is agent orchestration, not deterministic retrieval. LangGraph + `mlflow.langchain.autolog()` gives full span tree automatically — dramatically better P4 (lineage) story for Workflow A. OGX evaluated where its value is highest (multi-hop, Workflow B). | DEC-010 |
| OpenLineage Event 3 for query lineage | MLflow traces for query lineage; Marquez for pipeline lineage only | Marquez models datasets/jobs, not requests. Per-query OL events would show "collection was queried" but not which chunks/docs answered which question. MLflow traces are purpose-built for request-level provenance. | DEC-009 |
| OGX for ingest (Vector I/O) | Direct Milvus writes (the Ray team's upstream pattern) | OGX Vector I/O is opaque for lineage (no OL emission), Dev Preview, couples pipeline to OGX availability. Direct writes give full control over metadata stamping, lineage emission, and error handling. | ADR-003 |
| MLflow-Marquez bridge as primary lineage mechanism | Bridge OFF; direct OL emission from components | Bridge creates synthetic/duplicate nodes; naming not controllable; direct emission is cleaner and more predictable. Bridge available as opt-in for evaluation. | ADR-004 |
| Single unified pipeline (ingestion → processing → storage) | Separated concerns: Register → Build Collection → Pipeline Run (Acquire → Parse → Ingest) | Spec's 3-phase pipeline conflates curation with execution. Separating them enables: documents registered without processing, collections curated without triggering ingest, pipelines re-run without re-registering. | Collection lifecycle, ADR-010, ADR-012 |

---

## 4. What the POC Proves

### 1. The five-pillar architecture applies to enterprise RAG without a feature store

The POC demonstrates all five pillars operating for a knowledge retrieval workload with zero predictive AI, no feature engineering, and no Feast. The pillar model is technology-neutral: P1 is document connectors (not database connectors), P2 is RayData + Docling (not Feast materialization), P3 is vector search via MCP (not feature serving), P4 is lineage across both layers, P5 is a provenance portal.

### 2. Two-layer lineage is the correct architecture for RAG governance

The single most important architectural finding. Pipeline-time lineage (OpenLineage → Marquez) and query-time lineage (MLflow traces) serve fundamentally different purposes and operate at different granularities. The `pipeline_run_id` bridge connects them. This pattern should be adopted as the canonical lineage architecture for RAG scenarios in the Data Strategy proposal.

### 3. Answer provenance is achievable end-to-end

Chain 1 is fully verified: MLflow trace → retrieved chunks (doc_id, pipeline_run_id) → Registry (source_url, metadata) → Marquez (ingest lineage graph). A compliance officer can trace any AI-generated answer back to its source documents. This directly addresses NAIC Model Bulletin and State DOI audit requirements from the spec's regulatory context.

### 4. Document identity requires a dedicated registry

The spec assumes documents are tagged at ingestion time and their identity lives in Milvus metadata. The POC proves this is insufficient: documents need stable identity (`doc_id`) that persists across pipeline re-runs, source URL changes, and multi-collection membership. The Document Registry is a first-class system component, not an afterthought.

### 5. Direct Milvus writes are superior to OGX Vector I/O for production lineage

OGX Vector I/O is a lineage blind spot — it emits no OpenLineage events and conflates embedding + storage in an opaque call. Direct Milvus writes make every step observable, metadata controllable, and lineage emittable. This has implications for how the Data Strategy proposal recommends P3 implementation.

### 6. The pipeline can process real insurance documents at scale

11 real PDFs (12MB corpus including a 6.9MB FEMA manual), 363 vectors, ~7 min E2E. Complex table layouts, multi-page documents, and diverse formats all processed successfully. Docling's layout-aware parsing preserves structural relationships. This validates RayData + Docling as the production compute pattern for document processing.

### 7. LangGraph + MLflow autolog provides production-grade RAG observability

`mlflow.langchain.autolog()` captures the full trace tree automatically — no manual instrumentation needed. Every tool call, every retrieved chunk (with doc_id, similarity score, metadata), every LLM generation is recorded. This is the level of observability the spec's P4 demands but couldn't achieve via OpenLineage alone.

### 8. A federated provenance portal is feasible and high-impact

The Registry UI federating MLflow + Marquez + Registry APIs demonstrates that the "no unified provenance UI" gap is closable without building a dedicated lineage product. A compliance officer can navigate from document → queries that cited it → ingest pipeline → source URL without opening any backend system.

---

## 5. Recommendations for M5 and Beyond

### M5 Critical Path (Agentic RAG + Hardening)

| Priority | Item | Rationale |
|----------|------|-----------|
| **1** | OGX Responses API for Workflow B | M5 headline: evaluate OGX for multi-hop retrieval across all 3 collections. Direct comparison with M4's LangGraph approach on observability, developer experience, and orchestration quality. |
| **2** | Multi-collection query support | Extend MCP server to route queries to appropriate collection(s) based on question type. Agent decides which collection to search (underwriting_guidelines for policy questions, regulatory_bulletins for compliance, iso_forms for form references). |
| **3** | RBAC at query time (PG-008) | Application-level filtering: user role → permitted collections/document types. Critical for the spec's "restricted documents should only be retrievable by authorized users." |
| **4** | Impact analysis in provenance portal | "If I update/remove this document, which apps and queries are affected?" Reverse lookup via MLflow trace search by doc_id. Closes the spec's P4 "impact analysis" requirement. |
| **5** | Document lifecycle exercised (PG-026) | Supersede a document, re-run pipeline, verify old vectors removed and new version indexed. Exercises the version tracking the spec calls for. |

### Post-M5 / Product Direction

| Priority | Item | Rationale |
|----------|------|-----------|
| **6** | Hybrid search (PG-007) | Legal/regulatory terminology ("additional insured", "occurrence basis") benefits from keyword matching. Milvus 2.4+ supports; implement dual-vector schema. |
| **7** | Incremental processing (PG-006) | Registry already tracks `content_hash` and `last_ingested`. Pipeline needs delta logic: skip unchanged docs, re-process only modified. |
| **8** | Production connectors (PG-010) | SharePoint, Confluence connectors for real enterprise source systems. Likely product-level work (RFE-001 scope expansion). |
| **9** | Unity Catalog evaluation | Deploy OSS on OpenShift alongside RHOAI. Assess overlap with Registry (document identity, collection management) and Marquez (lineage visualization). |
| **10** | Embedding ISVC (PG-018) | Re-evaluate on RHOAI 3.5+ when vLLM supports `--task=embedding`. Remove local sentence-transformers workaround. |

### Proposal Updates Recommended

Based on POC findings, the Data Strategy Scenario B spec should be updated:

1. **Pillar 4: Add two-layer lineage framing.** Replace "Event 3: Query/Retrieval" (OL event to Marquez) with the two-layer model: Marquez for pipeline-time lineage (dataset/batch), MLflow traces for query-time lineage (request-level). Application-level OL for graph completion.

2. **Pillar 1: Add Document Registry concept.** The spec's ingestion phase needs a persistent registry that owns document identity separately from Milvus metadata. Documents are registered (identity), curated into collections (intent), then processed (execution).

3. **Pillar 3: Acknowledge LangGraph as a valid Workflow A implementation.** OGX Responses API is correct for agentic RAG but is not the only valid abstraction for deterministic RAG. LangGraph + MCP with MLflow autolog provides superior observability for deterministic patterns.

4. **Architecture diagram: Add Document Registry.** Between P1 (connectors) and P2 (compute), there should be a registry node that mediates document identity, collection membership, and pipeline triggering.

5. **Gap table: Add PG-018 (embedding ISVC limitation).** RHOAI 3.4 doesn't support embedding InferenceServices — relevant for any deployment today.

---

## Appendix: Production Gap Coverage

The POC tracks 53 production gaps (10 closed/mitigated, 43 open). The most critical gaps for production readiness:

| Gap | Impact | Closable By |
|-----|--------|-------------|
| PG-008 (No RBAC) | Users can query any document regardless of role | M5 |
| PG-006 (No incremental processing) | Full re-processing wastes compute | M5+ |
| PG-010 (Mock connectors only) | Can't connect to real enterprise sources | Product (RFE-001) |
| PG-001 (No Marquez auth) | Lineage backend is world-readable | M5 (OAuth proxy) |
| PG-011 (No TLS) | Internal services communicate unencrypted | Platform config |
| PG-007 (No hybrid search) | Poor recall on precise legal terminology | Milvus 2.4+ upgrade |

---

## Appendix: Cluster State Summary (Post-M4)

| Component | Status | Vectors/Data |
|-----------|--------|--------------|
| Milvus | Running (3 pods) | 363 vectors across 3 collections |
| Document Registry | Running | 20 documents, 3 collections |
| Marquez | Running (API + Web) | Full ingest lineage graph; `underwriter_chat` downstream |
| MLflow | Running (cluster-wide) | Query traces with full span trees |
| Granite LLM | Running (A100 GPU) | vLLM InferenceService for generation |
| KFP (DSPA) | Running (6 pods) | Pipeline orchestration ready |
| Query Service | Local only | Chainlit + LangGraph + MCP (deployment pending) |
