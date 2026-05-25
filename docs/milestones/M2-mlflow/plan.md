# M2: MLflow + Lineage

**Status:** Complete
**Started:** 2026-05-25
**Completed:** 2026-05-25

## Goal

Add pipeline observability (MLflow experiment tracking) and data lineage (OpenLineage/Marquez) to the ingest pipeline, with a new `rhoai-lineage` library seeded from the Waterford ET team's code.

## Objectives

1. `rhoai-lineage` package working and installable from git
2. Marquez deployed and receiving OpenLineage events from the pipeline
3. MLflow tracking pipeline runs with parameters and metrics
4. Full lineage graph in Marquez: S3 source → parse_and_chunk → S3 JSONL → ingest_to_milvus → Milvus collection
5. MLflow-Marquez bridge available as opt-in feature flag, evaluated with documented findings

## Scope

### In Scope

- `rhoai-lineage` Python package (new repo, seeded from ET team's openlineage-oai + sdk)
- Marquez deployment (API + Web UI + PostgreSQL)
- Lineage operator deployment (AgentCard CRD, pod watching -- infrastructure role)
- DSP namespace injection for OPENLINEAGE_NAMESPACE
- MLflow deployment via RHOAI MLflow Operator
- Lineage config ConfigMap with MLflow bridge feature flag
- OpenLineage emission from parse_and_chunk and ingest_to_milvus components
- MLflow experiment tracking in pipeline components
- Bridge ON/OFF evaluation with documented comparison

### Out of Scope

- Query-time tracing (M4 -- MLflow GenAI spans)
- Marquez auth / RBAC (M5 -- PG-001)
- Agent lineage via operator (M4/M5)
- OpenMetadata evaluation (M5+)

## Acceptance Criteria

- [x] `rhoai-lineage` installs via `pip install git+https://github.com/briangallagher/rhoai-lineage.git`
- [x] Naming helpers produce correct DEC-014 URIs (tests pass)
- [x] Marquez API healthy (`/api/v1/namespaces` returns data)
- [x] Marquez Web UI accessible via route
- [ ] ~~Lineage operator deployed and watching pods~~ — **Deferred** (PG-023, not in critical path)
- [x] DSP pods have `OPENLINEAGE_NAMESPACE` env var
- [x] MLflow Operator CR deployed, MLflow accessible
- [ ] ~~Pipeline run tracked in MLflow with params and metrics~~ — **Gap** (PG-024, SA token + workspace header)
- [x] **Bridge OFF:** Marquez graph shows clean pipeline chain (5 nodes: PVC → parse → S3 → ingest → Milvus)
- [ ] ~~**Bridge OFF:** `pipeline_run_id` in Milvus matches Marquez run ID~~ — **Gap** (PG-025, facet not emitted)
- [ ] **Bridge ON:** MLflow experiment metadata appears in Marquez (evaluation) — **Deferred** (requires PG-024 resolution first)
- [x] ADR-004 written (lineage architecture)
- [x] Technical deep dives written (lineage.md, mlflow-integration.md)
- [x] UJ-002 updated with both bridge modes
- [x] Production gaps documented
- [x] All repos tagged

## Phases

| Phase | Goal | Status |
|-------|------|--------|
| Phase 0 | Seed rhoai-lineage from ET team code | **Complete** |
| Phase 1 | Deploy Marquez + namespace injection | **Complete** |
| Phase 2 | Deploy MLflow (bridge OFF), add pipeline tracking | **Complete** |
| Phase 3 | Add OL emission to pipeline components | **Complete** |
| Phase 4 | E2E verification, ADRs, docs, checkpoint | **Complete** |

## Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| Cluster access (RHOAI 3.4) | Brian | Available |
| ET team's lineage-demo-pipeline code | Public repo | Available |
| MLflow Operator on cluster | RHOAI | Ready (DSC shows MLflowOperatorReady: True) |
| M1 ingest pipeline working | M1 complete | Verified |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ET team's code doesn't work with our setup | Medium | Medium | Phase 0 validates before deploying infra |
| Marquez PVC hits volume limit | Medium | Low | We freed PVCs in M1; only 2Gi needed |
| MLflow Operator CR config differs from manual deploy | Low | Medium | Fall back to manual deploy if needed |
| rhoai-lineage git install too slow in KFP pods | Medium | Low | Track as PG-021; move to wheel if needed |
| Bridge makes Marquez graph too noisy | Medium | Low | Bridge OFF by default; evaluate in Phase 4 |

## Resource Requirements

| Resource | Specification | Purpose |
|----------|--------------|---------|
| PostgreSQL (Marquez) | 200m CPU, 256Mi RAM, 2Gi PVC | Marquez metadata store |
| Marquez API | 200m CPU, 512Mi RAM | OpenLineage backend |
| Marquez Web UI | 100m CPU, 128Mi RAM | Lineage graph visualization |
| MLflow | Managed by Operator | Experiment tracking |
| No additional GPU | — | Lineage is CPU-only |
