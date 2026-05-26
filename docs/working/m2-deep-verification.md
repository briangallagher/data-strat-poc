# Milestone 2: Deep Verification Report

**Date:** 2026-05-26
**Cluster:** data-strat-poc namespace on api.dev.aip-ft.rh-ods.com
**Pipeline Run:** DEEP-VERIFY-2

## Pipeline Run Details

| Field | Value |
|-------|-------|
| KFP Run ID | `6a3dce66-4a4c-49a8-a439-c133488b6609` |
| Pipeline Run ID (correlation) | `fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9` |
| Display Name | DEEP-VERIFY-2 |
| Pipeline ID | `d2cf017d-06c6-4ef1-add7-f9f0ca0a1844` |
| Pipeline Version ID | `18e75599-4bb1-45f1-adf3-03b305a895b8` |
| Created | 2026-05-26T10:53:50Z |
| Finished | 2026-05-26T11:00:02Z |
| Duration | ~6 minutes 12 seconds |

### Runtime Parameters

| Parameter | Value |
|-----------|-------|
| namespace | data-strat-poc |
| pvc_name | data-pvc |
| input_path | input/pdfs |
| s3_endpoint | http://minio-service.data-strat-poc.svc.cluster.local:9000 |
| s3_bucket | rag-chunks |
| s3_prefix | chunks-deep-verify |
| milvus_host | milvus.data-strat-poc.svc.cluster.local |
| milvus_port | 19530 |
| collection_name | underwriting_guidelines |
| drop_existing | True |
| num_workers | 1 |
| worker_cpus | 4 |
| worker_memory_gb | 8 |
| num_files | 3 |
| bypass_kueue | True |
| pipeline_run_id | fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |
| doc_category | commercial_property |
| doc_subcategory | regulatory_bulletin |
| doc_date | 2024-01-01 |
| index_type | HNSW |

---

## 1. KFP Verification

**Result: PASS**

| Check | Status |
|-------|--------|
| Run state = SUCCEEDED | PASS |
| Both main tasks completed | PASS |
| Runtime parameters match submission | PASS |

### Task Execution Details

| Task | State | Pod |
|------|-------|-----|
| root | SUCCEEDED | rag-ingest-pipeline-xzt9v-3220418881 |
| root-driver | SUCCEEDED | rag-ingest-pipeline-xzt9v-4100518925 |
| parse-and-chunk | SUCCEEDED | rag-ingest-pipeline-xzt9v-3949182255 |
| parse-and-chunk-driver | SUCCEEDED | rag-ingest-pipeline-xzt9v-470530572 |
| ingest-to-milvus | SUCCEEDED | rag-ingest-pipeline-xzt9v-3481146483 |
| ingest-to-milvus-driver | SUCCEEDED | rag-ingest-pipeline-xzt9v-1989178024 |
| executor (parse_and_chunk) | SUCCEEDED | rag-ingest-pipeline-xzt9v-4224694965 |
| executor (ingest_to_milvus) | SUCCEEDED | — |

All 9 task nodes completed successfully. The pipeline DAG structure shows proper sequential execution: parse-and-chunk ran first (RayJob for document processing), followed by ingest-to-milvus (embedding and vector store loading).

---

## 2. Marquez Verification (OpenLineage)

**Result: PASS**

### Jobs

| Job | Type | Latest Run State | pipelineRunId |
|-----|------|-----------------|---------------|
| parse_and_chunk | BATCH | COMPLETED | fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |
| ingest_to_milvus | BATCH | COMPLETED | fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |

### Datasets (3 total across namespaces)

| Dataset | Namespace | Type | Custom Facets |
|---------|-----------|------|---------------|
| data-pvc/input/pdfs | pvc://data-strat-poc | DB_TABLE | — |
| rag-chunks/chunks-deep-verify | s3://minio-service.data-strat-poc.svc.cluster.local:9000 | DB_TABLE | custom_metrics |
| underwriting_guidelines | milvus://milvus.data-strat-poc.svc.cluster.local:19530 | DB_TABLE | custom_metrics |

### Dataset Custom Metrics

**S3 Dataset (rag-chunks/chunks-deep-verify):**

| Metric | Value |
|--------|-------|
| num_files | 3 |
| num_workers | 1 |
| chunk_max_tokens | 256 |
| tokenizer | ibm-granite/granite-embedding-125m-english |
| duration_seconds | 195.21 |
| _producer | https://github.com/rhoai-lineage |

**Milvus Dataset (underwriting_guidelines):**

| Metric | Value |
|--------|-------|
| collection_name | underwriting_guidelines |
| embedding_model | ibm-granite/granite-embedding-125m-english |
| embedding_dim | 768 |
| index_type | HNSW |
| vectors_inserted | 27 |
| duration_seconds | 4.35 |
| _producer | https://github.com/rhoai-lineage |

### Lineage Graph

```
Graph nodes: 5
Total edges: 4

[DATASET] pvc://data-strat-poc : data-pvc/input/pdfs
    → job:data-strat-poc:parse_and_chunk

[JOB] data-strat-poc : parse_and_chunk
    ← dataset:pvc://data-strat-poc:data-pvc/input/pdfs
    → dataset:s3://minio-service...:rag-chunks/chunks-deep-verify

[DATASET] s3://minio-service... : rag-chunks/chunks-deep-verify
    ← job:data-strat-poc:parse_and_chunk
    → job:data-strat-poc:ingest_to_milvus

[JOB] data-strat-poc : ingest_to_milvus
    ← dataset:s3://minio-service...:rag-chunks/chunks-deep-verify
    → dataset:milvus://...:underwriting_guidelines

[DATASET] milvus://... : underwriting_guidelines
    ← job:data-strat-poc:ingest_to_milvus
```

| Check | Status |
|-------|--------|
| Both jobs exist | PASS |
| 3 datasets exist (PVC, S3, Milvus) | PASS |
| pipelineRunId facet on both jobs' latest runs | PASS |
| pipelineRunId matches pipeline_run_id | PASS |
| Lineage graph has 5 nodes | PASS |
| Lineage graph has 4 edges | PASS |
| Custom metrics on S3 dataset | PASS |
| Custom metrics on Milvus dataset | PASS |

---

## 3. MLflow Verification

**Result: PASS**

### Experiment

| Field | Value |
|-------|-------|
| Experiment ID | 53 |
| Experiment Name | data-strat-ingest |
| Lifecycle Stage | active |

### Parent Run

| Field | Value |
|-------|-------|
| MLflow Run ID | `977ba18a18af4653ac6eafeaf0f8f3ef` |
| Run Name | fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |
| Status | FINISHED |
| Tags | kfp.component=pipeline, kfp.namespace=data-strat-poc, kfp.pipeline_run_id=fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |

### Nested Run: parse_and_chunk

| Field | Value |
|-------|-------|
| MLflow Run ID | `e13b876c1f2249ba811a9a91be9b1367` |
| Run Name | parse_and_chunk |
| Status | FINISHED |
| mlflow.parentRunId | 977ba18a18af4653ac6eafeaf0f8f3ef |

**Params:**

| Parameter | Value |
|-----------|-------|
| pipeline_run_id | fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |
| num_files | 3 |
| chunk_max_tokens | 256 |
| embedding_model | ibm-granite/granite-embedding-125m-english |
| doc_category | commercial_property |
| doc_subcategory | regulatory_bulletin |
| doc_date | 2024-01-01 |
| namespace | data-strat-poc |
| num_workers | 1 |
| worker_cpus | 4 |
| worker_memory_gb | 8 |
| ray_image | quay.io/rhoai-szaher/docling-ray:latest |
| s3_bucket | rag-chunks |
| s3_prefix | chunks-deep-verify |

**Metrics:**

| Metric | Value |
|--------|-------|
| duration_seconds | 195.37 |

### Nested Run: ingest_to_milvus

| Field | Value |
|-------|-------|
| MLflow Run ID | `928251f762bc44c59b9c0a5f1e8de24f` |
| Run Name | ingest_to_milvus |
| Status | FINISHED |
| mlflow.parentRunId | 977ba18a18af4653ac6eafeaf0f8f3ef |

**Params:**

| Parameter | Value |
|-----------|-------|
| pipeline_run_id | fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |
| collection_name | underwriting_guidelines |
| embedding_model | ibm-granite/granite-embedding-125m-english |
| embedding_dim | 768 |
| index_type | HNSW |
| milvus_host | milvus.data-strat-poc.svc.cluster.local |
| embed_batch_size | 64 |
| milvus_batch_size | 256 |
| drop_existing | True |
| s3_bucket | rag-chunks |
| s3_prefix | chunks-deep-verify |

**Metrics:**

| Metric | Value |
|--------|-------|
| vectors_inserted | 27.0 |
| documents_processed | 3.0 |
| duration_seconds | 4.35 |
| vectors_per_second | 6.20 |

### MLflow Checks

| Check | Status |
|-------|--------|
| Parent run exists with kfp.component=pipeline | PASS |
| Parent run has kfp.pipeline_run_id set | PASS |
| Two nested runs exist | PASS |
| Both nested runs have mlflow.parentRunId → parent | PASS |
| parse_and_chunk has all required params | PASS |
| parse_and_chunk has duration_seconds metric | PASS |
| ingest_to_milvus has all required params | PASS |
| ingest_to_milvus has vectors_inserted, documents_processed, duration_seconds, vectors_per_second | PASS |
| Both nested runs share same pipeline_run_id | PASS |
| Parent run status = FINISHED | PASS |

---

## 4. Milvus Verification

**Result: PASS**

### Collection Schema

| Field | Type |
|-------|------|
| id | INT64 (5) |
| source_file | VARCHAR (21) |
| source_document_id | VARCHAR (21) |
| pipeline_run_id | VARCHAR (21) |
| chunk_index | INT64 (5) |
| text | VARCHAR (21) |
| category | VARCHAR (21) |
| subcategory | VARCHAR (21) |
| document_date | VARCHAR (21) |
| embedding | FLOAT_VECTOR (101) |

**Total fields: 10**

### Vector Data

| Metric | Value |
|--------|-------|
| Total vectors | 27 |
| Unique pipeline_run_ids | 1 (fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9) |

### Per-Document Vector Counts

| Document | Vectors |
|----------|---------|
| ca-doi-bulletin-2024-7-rate-application-review | 7 |
| ca-doi-bulletin-2025-3-wildfire-claims | 6 |
| ca-doi-bulletin-2025-4-fair-plan-recoupment | 14 |

### Sample Vector Metadata

| Field | Value |
|-------|-------|
| source_document_id | ca-doi-bulletin-2024-7-rate-application-review |
| pipeline_run_id | fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9 |
| category | commercial_property |
| subcategory | regulatory_bulletin |
| document_date | 2024-01-01 |
| chunk_index | 0 |

### Metadata Completeness

| Field | Coverage |
|-------|----------|
| pipeline_run_id | 27/27 (100%) |
| category | 27/27 (100%) |
| subcategory | 27/27 (100%) |
| document_date | 27/27 (100%) |
| source_document_id | 27/27 (100%) |

### Milvus Checks

| Check | Status |
|-------|--------|
| All 10 schema fields present | PASS |
| pipeline_run_id matches run | PASS |
| category populated correctly | PASS |
| subcategory populated correctly | PASS |
| document_date populated correctly | PASS |
| Vectors queryable | PASS |

---

## 5. Cross-System Correlation

**Result: PASS — pipeline_run_id traced across all 4 systems**

The correlation ID `fd8abb5e-f8c5-4e2c-b31b-90ffe542b8b9` is present and consistent across:

| System | Location | Verified |
|--------|----------|----------|
| KFP | Runtime parameter `pipeline_run_id` | PASS |
| Marquez | `pipelineRunId` facet on parse_and_chunk run | PASS |
| Marquez | `pipelineRunId` facet on ingest_to_milvus run | PASS |
| MLflow | Parent run tag `kfp.pipeline_run_id` | PASS |
| MLflow | parse_and_chunk param `pipeline_run_id` | PASS |
| MLflow | ingest_to_milvus param `pipeline_run_id` | PASS |
| Milvus | All 27 vectors field `pipeline_run_id` | PASS |

```
KFP Run (pipeline_run_id param)
    │
    ├──→ Marquez parse_and_chunk (pipelineRunId facet)
    │       │
    │       └──→ Marquez ingest_to_milvus (pipelineRunId facet)
    │
    ├──→ MLflow Parent Run (kfp.pipeline_run_id tag)
    │       │
    │       ├──→ MLflow parse_and_chunk (pipeline_run_id param)
    │       │
    │       └──→ MLflow ingest_to_milvus (pipeline_run_id param)
    │
    └──→ Milvus vectors (pipeline_run_id field on all 27 vectors)
```

---

## 6. Issues Found

### Resolved During Run

1. **IBM VPC Block Storage attach timeouts** — The IBM Cloud `vpc.block.csi.ibm.io` CSI driver consistently timed out when attaching volumes, affecting both the data PVC and Milvus's etcd/standalone PVCs. This is a known IBM Cloud infrastructure issue on this cluster.
   - **Resolution:** Switched all PVCs to `nfs-csi` storage class which binds immediately and has no attach latency.

2. **Milvus unavailable on first pipeline attempt** — The initial pipeline run (KFP Run `be1a659e-4285-4ad7-8147-82e0e8e095ea`) failed because Milvus's etcd pod was stuck on block storage volume attach.
   - **Resolution:** Redeployed Milvus via Helm with NFS storage class for all components (etcd, minio, standalone).

### Observations (Not Blocking)

1. **MLflow start_time = 0** — Parent and nested runs all show `start_time: 0` which suggests the MLflow client isn't setting the start timestamp. The `end_time` is populated correctly. This is a cosmetic issue in the tracking code.

2. **No kfp.component tag on nested runs** — The nested MLflow runs (parse_and_chunk, ingest_to_milvus) don't carry the `kfp.component` tag. The parent run has `kfp.component: pipeline`. Adding `kfp.component: parse_and_chunk` / `kfp.component: ingest_to_milvus` to nested runs would improve discoverability.

---

## 7. UI Equivalent Views

### KFP Dashboard
The pipeline run "DEEP-VERIFY-2" shows as a green completed run with two sequential task nodes (parse-and-chunk → ingest-to-milvus) both showing green checkmarks. The run took ~6 minutes total. Parameters are visible in the run details panel.

### Marquez Lineage View
The lineage graph renders as a left-to-right DAG:
- **PVC input** (file icon) → **parse_and_chunk** (gear icon) → **S3 JSONL** (file icon) → **ingest_to_milvus** (gear icon) → **Milvus collection** (database icon)

Each job node shows "COMPLETED" state. Clicking the S3 or Milvus dataset nodes reveals the custom_metrics facet panel with processing statistics.

### MLflow Experiment View
The "data-strat-ingest" experiment shows a parent run named after the pipeline_run_id with two nested child runs indented below it. All three show "FINISHED" status. Clicking into ingest_to_milvus shows the metrics chart with vectors_inserted=27 and vectors_per_second=6.2.

---

## Summary

**All verification checks PASSED.** The data strategy PoC pipeline successfully:

1. Processes 3 PDF documents through Docling + chunking (Ray-based)
2. Writes enriched JSONL chunks to S3 (MinIO)
3. Embeds chunks using granite-embedding-125m-english
4. Inserts 27 vectors into Milvus with full metadata
5. Reports lineage to Marquez (OpenLineage) with custom metrics
6. Logs experiment tracking to MLflow with nested parent/child structure
7. Maintains a single correlation ID (`pipeline_run_id`) traceable across ALL four systems
