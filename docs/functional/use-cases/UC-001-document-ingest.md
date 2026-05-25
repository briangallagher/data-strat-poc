# UC-001: Document Ingest Pipeline

**Primary Actor:** Data Engineer
**Goal:** Process a corpus of PDF documents into searchable vector embeddings in Milvus
**Scope:** Ingest pipeline (connectors → processing → storage)
**Level:** User goal
**Milestone:** M1 (core pipeline), M3 (connectors extend the input sources)

## Preconditions

- Cluster deployed with RHOAI, KubeRay, Milvus, DSPA (see [prerequisites](../../operations/prerequisites.md))
- Document corpus available (PDFs in S3/MinIO staging area or via connector)
- Embedding model deployed and serving (vLLM InferenceService or equivalent)
- Milvus collection created with appropriate schema

## Main Success Scenario

1. Data Engineer triggers the KFP ingest pipeline (via KFP UI, SDK, or scheduled run)
2. Pipeline acquires documents from the configured source (S3 staging area; later: connectors)
3. RayData + Docling parses each PDF — extracts text, tables, and document structure
4. Parsed content is chunked using structure-aware chunking (section-level, table-level, paragraph-level)
5. Each chunk is embedded via the configured embedding service
6. Embeddings + metadata are inserted into the target Milvus collection, partitioned by line of business
7. Each vector carries `pipeline_run_id`, `source_document_id`, and standard metadata (LOB, doc type, effective date)
8. Pipeline run is tracked in MLflow with parameters (corpus size, embedding model, chunk strategy) and metrics (chunks created, duration, errors)
9. OpenLineage events are emitted to Marquez for pipeline-time lineage
10. KFP pipeline completes successfully with all steps green

## Extensions (Alternate Flows)

- **2a.** Source is a connector (M3): Connector acquires documents from Confluence/SharePoint/DMS → stages to S3 → pipeline continues from step 3
- **3a.** Docling fails to parse a document (corrupted PDF, unsupported format): Log the failure, skip the document, continue processing remaining docs. Report skipped docs in pipeline metrics.
- **5a.** Embedding service is unavailable: Pipeline fails with clear error. KFP retry policy triggers re-attempt. If persistent, pipeline fails and alerts.
- **6a.** Milvus write fails (connection, capacity): Pipeline fails with clear error. Chunks already written are idempotent (upsert by chunk ID). Re-run pipeline to complete.
- **6b.** Milvus collection doesn't exist: Pipeline fails with clear error indicating missing collection. Data Engineer creates collection (via runbook) and re-runs.
- **10a.** Pipeline partially succeeds (some docs processed, some failed): Pipeline reports partial success with list of failed documents. Data Engineer reviews failures and re-runs for failed subset.

## Postconditions

### Success

- All source documents have been parsed, chunked, embedded, and stored in Milvus
- Every vector in Milvus carries `pipeline_run_id` linking it to the KFP run and lineage graph
- MLflow experiment run records pipeline parameters and metrics
- Marquez lineage graph shows: source → staging → processing → Milvus collection
- Milvus collection is queryable (similarity search returns relevant chunks)

### Failure

- No partial data corruption — either chunks are correctly written or the pipeline reports what failed
- Failed documents are identifiable for re-processing
- No orphaned data in Milvus (idempotent writes via chunk ID)
- Pipeline failure is visible in KFP UI with clear error context

## Non-Functional Requirements

- Pipeline must be **idempotent** — re-running on the same corpus produces the same result
- Pipeline must be **resumable** — partial failures don't require full re-processing (stretch goal: checkpoint mechanism)
- Pipeline must handle **edge cases**: empty PDFs, image-only PDFs, very large tables, multi-column layouts
- Pipeline must be **observable**: KFP UI shows step status, MLflow tracks metrics, Marquez tracks lineage

## Related

- **ADRs:** ADR-001 (RayData+Docling), ADR-002 (chunking+Milvus), ADR-003 (OGX role)
- **Technical:** `docs/technical/raydata-docling.md`, `docs/technical/milvus-ingestion.md`
- **User Journey:** UJ-002 (Data Engineer Ingest)
- **Requirements:** FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007
- **Runbook:** `docs/operations/runbooks/run-ingest-pipeline.md`
- **Persona:** Data Engineer (see `docs/user-experience/personas.md`)
