# Operational Workflows

Step-by-step operational procedures for key system workflows. Each workflow describes the sequence of actions a persona takes to accomplish a goal.

**Last Updated:** 2026-05-25 (M2 — lineage verification workflows added)

<!-- Workflows are added as milestones deliver the corresponding capabilities -->
<!-- Each workflow links to the relevant use case, runbook, and persona -->

## Workflows Index

| Workflow | Persona | Use Case | Milestone | Status |
|----------|---------|----------|-----------|--------|
| Document corpus ingest | Data Engineer | UC-001 | M1 | Planned |
| Ad-hoc pipeline re-run | Data Engineer | UC-001 | M1 | Planned |
| Verify pipeline lineage (bridge OFF) | Data Engineer | UC-001 | M2 | Active |
| Verify pipeline lineage (bridge ON) | Data Engineer | UC-001 | M2 | Active |
| Underwriter guideline query | Underwriter | UC-002 | M4 | Planned |
| Compliance review request | Compliance Officer | UC-003 | M5 | Planned |
| System deployment | Platform Admin | — | M0-M1 | Planned |

---

## Verify Pipeline Lineage (Bridge OFF)

**Persona:** Data Engineer
**Prerequisite:** Pipeline run completed (check KFP UI)
**Relevant docs:** [UJ-002](journeys/UJ-002-data-engineer-ingest.md), [lineage technical](../technical/lineage.md)

### Steps

1. **Get the pipeline_run_id** from the KFP UI run details page (metadata panel)

2. **Open Marquez Web UI:**
   ```
   https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com
   ```

3. **Navigate to the `data-strat-poc` namespace** and select a job (`parse_and_chunk` or `ingest_to_milvus`)

4. **Inspect the lineage graph.** Expected chain:
   ```
   PVC (data-pvc/input/pdfs)
     → parse_and_chunk
       → S3 (rag-chunks/chunks-m2)
         → ingest_to_milvus
           → Milvus (underwriting_guidelines)
   ```

5. **Check dataset facets** by clicking on a dataset node. Look for `custom_metrics`:
   - S3 dataset: `num_files`, `chunk_max_tokens`, `duration_seconds`
   - Milvus dataset: `vectors_inserted`, `embedding_model`, `embedding_dim`

6. **Verify run status** — both jobs should show COMPLETED state with duration

7. **Cross-reference with Milvus** (optional, via notebook or CLI):
   ```python
   # Query Milvus for vectors with this pipeline_run_id
   results = collection.query(
       expr=f'pipeline_run_id == "{pipeline_run_id}"',
       output_fields=["pipeline_run_id", "source_document_id"]
   )
   ```

8. **Check via API** (alternative to Web UI):
   ```bash
   # Jobs
   curl -sk "https://marquez-data-strat-poc.apps.dev.aip-ft.rh-ods.com/api/v1/namespaces/data-strat-poc/jobs"

   # Lineage graph from Milvus output
   curl -sk "https://marquez-data-strat-poc.apps.dev.aip-ft.rh-ods.com/api/v1/lineage?nodeId=dataset:milvus://milvus.data-strat-poc.svc.cluster.local:19530:underwriting_guidelines&depth=5"
   ```

---

## Verify Pipeline Lineage (Bridge ON)

**Persona:** Data Engineer
**Prerequisite:** Pipeline run completed with `MLFLOW_BRIDGE_ENABLED=true` in ConfigMap
**Relevant docs:** [UJ-002](journeys/UJ-002-data-engineer-ingest.md), [MLflow integration](../technical/mlflow-integration.md)

### Steps

1. **Enable the bridge** (if not already):
   ```bash
   oc patch configmap data-strat-lineage-config -n data-strat-poc \
     -p '{"data":{"MLFLOW_BRIDGE_ENABLED":"true"}}'
   ```

2. **Re-run the pipeline** (bridge takes effect on next run)

3. **Open Marquez Web UI** and navigate to `data-strat-poc` namespace

4. **Observe additional nodes** from MLflow bridge:
   - MLflow experiment nodes appear as datasets
   - MLflow run metadata appears alongside OL lineage data

5. **Verify the physical data flow** is unchanged (same 5-node chain as bridge OFF)

6. **Compare graph complexity:**
   - Bridge OFF: 5 nodes (3 datasets + 2 jobs), 4 edges
   - Bridge ON: Additional MLflow experiment/run nodes

7. **Document findings** — is the combined view useful or noisy for your workflow?

8. **Reset bridge** (optional):
   ```bash
   oc patch configmap data-strat-lineage-config -n data-strat-poc \
     -p '{"data":{"MLFLOW_BRIDGE_ENABLED":"false"}}'
   ```

### Expected Outcome

The bridge adds MLflow experiment metadata to Marquez but does not replace direct OL emission. Both lineage paths coexist. The value depends on whether seeing experiment metrics alongside data flow in a single graph is useful for your workflow.
