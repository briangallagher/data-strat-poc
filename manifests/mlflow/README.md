# MLflow

MLflow is provided by the RHOAI MLflow Operator -- no custom deployment needed.

## Cluster-wide Instance

The cluster has a shared MLflow instance managed by the Operator:
- **Internal URL:** `https://mlflow.redhat-ods-applications.svc:8443`
- **External URL:** `https://mlflow-ui-redhat-ods-applications.apps.dev.aip-ft.rh-ods.com`
- **Auth:** Bearer token (from `oc whoami -t` or in-cluster SA token)
- **Workspace:** Each K8s namespace is a separate MLflow workspace (automatic via K8s auth plugin)

## Usage from Pipeline Components

```python
import mlflow
import os

# In-cluster: use internal service URL
mlflow.set_tracking_uri("https://mlflow.redhat-ods-applications.svc:8443")

# The K8s auth plugin automatically:
# - Reads the SA token from /var/run/secrets/kubernetes.io/serviceaccount/token
# - Sets the workspace to the pod's namespace
# - Handles TLS verification via the cluster CA

mlflow.set_experiment("data-strat-ingest")
with mlflow.start_run():
    mlflow.log_param("corpus_size", 11)
    mlflow.log_metric("chunks_created", 312)
```

## Bridge Mode (opt-in)

When `MLFLOW_BRIDGE_ENABLED=true` in the `data-strat-lineage-config` ConfigMap,
the tracking URI changes to `openlineage+https://mlflow.redhat-ods-applications.svc:8443`
which routes through the rhoai-lineage tracking store adapter, emitting OL events to Marquez.

See DEC-007 and ADR-004 for the bridge design.
