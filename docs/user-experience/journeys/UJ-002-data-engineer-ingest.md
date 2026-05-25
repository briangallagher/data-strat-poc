# UJ-002: Data Engineer Verifies Pipeline Lineage

**Persona:** Data Engineer (Dana)
**Goal:** Confirm that a pipeline run completed successfully AND verify the full data lineage chain from source documents to vectors
**Trigger:** Pipeline run completes (success or failure notification from KFP UI)

## Journey Steps

### Mode A: Bridge OFF (Default — M2)

| Step | Action | System Response | Touchpoint | Pain Point | Opportunity |
|------|--------|-----------------|------------|------------|-------------|
| 1 | Check KFP UI for pipeline run status | Shows run as Succeeded/Failed with step durations | KFP UI | Must navigate to RHOAI dashboard first | Deep-link from notification |
| 2 | Note the `pipeline_run_id` from KFP run details | Displays run ID in metadata panel | KFP UI | ID is in a nested panel | Copy-to-clipboard button |
| 3 | Open Marquez Web UI | Shows lineage graph for namespace `data-strat-poc` | Marquez Web UI | Separate URL, no SSO | Unified observability UI |
| 4 | Navigate to jobs → select `parse_and_chunk` or `ingest_to_milvus` | Shows job details with latest run, inputs, outputs | Marquez Web UI | Must know job names | Job list with search |
| 5 | Inspect the lineage graph | Visualizes: PVC → parse_and_chunk → S3 → ingest_to_milvus → Milvus | Marquez Web UI | Graph is small and navigable | — |
| 6 | Check dataset facets for metrics | Shows custom_metrics (duration, vectors_inserted, chunk count) | Marquez Web UI | Facets shown as raw JSON | Formatted metric display |
| 7 | Cross-reference `pipeline_run_id` with Milvus metadata | Query Milvus to verify vectors have matching pipeline_run_id | CLI / notebook | Manual query needed (PG-025) | Auto-correlation via run facet |
| 8 | (Optional) Check MLflow for experiment metrics | Open MLflow UI, find experiment for namespace | MLflow UI | Auth + workspace header complexity (PG-024) | SA token auto-injection |

### Mode B: Bridge ON (Opt-in)

| Step | Action | System Response | Touchpoint | Pain Point | Opportunity |
|------|--------|-----------------|------------|------------|-------------|
| 1 | Check KFP UI for pipeline run status | Shows run as Succeeded/Failed | KFP UI | Same as Mode A | — |
| 2 | Open Marquez Web UI | Shows combined lineage graph with MLflow experiment nodes | Marquez Web UI | Graph is noisier with bridge nodes | Filter by node type |
| 3 | Navigate to the pipeline lineage subgraph | Visualizes physical data flow (same 5-node chain) | Marquez Web UI | Must distinguish bridge nodes from OL nodes | Node type labels |
| 4 | Check MLflow experiment nodes in graph | Shows experiment/run metadata as Marquez datasets | Marquez Web UI | Synthetic nodes may confuse | Bridge documentation |
| 5 | View combined metrics (OL facets + MLflow params) | Both visible in single UI | Marquez Web UI | — | Unified metrics view |

## Current State vs. Target State

| Aspect | Current (M2) | Target (M4+) |
|--------|-------------|--------------|
| Pipeline lineage | Full 5-node graph in Marquez | Same + query-time lineage |
| MLflow tracking | Not working from KFP pods (PG-024) | SA token + workspace header resolved |
| Cross-correlation | Manual (timestamp matching) | Automatic via pipeline_run_id facet |
| Bridge | Available but OFF by default | Evaluated; decision on permanent state |
| Query tracing | Not implemented | MLflow GenAI spans in Marquez |

## Related

- **Use Cases:** UC-001 (Document Ingest)
- **Workflows:** `docs/user-experience/workflows.md#verify-pipeline-lineage-bridge-off`
- **Technical:** `docs/technical/lineage.md`, `docs/technical/mlflow-integration.md`
- **ADR:** ADR-004 (Lineage Architecture)
