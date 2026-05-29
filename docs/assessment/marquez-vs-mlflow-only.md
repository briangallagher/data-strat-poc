# Can We Remove Marquez? MLflow-Only Lineage Assessment

**Date:** 2026-05-29
**Author:** Brian Gallagher, AIP Kubeflow-DevX
**Status:** Working analysis — for discussion with the Data Strategy team, ET team, and teammates
**Context:** Data Strategy POC, M5 complete. Assessing whether the two-layer lineage architecture (Marquez + MLflow) can be simplified to MLflow-only.

---

## 1. What Marquez Provides Today (from the Live Deployment)

The Marquez instance at `data-strat-poc` contains **12 jobs**, **40 lineage graph nodes**, and **3 dataset namespaces** (Milvus, S3, Registry). This is what's actually stored:

### Jobs (12 total)

| Job | Type | Inputs | Outputs | Run Facets |
|-----|------|--------|---------|------------|
| `acquire_documents/underwriting_guidelines` | BATCH | 10 registry documents (ug-001..ug-010) | S3 staging bucket | `pipelineRunId`, `jobType` |
| `parse_and_chunk/underwriting_guidelines` | BATCH | S3 staging bucket | S3 chunks bucket | `pipelineRunId`, `jobType` |
| `ingest_to_milvus/underwriting_guidelines` | BATCH | S3 chunks bucket | Milvus `underwriting_guidelines` | `pipelineRunId`, `jobType` |
| `acquire_documents/regulatory_bulletins` | BATCH | 5 registry documents (rb-001..rb-005) | S3 staging bucket | `pipelineRunId`, `jobType` |
| `parse_and_chunk/regulatory_bulletins` | BATCH | S3 staging bucket | S3 chunks bucket | `pipelineRunId`, `jobType` |
| `ingest_to_milvus/regulatory_bulletins` | BATCH | S3 chunks bucket | Milvus `regulatory_bulletins` | `pipelineRunId`, `jobType` |
| `acquire_documents/iso_forms` | BATCH | 5 registry documents (if-001..if-005) | S3 staging bucket | `pipelineRunId`, `jobType` |
| `parse_and_chunk/iso_forms` | BATCH | S3 staging bucket | S3 chunks bucket | `pipelineRunId`, `jobType` |
| `ingest_to_milvus/iso_forms` | BATCH | S3 chunks bucket | Milvus `iso_forms` | `pipelineRunId`, `jobType` |
| `underwriter_chat` | APPLICATION | Milvus `underwriting_guidelines` | — | `processing_engine` |
| `compliance_review_agent` | APPLICATION | Milvus (all 3 collections) | — | — |
| `parse_and_chunk/staging` | BATCH | S3 staging (legacy) | S3 chunks (legacy) | `pipelineRunId` |

### The Lineage Graph

The full graph traces data flow across 40 nodes:

```
registry://ny_dfs/ug-001 ──┐
registry://ca_doi/ug-004 ──┤
registry://tx_tdi/ug-007 ──┼─→ acquire_documents/uw ─→ S3 staging/uw ─→ parse_and_chunk/uw ─→ S3 chunks/uw ─→ ingest_to_milvus/uw ─→ Milvus:underwriting_guidelines ──┬─→ underwriter_chat
...8 more docs ────────────┘                                                                                                                                              └─→ compliance_review_agent
                                                                                                                                                                                        ↑
registry://tx_tdi/rb-001 ──┐                                                                                                                                                           |
...4 more docs ────────────┼─→ acquire_documents/rb ─→ S3 staging/rb ─→ parse_and_chunk/rb ─→ S3 chunks/rb ─→ ingest_to_milvus/rb ─→ Milvus:regulatory_bulletins ─────────────────────┤
                                                                                                                                                                                        |
registry://iso/if-001 ─────┐                                                                                                                                                           |
...4 more docs ────────────┼─→ acquire_documents/if ─→ S3 staging/if ─→ parse_and_chunk/if ─→ S3 chunks/if ─→ ingest_to_milvus/if ─→ Milvus:iso_forms ────────────────────────────────┘
```

This is a **dataset-flow graph** — it shows how data transforms through pipeline stages, from individual source documents through staging, chunking, and embedding to vector storage, and then which applications consume each collection.

### What a Marquez Job Run Contains

A typical `ingest_to_milvus/underwriting_guidelines` run:

```json
{
  "id": "68846346-c034-49f8-9f17-a9136dccd40e",
  "state": "COMPLETED",
  "startedAt": "2026-05-27T21:23:17.915Z",
  "endedAt": "2026-05-27T21:23:17.983Z",
  "durationMs": 68,
  "inputDatasetVersions": [
    { "namespace": "s3://minio-service...:9000", "name": "rag-chunks/chunks/underwriting_guidelines" }
  ],
  "outputDatasetVersions": [
    { "namespace": "milvus://milvus...:19530", "name": "underwriting_guidelines" }
  ],
  "facets": {
    "pipelineRunId": { "id": "7785573b-5b23-4171-8f13-a904f749b8bd" }
  }
}
```

Key data per run: **state**, **timing**, **input/output dataset versions**, and the **`pipelineRunId`** custom facet that bridges to MLflow.

### What Marquez Does NOT Contain

- No parameters (chunk size, model name, tokenizer) — those are in MLflow
- No metrics (chunk counts, vector counts, durations) — those are in MLflow
- No per-request data — Marquez models datasets and jobs, not individual queries
- No document content or metadata — the Registry owns that
- Dataset facets are empty (`"facets": {}`) — we emit dataset identity but no schema/stats facets

---

## 2. What MLflow Already Provides for Ingest

MLflow has two experiments in the `data-strat-poc` workspace: `underwriter-chat-v3` (experiment 57) and `compliance-review-agent` (experiment 58). These are query-time experiments with traces. The ingest-time data was logged directly from KFP pods using `mlflow.log_param()` and `mlflow.log_metric()`.

### Ingest Run Data (from KFP Components)

Each pipeline component logs to MLflow:

**parse_and_chunk:**
- Params: `corpus_path`, `chunk_max_tokens`, `tokenizer`, `num_workers`, `pipeline_run_id`
- Metrics: `num_files_processed`, `total_chunks_created`, `duration_seconds`

**ingest_to_milvus:**
- Params: `collection_name`, `embedding_model`, `embedding_dim`, `index_type`, `pipeline_run_id`
- Metrics: `vectors_inserted`, `duration_seconds`

### What MLflow Has That Marquez Doesn't (Ingest)

| Data | MLflow | Marquez |
|------|--------|---------|
| Processing parameters (chunk size, model, tokenizer) | Yes — `log_param()` | No |
| Processing metrics (counts, durations) | Yes — `log_metric()` | No |
| Nested runs (parent pipeline → child steps) | Yes — parent/child run IDs | No (flat job runs) |
| Artifacts (sample outputs, configs) | Yes — `log_artifact()` | No |
| `mlflow.log_input()` dataset references | Yes — basic source/name/digest | No equivalent |

### What Marquez Has That MLflow Doesn't (Ingest)

| Data | Marquez | MLflow |
|------|---------|--------|
| **Dataset-flow graph** (A → Job → B → Job → C) | Yes — first-class | No — no concept of "this run produced dataset X which was consumed by run Y" |
| **Cross-run dataset identity** ("who else consumed this dataset?") | Yes — dataset versioning with consumer tracking | No — runs are independent; no shared dataset registry |
| **Visual lineage graph** (DAG of data transformation) | Yes — Marquez UI renders the full pipeline graph | No — MLflow UI shows individual runs, not data flows |
| **Application-level consumption** ("which apps use this collection?") | Yes — `underwriter_chat` and `compliance_review_agent` as job nodes | No — MLflow has no concept of "consumers" |
| **Impact analysis** ("if I change this source, what's affected?") | Yes — trace upstream/downstream from any node | No — no graph structure to traverse |
| **Per-document source tracking** (individual registry docs as input nodes) | Yes — 20 individual document nodes as pipeline inputs | No — MLflow knows `corpus_path` but not individual documents |

---

## 3. Could MLflow Replace Marquez?

### Capability-by-Capability Assessment

| Marquez Capability | MLflow Equivalent | Gap | Severity |
|---|---|---|---|
| **Dataset-flow graph** (source → staging → chunks → Milvus → app) | None. MLflow has `log_input()` which records that a run *used* a dataset, but no graph linking run outputs to downstream run inputs. | **Fundamental** — MLflow's data model is run-centric, not dataset-centric. There is no way to express "the output of run A is the input of run B" as a navigable graph. | **High** |
| **Cross-run dataset identity** ("underwriting_guidelines" as a persistent entity consumed by multiple jobs/apps) | None. MLflow datasets are logged per-run as metadata. No shared dataset entity that aggregates all producers and consumers. | **Fundamental** — would require building a dataset registry inside or alongside MLflow. | **High** |
| **Visual lineage graph** | None built-in. The MLflow UI shows experiment runs, not data flows. | **High for demos, moderate for production** — the Marquez graph is visually compelling for stakeholders. Could be rebuilt with a custom UI reading from MLflow metadata, but would require significant effort. | **Medium-High** |
| **Job run history per pipeline stage** | MLflow runs per experiment, filterable by params. Achievable if each pipeline stage logs to a named experiment. | **Low** — MLflow can do this. Run history per component is available via experiment search. | **Low** |
| **Application consumption tracking** | None. MLflow has no concept of downstream consumers. | **Medium** — could be modelled as a "registration run" in a dedicated experiment, but it's a hack. | **Medium** |
| **Impact analysis** (upstream/downstream traversal) | None. No graph structure to traverse. | **Fundamental** — requires either (a) Marquez or equivalent graph DB, or (b) a custom graph built from MLflow metadata at query time. | **High** |
| **Individual document provenance** (20 source docs as graph nodes) | `log_input()` can reference source documents, but they're per-run metadata, not graph nodes. | **Medium** — the Document Registry already owns document identity. Marquez just mirrors it. | **Medium** |
| **`pipelineRunId` as a bridge key** | MLflow already stores `pipeline_run_id` as a run parameter. The bridge works without Marquez — the key is on the Milvus vectors, and MLflow runs have it as a param. | **None** — this works today. | **None** |

### Summary

MLflow can replace Marquez for **run-level data** (parameters, metrics, timing, artifacts) — and already does, since we log to both systems. What MLflow **cannot** replace is the **dataset-flow graph**: the visual and queryable representation of how data transforms through pipeline stages, and which applications consume which datasets. This is Marquez's unique contribution.

---

## 4. What OpenLineage Specifically Gives Us

### Is OL the Only Way to Get Dataset-Flow Semantics?

No, but it's the only *standardised* way. MLflow's `log_input()` / `log_output()` can record dataset references on individual runs, but there's no aggregation layer that builds a graph from these references. You could build one — parse all MLflow runs, extract input/output references, build an adjacency list, render it — but you'd be reimplementing what Marquez already does, without the OL ecosystem.

### Which RHOAI Components Natively Emit OpenLineage?

**Essentially none.** PG-013 confirms: "No RHOAI component currently emits OpenLineage events; adoption requires upstream work in every participating component." Everything in the POC is custom emission via `rhoai-lineage`.

### OpenLineage Integration Matrix (What Exists in the Ecosystem)

| Tool | OL Integration | In RHOAI Stack? | Notes |
|------|---------------|-----------------|-------|
| Apache Spark | Native (SparkListener) | Yes — Spark Operator in RHOAI | Table-level + column-level lineage. This is the most mature OL integration. |
| Apache Airflow | Native (Provider) | No — RHOAI uses KFP, not Airflow | Strong integration but irrelevant to RHOAI. |
| dbt | Native | No | SQL transformation lineage. Not in the RHOAI stack. |
| Apache Flink | Native (Listener) | No | Stream processing lineage. Not in RHOAI. |
| Kubeflow Pipelines | **None** | Yes — core component | PG-013. No OL emission from KFP. |
| KServe / Model Serving | **None** | Yes | No inference-time lineage. |
| Ray / RayData | **None** | Yes — CodeFlare/RayCluster | No OL emission. |
| Milvus / Vector Stores | **None** | Yes (via Helm) | No OL emission. |
| MLflow | Custom bridge only | Yes — RHOAI Operator | The `rhoai-lineage` bridge converts MLflow events to OL. Not native. |

**The only RHOAI component with native OL integration is Spark** — and the POC doesn't use Spark. For RAG workloads, all OL emission is custom regardless.

### If We're Building Custom Emission Anyway, Does the Target Matter?

This is the key question. Since no RHOAI component auto-emits OL events, every lineage event in the POC is explicitly coded in Python using `rhoai-lineage`. Whether that code emits to Marquez (via OL HTTP POST) or logs to MLflow (via `mlflow.log_input()` / custom tags) is a library choice, not an ecosystem capability.

The difference is what happens *after* emission:
- **Emit to Marquez (OL):** Events are stored in a graph database. You get dataset-flow graphs, impact analysis, and a lineage UI for free.
- **Log to MLflow:** Events are stored as run metadata. You get run-level search and filtering. No graph, no impact analysis. You build those yourself.

---

## 5. The Case FOR Removing Marquez

### Operational Simplification

1. **One less system to deploy, manage, secure.** Marquez requires PostgreSQL, a web UI, and an API server — all with no built-in auth (PG-001). We deploy and manage it ourselves. MLflow is operator-managed by RHOAI.

2. **The `rhoai-lineage` bridge becomes unnecessary.** The entire `rhoai-lineage` library — tracking store wrapper, KFP context manager, OL emitter, naming conventions — exists to emit OpenLineage events to Marquez. Remove Marquez, and this library (plus its `pip install git+https://...` slow install — PG-021) goes away.

3. **Simpler architecture for the POC.** The two-layer lineage architecture (DEC-009) is intellectually elegant but adds real complexity. A single-layer MLflow approach is easier to explain, demo, and maintain.

4. **MLflow is already in RHOAI.** Every RHOAI user gets MLflow. Adding Marquez is additional cognitive load — another system to learn, another UI to navigate, another set of APIs to understand.

5. **The bridge key still works.** `pipeline_run_id` is on the Milvus vectors and in MLflow run params. The cross-system join doesn't require Marquez — it just needs MLflow and the vector metadata.

### What We'd Lose That We Could Rebuild

6. **The lineage graph is replicate-able.** The pipeline DAG is known (acquire → parse → embed → store). It could be rendered as a static Mermaid diagram or built dynamically from MLflow run metadata. It wouldn't be as feature-rich as Marquez's interactive graph, but for a POC, it may be sufficient.

7. **Application consumption tracking can use the Document Registry.** The Registry already knows which collections exist and which applications query them (from MLflow traces). The Marquez application-level nodes are informational duplicates.

---

## 6. The Case AGAINST Removing Marquez

### What We'd Actually Lose

1. **The dataset-flow graph has no MLflow equivalent.** The 40-node graph showing data transformation from 20 individual source documents through 4 pipeline stages to 3 Milvus collections to 2 consuming applications — this is Marquez's unique contribution. Rebuilding it from MLflow metadata requires a custom graph builder, storage, and UI. This is not trivial.

2. **Impact analysis disappears.** "If I update document `ug-001`, what collections and applications are affected?" In Marquez, this is a graph traversal. In MLflow, it requires querying all runs across all experiments, parsing dataset references, and building the dependency chain manually.

3. **The visual lineage graph is the most compelling demo artifact.** For stakeholders (the Data Strategy team, product managers, customers), the Marquez graph is immediately understandable. It answers "how does data flow through the system?" at a glance. MLflow's experiment UI doesn't convey this.

4. **OpenLineage standardisation has future value if Spark enters the picture.** Spark is in the RHOAI stack and has native OL integration. If data processing moves from RayData/Docling to Spark (which the Data Strategy proposal envisions), Spark would auto-emit OL events that Marquez would capture. Without Marquez, that capability has nowhere to go.

5. **The Data Strategy proposal is built on OpenLineage/Marquez.** Removing Marquez from the POC contradicts the proposal's Pillar 4 framing. This matters politically — the POC is supposed to validate the proposal, not undermine it.

6. **The rhoai-lineage library has value beyond Marquez.** The ET team built it for general OL emission. Even if we remove Marquez from the POC, the library pattern (structured lineage emission from pipeline components) is sound and reusable.

### The "80% Coverage" Question

Could an MLflow-only approach cover 80% of the lineage value?

**For ingest-time lineage:** Yes. MLflow already has all the run-level data (params, metrics, timing). The only thing missing is the graph — and for a POC, a static diagram or a Registry-built graph may be sufficient.

**For query-time lineage:** Already MLflow-only (DEC-009). No change.

**For the full provenance chain (query → ingest → source):** The `pipeline_run_id` bridge works without Marquez. MLflow trace → chunk metadata → `pipeline_run_id` → MLflow ingest run → source information. The Registry already federates this.

**For impact analysis:** No. This requires graph traversal that MLflow cannot provide without a custom layer.

**For the demo/stakeholder story:** Weaker without the visual lineage graph. The graph is worth more than the sum of its data.

---

## 7. What OpenLineage Specifically Gives Us (Ecosystem Analysis)

### RHOAI Native OL Emitters: Present and Future

| Component | Current OL Status | Future Potential |
|-----------|------------------|-----------------|
| **Spark Operator** | Native via SparkListener | **High** — if data processing moves to Spark, OL emission is automatic. Column-level lineage included. |
| **Kubeflow Pipelines** | None | **Low-medium** — would require upstream KFP changes. The community has discussed it but no implementation exists. |
| **Ray / CodeFlare** | None | **Low** — no OL integration roadmap known. |
| **KServe** | None | **Low** — inference lineage is a different problem (model → prediction, not dataset → dataset). |
| **MLflow** | Bridge via `rhoai-lineage` | **Medium** — the tracking store bridge exists and works. Could become a standard pattern. |
| **Milvus** | None | **None** — vector DB lineage isn't a standard concept. |

The ecosystem value of OpenLineage in RHOAI comes down to **Spark**. If Spark becomes a significant part of the RHOAI data processing story (and the Data Strategy proposal says it should), then having Marquez as an OL aggregation backend has clear value. If the stack stays KFP + Ray + custom components, OL's value is limited to what we manually emit.

---

## 8. Recommendation: Keep Marquez, but Reframe Its Role

### Don't Remove Marquez. Instead, Be Honest About What It Provides.

The analysis reveals that Marquez's unique value is narrow but real:

1. **The dataset-flow graph** — irreplaceable without building a custom graph layer
2. **Visual lineage for stakeholders** — the most compelling demo artifact
3. **Future Spark integration** — the only native OL emitter in the RHOAI stack
4. **Alignment with the Data Strategy proposal** — political/strategic value

What Marquez does NOT provide that matters:
- No per-request provenance (MLflow handles this)
- No processing parameters or metrics (MLflow handles this)
- No dataset content or metadata (Document Registry handles this)
- No auth (PG-001 — significant production gap)

### The Honest Framing

Marquez is a **lineage visualisation and graph query tool** for pipeline-time data flows. It is not the lineage *backbone* of the system — MLflow and the Document Registry carry most of the provenance weight. In a production RHOAI deployment:

- If Spark is involved → Marquez has clear value (native OL from Spark)
- If only KFP + custom components → Marquez's value is primarily visual/graph (all emission is manual anyway)
- If the goal is POC simplicity → Marquez can be removed with the understanding that the graph is lost

### What Would Need to Change If Marquez Were Removed

| Current | Without Marquez |
|---------|----------------|
| `rhoai-lineage` library for OL emission | **Remove** — no longer needed |
| `rhoai-lineage` `kfp_lineage` context manager | **Remove** — no longer needed |
| `lineage-config` ConfigMap (Marquez URL, OL namespace) | **Simplify** — MLflow config only |
| Application-level OL events (`underwriter_chat`, etc.) | **Move** — register applications in Document Registry instead |
| Marquez deployment (PostgreSQL, API, UI) | **Remove** — saves infra + ops |
| `pipelineRunId` bridge key | **Keep** — already in MLflow params and Milvus metadata |
| Registry provenance portal (Marquez federation) | **Simplify** — remove Marquez lineage graph view, keep MLflow trace and Registry views |
| ADR-004 | **Supersede** — new ADR for MLflow-only lineage |
| DEC-009 | **Simplify** — single-layer instead of two-layer |
| Production gap PG-001 (Marquez auth) | **Close** — no longer relevant |
| Production gap PG-022 (Marquez namespace isolation) | **Close** — no longer relevant |
| Production gap PG-041 (Marquez naming) | **Close** — no longer relevant |

Net: removing Marquez closes 3 production gaps, eliminates 1 library dependency, and removes 1 deployed system. The cost is losing the dataset-flow graph and the future Spark integration point.

---

## 9. Discussion Points for Stakeholders

### For the Data Strategy Team

**Framing:** "The POC validated that Pillar 4 needs two layers — pipeline-time and query-time — and that MLflow is the right tool for query-time. The question for pipeline-time is whether Marquez justifies its operational cost, given that all OL emission is manual today."

**Key points:**
1. The Data Strategy proposal's Pillar 4 assumes OpenLineage emitters will exist. In practice, zero RHOAI components emit OL natively except Spark. For RAG workloads, all emission is custom.
2. Marquez's unique value is the dataset-flow graph. If the proposal is comfortable with "lineage metadata in MLflow, lineage graph as a separate concern (Marquez or future alternative)", the architecture is sound.
3. If Spark becomes central to the RHOAI data processing story, Marquez (or an OL-compatible backend) is essential. If not, it's optional for RAG scenarios.
4. **Ask:** Does the proposal envision Marquez as the standard lineage backend for RHOAI, or as one option among several? This determines how much weight we put on validating it in the POC.

### For the ET Team (rhoai-lineage Builders)

**Framing:** "The bridge you built works. The question is whether the destination (Marquez) is the right long-term choice, or whether MLflow's evolving dataset tracking could absorb the graph semantics."

**Key points:**
1. The `rhoai-lineage` library is excellent engineering — thread-safe, non-blocking, proper facets. The question isn't code quality; it's architectural direction.
2. If Marquez stays, `rhoai-lineage` should evolve toward a proper PyPI package (closing PG-021) and add a `QueryAdapter` for MLflow trace enrichment.
3. If Marquez is removed, the library's value shrinks to "structured logging helpers for MLflow." The OL emission machinery becomes dead code.
4. **Ask:** In your vision, does OpenLineage converge with or stay separate from MLflow's dataset tracking? MLflow added `log_input()` and `log_output()` in 2.x — is that heading toward graph semantics, or staying run-centric?

### For Teammates

**Framing:** "Here's the trade-off: simpler architecture (one less system) vs. richer lineage visualisation (the graph). For the POC, we need to decide which matters more."

**Key points:**
1. Removing Marquez means: no more `rhoai-lineage` dependency in pipeline components, no more port-forward to Marquez, no more lineage config in the ConfigMap, 3 production gaps closed. Pipeline development gets simpler.
2. Keeping Marquez means: the lineage graph stays (it's the best demo artifact we have), future Spark integration has a landing zone, and the Data Strategy alignment is maintained.
3. The practical impact on daily work is small either way — most provenance questions are answered by the Registry UI, which federates MLflow traces and Registry data. Marquez's graph is rarely consulted directly.
4. **Ask:** How often do any of us actually look at the Marquez graph vs. the Registry UI or MLflow traces? If the answer is "rarely," that's evidence for removal. If it's "every demo," that's evidence for keeping it.

### The Bottom Line

Marquez provides a unique capability (dataset-flow graph) that MLflow cannot replicate without significant custom development. However, for the POC's primary use cases — answer provenance, document provenance, audit trail — the MLflow + Registry combination already does the heavy lifting. Marquez's role is supplementary: visual lineage for stakeholders and a future integration point for Spark.

The decision depends on which audience matters most:
- **For engineers building and running the POC:** Remove Marquez (simpler)
- **For stakeholders evaluating the Data Strategy:** Keep Marquez (proves Pillar 4)
- **For production RHOAI with Spark:** Keep Marquez (native OL from Spark)
- **For production RHOAI without Spark (RAG-only):** Marquez is optional

---

## References

| Source | Location |
|--------|----------|
| ADR-004 (lineage architecture) | `docs/architecture/adrs/ADR-004-lineage-architecture.md` |
| DEC-009 (two-layer lineage) | `docs/decisions.md` |
| MLflow integration doc | `docs/technical/mlflow-integration.md` |
| Production gaps (PG-001, PG-013, PG-021, PG-022, PG-041) | `docs/production-gaps.md` |
| Lineage correlation analysis | `docs/assessment/lineage-correlation-analysis.md` |
| Data Strategy feedback (Finding 1) | `docs/assessment/data-strategy-feedback.md` |
| rhoai-lineage tracking store | `rhoai-lineage/src/rhoai_lineage/mlflow/tracking_store.py` |
| rhoai-lineage KFP adapter | `rhoai-lineage/src/rhoai_lineage/kfp/lineage.py` |
| OpenLineage integration matrix | https://github.com/OpenLineage/OpenLineage (v1.46.0, April 2026) |
| Marquez API (live queries, 2026-05-29) | `http://localhost:5000/api/v1/namespaces/data-strat-poc/` |
| MLflow API (live queries, 2026-05-29) | `https://mlflow-ui-redhat-ods-applications.apps.dev.aip-ft.rh-ods.com/api/2.0/mlflow/` |
