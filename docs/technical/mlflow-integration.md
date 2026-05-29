# MLflow Integration

## What This Is

MLflow serves dual roles in this project: **pipeline experiment tracking** (recording parameters, metrics, and artifacts for each ingest run) and **query-time tracing** (capturing GenAI traces for both deterministic and agentic RAG inference paths). Deployed via the RHOAI MLflow Operator (cluster-wide instance with per-namespace workspaces), MLflow is used alongside Marquez (not as a replacement) for observability. Last Updated: 2026-05-28 (M5 complete).

## Architecture Context

MLflow sits alongside Marquez as a complementary observability system:

- **MLflow:** Tracks *what happened* in a run — parameters used, metrics produced, model artifacts — **and** captures GenAI traces from query-time inference paths
- **Marquez:** Tracks *data flow* — which datasets were consumed and produced, by which jobs

```mermaid
graph LR
    subgraph "Pipeline Components"
        PC[parse_and_chunk]
        IM[ingest_to_milvus]
    end

    subgraph "Query Components"
        LG["LangGraph Agent"]
        OGX["OGX / vLLM"]
    end

    subgraph "Observability"
        MLF[MLflow<br/>params, metrics, artifacts, traces]
        MQ[Marquez<br/>lineage graph]
    end

    subgraph "Data Layer"
        REG["Document Registry"]
    end

    PC -->|log params/metrics| MLF
    IM -->|log params/metrics| MLF
    LG -->|"autolog traces"| MLF
    OGX -->|"autolog traces"| MLF
    REG -->|"read traces"| MLF
    PC -->|emit OL events| MQ
    IM -->|emit OL events| MQ

    MLF -.->|bridge ON: openlineage+| MQ
```

## How It Works

### RHOAI MLflow Operator

The MLflow Operator deploys a cluster-wide MLflow instance managed by RHOAI:

| Aspect | Detail |
|--------|--------|
| Operator | `opendatahub-io/mlflow-operator` (installed via RHOAI DSC) |
| Deployment | Cluster-wide in `redhat-ods-applications` namespace |
| Multi-tenancy | Per-namespace workspaces via `X-Mlflow-Workspace` header |
| Auth | SA token + `Authorization: Bearer` header |
| Internal endpoint | `https://mlflow.redhat-ods-applications.svc:8443` |
| External endpoint | `https://mlflow-ui-redhat-ods-applications.apps.dev.aip-ft.rh-ods.com` |

### Pipeline Component Logging

Pipeline components log to MLflow using the standard `mlflow` Python client. Parameters and metrics tracked:

**parse_and_chunk:**
| Type | Key | Example Value |
|------|-----|---------------|
| param | `corpus_path` | `/mnt/data/input/pdfs` |
| param | `chunk_max_tokens` | `256` |
| param | `tokenizer` | `ibm-granite/granite-embedding-125m-english` |
| param | `num_workers` | `2` |
| param | `pipeline_run_id` | `1c067bcc-8dd9-41ab-a264-58a7e4f2d39c` |
| metric | `num_files_processed` | `11` |
| metric | `total_chunks_created` | `312` |
| metric | `duration_seconds` | `240.36` |

**ingest_to_milvus:**
| Type | Key | Example Value |
|------|-----|---------------|
| param | `collection_name` | `underwriting_guidelines` |
| param | `embedding_model` | `ibm-granite/granite-embedding-125m-english` |
| param | `embedding_dim` | `768` |
| param | `index_type` | `HNSW` |
| param | `pipeline_run_id` | `1c067bcc-8dd9-41ab-a264-58a7e4f2d39c` |
| metric | `vectors_inserted` | `312` |
| metric | `duration_seconds` | `29.17` |

### SA Token Auth for In-Cluster Access

KFP pods accessing the RHOAI MLflow instance need:

1. **ServiceAccount token** mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`
2. **Authorization header:** `Bearer <sa-token>`
3. **Workspace header:** `X-Mlflow-Workspace: data-strat-poc`

```python
import mlflow
import os

token = open("/var/run/secrets/kubernetes.io/serviceaccount/token").read()
os.environ["MLFLOW_TRACKING_TOKEN"] = token
os.environ["MLFLOW_TRACKING_URI"] = "https://mlflow.redhat-ods-applications.svc:8443"

mlflow.set_experiment("data-strat-poc/ingest")
with mlflow.start_run():
    mlflow.log_param("corpus_size", num_files)
    mlflow.log_metric("chunks_created", chunk_count)
```

**PG-024 update:** The `X-Mlflow-Workspace` header required by the RHOAI operator is now injected via a custom `RequestHeaderProvider` (see [RHOAI MLflow Auth for Query Pods](#rhoai-mlflow-auth-for-query-pods)). This is validated and working for query pods. KFP pod validation is still pending.

### Bridge Mode

When `MLFLOW_BRIDGE_ENABLED=true`, the MLflow tracking URI is set to:

```
openlineage+https://marquez-data-strat-poc.apps.dev.aip-ft.rh-ods.com/api/v1/lineage
```

This causes the `mlflow` client to emit OpenLineage events to Marquez for every experiment/run operation. The result is that MLflow experiment metadata appears as additional nodes in the Marquez graph.

| Bridge State | MLflow Tracking URI | Marquez Impact |
|-------------|--------------------| --------------|
| OFF (default) | `https://mlflow.redhat-ods-applications.svc:8443` | Only rhoai-lineage OL events |
| ON | `openlineage+https://marquez.../api/v1/lineage` | MLflow events + rhoai-lineage events |

**Trade-off:** Bridge ON provides a unified view but creates synthetic nodes in Marquez that may not map cleanly to the physical data flow. Bridge OFF keeps the graph clean and predictable.

### Configuration

| Environment Variable | Source | Value |
|---------------------|--------|-------|
| `MLFLOW_TRACKING_URI` | `data-strat-lineage-config` ConfigMap | `https://mlflow.redhat-ods-applications.svc:8443` |
| `MLFLOW_BRIDGE_ENABLED` | `data-strat-lineage-config` ConfigMap | `false` |
| `MLFLOW_TRACKING_TOKEN` | SA token (pod mount) | Auto from `/var/run/secrets/...` |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| MLflow (server) | Managed by RHOAI Operator | Experiment tracking backend |
| `mlflow` (Python) | 2.x | Client library in pipeline components |
| MLflow Operator | Part of RHOAI 3.4+ DSC | Deploys and manages MLflow |

## Query-Time Tracing (M4/M5)

### Deterministic RAG (M4)

`mlflow.langchain.autolog()` captures the full LangGraph span tree for each query. Every retrieval, rerank, and generation step is recorded as a nested span.

| Aspect | Detail |
|--------|--------|
| Autolog call | `mlflow.langchain.autolog()` |
| Experiment name | `underwriter-chat-v3` |
| Span structure | Full LangGraph span tree (retrieval → rerank → generation) |

Each trace is enriched with tags for downstream consumption by the Document Registry:

| Tag | Purpose |
|-----|---------|
| `doc_ids_cited` | Document IDs referenced in the response |
| `pipeline_run_ids` | Ingest pipeline run(s) that produced the cited chunks |
| `collection_queried` | Milvus collection searched |
| `chunks_detail` | Serialised chunk metadata |
| `answer_preview` | Truncated answer text |
| `chunks_retrieved_count` | Number of chunks returned by retrieval |

### Agentic RAG (M5)

`mlflow.openai.autolog()` captures OpenAI-format traces for the agentic path. Tool calls are visible as `function_call` / `function_call_output` spans within the trace tree.

| Aspect | Detail |
|--------|--------|
| Autolog call | `mlflow.openai.autolog()` |
| Experiment name | `compliance-review-agent` |
| Tag contract | Same as M4 (`doc_ids_cited`, `pipeline_run_ids`, etc.) |
| Tool visibility | `function_call` and `function_call_output` spans |

### RHOAI MLflow Auth for Query Pods

Query pods (outside KFP) authenticate to the RHOAI MLflow instance using a custom `RequestHeaderProvider` class that injects the required headers on every request:

```python
class RHOAIHeaderProvider:
    """Injects SA token + workspace header for RHOAI MLflow."""

    def in_context(self):
        return True

    def request_headers(self):
        token = open("/var/run/secrets/kubernetes.io/serviceaccount/token").read()
        return {
            "Authorization": f"Bearer {token}",
            "X-Mlflow-Workspace": "data-strat-poc",
        }
```

Activated via environment variable:

```
MLFLOW_TRACKING_REQUEST_HEADER_PROVIDER=<module>.RHOAIHeaderProvider
```

### MLflow API Truncation Caveat

The `search_traces` API truncates `traceInputs` and `traceOutputs` to 250 characters. The Document Registry works around this via:

1. **Tag-based extraction** — critical metadata is stored as trace tags (see tag table above), which are not truncated
2. **Regex fallbacks** — for fields not available as tags, regex parsing extracts values from the truncated strings where possible

## Design Decisions

- **ADR-004:** MLflow and Marquez are independent systems, correlated by `pipeline_run_id`
- **Bridge OFF by default:** Direct OL emission is cleaner for pipeline-time lineage

## Known Limitations

| ID | Limitation | Impact |
|----|-----------|--------|
| PG-002 | MLflow auth relies on RHOAI operator patterns | External access requires kube-auth-proxy |
| PG-024 | MLflow tracking from KFP pods requires RequestHeaderProvider | Resolved for query pods via custom `RequestHeaderProvider`; KFP pod validation still pending |
| PG-060 | ~~MLflow auth for query pods~~ | **Closed** — resolved via `RequestHeaderProvider` injecting SA token + `X-Mlflow-Workspace` header |

## Future Considerations

- ~~**Query-time GenAI traces (M4):**~~ Implemented — see [Query-Time Tracing (M4/M5)](#query-time-tracing-m4m5) above.
- **Model registry integration:** MLflow model registry could track fine-tuned models alongside experiment runs, providing a full lineage from training data → model → deployed endpoint.
- **Artifact logging:** Log chunked JSONL files or embedding samples as MLflow artifacts for debugging and reproducibility.

## References

| Source | Link |
|--------|------|
| ADR-004 | `docs/architecture/adrs/ADR-004-lineage-architecture.md` |
| RHOAI MLflow overview | `knowledge/rhoai/mlflow/mlflow.md` |
| MLflow technical architecture | `knowledge/rhoai/mlflow/technical-architecture.md` |
| MLflow Operator | https://github.com/opendatahub-io/mlflow-operator |
| MLflow Python client | https://mlflow.org/docs/latest/python_api/ |
| ConfigMap manifest | `manifests/marquez/lineage-config.yaml` |
