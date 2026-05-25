# Runbook: Run Ingest Pipeline

**Last Verified:** 2026-05-25 (M1 Phase 2 — 11 PDFs, 312 vectors)
**Prerequisites:** [prerequisites.md](../prerequisites.md)

## Pipeline Variants

| Pipeline | File | Compiled YAML | When to Use |
|----------|------|---------------|-------------|
| **Ingest (data-chain-only)** | `ingest_pipeline.py` | `rag_ingest_pipeline.yaml` | M1–M3: parse, chunk, embed, store. No model deployment. |
| **Full multi-step** | `pipeline.py` | `rag_multistep_pipeline.yaml` | M4+: adds LLM download + deployment for RAG inference. |

This runbook uses the **data-chain-only ingest pipeline** (`rag_ingest_pipeline.yaml`). See [DEC-007](../../decisions.md#dec-007-data-chain-only-ingest-pipeline-for-m1m3) for the rationale behind the split.

## What This Does

Compiles, uploads, and runs the KFP-orchestrated ingest pipeline that parses PDFs with RayData + Docling, generates embeddings with Granite Embedding 125M, and stores vectors in Milvus. This runbook covers a single end-to-end pipeline run from compilation to result verification.

## Prerequisites

- [ ] Cluster infrastructure deployed per [getting-started.md](../getting-started.md) (steps 1–7)
- [ ] Milvus running and accessible at `milvus.data-strat-poc.svc.cluster.local:19530`
- [ ] MinIO running with `rag-chunks` and `pipeline-artifacts` buckets
- [ ] DSPA deployed with all 6 `ds-pipeline-*` pods Running
- [ ] RBAC applied for pipeline SA (`manifests/rbac/pipeline-rbac.yaml`)
- [ ] PDF documents uploaded to S3 at your chosen input path
- [ ] `oc` logged in with access to the `data-strat-poc` namespace
- [ ] Python 3.11+ with `kfp` installed locally

## Steps

### 1. Install pipelines-components

Install the fork branch with auth fixes. Use a `/tmp` clone to avoid the file watcher issue (see [Phase 0 lessons learned](../../working/m1-phase0-lessons-learned.md)).

```bash
rm -rf /tmp/pipelines-components
git clone --branch data-strat-poc \
  https://github.com/briangallagher/pipelines-components.git \
  /tmp/pipelines-components

pip install -e /tmp/pipelines-components
```

**Expected output:** Successful pip install with no errors.

**If it fails:** Check that the `data-strat-poc` branch exists on the fork. Verify Python version is 3.11+.

### 2. Compile the Pipeline

```bash
python3 -c "
from kfp import compiler
from kfp_components.pipelines.data_processing.ray_data.pdf_documents_processing_rag_pipeline.ingest_pipeline import rag_ingest_pipeline
compiler.Compiler().compile(rag_ingest_pipeline, package_path='rag_ingest_pipeline.yaml')
print('Pipeline compiled successfully')
"
```

**Expected output:** `Pipeline compiled successfully` and a `rag_ingest_pipeline.yaml` file in the current directory.

**If it fails:**
- `ModuleNotFoundError` — re-run `pip install -e /tmp/pipelines-components`
- `ImportError` on `component.py` — the file watcher may have deleted it. Re-clone to `/tmp`

### 3. Upload the Pipeline

```bash
TOKEN=$(oc whoami -t)
DSP_HOST="https://$(oc get route ds-pipeline-dspa -n data-strat-poc -o jsonpath='{.spec.host}')"

curl -sk "$DSP_HOST/apis/v2beta1/pipelines/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "uploadfile=@rag_ingest_pipeline.yaml;type=application/x-yaml"
```

**Expected output:** JSON response with `pipeline_id` and `display_name`. Note the `pipeline_id` — you need it to create a run.

**If it fails:**
- `401 Unauthorized` — token expired; re-run `oc login`
- `Connection refused` — DSPA pods not running; check `oc get pods -n data-strat-poc | grep ds-pipeline`
- SSL errors — use `curl -sk` (the `-k` flag skips certificate verification)

### 4. Get the Pipeline Version ID

```bash
PIPELINE_ID="<pipeline_id from step 3>"

curl -sk "$DSP_HOST/apis/v2beta1/pipelines/$PIPELINE_ID/versions" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Note the `pipeline_version_id` from the response.

### 5. Create a Pipeline Run

Generate a unique `pipeline_run_id` and submit the run with all required parameters:

```bash
PIPELINE_VERSION_ID="<pipeline_version_id from step 4>"
PIPELINE_RUN_ID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")

echo "Pipeline run ID: $PIPELINE_RUN_ID"

curl -sk "$DSP_HOST/apis/v2beta1/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "ingest-run-'"$(date +%Y%m%d-%H%M%S)"'",
    "pipeline_version_reference": {
      "pipeline_id": "'"$PIPELINE_ID"'",
      "pipeline_version_id": "'"$PIPELINE_VERSION_ID"'"
    },
    "runtime_config": {
      "parameters": {
        "namespace": "data-strat-poc",
        "milvus_host": "milvus.data-strat-poc.svc.cluster.local",
        "milvus_port": "19530",
        "collection_name": "underwriting_guidelines",
        "drop_existing": "true",
        "pipeline_run_id": "'"$PIPELINE_RUN_ID"'",
        "s3_endpoint": "http://minio-service:9000",
        "s3_access_key": "minioadmin",
        "s3_secret_key": "minioadmin",
        "input_s3_path": "rag-chunks/input/pdfs",
        "embedding_model": "ibm-granite/granite-embedding-125m-english",
        "embedding_dim": "768",
        "max_tokens": "256",
        "ray_image": "quay.io/rhoai-szaher/docling-ray:latest",
        "doc_lob": "commercial_property",
        "doc_type": "underwriting_guidelines",
        "doc_effective_date": "2025-01-01"
      }
    }
  }'
```

**Key parameters to customise per run:**

| Parameter | What to Set | Example |
|-----------|------------|---------|
| `collection_name` | Target Milvus collection | `underwriting_guidelines` |
| `drop_existing` | `true` for clean re-run, `false` to append | `true` |
| `pipeline_run_id` | Unique UUID for lineage tracing | auto-generated above |
| `input_s3_path` | S3 path to your PDFs | `rag-chunks/input/pdfs` |
| `doc_lob` | Line of business for all docs in this run | `commercial_property` |
| `doc_type` | Document type for all docs | `underwriting_guidelines` |
| `doc_effective_date` | Effective date for all docs | `2025-01-01` |

**Expected output:** JSON response with `run_id` and status `PENDING`.

**If it fails:** Check that `pipeline_id` and `pipeline_version_id` are correct. Verify parameter names match exactly.

### 6. Monitor the Pipeline Run

```bash
RUN_ID="<run_id from step 5>"

# Check run status
curl -sk "$DSP_HOST/apis/v2beta1/runs/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f'Status: {r.get(\"state\", \"UNKNOWN\")}')
for t in r.get('run_details', {}).get('task_details', []):
    print(f'  {t[\"display_name\"]}: {t.get(\"state\", \"UNKNOWN\")}')
"
```

You can also monitor via:

```bash
# Watch pods (RayJob creates ray-head and ray-worker pods)
oc get pods -n data-strat-poc -w

# Check RayJob status
oc get rayjobs -n data-strat-poc

# View pipeline runner pod logs
oc logs -n data-strat-poc -l pipeline/runid=$RUN_ID --tail=50 -f
```

**Typical timing (11 PDFs):**
- `parse_and_chunk`: ~4–5 minutes (includes Ray cluster spinup + Docling processing)
- `ingest_to_milvus`: ~2 minutes (embedding + Milvus insert)
- Total end-to-end: ~7 minutes

**If it hangs:** Check Ray worker pods for OOM (`oc describe pod <ray-worker>`). Check RayJob events (`oc describe rayjob <name>`). The 4-hour timeout will eventually fail the job.

### 7. Verify Results

#### Check Milvus Collection

Port-forward to Milvus and query:

```bash
# In a separate terminal
oc port-forward svc/milvus 19530:19530 -n data-strat-poc
```

```python
from pymilvus import connections, Collection

connections.connect(host="localhost", port="19530")
col = Collection("underwriting_guidelines")
col.load()

print(f"Vector count: {col.num_entities}")

# Sample query — check metadata fields
results = col.query(
    expr='chunk_index >= 0',
    output_fields=["source_file", "source_document_id", "pipeline_run_id",
                    "chunk_index", "lob", "doc_type", "effective_date"],
    limit=5
)
for r in results:
    print(r)

# Verify pipeline_run_id matches
results = col.query(
    expr=f'pipeline_run_id == "{PIPELINE_RUN_ID}"',
    output_fields=["source_file", "chunk_index"],
    limit=5
)
print(f"\nVectors with this pipeline_run_id: {len(results)}")
```

**Expected:** All vectors have non-empty `source_file`, `source_document_id`, `pipeline_run_id`, `lob`, `doc_type`, `effective_date`. Vector count should roughly match: ~25–30 chunks per PDF for typical documents.

#### Check S3 JSONL Output

```bash
# List JSONL files in MinIO
oc run mc-check --rm -i --restart=Never \
  --image=minio/mc:latest \
  --env=MC_CONFIG_DIR=/tmp/.mc \
  -n data-strat-poc -- sh -c "
    mc alias set local http://minio-service:9000 minioadmin minioadmin
    mc ls local/rag-chunks/ --recursive | grep '.jsonl'
  "
```

#### Similarity Search Test

```python
from pymilvus import connections, Collection

connections.connect(host="localhost", port="19530")
col = Collection("underwriting_guidelines")
col.load()

from sentence_transformers import SentenceTransformer
model = SentenceTransformer("ibm-granite/granite-embedding-125m-english")
query_vec = model.encode("property insurance coverage limits").tolist()

results = col.search(
    data=[query_vec],
    anns_field="embedding",
    param={"metric_type": "COSINE", "params": {"ef": 64}},
    limit=3,
    output_fields=["source_file", "text", "lob"]
)

for hits in results:
    for hit in hits:
        print(f"Score: {hit.score:.4f} | {hit.entity.get('source_file')}")
        print(f"  {hit.entity.get('text')[:200]}...")
        print()
```

## Verification

| Check | Method | Expected |
|-------|--------|----------|
| Pipeline status | DSP API or `oc get pods` | All steps Succeeded |
| Vector count | `col.num_entities` | ~25-30 per PDF (312 for 11 PDFs) |
| Metadata present | `col.query()` with `output_fields` | All 8 metadata fields populated |
| `pipeline_run_id` set | Query by `pipeline_run_id` | All vectors match the run UUID |
| Similarity search | `col.search()` with a test query | Relevant results returned with scores > 0.5 |
| Idempotency | Re-run with `drop_existing=true`, compare counts | Same vector count as first run |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `parse_and_chunk` stuck creating RayJob | SA lacks permissions | Apply `manifests/rbac/pipeline-rbac.yaml` |
| RayJob stuck in PENDING | No workers scheduled (resource constraints) | Check node resources; try `bypass_kueue=true` |
| Ray worker OOM | Large PDFs or too many actors | Reduce `num_actors` or increase `ray_worker_memory` |
| `ingest_to_milvus` connection refused | Wrong Milvus host | Use `milvus.data-strat-poc.svc.cluster.local` (not `milvus-standalone`) |
| Empty Milvus collection | JSONL path mismatch | Verify `chunks_s3_path` matches `parse_and_chunk` output path |
| Embedding dimension mismatch | Model changed without updating `embedding_dim` | Ensure model and `embedding_dim` match (768 for Granite 125M) |
| Pipeline upload 401 | Token expired | Re-run `oc login` and `TOKEN=$(oc whoami -t)` |
| `component.py` not found | File watcher deleting it | Re-clone to `/tmp/pipelines-components` |
