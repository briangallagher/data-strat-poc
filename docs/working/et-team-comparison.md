# ET Team Lineage Demo: What We Took, What We Changed, What's Deferred

**Date:** 2026-05-26
**Source:** [rh-waterford-et/lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline)
**Our repo:** [briangallagher/rhoai-lineage](https://github.com/briangallagher/rhoai-lineage)
**Related ADR:** ADR-004 (lineage architecture)

---

## Summary

The Waterford Emerging Tech team built a lineage demo for a customer churn ML pipeline (Feast, Spark, KFP, MLflow). We forked their lineage code for our Scenario B RAG pipeline. This document tracks what we took, what we changed, and what's planned.

## What We Took (in use)

| ET Team Asset | Our Location | Changes Made |
|--------------|-------------|--------------|
| `openlineage-oai/adapters/kfp/` | `rhoai-lineage/kfp/` | Re-namespaced imports. Added `run_facets` parameter to `kfp_lineage` context manager for `pipelineRunId` facet. |
| `openlineage-oai/core/config.py` | `rhoai-lineage/config.py` | Re-namespaced imports. No logic changes. |
| `openlineage-oai/core/emitter.py` | `rhoai-lineage/emitter.py` | Re-namespaced imports. No logic changes. |
| `openlineage-oai/core/facets.py` | `rhoai-lineage/core/facets.py` | Re-namespaced imports. No logic changes. |
| `openlineage-oai/adapters/base.py` | `rhoai-lineage/adapters/base.py` | Re-namespaced imports. No logic changes. |
| `openlineage-oai/utils/` | `rhoai-lineage/utils/` | Re-namespaced imports. |
| `openlineage-sdk/` | `rhoai-lineage/sdk/` | Merged `client.py` + `models.py` into single module. Re-namespaced. |
| Marquez deployment (PostgreSQL + Marquez API + Web UI) | `data-strat-poc/manifests/marquez/` | Adapted for our namespace. Fixed: `fsGroup` for PostgreSQL PVC, `WEB_PORT` env var, `MARQUEZ_CONFIG` pointing to mounted config. |
| DSP namespace injection | `data-strat-poc/manifests/marquez/inject-openlineage-namespace.sh` | Extracted into standalone script. Same pattern: patch workflow controller ConfigMap with `OPENLINEAGE_NAMESPACE` from downward API. |
| Naming normalisation | `rhoai-lineage/naming.py` | Extended with DEC-014 helpers (`s3_dataset()`, `milvus_dataset()`, `feast_dataset()`, etc.). Added normalisation from their lessons learned (`postgresql://` → `postgres://`, `s3a://` → `s3://`). |

## What We Added (not in ET team's code)

| Feature | Location | Why |
|---------|----------|-----|
| `naming.py` DEC-014 helpers | `rhoai-lineage/naming.py` | Enforce dataset naming conventions in code, not documentation. ET team documented the need but didn't build programmatic helpers. |
| `pipelineRunId` custom run facet | Pipeline components + `rhoai-lineage/kfp/lineage.py` | Vector lineage bridging -- RAG-specific requirement. ET team doesn't do RAG, so no need for Milvus ↔ Marquez correlation. |
| `_MLflowRESTTracker` | Pipeline components (inline) | Direct REST API calls to RHOAI MLflow Operator with SA token auth. ET team's MLflow adapter uses the `openlineage+` tracking URI which doesn't work with RHOAI's auth plugin. |
| Generic metadata fields | Pipeline components | `category`, `subcategory`, `document_date` on Milvus vectors. ET team uses Feast feature views, not vector stores. |
| Bridge feature flag | `data-strat-lineage-config` ConfigMap | `MLFLOW_BRIDGE_ENABLED` toggle. ET team always uses the bridge. |

## What We Took But Haven't Activated

| ET Team Asset | Status | Plan |
|--------------|--------|------|
| `openlineage-oai/adapters/mlflow/` (tracking store adapter, bridge) | Included in `rhoai-lineage/mlflow/` | Bridge is OFF by default (DEC, ADR-004). Available for evaluation. Blocked by RHOAI MLflow auth (PG-024 workaround is REST API instead). |
| MLflow entry points in `pyproject.toml` | Registered (`openlineage+http`, `openlineage+https`, etc.) | Will activate if/when RHOAI MLflow auth is resolved or RHOAIENG-50328 changes the integration model. |

## What's Deferred

| ET Team Asset | Status | When | Why Deferred |
|--------------|--------|------|-------------|
| **Lineage operator** (`lineage-operator/`) | PG-023, not deployed | **M4** (agents) | Not in critical path for pipeline-time lineage. Becomes relevant when OGX agents need lineage (AgentCard CRD). Will copy manifests to `data-strat-poc/manifests/operator/` or fork to own repo if customised. |
| **Dataset registry** (`dataset-registry/`) | Not used | **M3** (connectors) | Evaluate as part of connector architecture. The registry provides canonical dataset identity + Marquez correlation -- useful for multi-collection routing. May adopt their FastAPI + PatternFly pattern or integrate with OpenMetadata (M5+). |
| **Feast OpenLineage emitter** | Not applicable | Never (Scenario B) | No Feast in Scenario B. Relevant only for Scenario A. |
| **Spark OpenLineage listener** | Not applicable | Never (Scenario B) | No Spark in Scenario B. |

## Key Differences in Approach

| Aspect | ET Team | Our Approach | Rationale |
|--------|---------|-------------|-----------|
| **Use case** | Customer churn (traditional ML: Feast → Spark → training → model) | P&C knowledge assistant (RAG: Docling → Milvus → OGX) | Different pipeline shapes require different lineage patterns |
| **Vector lineage** | Not needed (no vector store) | Core requirement (`pipeline_run_id` on every Milvus vector) | RAG provenance: answer → chunks → pipeline → source docs |
| **Package structure** | Two packages (`openlineage-oai` + `openlineage-sdk`) | Single package (`rhoai-lineage`) with submodules | Simpler install, one version to track |
| **MLflow integration** | Bridge always ON (`openlineage+` URI) | Bridge OFF by default; REST API for tracking | RHOAI MLflow auth incompatible with bridge; keep graph clean |
| **Operator** | Deployed, watches pods, creates AgentCards | Deferred to M4/M5 | Not needed until agents enter the picture |
| **Auth** | No RBAC concerns (their cluster config) | Added K8s RBAC for `mlflow.kubeflow.org` and `ray.io` | RHOAI production-grade requirements |
| **Naming conventions** | Documented in lessons learned | Enforced in code via `naming.py` helpers | "Never construct dataset strings by hand" |

## Upstream Contributions

If our changes prove valuable, these could be contributed back to the ET team or upstream:

1. **`pipelineRunId` run facet pattern** -- useful for any RAG pipeline on RHOAI
2. **`naming.py` helpers** -- useful for any team using OpenLineage on RHOAI
3. **SA token auth workaround** -- needed by anyone running lineage from KFP pods on RHOAI
4. **Bridge feature flag** -- useful for controlling Marquez graph complexity
5. **MLflow REST tracker** -- workaround for RHOAI MLflow auth from KFP pods

## References

| Source | Link |
|--------|------|
| ET team repo | [rh-waterford-et/lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline) |
| rhoai-lineage | [briangallagher/rhoai-lineage](https://github.com/briangallagher/rhoai-lineage) |
| ET team lessons learned | [docs/intro-and-lessons-learned.md](https://github.com/rh-waterford-et/lineage-demo-pipeline/blob/main/docs/intro-and-lessons-learned.md) |
| ADR-004 | `docs/architecture/adrs/ADR-004-lineage-architecture.md` |
| Prior-art synthesis | `docs/working/prior-art-synthesis.md` |
| PG-023 (operator deferred) | `docs/production-gaps.md` |
