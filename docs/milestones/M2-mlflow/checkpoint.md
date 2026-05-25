# M2 Checkpoint: MLflow + Lineage

**Date:** 2026-05-25
**Status:** Complete with gaps

## What Was Built

### Phase 0: rhoai-lineage Library
- Forked and restructured ET team's `openlineage-oai` + SDK into standalone `rhoai-lineage` Python package
- Naming module enforces DEC-014 conventions (PVC, S3, Milvus dataset URIs)
- Marquez client with HTTP transport
- MLflow-Marquez bridge support (openlineage+ tracking URI)
- Published to https://github.com/briangallagher/rhoai-lineage
- Installable via `pip install git+https://github.com/briangallagher/rhoai-lineage.git`

### Phase 1: Marquez Infrastructure
- PostgreSQL deployed (200m CPU, 256Mi RAM, 2Gi PVC)
- Marquez API deployed (port 5000, `/api/v1/lineage` endpoint)
- Marquez Web UI deployed (port 3000, route exposed)
- DSP namespace injection applied (`OPENLINEAGE_NAMESPACE` from downward API)
- Lineage ConfigMap (`data-strat-lineage-config`) with bridge toggle

### Phase 2: MLflow Configuration
- MLflow already available via RHOAI Operator (DSC shows `MLflowOperatorReady: True`)
- No per-namespace deployment needed — operator manages cluster-wide instance
- ConfigMap configured with MLflow tracking URI
- Bridge set to OFF (`MLFLOW_BRIDGE_ENABLED=false`)

### Phase 3: OpenLineage Emission
- `parse_and_chunk` emits START/COMPLETE events with input (PVC) and output (S3) datasets
- `ingest_to_milvus` emits START/COMPLETE events with input (S3) and output (Milvus) datasets
- Custom facets emitted on output datasets (metrics, dimensions, durations)
- JobType facet: `KFP_COMPONENT` with producer `rhoai-lineage/kfp-adapter`
- Pipeline run SUCCEEDED: run ID `e733d2cc-ac2f-4cd7-a761-0a9bc19df427`

### Phase 4: Verification + Documentation
- Full E2E verification of Marquez graph
- MLflow verification (finding: not working from KFP pods)
- ADR-004, technical deep dives, user journey, production gaps documented
- All repos tagged `m2-complete`

## Verification Results

| Test | Method | Result | Evidence |
|------|--------|--------|----------|
| Marquez API healthy | `GET /api/v1/namespaces/data-strat-poc/jobs` | **Pass** | 2 jobs returned |
| Lineage graph complete | `GET /api/v1/lineage?nodeId=...&depth=5` | **Pass** | 5 nodes, 4 edges: PVC→parse→S3→ingest→Milvus |
| parse_and_chunk run | `GET .../jobs/parse_and_chunk/runs` | **Pass** | Run `99029c77` COMPLETED (1055ms) |
| ingest_to_milvus run | `GET .../jobs/ingest_to_milvus/runs` | **Pass** | Run `58d9dc2e` COMPLETED (160ms) |
| Dataset facets (S3) | Dataset detail query | **Pass** | `custom_metrics`: num_files=0, chunk_max_tokens=256, duration_seconds=240.36 |
| Dataset facets (Milvus) | Dataset detail query | **Pass** | `custom_metrics`: vectors_inserted=312, embedding_dim=768, index_type=HNSW |
| JobType facet | Job detail query | **Pass** | `KFP_COMPONENT`, producer=`rhoai-lineage`, integration=`KFP` |
| MLflow experiments | `GET /api/2.0/mlflow/experiments/search` | **Fail** | Empty response `{}` — PG-024 |
| pipeline_run_id in Marquez | Search API + run facets | **Fail** | Not present in Marquez — PG-025 |
| Marquez Web UI accessible | Browser check | **Pass** | Route: https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Bridge OFF verified | ConfigMap check + graph inspection | **Pass** | No synthetic MLflow nodes in graph |

### Regression Results

| Previous Milestone | Result | Notes |
|--------------------|--------|-------|
| M1 (ingest pipeline) | **Pass** | Pipeline run succeeded with same parameters; 312 vectors verified in Milvus; metadata intact |

## Production Gaps Identified

| Gap ID | Description | Logged in production-gaps.md |
|--------|-------------|------------------------------|
| PG-021 | rhoai-lineage installed via git URL (slow ~30s) | Yes |
| PG-022 | Marquez in same namespace (no isolation) | Yes |
| PG-023 | Lineage operator not deployed (deferred) | Yes |
| PG-024 | MLflow tracking doesn't work from KFP pods (SA token + workspace header) | Yes |
| PG-025 | pipeline_run_id not in Marquez run facets (no cross-correlation) | Yes |

## Cluster State

What's deployed in `data-strat-poc` namespace after M2:

| Component | Pods | Status | Endpoint |
|-----------|------|--------|----------|
| DSPA (KFP v2) | 6 ds-pipeline-* pods | Running | Route: ds-pipeline-dspa |
| MinIO | 1 pod | Running | minio-service:9000 |
| Milvus | 3 pods (standalone, etcd, minio) | Running | milvus:19530 |
| Marquez PostgreSQL | 1 pod | Running | marquez-postgres:5432 |
| Marquez API | 1 pod | Running | marquez-api:5000 (route exposed) |
| Marquez Web UI | 1 pod | Running | marquez-web:3000 (route exposed) |
| MLflow | Cluster-wide (redhat-ods-applications) | Running | mlflow.redhat-ods-applications.svc:8443 |

**Namespace resources:** ~14 pods, 6 PVCs, 3 routes (DSP, Marquez API, Marquez Web)

## How to Resume

### For M3 (Connectors)
1. Check out `m2-complete` tag across all repos
2. Cluster is ready — all M2 components running
3. M3 adds data source connectors (dlt, Confluence, S3 multi-source)
4. Pipeline components in `/tmp/pipelines-components` (branch `data-strat-poc`)
5. rhoai-lineage at `~/dev/git-repos/rhoai-lineage` — extend with connector-specific naming if needed

### Key files
- Pipeline YAML: `rag_ingest_pipeline.yaml` (repo root)
- Manifests: `manifests/` (base, minio, dspa, milvus, marquez, rbac)
- Lineage config: `manifests/marquez/lineage-config.yaml`
- Component code: `/tmp/pipelines-components` or `~/dev/odh/pipelines-components` (branch `data-strat-poc`)
- rhoai-lineage: `~/dev/git-repos/rhoai-lineage`

### Compile pipeline from M2 state
```bash
rm -rf /tmp/pipelines-components
git clone --branch data-strat-poc https://github.com/briangallagher/pipelines-components.git /tmp/pipelines-components
pip install -e /tmp/pipelines-components
python3 -c "
from kfp import compiler
from kfp_components.pipelines.data_processing.ray_data.pdf_documents_processing_rag_pipeline.pipeline import rag_ingest_pipeline
compiler.Compiler().compile(rag_ingest_pipeline, package_path='rag_ingest_pipeline.yaml')
"
```

## Lessons Learned

1. **MARQUEZ_CONFIG env var is required** — Marquez won't start with inline configuration; it needs a mounted config file referenced by `MARQUEZ_CONFIG=/path/to/marquez.yml`.

2. **WEB_PORT, not PORT** — Marquez Web UI uses `WEB_PORT` for its listen port, not the generic `PORT` env var. Cost: one failed deployment iteration.

3. **fsGroup for PostgreSQL** — The PostgreSQL container needs `fsGroup` in its SecurityContext to write to the PVC on OpenShift. Without it, the init container fails silently.

4. **ConfigMap env conflicts with DSP injection** — Both the lineage ConfigMap (`configMapAsEnv`) and the downward API can try to set `OPENLINEAGE_NAMESPACE`. The downward API approach is more portable and should take precedence. Resolved by only setting namespace via downward API.

5. **MLflow Operator already available** — No deployment work needed for MLflow. The RHOAI Operator manages it cluster-wide. However, accessing it from KFP pods requires auth configuration that isn't straightforward (PG-024).

6. **Bridge OFF is the right default** — Direct OL emission gives precise control over the Marquez graph. The bridge adds noise for pipeline-time use cases. Keep it as an evaluation toggle for M4 query-time tracing.

7. **Custom facets work well for metrics** — Embedding metrics (vectors_inserted, duration, embedding_dim) as OpenLineage custom facets on output datasets provides a clean metrics path that doesn't require MLflow to be working.
