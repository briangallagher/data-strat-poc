# M3 Checkpoint: Connectors + Document Registry

**Date:** 2026-05-26
**Status:** Complete

## What Was Built

### Phase 0: Corpus Organisation
- Renamed `regulatory_filings` → `regulatory_bulletins` (match DEC-008)
- Created ~5 mock docs for `iso_forms` collection
- Final corpus: 20 docs across 3 collections with intentional many-to-many overlap
- Uploaded to MinIO: `corpus/<collection>/<filename>`

### Phase 1: Document Registry (FastAPI + PostgreSQL + SDK + UI)
- FastAPI backend (`src/registry/`) with PostgreSQL (shared Marquez PG, separate `doc_registry` database)
- Data model: `documents`, `collections`, `collection_documents` tables with many-to-many support
- All API endpoints: `/resolve`, CRUD, `/bulk`, `/supersede`, `/lineage`, collection management
- Auto-enrichment on registration: `content_hash`, `file_format`, `file_size_bytes`, `page_count`
- `doc_id` auto-generation from collection `doc_id_prefix` + sequential number
- OL identity derivation: `registry://source_system:doc_id`
- Python SDK (`registry-sdk/`): `RegistryClient` with typed Pydantic models
- PatternFly 6 UI (`src/registry-ui/`): document list, detail, collection management, lineage view
- Deployed via git-clone init container with sparse checkout

### Phase 2: Manifest-Driven parse_and_chunk (PG-020 Closed)
- `parse_and_chunk` reads per-document metadata from staging `manifest.json`
- Each chunk inherits parent document's `doc_id`, `line_of_business`, `jurisdiction`, `effective_date`, `document_type`
- Pipeline-level params retained as fallback defaults

### Phase 3: acquire_documents KFP Component
- New KFP component in `pipelines-components` fork
- Queries registry (SDK, not raw HTTP) for collection members → authenticates connector → fetches each doc → writes manifest → emits per-doc OL InputDataset → logs to MLflow
- Graceful failure handling: missing files skipped, flagged `status: unavailable`
- `connector.resolve()` NOT called (ADR-010)
- OL emission from pipeline only (ADR-011)

### Phase 4: Multi-Collection Orchestration
- `scripts/run-multi-collection.py` reads `config/collections.yaml`
- Triggers one KFP pipeline run per collection via KFP API
- Ran all 3 collections: `underwriting_guidelines`, `regulatory_bulletins`, `iso_forms`

### Phase 5: Verification + Documentation
- Full E2E verification (see table below)
- ADRs 006–012 written
- Technical docs: document-registry, connectors, collection-lifecycle
- Production gaps PG-026 through PG-035 logged
- All repos tagged `m3-complete`

---

## Verification Results

| Test | Result | Evidence |
|------|--------|----------|
| Registry deployed and seeded | **PASS** | 20 docs, 3 collections, many-to-many verified |
| acquire_documents step | **PASS** | Queries registry, fetches from S3, writes manifest |
| parse_and_chunk with manifest | **PASS** | Per-doc metadata from manifest (PG-020 closed) |
| ingest_to_milvus | **PASS** | 131 vectors across 3 collections |
| Milvus `underwriting_guidelines` | **PASS** | 27 vectors, 3 unique doc_ids |
| Milvus `regulatory_bulletins` | **PASS** | 93 vectors, 7 docs (incl 2 shared) |
| Milvus `iso_forms` | **PASS** | 11 vectors, 5 mock docs |
| Per-doc metadata differs | **PASS** | Different category/subcategory/date per doc |
| Marquez acquire_documents | **PASS** | Per-doc InputDataset nodes in graph |
| Marquez full chain | **PASS** | 3 jobs: acquire, parse, ingest all COMPLETED |
| DEC-008 multi-collection | **PASS** | 3 separate pipeline runs, 3 Milvus collections |
| Many-to-many | **PASS** | `ug-008` in both `underwriting_guidelines` and `regulatory_bulletins` |

### Regression Results

| Previous Milestone | Result | Notes |
|--------------------|--------|-------|
| M1 (ingest pipeline) | **PASS** | Pipeline structure intact; vectors verified |
| M2 (lineage) | **PASS** | Marquez graph extended with per-doc nodes; existing jobs still COMPLETED |

---

## Production Gaps Identified

| ID | Gap | Path to Close |
|----|-----|---------------|
| PG-026 | Document versioning not exercised | Content-hash comparison in connector; exercise with a doc update |
| PG-027 | Identity drift detection not implemented | Hash-based dedup in registry `/resolve` |
| PG-028 | No routing rules in registry | Rules table + matching logic for auto-assignment |
| PG-029 | Registry has no HA/failover | Standard K8s HA patterns |
| PG-030 | No deep schema introspection | Docling metadata extraction as enrichment step |
| PG-031 | Registry UI has no auth | OAuth proxy or K8s auth plugin |
| PG-032 | Multiple standalone SDKs | Unified `rhoai-data-sdk` post-M3 |
| PG-033 | No discovery/sync process | Separate KFP pipeline or cron job |
| PG-034 | Manifest not treated as versioned record | Version and store per `pipeline_run_id` |
| PG-035 | Connector ABC not split into Fetcher/Discoverer | Refactor when discovery workflow lands |
| PG-036 | Registry models "Document" not generic "Dataset" | Generalise to Dataset with type discrimination (document, table, feature_set, model) when Scenario A or broader use cases arrive. See Option C below. |
| PG-037 | Registry UI lacks registration form | Add "Register Document" page with form fields for manual registration via the UI (M5+) |
| PG-038 | Registry UI lacks discovery/re-scan trigger | Add "Scan Source" button on collection detail page to trigger discovery workflow (M5+, depends on PG-033) |

| PG-039 | PVC not supported as staging surface | Design A uses S3 exclusively for staging; some users may need PVC-based staging (air-gapped, no object store) | Support PVC as alternative staging surface (configurable: S3 or PVC) | Add `staging_type` param (s3 or pvc); parse_and_chunk already has PVC fallback path | Open |

**Design A — S3 as Sole Staging Surface:**

The pipeline flow is: `acquire_documents` fetches from remote sources → writes to S3 staging → `parse_and_chunk` downloads from S3 staging → processes → writes JSONL chunks to S3 → `ingest_to_milvus` reads chunks from S3 → embeds → writes to Milvus. S3 (MinIO) is the handoff surface between all steps. This makes the Marquez lineage graph fully connected (same S3 dataset node is output of acquire and input of parse). PVC is not used in the pipeline flow. If PVC-based staging is needed (air-gapped environments, no object store), it can be added as an alternative — the fallback path exists in `parse_and_chunk` (PG-039).

**Document Lifecycle (Register → Build → Acquire):**

1. **Register** — declare existence. "This document exists at this URL with this metadata." No data moves.
2. **Build Collection** — declare intent. "I want these documents queryable together in this Milvus collection." No data moves.
3. **Pipeline run (Acquire)** — execute. Bytes flow from remote → S3 staging → parsed → embedded → Milvus. This is when data actually moves into the cluster.

**Option C — Document to Dataset Generalisation (M5+):**

The registry currently models "Documents" (PDFs, DOCX, HTML) with document-specific fields (`page_count`, `file_format`, `effective_date`, `jurisdiction`). For broader RHOAI use, the registry should generalise to "Dataset" — a term aligned with OpenLineage and the ET team's registry — with a `type` field discriminating between document, table, feature_set, model, etc. Document-specific metadata would move to a flexible JSONB column. This refactoring is deferred until Scenario A or cross-scenario use cases require it. The current Document model is correct and sufficient for Scenario B.

**UI Enhancements (M5+):**
- Register Document page (form: name, source_system, source_url, document_type, LOB, jurisdiction, effective_date, collection assignment)
- "Scan Source" button on Collection Detail (triggers discovery workflow)
- Bulk upload/import from CSV or manifest file via UI
- Document versioning UI (view version history, mark superseded)
- Inline metadata editing on Document Detail page

---

## Cluster State

What's deployed in `data-strat-poc` namespace after M3:

| Component | Pods | Status | Endpoint |
|-----------|------|--------|----------|
| DSPA (KFP v2) | 6 ds-pipeline-* pods | Running | Route: ds-pipeline-dspa |
| MinIO | 1 pod | Running | minio-service:9000 |
| Milvus | 3 pods (standalone, etcd, minio) | Running | milvus:19530 |
| Marquez PostgreSQL | 1 pod | Running | marquez-postgres:5432 |
| Marquez API | 1 pod | Running | marquez-api:5000 (route exposed) |
| Marquez Web UI | 1 pod | Running | marquez-web:3000 (route exposed) |
| MLflow | Cluster-wide (redhat-ods-applications) | Running | mlflow.redhat-ods-applications.svc:8443 |
| Document Registry | 1 pod (FastAPI + nginx UI) | Running | doc-registry:8080 (route exposed) |

**Milvus collections:** `underwriting_guidelines` (27 vectors), `regulatory_bulletins` (93 vectors), `iso_forms` (11 vectors)

**Namespace resources:** ~15 pods, 6 PVCs, 4 routes (DSP, Marquez API, Marquez Web, Registry)

---

## How to Resume for M4

1. Check out `m3-complete` tag across all repos
2. Cluster is ready — all M3 components running
3. M4 adds query-time lineage (MLflow GenAI spans, OGX query path)
4. Registry and connectors are stable — no changes expected in M4
5. Key repos:
   - Pipeline components: `/tmp/pipelines-components` (branch `data-strat-poc`)
   - rhoai-lineage: `~/dev/git-repos/rhoai-lineage`
   - Registry: `data-strat-poc/src/registry/` and `registry-sdk/`
   - Manifests: `manifests/` (base, minio, dspa, milvus, marquez, rbac, registry)

### Compile pipeline from M3 state

```bash
rm -rf /tmp/pipelines-components
git clone --branch data-strat-poc https://github.com/briangallagher/pipelines-components.git /tmp/pipelines-components
pip install -e /tmp/pipelines-components
pip install -e registry-sdk/
python3 -c "
from kfp import compiler
from kfp_components.pipelines.data_processing.ray_data.pdf_documents_processing_rag_pipeline.pipeline import rag_ingest_pipeline
compiler.Compiler().compile(rag_ingest_pipeline, package_path='rag_ingest_pipeline.yaml')
"
```

### Run multi-collection ingest

```bash
python3 scripts/run-multi-collection.py --config config/collections.yaml
```

---

## Lessons Learned

1. **S3 path consistency matters** — Corpus paths in the registry (`source_url`) must exactly match the S3 key layout (`corpus/<collection>/<filename>`). A trailing slash mismatch caused silent 404s in `acquire_documents` until the connector normalised paths.

2. **PVC vs S3 staging** — The acquire step stages files to S3 (not PVC). This avoids PVC size limits and makes staging artifacts accessible across pipeline steps without shared-volume configuration. Parse_and_chunk reads directly from the S3 staging path.

3. **Registry password in shared PG** — Sharing the Marquez PostgreSQL instance means the registry database uses the same credentials. For production, separate PG instances or at minimum separate users with scoped permissions (PG-029).

4. **Sparse git checkout for deployment** — The registry is deployed via a git-clone init container with sparse checkout to pull only `src/registry/` and `registry-sdk/`. This avoids cloning the full repo (with corpus data) into every pod.

5. **KFP v2 type strictness for integer params** — KFP v2 enforces strict typing on component parameters. Passing `collection_name` (string) where an integer was expected caused a compile-time error that wasn't obvious. All component params need explicit type annotations.
