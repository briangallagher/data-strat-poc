# Getting Started

Step-by-step guide to deploy the system from scratch. Start here after confirming all [prerequisites](prerequisites.md).

**Last Updated:** 2026-05-25 (M2 complete — lineage + MLflow added)

## Deployment Order

Components must be deployed in this order due to dependencies:

```
1. Namespace + Secrets + PVCs   (base)
2. MinIO                        (needed by DSPA and pipeline)
3. MinIO buckets                (needed by DSPA)
4. DSPA                         (needs MinIO)
5. Milvus                       (independent, but needed before pipeline runs)
6. RBAC                         (needs DSPA service account to exist)
7. Marquez + PostgreSQL         (M2 — lineage backend)
8. Lineage ConfigMap            (M2 — configures OL emission + bridge toggle)
9. DSP namespace injection      (M2 — OPENLINEAGE_NAMESPACE via downward API)
10. MLflow                      (M2 — already deployed via RHOAI Operator, no action needed)
11. Upload test data            (needs data-pvc)
12. Milvus collection setup     (auto-created by pipeline; embedding via local model)
13. Compile + upload pipeline   (needs DSPA + pipelines-components fork)
14. Run pipeline                (see runbook)
```

## Step 1: Create Namespace and Base Resources

```bash
oc new-project data-strat-poc

# Grant anyuid SCC for Milvus (PG-016)
oc adm policy add-scc-to-user anyuid -z default -n data-strat-poc

# Create secrets, PVCs
# IMPORTANT: Edit hf-token-secret with your real HuggingFace token first
oc apply -f manifests/base/namespace-setup.yaml -n data-strat-poc

# Update HF token with real value
oc patch secret hf-token-secret -n data-strat-poc \
  -p '{"stringData":{"token":"YOUR_REAL_HF_TOKEN"}}'
```

## Step 2: Deploy MinIO

```bash
oc apply -f manifests/minio/minio.yaml -n data-strat-poc

# Wait for MinIO to be ready
oc rollout status deployment/minio-service -n data-strat-poc --timeout=2m
```

## Step 3: Create MinIO Buckets

```bash
./manifests/minio/create-buckets.sh
```

**Expected output:** `Buckets created successfully`

## Step 4: Deploy DSPA (KFP v2)

```bash
oc apply -f manifests/dspa/dspa.yaml -n data-strat-poc

# Wait for all DSP components (~1-2 minutes)
sleep 30
oc get pods -n data-strat-poc | grep ds-pipeline
```

**Expected:** 6 `ds-pipeline-*` pods all Running.

## Step 5: Deploy Milvus

```bash
helm repo add milvus https://zilliztech.github.io/milvus-helm/ 2>/dev/null
helm install milvus milvus/milvus -n data-strat-poc -f manifests/milvus/values.yaml

# Wait for Milvus (~2 minutes)
sleep 60
oc get pods -n data-strat-poc | grep milvus
```

**Expected:** `milvus-etcd-0`, `milvus-minio-*`, `milvus-standalone-*` all Running.

**Milvus service endpoint:** `milvus.data-strat-poc.svc.cluster.local:19530`

## Step 6: Apply Pipeline RBAC

```bash
oc apply -f manifests/rbac/pipeline-rbac.yaml -n data-strat-poc
```

## Step 7: Upload Test Data

```bash
# Create a helper pod to copy files to the data PVC
oc run data-loader --image=registry.redhat.io/ubi9/ubi:latest \
  --restart=Never -n data-strat-poc \
  --overrides='{"spec":{"securityContext":{"fsGroup":0},"containers":[{"name":"loader","image":"registry.redhat.io/ubi9/ubi:latest","command":["sleep","3600"],"securityContext":{"runAsUser":0},"volumeMounts":[{"name":"data","mountPath":"/mnt/data"}]}],"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"data-pvc"}}]}}' \
  --command -- sleep 3600

# Wait for pod
sleep 15

# Create directory and copy PDFs
oc exec data-loader -n data-strat-poc -- mkdir -p /mnt/data/input/pdfs
oc cp /path/to/your/test.pdf data-strat-poc/data-loader:/mnt/data/input/pdfs/

# Verify
oc exec data-loader -n data-strat-poc -- ls -la /mnt/data/input/pdfs/

# Clean up helper pod
oc delete pod data-loader -n data-strat-poc
```

## Step 8: Deploy Milvus Collection (M1)

Milvus is deployed in Step 5 via Helm. The collection schema and HNSW index are created automatically by the `ingest_to_milvus` pipeline component on first run (or on every run with `drop_existing=true`). No manual collection creation is needed.

**Embedding model:** M1 uses local `sentence-transformers` (Granite Embedding 125M, 768-dim) running inside the `ingest_to_milvus` KFP pod. No separate embedding InferenceService is needed — RHOAI 3.4's vLLM lacks `--task=embedding` support (PG-018). The model (~500MB) downloads from HuggingFace on each run (PG-019).

## Step 9: Compile and Upload Pipeline

```bash
# Clone the fork (use /tmp to avoid file watcher issue)
rm -rf /tmp/pipelines-components
git clone --branch data-strat-poc \
  https://github.com/briangallagher/pipelines-components.git \
  /tmp/pipelines-components

pip install -e /tmp/pipelines-components

# Compile
python3 -c "
from kfp import compiler
from kfp_components.pipelines.data_processing.ray_data.pdf_documents_processing_rag_pipeline.pipeline import rag_multistep_pipeline
compiler.Compiler().compile(rag_multistep_pipeline, package_path='rag_multistep_pipeline.yaml')
"

# Upload pipeline via DSP API
TOKEN=$(oc whoami -t)
DSP_HOST="https://$(oc get route ds-pipeline-dspa -n data-strat-poc -o jsonpath='{.spec.host}')"

curl -sk "$DSP_HOST/apis/v2beta1/pipelines/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "uploadfile=@rag_multistep_pipeline.yaml;type=application/x-yaml"
```

## Step 10: Run the Pipeline

See [runbooks/run-ingest-pipeline.md](runbooks/run-ingest-pipeline.md) for full step-by-step instructions on creating a pipeline run with the correct parameters, monitoring progress, and verifying results.

## Health Verification

After deployment, verify all components:

```bash
echo "=== Pods ==="
oc get pods -n data-strat-poc

echo "=== Milvus ==="
oc get svc milvus -n data-strat-poc

echo "=== DSPA ==="
oc get dspa -n data-strat-poc

echo "=== PVCs ==="
oc get pvc -n data-strat-poc

echo "=== Routes ==="
oc get routes -n data-strat-poc
```

**Expected:** All pods Running, Milvus service on port 19530, DSPA ready, PVCs bound, DSP route available.

## Tagging Checkpoints (DEC-006)

After verifying a milestone phase, tag **all project repos** simultaneously so the state can be recreated.

### Tagging

```bash
# After verifying a milestone phase, tag all repos with the same tag
TAG="m1-p2"  # pattern: m<milestone>-p<phase>

# Tag data-strat-poc
git -C ~/dev/git-repos/data-strat-poc tag "$TAG"
git -C ~/dev/git-repos/data-strat-poc push origin "$TAG"

# Tag pipelines-components fork (data-strat-poc branch)
git -C ~/dev/odh/pipelines-components tag "$TAG"
git -C ~/dev/odh/pipelines-components push fork "$TAG"

echo "Tagged all repos with $TAG"
```

For full milestone sign-off, also create a `m<N>-complete` tag.

### Recreating a Checkpoint

```bash
# Check out a specific milestone/phase across all repos
TAG="m1-p2"
git -C ~/dev/git-repos/data-strat-poc checkout "$TAG"
git -C ~/dev/odh/pipelines-components checkout "$TAG"

# Recompile the pipeline from that state
pip install -e ~/dev/odh/pipelines-components  # or /tmp clone if file watcher issue
python3 -c "
from kfp import compiler
from kfp_components.pipelines.data_processing.ray_data.pdf_documents_processing_rag_pipeline.pipeline import rag_multistep_pipeline
compiler.Compiler().compile(rag_multistep_pipeline, package_path='rag_multistep_pipeline.yaml')
"

# Redeploy infrastructure from that tag's manifests
oc apply -f manifests/base/namespace-setup.yaml -n data-strat-poc
# ... follow the deployment steps above
```

### Falling Back

```bash
# If a change breaks things, revert to the last known-good tag
TAG="m1-p1"
git -C ~/dev/git-repos/data-strat-poc checkout "$TAG"
git -C ~/dev/odh/pipelines-components checkout "$TAG"
# Recompile pipeline and redeploy
```

### Comparing Phases

```bash
# See what changed between phases
git -C ~/dev/git-repos/data-strat-poc diff m1-p1..m1-p2
git -C ~/dev/odh/pipelines-components diff m1-p1..m1-p2
```

### Current Tags

| Tag | Date | Description |
|-----|------|-------------|
| `m0-complete` | 2026-05-25 | M0 documentation and planning complete |
| `m1-p0` | 2026-05-25 | M1 Phase 0: Saad's baseline validated on cluster |
| `m1-p1` | 2026-05-25 | M1 Phase 1: Scenario B metadata adaptations verified (small scale) |
| `m1-p2` | 2026-05-25 | M1 Phase 2: Full corpus (11 PDFs, 312 vectors), idempotency verified |
| `m1-complete` | 2026-05-25 | M1 milestone sign-off |
| `m2-complete` | 2026-05-25 | M2 milestone sign-off: lineage + MLflow |

## M2: Marquez + Lineage Configuration

### Step 7: Deploy Marquez (Lineage Backend)

```bash
# Deploy PostgreSQL + Marquez API + Web UI
oc apply -f manifests/marquez/ -n data-strat-poc

# Wait for PostgreSQL
oc rollout status deployment/marquez-postgres -n data-strat-poc --timeout=2m

# Wait for Marquez API
oc rollout status deployment/marquez-api -n data-strat-poc --timeout=2m

# Wait for Marquez Web UI
oc rollout status deployment/marquez-web -n data-strat-poc --timeout=2m
```

**Expected:** Three deployments Running. Routes created for API and Web UI.

**Verification:**
```bash
# API health
curl -sk "https://marquez-data-strat-poc.apps.dev.aip-ft.rh-ods.com/api/v1/namespaces"

# Web UI
echo "https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com"
```

**Key gotchas:**
- PostgreSQL needs `fsGroup` in SecurityContext for PVC write access
- Marquez API requires `MARQUEZ_CONFIG` env var pointing to config file (not inline YAML)
- Marquez Web UI needs `WEB_PORT` set explicitly (not `PORT`)

### Step 8: Apply Lineage ConfigMap

```bash
oc apply -f manifests/marquez/lineage-config.yaml -n data-strat-poc
```

This creates the `data-strat-lineage-config` ConfigMap with:
- `MARQUEZ_URL` — internal Marquez API endpoint
- `MLFLOW_BRIDGE_ENABLED` — `false` by default
- `MLFLOW_TRACKING_URI` — RHOAI MLflow endpoint

### Step 9: Inject OpenLineage Namespace into DSP

```bash
./scripts/inject-openlineage-namespace.sh
```

This patches the DSPA CR to include `OPENLINEAGE_NAMESPACE` from the Kubernetes downward API (`metadata.namespace`). Pipeline pods will automatically receive the namespace as an environment variable.

**Verification:**
```bash
# Check DSPA has the annotation
oc get dspa dspa -n data-strat-poc -o jsonpath='{.spec.apiServer}' | python3 -m json.tool
```

**Key gotcha:** The ConfigMap env injection and downward API injection can conflict if both try to set `OPENLINEAGE_NAMESPACE`. The downward API approach takes precedence and is more portable.

### Step 10: MLflow (No Action Needed)

MLflow is deployed cluster-wide by the RHOAI MLflow Operator. No per-namespace deployment is required.

**Verification:**
```bash
# Check MLflow Operator status
oc get mlflow -A

# Check MLflow route
oc get route mlflow-ui -n redhat-ods-applications
```

**Access from pipeline pods:** Requires SA token + `X-Mlflow-Workspace: data-strat-poc` header. See [MLflow integration](../technical/mlflow-integration.md) for details. Note: this is currently a known limitation (PG-024).

---

## Known Issues

See [troubleshooting.md](troubleshooting.md) and [M1 Phase 0 lessons learned](../working/m1-phase0-lessons-learned.md) for known issues and workarounds.

Key gotchas:
- Milvus service is `milvus` not `milvus-standalone` — use `milvus.data-strat-poc.svc.cluster.local:19530`
- KFP Python client SSL verification doesn't work on Python 3.14 — use `curl -sk` via route
- MinIO `mc` image needs `MC_CONFIG_DIR=/tmp/.mc` env var
- IBM Cloud VPC block storage has per-node volume limits (~12) — PVCs may stay Pending on busy clusters
