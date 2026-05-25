# M1 Phase 0: Baseline Lessons Learned

**Date:** 2026-05-23
**Runs:** 11 pipeline runs to reach full data chain success
**Fork branch:** `briangallagher/pipelines-components:data-strat-poc`

---

## Result Summary

| Step | Status | Details |
|------|--------|---------|
| Infrastructure deploy | **PASS** | Milvus, MinIO, DSPA, PVCs, secrets all healthy |
| parse_and_chunk (RayJob) | **PASS** (with fix) | Docling + HybridChunker parsed 2 PDFs, JSONL in S3 |
| ingest_to_milvus | **PASS** | Local Granite Embedding 125M, chunks in Milvus, queryable |
| download_model | **PASS** | Mistral 7B downloaded to PVC with cache-skip |
| model_deployment | **BLOCKED** | `_VLLM_IMAGE` constant outside KFP scope + PVC scheduling. Fixed constant, but LLM deployment is M4 scope. |
| deploy_embedding_model | **BLOCKED** | RHOAI 3.4 vLLM image doesn't support `--task=embedding`. Not needed — local sentence-transformers works in `ingest_to_milvus`. |

**Data chain fully verified:** PDF → KFP → RayJob (Docling) → S3 JSONL → Milvus (embedded with Granite Embedding 125M). 5 chunks queryable with real P&C insurance content.

---

## Fixes Applied (on fork branch)

### 1. KFP pod K8s auth (CRITICAL — 7 iterations)

**Problem:** KFP v2 on RHOAI strips `KUBERNETES_SERVICE_HOST` env var from user containers. The SA token is mounted at `/var/run/secrets/kubernetes.io/serviceaccount/` but `load_incluster_config()` fails because it checks for the env var first.

**Root cause chain:**
1. `codeflare_sdk.RayJob.submit()` creates its own K8s client via `kube-authkit` — doesn't use `load_incluster_config()`
2. `load_incluster_config()` itself fails because `KUBERNETES_SERVICE_HOST` is stripped by KFP/Argo
3. Even `set_api_client()` (codeflare SDK) didn't fix it — the SDK's internal client creation path is separate
4. `Configuration.set_default()` doesn't propagate to `CustomObjectsApi()` created without an explicit client

**Fix:** Manually construct `Configuration` from the SA token file, create an explicit `ApiClient`, pass it to `CustomObjectsApi`, and bypass `codeflare_sdk.RayJob.submit()` by calling `job._build_rayjob_cr()` then `custom_api.create_namespaced_custom_object()`.

```python
sa_token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
sa_ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"

conf = k8s_client.Configuration()
conf.host = "https://kubernetes.default.svc"
conf.ssl_ca_cert = sa_ca_path
with open(sa_token_path) as f:
    token = f.read().strip()
conf.api_key = {"BearerToken": token}
conf.api_key_prefix = {"BearerToken": "Bearer"}
api_client = k8s_client.ApiClient(conf)

custom_api = k8s_client.CustomObjectsApi(api_client)

rayjob_cr = job._build_rayjob_cr()
custom_api.create_namespaced_custom_object(
    group="ray.io", version="v1", namespace=namespace,
    plural="rayjobs", body=rayjob_cr,
)
```

**Impact:** All components that call K8s API from KFP pods need this pattern. Applied to `parse_and_chunk`, `model_deployment`, `deploy_embedding_model`.

**Upstream action:** This should be reported to codeflare-sdk and/or the RHOAI DSP team. The env var stripping is deliberate (security isolation), but the official SDK should handle it.

### 2. Module-level constants not captured by KFP (model_deployment)

**Problem:** `_VLLM_IMAGE` defined at module level (outside `@dsl.component` function). KFP serialization only captures the function body, so the constant is undefined at runtime.

**Fix:** Inline the image string directly in the function body.

**Rule for future components:** Never reference module-level variables from inside a `@dsl.component` function. Everything the function needs must be defined within it or passed as parameters.

### 3. RBAC for RayJob creation

**Problem:** Pipeline SA `pipeline-runner-dspa` lacks permissions to create RayJob CRs.

**Fix:** Created Role + RoleBinding granting `create/delete/get/list/patch/update/watch` on `ray.io/rayjobs` and `ray.io/rayclusters`. Also added KServe and HardwareProfile permissions.

**Note:** This is a one-time namespace setup step that should be in the manifests and getting-started guide.

---

## Infrastructure Lessons

### Milvus Helm

- **SCC:** `anyuid` SCC required for Milvus pods (same as v1)
- **Service name:** Helm creates `milvus` service, NOT `milvus-standalone`. The pipeline default `milvus_host` parameter is wrong — must use `milvus.<namespace>.svc.cluster.local`
- **MinIO storage:** Helm defaults to 500Gi for Milvus's internal MinIO. Way oversized for POC — should set to 10-50Gi
- **Deployment time:** ~2 minutes for all Milvus components to be ready

### DSPA

- **External storage config:** Omit the `spec.objectStorage.minio` block entirely when using external S3. Setting `deploy: false` still requires `image` field, which fails validation.
- **DSP Route:** Always HTTPS (even port 8888 named `http`). Use `curl -sk` or the external route URL.

### MinIO

- **mc image:** Needs `MC_CONFIG_DIR=/tmp/.mc` env var to work in OpenShift (home dir permissions)
- **Bucket creation:** Must use `mc` with proper config dir, not `curl` (MinIO requires AWS4-HMAC-SHA256 auth)

### PVCs

- **IBM Cloud VPC block storage:** Max ~12 volumes per node. Shared cluster with 64 PVs can hit this limit. PVC stays Pending until a slot frees up.
- **model-cache-pvc:** Resolved itself after cleanup of other namespaces' PVCs

### KFP Python client (local)

- **SSL verification:** `ssl_ca_cert=False` parameter doesn't actually disable SSL verification on Python 3.14. The internal urllib3 pool manager still validates. Use `curl -sk` via the route instead.
- **Pipeline upload:** The `/apis/v2beta1/pipelines/upload` endpoint with multipart form works reliably via curl.

### pipelines-components repo

- **component.py deletion:** Something in the local development environment (likely Cursor file watcher or indexer) actively deletes `components/data_processing/parse_and_chunk/component.py` within seconds of checkout. Workaround: clone to `/tmp` for compilation. Root cause unknown.

### Ray/Docling image

- **Image size:** `quay.io/rhoai-szaher/docling-ray:latest` is large (~3GB). First pull takes ~1 minute.
- **Image pull timeout:** On slow nodes, the 600s timeout for cluster readiness may not be enough when combined with image pull time.

### Embedding model

- **RHOAI 3.4 vLLM:** Does NOT support `--task=embedding` flag. This flag is from a newer vLLM version.
- **Local embedding works:** The `ingest_to_milvus` component's local `sentence-transformers` mode works well — downloads Granite Embedding 125M from HuggingFace at runtime (~500MB) and embeds in-pod. No separate embedding service needed for the data pipeline.

---

## What Saad's Pipeline Does Well

- **Parallel chains:** Data chain (parse → ingest) and model chain (download → deploy) run independently. Data chain succeeds even when model chain is blocked.
- **S3 intermediate storage:** Chunks in S3 as JSONL between parse and ingest steps. Enables retry of ingest without re-parsing.
- **Dual embedding modes:** Local sentence-transformers or remote vLLM endpoint — configurable per run.
- **Component structure:** Clean separation of concerns. Each component is self-contained.
- **RayJob + Docling actors:** HybridChunker with configurable actor pool and batch size.

## What Needs Fixing for Production

1. **K8s auth in KFP pods** — critical fix applied on fork branch
2. **Module-level constants** — `_VLLM_IMAGE` and potentially others need inlining
3. **Milvus host parameter default** — wrong service name
4. **Timeout logic** — the old `parse_and_chunk` code had a 600s timeout for cluster readiness separate from job completion. New code uses 4-hour job-level timeout but should detect SUCCEEDED status sooner.
5. **`drop_existing: true` default** — drops the entire Milvus collection on every run. Should default to `false` for production (append mode).

---

## Production Gaps Discovered

| ID | Gap | Detail |
|----|-----|--------|
| PG-014 | KFP pods lack K8s API access by default | KUBERNETES_SERVICE_HOST stripped; manual SA token loading required |
| PG-015 | No RBAC automation for pipeline SA | Role/RoleBinding for RayJob, KServe, HardwareProfile created manually |
| PG-016 | Milvus deployed with anyuid SCC | Security review concern; should evaluate restricted SCC or operator |
| PG-017 | 500Gi MinIO PVC from Helm defaults | Way oversized for POC; wastes cluster volume attachment slots |
| PG-018 | RHOAI 3.4 vLLM lacks --task=embedding | Can't deploy dedicated embedding service via KServe on this version |
| PG-019 | Local sentence-transformers downloads model every run | No caching across ingest_to_milvus runs; should pre-load or use PVC cache |

---

## Cluster State After Phase 0

**Namespace:** `data-strat-poc`

| Component | Status | Notes |
|-----------|--------|-------|
| Milvus (standalone) | Running | `rag_documents` collection with 5+ chunks |
| MinIO (pipeline) | Running | `rag-chunks` and `pipeline-artifacts` buckets |
| DSPA (KFP v2) | Running | 6 components |
| data-pvc | Bound (5Gi) | 2 test PDFs loaded |
| model-cache-pvc | Bound (50Gi) | Mistral 7B cached |
| mariadb-dspa | Bound (10Gi) | KFP metadata |

**Fork:** `briangallagher/pipelines-components:data-strat-poc` with auth fixes.

---

## References

| Item | Location |
|------|----------|
| Fork branch | https://github.com/briangallagher/pipelines-components/tree/data-strat-poc |
| Saad's original PR | https://github.com/opendatahub-io/pipelines-components/pull/53 |
| deploy-model-openshift skill | `~/dev/git-repos/team-kubeflow-devx/skills/deploy-model-openshift/SKILL.md` |
| KFP setup skill | `~/dev/git-repos/team-kubeflow-devx/skills/KFP-setup/SKILL.md` |
