# ADR-005: MLflow-KFP Integration Strategy

**Date:** 2026-05-26
**Status:** Decided (with forward-looking transition plan)
**Milestone:** M2

## Context

We implemented MLflow tracking in our pipeline components using a custom `_MLflowRESTTracker` class that calls the MLflow REST API directly with explicit SA token + workspace headers. This was a workaround for PG-024 (RHOAI MLflow Operator auth from KFP pods).

Investigation of [RHOAIENG-50328](https://redhat.atlassian.net/browse/RHOAIENG-50328) and upstream [KEP-12862](https://github.com/kubeflow/pipelines/tree/master/proposals/12862-mlflow-integration) revealed that the KFP team is building **platform-level MLflow integration** that will make our workaround unnecessary.

### What the Platform Integration Does

KEP-12862 adds automatic MLflow tracking across three KFP backend components:

**API Server:** On `CreateRun`, automatically creates an MLflow experiment and parent run, tags it with KFP metadata (run URL, pipeline ID). On completion, marks the parent run complete/failed.

**Driver:** For each task, creates a **nested MLflow run** under the parent. Injects env vars into user containers:
- `MLFLOW_TRACKING_URI`
- `MLFLOW_WORKSPACE`
- `MLFLOW_EXPERIMENT_ID`
- `MLFLOW_RUN_ID` (points to this task's nested run)
- `MLFLOW_TRACKING_TOKEN` (SA token for auth)

**Launcher:** Post-execution, logs input parameters and scalar output metrics to MLflow automatically. Non-blocking to user code.

### MLflow Run Hierarchy

```
MLflow Experiment (user-specified or "Default")
  └── Parent Run (1 per KFP pipeline run)
        │   tagged: KFP run URL, pipeline ID, pipeline version
        ├── Nested Run: parse_and_chunk
        │     auto-logged: input params, scalar output metrics
        ├── Nested Run: ingest_to_milvus
        │     auto-logged: input params, scalar output metrics
        └── ... (one nested run per task)
```

### Upstream Status

| PR | Repo | Status | What |
|----|------|--------|------|
| [#13005](https://github.com/kubeflow/pipelines/pull/13005) | kubeflow/pipelines | **Merged** (Mar 31) | API server lifecycle hooks |
| [#13052](https://github.com/kubeflow/pipelines/pull/13052) | kubeflow/pipelines | **Merged** (May 7) | Driver + launcher hooks |
| [#1048](https://github.com/opendatahub-io/data-science-pipelines-operator/pull/1048) | DSP operator | **Open** | RHOAI auto-detect MLflow, configure plugin |
| [#299](https://github.com/opendatahub-io/data-science-pipelines/pull/299) | DSP | **Open** | Upstream rebase to pick up KEP changes |
| [#6948](https://github.com/opendatahub-io/odh-dashboard/pull/6948) | Dashboard | **Merged** (Apr 6) | MLflow experiment UI in pipeline runs |

**The DSP operator piece (#1048) is the critical missing piece.** Until it merges, RHOAI won't have automatic MLflow tracking.

## Decision

### Current State (M2)

Use our `_MLflowRESTTracker` workaround to log pipeline params and metrics to MLflow. This is custom code in each pipeline component that:
- Reads the SA token from the projected volume
- Calls MLflow REST API with explicit auth headers
- Creates experiments and runs, logs params/metrics
- Best-effort (try/except, non-blocking)

### Transition Plan (When RHOAIENG-50328 Lands)

When the platform integration becomes available in RHOAI:

1. **Remove** `_MLflowRESTTracker` from both pipeline components
2. **Remove** MLflow RBAC manifest (`manifests/mlflow/mlflow-rbac.yaml`) -- platform handles auth
3. **Keep** any custom `mlflow.log_metric()` calls for metrics not captured by the launcher (e.g., `vectors_per_second` -- derived metrics the launcher can't compute)
4. **Keep** `pipeline_run_id` as a custom param -- the platform logs KFP input params, but `pipeline_run_id` may need explicit logging if it's not a pipeline input
5. **Verify** the nested run structure matches what we need for cross-referencing with Marquez

### What Stays Regardless

- **Marquez / OpenLineage** -- platform integration doesn't touch lineage. Our direct OL emission stays.
- **`pipeline_run_id` on Milvus vectors** -- this is our code, not platform-managed
- **`pipeline_run_id` in Marquez run facets** -- this is our code, not platform-managed
- **The rhoai-lineage library** -- lineage emission is separate from experiment tracking

## Consequences

- Our workaround is **temporary** -- designed for easy removal
- We're **early-adopting the pattern** (params + metrics in MLflow) that will become automatic
- The nested run hierarchy (parent per pipeline, child per task) is the correct MLflow structure -- our flat experiment runs are simpler but will be replaced
- When the platform integration lands, pipeline components become simpler (remove ~50 lines of tracker code per component)
- The `pipelines-components` team is already **removing manual MLflow params** from training pipelines ([PR #81](https://github.com/opendatahub-io/pipelines-components/pull/81)) in anticipation

## Future Considerations

- **RHOAI version dependency:** The integration needs DSP operator PR #1048 merged and a RHOAI release containing it. Track against RHOAI release notes.
- **Custom metrics:** The platform auto-logs scalar output metrics, but derived metrics (vectors_per_second) and non-scalar data need custom `mlflow.log_metric()` calls using the injected `MLFLOW_RUN_ID` env var.
- **Experiment naming:** The platform lets users specify an experiment name at run creation (via `plugins_input.mlflow.experiment_name`). Our pipeline should expose this as a parameter.
- **MLflow bridge re-evaluation:** With platform-managed auth, the `openlineage+` bridge in rhoai-lineage might work. Re-evaluate when the platform integration lands.
- **KEP #12700 (generic plugin architecture):** MLflow is the first plugin. The generic architecture (blocked on MLMD removal) will allow other plugins. Monitor for OpenLineage as a potential future plugin.

## References

| Source | Link |
|--------|------|
| KEP-12862 (upstream proposal) | [kubeflow/pipelines/proposals/12862-mlflow-integration](https://github.com/kubeflow/pipelines/tree/master/proposals/12862-mlflow-integration) |
| API server PR (merged) | [kubeflow/pipelines#13005](https://github.com/kubeflow/pipelines/pull/13005) |
| Driver/launcher PR (merged) | [kubeflow/pipelines#13052](https://github.com/kubeflow/pipelines/pull/13052) |
| DSP operator PR (open) | [opendatahub-io/data-science-pipelines-operator#1048](https://github.com/opendatahub-io/data-science-pipelines-operator/pull/1048) |
| Dashboard PR (merged) | [opendatahub-io/odh-dashboard#6948](https://github.com/opendatahub-io/odh-dashboard/pull/6948) |
| RHOAIENG-50328 (Jira EPIC) | [redhat.atlassian.net/browse/RHOAIENG-50328](https://redhat.atlassian.net/browse/RHOAIENG-50328) |
| pipelines-components removing manual MLflow | [opendatahub-io/pipelines-components#81](https://github.com/opendatahub-io/pipelines-components/pull/81) |
