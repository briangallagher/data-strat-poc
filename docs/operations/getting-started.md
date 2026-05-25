# Getting Started

Step-by-step guide to deploy the system from scratch. Start here after confirming all [prerequisites](prerequisites.md).

**Last Updated:** 2026-05-23 (M1 Phase 0 — verified deployment sequence)

## Deployment Order

Components must be deployed in this order due to dependencies:

```
1. Namespace + Secrets + PVCs  (base)
2. MinIO                       (needed by DSPA and pipeline)
3. MinIO buckets               (needed by DSPA)
4. DSPA                        (needs MinIO)
5. Milvus                      (independent, but needed before pipeline runs)
6. RBAC                        (needs DSPA service account to exist)
7. Upload test data            (needs data-pvc)
8. Compile + upload pipeline   (needs DSPA)
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

## Step 8: Compile and Run Pipeline

```bash
# Install pipelines-components (from fork with auth fixes)
pip install -e /path/to/pipelines-components

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

See `docs/operations/runbooks/run-ingest-pipeline.md` for creating a pipeline run with the correct parameters.

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

## Known Issues

See [troubleshooting.md](troubleshooting.md) and [M1 Phase 0 lessons learned](../working/m1-phase0-lessons-learned.md) for known issues and workarounds.

Key gotchas:
- Milvus service is `milvus` not `milvus-standalone` — use `milvus.data-strat-poc.svc.cluster.local:19530`
- KFP Python client SSL verification doesn't work on Python 3.14 — use `curl -sk` via route
- MinIO `mc` image needs `MC_CONFIG_DIR=/tmp/.mc` env var
- IBM Cloud VPC block storage has per-node volume limits (~12) — PVCs may stay Pending on busy clusters
