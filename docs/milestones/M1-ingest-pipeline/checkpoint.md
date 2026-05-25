# M1 Checkpoint: Ingest Pipeline

**Date:** 2026-05-25
**Status:** Complete with gaps

## What Was Built

A KFP-orchestrated document ingest pipeline that parses PDFs with RayData + Docling, generates embeddings with Granite Embedding 125M (local sentence-transformers), and stores vectors with full Scenario B metadata in Milvus. Delivered across three phases:

### Phase 0: Baseline Validation

Deployed Saad's pipeline components (PR #53) on the `data-strat-poc` cluster exactly as shipped. Validated the data chain (parse_and_chunk → ingest_to_milvus) end-to-end. Identified and fixed critical K8s auth issue (PG-014) that blocked RayJob submission from KFP pods. Model chain (download_model + deploy_embedding_model) was tested but partially blocked — LLM deployment is M4 scope, and RHOAI 3.4 vLLM lacks `--task=embedding` (PG-018).

**Result:** 2 PDFs processed, 5 chunks in Milvus, data chain fully green. 6 production gaps documented (PG-014 through PG-019).

### Phase 1: Scenario B Adaptations

Extended the pipeline for Scenario B requirements:
- Milvus collection schema expanded to 10 fields (ADR-002): `pipeline_run_id`, `source_document_id`, `lob`, `doc_type`, `effective_date` added alongside baseline fields
- HNSW index replaced IVF_FLAT (better for incremental inserts and sub-1M collections)
- Metadata flow: pipeline params → env vars → JSONL → Milvus vectors
- Verified with 2–3 small P&C PDFs from the v1 corpus

**Result:** All metadata fields present on every vector. `pipeline_run_id` correctly links vectors to KFP runs. PG-020 identified (pipeline-level metadata only, no per-document).

### Phase 2: Full Corpus Verification

Ran the adapted pipeline against the full v1 P&C corpus (11 PDFs). Verified at medium scale: performance, edge case handling, idempotency.

**Result:** 11 PDFs → 312 vectors. ~7 minutes end-to-end. Idempotent (re-run with `drop_existing=true` produces identical count). All acceptance criteria met for the data chain.

## Verification Results

| Test | Method | Result | Evidence |
|------|--------|--------|----------|
| Infrastructure deploys cleanly | `oc get pods` after full deploy sequence | **Pass** | All pods Running in `data-strat-poc` namespace |
| Phase 0: data chain (parse + ingest) | Pipeline run with 2 test PDFs | **Pass** | 5 chunks in Milvus, queryable with similarity search |
| Phase 0: model chain | Pipeline run (download_model + deploy_embedding_model) | **Partial** | download_model passes; deploy_embedding_model blocked (PG-018). Deferred to M4. |
| Phase 1: Scenario B metadata | Query Milvus for all 10 fields | **Pass** | All vectors have source_document_id, pipeline_run_id, lob, doc_type, effective_date |
| Phase 1: HNSW index | Collection info query | **Pass** | HNSW with M=16, efConstruction=256, COSINE metric |
| Phase 2: full corpus (11 PDFs) | Pipeline run with v1 P&C corpus | **Pass** | 312 vectors, ~7 min e2e, no failures |
| Phase 2: idempotency | Re-run pipeline with `drop_existing=true`, compare counts | **Pass** | Same 312 vectors on second run |
| Phase 2: similarity search | Query with "property insurance coverage" | **Pass** | Relevant results returned with cosine scores > 0.5 |
| Runbook verified | Follow run-ingest-pipeline.md from scratch | **Pass** | All steps reproducible |
| ADRs written | ADR-002 (schema), ADR-003 (OGX role) | **Pass** | Both reviewed and complete |
| Technical deep dives | raydata-docling.md, milvus-ingestion.md | **Pass** | Both written following doc-standards template |

### Regression Results

| Previous Milestone | Result | Notes |
|--------------------|--------|-------|
| M0 (Documentation) | **Pass** | All M0 docs intact and accessible. Architecture overview, functional specs, decisions log, production gaps all current. |

## Production Gaps Identified

| Gap ID | Description | Logged in production-gaps.md |
|--------|-------------|------------------------------|
| PG-014 | KFP pods lack K8s API access by default (KUBERNETES_SERVICE_HOST stripped) | Yes — **Mitigated** (SA token workaround on fork) |
| PG-015 | No RBAC automation for pipeline SA (RayJob, KServe permissions created manually) | Yes |
| PG-016 | Milvus deployed with anyuid SCC | Yes |
| PG-017 | 500Gi MinIO PVC from Milvus Helm defaults (oversized) | Yes |
| PG-018 | RHOAI 3.4 vLLM lacks `--task=embedding` | Yes — **Mitigated** (local sentence-transformers works) |
| PG-019 | Local sentence-transformers downloads embedding model (~500MB) every run | Yes |
| PG-020 | Pipeline-level metadata only — all docs in a run get same LOB/doc_type/effective_date | Yes |

**Total gaps at M1 completion:** 20 (2 mitigated, 18 open). PG-001 through PG-013 from M0 planning, PG-014 through PG-020 discovered during M1.

## Cluster State

**Namespace:** `data-strat-poc`

| Component | Status | Details |
|-----------|--------|---------|
| Milvus (standalone, Helm) | Running | `underwriting_guidelines` collection: 312 vectors, HNSW index, 10-field schema |
| MinIO (pipeline storage) | Running | Buckets: `rag-chunks` (input PDFs + JSONL output), `pipeline-artifacts` |
| Milvus MinIO (Helm-managed) | Running | 500Gi PVC (PG-017 — oversized) |
| DSPA (KFP v2) | Running | 6 `ds-pipeline-*` pods. 11+ pipeline runs in history. |
| data-pvc | Bound (5Gi) | 11 PDFs from v1 P&C corpus |
| model-cache-pvc | Bound (50Gi) | Mistral 7B cached (for M4) |
| mariadb-dspa | Bound (10Gi) | KFP metadata |
| Pipeline SA RBAC | Applied | Role + RoleBinding for RayJob, KServe, HardwareProfile CRDs |

**Repos:**

| Repo | Branch | Tag | State |
|------|--------|-----|-------|
| `data-strat-poc` | main | `m1-complete` | All docs, manifests, compiled pipeline YAML |
| `briangallagher/pipelines-components` | `data-strat-poc` | `m1-complete` | Fork with SA token auth fix + Scenario B metadata adaptations |

## How to Resume

### For M2 (Lineage + MLflow)

1. **Check out `m1-complete` tag** on both repos to start from known-good state
2. **Pipeline is operational** — the ingest pipeline runs as-is; M2 adds OpenLineage emission and MLflow tracking to the existing components
3. **Key entry points:**
   - `ingest_to_milvus` — wrap embed and insert calls with OpenLineage event emission
   - `parse_and_chunk` — emit OL events for S3 reads/writes
   - New: MLflow tracking server deployment (manifests needed)
   - New: Marquez/OpenLineage backend deployment
4. **The `pipeline_run_id` on every Milvus vector** is the bridge between pipeline-time lineage (Marquez) and query-time lineage (MLflow). This was validated in M1.
5. **Read:** `projects/data-strategy/docs/poc/lineage/` for lineage scenarios and library design

### For Pipeline Changes

1. Clone the pipelines-components fork to `/tmp` (file watcher issue)
2. Edit components on the `data-strat-poc` branch
3. Recompile with `kfp.compiler.Compiler().compile()`
4. Upload via curl to DSP route
5. See [run-ingest-pipeline.md](../../operations/runbooks/run-ingest-pipeline.md)

### Key Files

| File | Purpose |
|------|---------|
| `docs/operations/runbooks/run-ingest-pipeline.md` | How to run the pipeline |
| `docs/operations/getting-started.md` | Full deployment from scratch |
| `docs/technical/raydata-docling.md` | How parse_and_chunk works |
| `docs/technical/milvus-ingestion.md` | How ingest_to_milvus works |
| `docs/architecture/adrs/ADR-002-chunking-milvus-schema.md` | Schema and index design |
| `docs/working/m1-phase0-lessons-learned.md` | Detailed Phase 0 debug log |
| `docs/production-gaps.md` | All known gaps with IDs |

## Lessons Learned

### What Went Well

- **Validate-first approach paid off.** Phase 0 (run Saad's code unchanged) caught the K8s auth issue early, before any Scenario B customisation. All 7 iterations of the auth fix were on a known baseline.
- **S3 intermediate storage is valuable.** JSONL between parse and ingest steps enabled debugging each step independently and retrying ingest without re-parsing.
- **Local embedding mode is a good fallback.** When vLLM `--task=embedding` was blocked (PG-018), local sentence-transformers worked immediately. No GPU needed for the ingest pipeline.
- **ADR-003 decision vindicated.** Direct Milvus writes gave full control over schema, metadata, and error handling — exactly what was needed for Scenario B. OGX Vector I/O would have been a black box.
- **Incremental phases.** Phase 0 → Phase 1 → Phase 2 progression kept each step small and verifiable.

### What Didn't Go Well

- **K8s auth fix took 7 iterations (PG-014).** The interaction between RHOAI's env var stripping, codeflare-sdk's client creation, and the kubernetes Python client's configuration precedence was deeply non-obvious. Better upstream documentation or SDK handling would have saved ~4 hours.
- **File watcher deleting `component.py`.** A local development environment issue (likely Cursor indexer) that forced using `/tmp` clones. Root cause still unknown — should investigate.
- **Pipeline-level metadata (PG-020).** Discovered late in Phase 1 that all documents in a run share the same metadata. Should have designed the manifest approach from the start.

### Changes for Next Milestone

- **Start with lineage contract design** before implementation. Define OpenLineage event schemas and Marquez expectations upfront.
- **Investigate the file watcher issue** — it wastes time on every compilation cycle.
- **Consider PVC-mounted embedding model** (PG-019) to eliminate the per-run download overhead.
- **Document the SA token auth pattern** as a reusable snippet for all future KFP components.

## Component Extraction Assessment

Per ADR-007 criteria (stable interface, independent release cadence, different tech stack):

| Component | Assessment | Rationale |
|-----------|-----------|-----------|
| `parse_and_chunk` | **Contribute upstream** | Auth fix is general-purpose. Metadata adaptations could be parameterised (manifest file approach). |
| `ingest_to_milvus` | **Contribute upstream** | Schema is parameterised. Scenario B metadata fields are passed as pipeline params, not hardcoded. |
| `download_model` | **Use upstream directly** | No changes needed from Saad's baseline. |
| `deploy_embedding_model` | **Use upstream directly** | No changes needed (blocked on RHOAI version, not code). |
| KFP pipeline definition | **Keep in this repo** | Project-specific orchestration. |
| Milvus Helm values | **Keep in this repo** | Cluster-specific configuration. |
| Docling Ray image | **Use Saad's image** | `quay.io/rhoai-szaher/docling-ray:latest` works as-is. Custom image not needed for M1. |

**Key finding:** The SA token auth fix and Scenario B metadata adaptations both generalise. The auth fix should be reported upstream to codeflare-sdk. The metadata approach could be contributed as an enhancement to `opendatahub-io/pipelines-components` once the manifest file approach (PG-020 resolution) is implemented.

## Tags Applied

| Tag | Repo | Description |
|-----|------|-------------|
| `m0-complete` | data-strat-poc | M0 documentation and planning complete |
| `m1-p0` | data-strat-poc, pipelines-components | Phase 0: Saad's baseline validated |
| `m1-p1` | data-strat-poc, pipelines-components | Phase 1: Scenario B metadata adaptations |
| `m1-p2` | data-strat-poc, pipelines-components | Phase 2: Full corpus, 312 vectors, idempotency |
| `m1-complete` | data-strat-poc, pipelines-components | M1 milestone sign-off |

See [getting-started.md](../../operations/getting-started.md#tagging-checkpoints-dec-006) for how to recreate a checkpoint from tags.
