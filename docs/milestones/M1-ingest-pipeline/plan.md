# M1: Ingest Pipeline

**Status:** Complete
**Started:** 2026-05-23
**Completed:** 2026-05-25

## Goal

Deploy and verify a KFP-orchestrated document ingest pipeline that parses PDFs with RayData + Docling, embeds chunks via vLLM, and stores vectors in Milvus — starting by validating Saad's components standalone, then incrementally adapting for Scenario B requirements.

## Objectives

1. Saad's pipeline components (PR #53) run successfully as-is on our cluster (Phase 0 baseline)
2. Incremental changes add `pipeline_run_id`, `source_document_id`, Scenario B metadata, and collection design
3. Pipeline is idempotent — re-running on the same corpus produces the same result
4. Verified at two scales: small (2-3 PDFs) and medium (10-15 PDFs)
5. Component extraction candidates identified and documented

## Approach: Validate First, Adapt Incrementally

**Phase 0 (Baseline):** Deploy Saad's pipeline components exactly as shipped in PR #53. Run them with his default configuration and a small test corpus. Verify the pipeline works end-to-end before changing anything. This proves the infrastructure and identifies any cluster-specific issues.

**Phase 1 (Adapt):** Incrementally modify components for Scenario B:
- Add `pipeline_run_id` and `source_document_id` to Milvus vectors
- Adjust Milvus collection schema for P&C metadata (LOB, doc type, effective date)
- Adjust chunking strategy if needed (HybridChunker tuning)
- Add our document corpus alongside Saad's test data

**Phase 2 (Verify):** Run at medium scale with v1's P&C corpus. Verify quality, performance, idempotency.

## Scope

### In Scope

- **Infrastructure manifests:** Milvus (Helm), KubeRay, DSPA, MinIO/S3, embedding model InferenceService
- **Saad's KFP pipeline components** (from merged PR #53):
  - `parse_and_chunk` — RayJob + Docling parsing + HybridChunker → S3 JSONL
  - `ingest_to_milvus` — read chunks from S3, embed via vLLM endpoint, insert into Milvus
  - `download_model` — HuggingFace model download to PVC with cache-skip sentinel
  - `deploy_embedding_model` — KServe InferenceService for embedding (vLLM `--task embedding`)
- **KFP pipeline definition** orchestrating the above with parallel data/model chains
- **Incremental adaptations** for Scenario B (metadata, collection design, corpus)
- **Milvus collection design:** schema, partitioning by LOB, HNSW index, cosine similarity
- **Document corpus:** Saad's test data (Phase 0) + v1's 15 public-domain P&C docs (Phase 1-2)
- **Runbook:** `docs/operations/runbooks/run-ingest-pipeline.md`
- **Technical deep dives:** `docs/technical/raydata-docling.md`, `docs/technical/milvus-ingestion.md`
- **ADRs:** ADR-001 (RayData+Docling pipeline design), ADR-002 (chunking+Milvus)
- **Component extraction assessment**

### Out of Scope

- OGX (deferred to M4 per ADR-003)
- MLflow tracking (M2)
- OpenLineage / Marquez (M2)
- Connectors (M3) — documents are pre-staged in S3
- Query path (M4)
- Auth, RBAC, TLS (tracked as production gaps)

## Acceptance Criteria

- [x] All infrastructure manifests deploy cleanly to `data-strat-poc` namespace
- [x] **Phase 0 (Saad's baseline):**
  - [x] Saad's pipeline data chain runs on our cluster (with auth fixes on fork branch)
  - [x] parse_and_chunk + ingest_to_milvus complete (data chain green)
  - [x] Milvus collection queryable (5 chunks, real P&C content)
  - [x] Issues documented (`docs/working/m1-phase0-lessons-learned.md`, PG-014 through PG-019)
  - [x] Model chain (download_model + model_deployment) — download works; deploy blocked by PG-018 (deferred to M4)
- [x] **Phase 1 (Scenario B adaptations):**
  - [x] Milvus collection schema includes: pipeline_run_id, source_document_id, chunk_text, LOB, doc_type, effective_date
  - [x] Every vector has `pipeline_run_id` set
  - [x] Pipeline runs with 2-3 small P&C PDFs from v1 corpus
  - [x] Chunks are correct (manual inspection: text extracted, tables handled, structure preserved)
  - [x] Embeddings are sane (dimension matches model, non-zero, normalized)
- [x] **Phase 2 (Medium scale):**
  - [x] Pipeline handles full v1 corpus (11 docs) without failure
  - [x] Edge cases handled: empty sections, large tables, multi-column layouts
  - [x] Pipeline is idempotent: re-run produces same chunk count (312) and same vectors
  - [x] Performance acceptable (~7 minutes for 11 docs — well under 15 min target)
- [x] Runbook written and verified (someone can follow it from scratch)
- [x] ADR-002 written (ADR-001 covered by ADR-002 + ADR-003 + technical deep dive)
- [x] Technical deep dives written for RayData+Docling and Milvus ingestion
- [x] Getting-started doc updated with M1 deployment steps
- [x] Production gaps documented for anything that falls short of enterprise standard
- [x] Component extraction assessment documented (in M1 checkpoint)
- [x] No regressions from M0

## Tasks

### Infrastructure (tasks 1-7)

| # | Task | Effort | Status | Notes |
|---|------|--------|--------|-------|
| 1 | Write Milvus manifest (Helm values, SCC, namespace) | 2 hr | Done | Helm install with standalone mode, anyuid SCC. Service is `milvus` not `milvus-standalone`. 500Gi MinIO default — PG-017. |
| 2 | Write MinIO/S3 manifest | 1 hr | Done | Deployment + Service. Buckets: `rag-chunks`, `pipeline-artifacts`. MC_CONFIG_DIR=/tmp/.mc required. |
| 3 | Write DSPA manifest | 1 hr | Done | External storage config — omit `minio` block, point to minio-service. |
| 4 | Write embedding model InferenceService manifest | 1 hr | Skipped | RHOAI 3.4 vLLM lacks `--task=embedding` (PG-018). Local sentence-transformers in ingest_to_milvus works. |
| 5 | Write KubeRay / RayCluster config | 1 hr | Done | KubeRay managed by RHOAI. RayJob created by parse_and_chunk component. |
| 6 | Deploy all infrastructure to cluster | 2 hr | Done | All pods healthy. RBAC for pipeline SA created manually (PG-015). |
| 7 | Prepare test data on PVC | 30 min | Done | 2 PDFs from v1 corpus uploaded via data-loader pod (UBI image, not ubi-minimal — needs tar). |

### Phase 0: Validate Saad's Baseline (tasks 8-11)

| # | Task | Effort | Status | Notes |
|---|------|--------|--------|-------|
| 8 | Fork pipelines-components, create data-strat-poc branch | 1 hr | Done | `briangallagher/pipelines-components:data-strat-poc`. Needed due to auth fixes. |
| 9 | Fix K8s auth for KFP pods | 4 hr | Done | 7 iterations. Manual SA token loading + explicit ApiClient + bypass codeflare submit. See lessons learned. |
| 10 | Compile and upload pipeline, run on cluster | 2 hr | Done | 11 runs total. Data chain (parse+ingest) PASSES. Model chain blocked by PVC + VLLM_IMAGE constant. |
| 11 | **Document baseline results** | 2 hr | Done | `docs/working/m1-phase0-lessons-learned.md`. 6 new production gaps (PG-014 through PG-019). |

### Phase 1: Scenario B Adaptations (tasks 12-18)

| # | Task | Effort | Status | Notes |
|---|------|--------|--------|-------|
| 12 | Design Milvus collection schema for Scenario B | 1 hr | Done | 10-field schema: id, source_file, source_document_id, pipeline_run_id, chunk_index, text, lob, doc_type, effective_date, embedding. ADR-002. |
| 13 | Adapt `ingest_to_milvus` for Scenario B metadata | 2 hr | Done | Writes all 10 fields. pipeline_run_id added at ingest step. HNSW index (M=16, COSINE). |
| 14 | Adapt `parse_and_chunk` JSONL output for metadata | 1 hr | Done | JSONL includes source_document_id (from filename) + metadata from env vars. PG-020 for per-doc metadata. |
| 15 | Prepare v1 P&C corpus (small subset) in S3 | 30 min | Done | 2-3 small PDFs uploaded via data-loader pod. |
| 16 | **Small-scale verification** | 2 hr | Done | All metadata fields present. pipeline_run_id links to KFP run. Similarity search returns relevant results. |
| 17 | Fix issues from small-scale verification | 2-4 hr | Done | PG-020 identified (pipeline-level metadata). Schema and chunking work correctly. |
| 18 | Write ADR-002 (chunking + Milvus collection design) | 1 hr | Done | ADR-002-chunking-milvus-schema.md. Covers schema, HNSW index, metadata flow, collection naming. |

### Phase 2: Scale Up and Verify (tasks 19-22)

| # | Task | Effort | Status | Notes |
|---|------|--------|--------|-------|
| 19 | Upload full v1 corpus (10-15 PDFs) to S3 | 30 min | Done | 11 PDFs from v1 P&C corpus uploaded. |
| 20 | **Medium-scale verification** | 2 hr | Done | 11 PDFs → 312 vectors. ~7 min e2e. All edge cases handled. |
| 21 | Fix issues from medium-scale verification | 2-4 hr | Done | No blocking issues at this scale. Performance within target (<15 min for 11 PDFs). |
| 22 | **Idempotency verification** | 1 hr | Done | Re-run with `drop_existing=true` produces same 312 vectors. |

### Documentation (tasks 23-30)

| # | Task | Effort | Status | Notes |
|---|------|--------|--------|-------|
| 23 | Write ADR-001 (RayData+Docling pipeline design) | 1 hr | Skipped | Covered by ADR-002 (chunking+schema) and ADR-003 (OGX role). Separate ADR-001 not needed — the technical deep dive in raydata-docling.md serves this purpose. |
| 24 | Write `docs/technical/raydata-docling.md` | 1 hr | Done | Technical deep dive: RayJob submission, Docling actors, HybridChunker, SA token fix, config, Mermaid diagram. |
| 25 | Write `docs/technical/milvus-ingestion.md` | 1 hr | Done | Technical deep dive: 10-field schema, HNSW index, metadata flow, embedding modes, batch processing. Mermaid diagrams. |
| 26 | Write `docs/operations/runbooks/run-ingest-pipeline.md` | 1 hr | Done | Step-by-step: compile, upload, create run with all params, monitor, verify. Troubleshooting table. |
| 27 | Update `docs/operations/getting-started.md` with M1 steps | 30 min | Done | M1 deployment steps, Milvus collection note, embedding model note, tag table populated. |
| 28 | Update `docs/operations/prerequisites.md` with actual measurements | 30 min | Done | Actual CPU/memory/storage from M1: 4 CPU/8GB Ray workers, 312 vectors, ~7 min e2e. |
| 29 | Document production gaps found during M1 | 30 min | Done | PG-014 through PG-020 logged. Summary: 20 total, 2 mitigated, 18 open. |
| 30 | **Component extraction assessment** | 1 hr | Done | Included in M1 checkpoint. Key finding: auth fix + metadata adaptations generalise for upstream contribution. |
| 31 | Write M1 checkpoint | 1 hr | Done | Full checkpoint: verification results, 7 production gaps, cluster state, resume context, lessons learned, tags. |

**Estimated total effort:** 35-45 hours

## Component Extraction Assessment

At M1 completion, assess each component for extraction potential per ADR-007 criteria (stable interface, independent release cadence, different tech stack).

| Component | Current Location | Extraction Candidate? | Assessment Criteria |
|-----------|-----------------|----------------------|---------------------|
| `parse_and_chunk` | `pipelines/components/` (adapted from Saad) | **Contribute upstream** | If adaptations are general-purpose, PR to `opendatahub-io/pipelines-components` |
| `ingest_to_milvus` | `pipelines/components/` (adapted from Saad) | **Contribute upstream** | Same — Scenario B metadata could be parameterised for reuse |
| `download_model` | `pipelines/components/` (from Saad) | **No** (already upstream) | Minimal changes; use upstream directly |
| `deploy_embedding_model` | `pipelines/components/` (from Saad) | **No** (already upstream) | Minimal changes; use upstream directly |
| KFP pipeline definition | `pipelines/` | **No** | Project-specific orchestration; not reusable |
| Milvus Helm values | `manifests/milvus/` | **No** | Cluster-specific configuration |
| Docling Ray worker image | `images/` (if custom) | **Evaluate** | If Saad's `quay.io/rhoai-szaher/docling-ray:latest` works, use it. If custom image needed, may warrant own repo + CI. |

**Key question for M1:** Do our Scenario B adaptations to `parse_and_chunk` and `ingest_to_milvus` generalise (parameterised metadata fields) or specialise (P&C-specific logic)? If they generalise, contribute upstream. If they specialise, keep in this repo.

### Future Milestone Extraction Outlook

| Milestone | Likely Extraction Candidates |
|-----------|------------------------------|
| M2 (MLflow) | `rhoai-lineage` Python library — **dedicated repo + PyPI** once API stabilises |
| M3 (Connectors) | Connector package — **dedicated repo + PyPI** if interface proves general |
| M4 (Query) | None expected — OGX integration is configuration, not a reusable component |
| M5 (Hardening) | Lineage operator — **dedicated repo** (Go, different tech stack) if built |

## Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| OpenShift cluster with RHOAI 3.5+ | Brian | Available |
| GPU node (L40S/A100/H100, 24GB+ VRAM) | Cluster | Verify |
| KubeRay operator installed | RHOAI | Installed via RHOAI |
| Milvus operator or Helm chart | Zilliz (Certified Partner) | Available |
| Saad's merged pipeline components | `opendatahub-io/pipelines-components` main | Available |
| v1 document corpus (15 P&C PDFs) | v1 repo | Available at `data-strategy-poc/corpus/` |
| HuggingFace token (gated model access) | Brian | Available |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Saad's pipeline doesn't run on our cluster (image pulls, RBAC, SCC) | Medium | Medium | Phase 0 catches this early before any customisation |
| Milvus Helm deployment issues (SCC, storage) | Medium | Medium | v1 solved these (DEC-008); reuse manifests |
| Docling parsing failures on edge-case PDFs | Medium | Low | Phase 0 uses Saad's known-good data; P&C edge cases in Phase 1-2 |
| RayJob scheduling issues (GPU contention, Kueue) | Medium | Medium | Use `bypass_kueue` flag initially |
| Embedding model InferenceService not starting | Low | High | Verify GPU availability first; fall back to local sentence-transformers |
| Scenario B metadata adaptations break Saad's components | Low | Medium | Incremental changes with verification after each; keep Saad's baseline as reference |

## Resource Requirements

| Resource | Specification | Purpose |
|----------|--------------|---------|
| GPU | 1x NVIDIA L40S/A100 (24GB+ VRAM) | Embedding model serving (vLLM) |
| CPU workers | 4 vCPU, 16GB RAM per Ray worker (2-4 workers) | RayData + Docling document processing |
| Ray head | 2 vCPU, 8GB RAM | Ray head node for RayJob |
| MinIO storage | 5GB | Document staging, pipeline artifacts, JSONL chunks |
| Milvus storage | 2GB | Vector storage for 15-doc corpus (~500 chunks) |
| PVC | 20GB RWO | Model weights cache |

## Verification Plan

### Phase 0: Saad's Baseline

**What:** Run Saad's pipeline exactly as shipped on our cluster.

**How:**
1. Deploy infrastructure (Milvus, MinIO, DSPA, embedding ISVC, KubeRay)
2. Clone Saad's components and pipeline from `opendatahub-io/pipelines-components`
3. Compile and upload pipeline — no modifications
4. Trigger pipeline with Saad's default parameters and test data
5. Verify all steps green, Milvus queryable

**Pass:** Pipeline completes, Milvus contains vectors, similarity search works.
**Fail:** Any infrastructure or pipeline step fails.

### Phase 1: Scenario B (Small Scale, 2-3 PDFs)

**What:** Run adapted pipeline with small P&C corpus.

**How:**
1. Apply Scenario B metadata adaptations
2. Upload 2-3 small P&C PDFs
3. Run pipeline
4. Inspect JSONL chunks (metadata present, structure preserved)
5. Query Milvus (similarity search, metadata filters, pipeline_run_id present)

**Pass:** Chunks correct, metadata present, Milvus queryable with filters, `pipeline_run_id` set.
**Fail:** Chunks malformed, metadata missing, queries return garbage.

### Phase 2: Medium Scale (10-15 PDFs)

**What:** Run with full v1 corpus.

**How:**
1. Upload full corpus
2. Run pipeline
3. Verify chunk count (~300-400), edge cases, performance
4. Re-run: verify idempotency

**Pass:** All docs processed, edge cases handled, idempotent, under 15 minutes.
**Fail:** Any doc fails, duplicates on re-run, over 30 minutes.

### Regression Checks

- M0 documentation still correct and accessible
- All M0 artifacts intact

## Documentation Deliverables

- [x] ADR-002: Chunking strategy and Milvus ingestion (ADR-001 scope covered by ADR-002 + ADR-003)
- [x] Technical: `docs/technical/raydata-docling.md`
- [x] Technical: `docs/technical/milvus-ingestion.md`
- [x] Runbook: `docs/operations/runbooks/run-ingest-pipeline.md`
- [x] Update: `docs/operations/getting-started.md` (M1 section)
- [x] Update: `docs/operations/prerequisites.md` (actual measurements)
- [x] Update: `docs/production-gaps.md` (M1 gaps — PG-014 through PG-020)
- [x] Component extraction assessment (in M1 checkpoint)
- [x] Checkpoint: `docs/milestones/M1-ingest-pipeline/checkpoint.md`
