# ET Team vs Data Strategy POC: Comprehensive Gap Analysis

**Date:** 2026-05-26 (updated 2026-05-29 after M0–M5 POC completion)
**Source:** [rh-waterford-et/lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline)
**Our repos:** [data-strat-poc](https://github.com/briangallagher/data-strat-poc), [rhoai-lineage](https://github.com/briangallagher/rhoai-lineage)
**Related:** [ET Team Questions](../assessment/et-team-questions.md), [ADR-004](../architecture/adrs/ADR-004-lineage-architecture.md), [lineage-next-steps.md](../../../../projects/data-strategy/docs/poc/lineage/lineage-next-steps.md)

---

## Summary

Both teams addressed lineage on RHOAI but from different angles. The ET team built **infrastructure** (operator, MLflow bridge, deployment patterns) for a traditional ML pipeline (Feast → Spark → training → model). We built **compute-engine integration patterns** for a RAG pipeline (Docling → Milvus → LLM → answer provenance). This doc captures what each team built, where approaches diverged, and where they should converge.

---

## Side-by-Side Comparison

### Architecture

| Dimension | ET Team | Our POC (M0–M5) | Assessment |
|-----------|---------|------------------|------------|
| **Use case** | Customer churn (traditional ML: Feast → Spark → KFP → MLflow → model) | P&C knowledge assistant (RAG: Docling → Milvus → LLM → answer) | Different pipeline shapes — both valid for RHOAI |
| **Pipeline-time lineage** | MLflow-Marquez bridge (`OpenLineageTrackingStore`) intercepts MLflow tracking calls → emits OL events | Per-KFP-component OL emission (Pattern 2) directly to Marquez | We deliberately turned the bridge OFF (ADR-004) — cleaner graph, predictable naming |
| **Query-time lineage** | Not addressed | MLflow GenAI traces (`autolog()`) + provenance tags. Two paths: LangGraph (M4) and OGX Responses API (M5) | Key gap in ET approach — we solved this with the two-layer architecture |
| **Lineage backend** | Marquez (same) | Marquez (same) + MLflow traces for query-time | Marquez shared; we added MLflow as the request-level complement |
| **Correlation mechanism** | MLflow bridge emits events keyed by MLflow run ID; `KFP_RUN_ID` env var for KFP correlation | `pipeline_run_id` UUID flows through KFP → Ray → Milvus → MLflow → Marquez → audit log | Our approach is more explicit; theirs relies on env var injection |
| **Tool integration** | N/A (no agent/tool calling) | MCP (Model Context Protocol) via SSE. FastMCP server exposes Milvus tools. OGX discovers and calls autonomously. | MCP is an M5 discovery — not in ET scope |
| **LLM** | N/A (training pipeline, no inference) | Hermes-3-Llama-3.1-70B-FP8 (NeuralMagic FP8, 1x A100-80GB). Granite 3.3 8B does not support vLLM tool calling. | Different scope |
| **UI** | Dataset registry (FastAPI + PatternFly) | Document Registry → Provenance Portal (FastAPI + React/PatternFly) federating MLflow + Marquez + Registry DB | Both built registries; ours evolved into a provenance federation layer |

### Lineage Operator

| Dimension | ET Team | Our POC | Assessment |
|-----------|---------|---------|------------|
| **Deployed?** | Yes — Go operator watches annotated pods | **No** — deferred (PG-023) | We did not use their operator |
| **What it does** | Watches pods with `lineage.openlineage.io/*` annotations → queries Marquez → creates `AgentCard` CRDs | N/A | Interesting for deployment-level lineage |
| **Why we didn't use it** | — | Not in the critical path for pipeline-time lineage. Our lineage is emitted from within KFP components and application code, not from pod annotations. | The operator solves a different problem — "what deployed services consume which data?" vs "what pipeline steps produced this data?" |
| **Agent lineage model** | Pod annotations declare data inputs/outputs → operator generates lineage | OGX calls MCP tools → MLflow traces capture tool call details → application-level OL event registers the app in Marquez | Different granularity. Operator = deployment-level. Ours = request-level (via MLflow) + deployment-level (via OL event). |
| **Convergence opportunity** | — | — | The operator could complement our approach: it handles deployment discovery (new pods → auto-registration in Marquez), while our per-request MLflow traces handle what actually happens at query time. Both are needed for production. |

### OpenLineage Emission

| Dimension | ET Team | Our POC | Assessment |
|-----------|---------|---------|------------|
| **Emission pattern** | MLflow tracking store adapter intercepts `log_param`, `log_metric`, `set_tag`, `log_input` → emits OL events | Per-KFP-component emission. Each pipeline step emits its own OL START/COMPLETE events directly to Marquez. | Different strategies. Theirs = implicit (wraps MLflow). Ours = explicit (emit directly). |
| **MLflow bridge** | Always ON via `openlineage+http://` tracking URI | OFF by default (`MLFLOW_BRIDGE_ENABLED=false`). Available but not used for pipeline lineage. | We found the bridge creates duplicate/synthetic nodes in Marquez. Direct emission is cleaner. |
| **KFP integration** | KFP adapter wraps steps with a context manager | KFP components emit directly using `openlineage-python`. Namespace injection via downward API. | Similar outcome, different mechanism. Ours is more explicit but also more boilerplate per component. |
| **Facets** | Custom `mlflow_run`, `mlflow_dataset`, `mlflow_model`, `parent` run facets | Standard OpenLineage facets + `pipelineRunId` custom run facet + `ProcessingEngineRunFacet` for Docling version | We use fewer custom facets. The `pipelineRunId` facet is RAG-specific (links Milvus vectors back to pipeline runs). |
| **Error handling** | Production-grade: emission failures are warnings, thread-safe with `threading.Lock` | Basic: emit-and-continue, no lock (KFP steps are single-threaded) | Their production hardening is more mature. We should adopt their error handling patterns. |

### Correlation and Identity

| Dimension | ET Team | Our POC | Assessment |
|-----------|---------|---------|------------|
| **Primary correlation key** | MLflow run ID (bridged to Marquez run via tracking store adapter) | `pipeline_run_id` UUID — generated once, propagated everywhere | Different philosophical approaches. Theirs ties to MLflow's identity. Ours is an independent UUID. |
| **Cross-system propagation** | `KFP_RUN_ID` env var → MLflow run tags → Marquez via bridge | `pipeline_run_id` flows through: KFP param → Ray env var → Milvus metadata → MLflow tags → Marquez facet → audit log | Ours covers more systems (especially Milvus vector metadata for RAG) |
| **Dataset naming** | Documented conventions in lessons-learned. `normalise_namespace()` for URI normalisation. | Codified in `naming.py` helpers (`s3_dataset()`, `milvus_dataset()`, etc.) following DEC-014. Same normalisation rules. | Both agree naming is the #1 lineage issue. We codified it; they documented it. |
| **Document identity** | N/A (no document processing) | `parent_document_id` from manifest → Milvus metadata → Registry DB. Gap: not yet surfaced in OL events as per-document `InputDataset`. | Our gap — identified in `identity-correlation.md` |
| **Cross-pipeline identity** | Not addressed | S3 URI as the linking dataset between acquisition and ingest pipelines. Consistent naming enables Marquez graph connection. | Works for POC. Production may need `batch_id` or `staging_manifest_id`. |

### Query-Time Lineage (Biggest Divergence)

| Dimension | ET Team | Our POC | Assessment |
|-----------|---------|---------|------------|
| **Problem awareness** | Focused on training pipelines. Query/inference lineage not in scope. | Central design challenge. How to trace from a user's question back to source documents? | Our problem space is fundamentally different |
| **Architecture** | N/A | **Two-layer**: Marquez for pipeline-time (batch), MLflow traces for query-time (per-request). DEC-009/ADR-004. | Validated across M4 (deterministic) and M5 (agentic). The split is necessary — Marquez can't model per-request provenance. |
| **MLflow traces** | MLflow tracking store (runs, params, metrics) | MLflow GenAI traces (spans, inputs, outputs, tool calls). Two autolog paths: `mlflow.langchain.autolog()` (M4) and `mlflow.openai.autolog()` (M5). | Different MLflow APIs. Theirs = classic experiment tracking. Ours = GenAI tracing (newer API). |
| **Provenance tags on traces** | N/A | `collection`, `answer_preview`, `query` tags on every trace. Multi-experiment search (`compliance-review-agent` + `underwriter-chat-v3`). | Enables the Registry to discover and federate traces across experiments. |
| **Application registration** | Operator watches annotated pods → creates lineage | One-time OL event per app (`emit_application_registration()`). Both `underwriter_chat` and `compliance_review_agent` registered. | Lightweight vs infrastructure-heavy. Both valid; ours is simpler to deploy. |
| **Provenance portal** | Dataset registry (basic CRUD + PatternFly) | Registry UI with federated provenance: document provenance, trace detail, collection health, impact analysis, app overview. Links to KFP runs, MLflow traces, and Marquez graphs. | Ours is significantly more developed — provenance federation is the key differentiator. |

### Marquez Auth and Multi-Tenancy

| Dimension | ET Team | Our POC | Assessment |
|-----------|---------|---------|------------|
| **Auth** | No RBAC. Cluster-level access only. Flagged as unresolved. | No RBAC (PG-001). Documented three options in `lineage-next-steps.md`: in-process plugin, sidecar proxy, operator-only. Mapped the MLflow kubernetes-auth prior art. | Neither team has solved this. We've done the analysis; they've flagged the gap. |
| **Multi-tenancy** | Key question: per-namespace or cluster-wide? Unresolved. | POC uses single namespace. Analysis shows Marquez's existing namespace concept makes K8s namespace mapping easier than MLflow's (which had to invent workspaces). | The K8s namespace → Marquez namespace mapping is natural but unbuilt. |
| **Recommended path** | Not proposed | Option C (operator + oauth-proxy sidecar) as minimum viable, with Option A (in-process plugin) for production RBAC. | Our `lineage-next-steps.md` has the fullest analysis of this problem. |

---

## What We Built That They Didn't

| Capability | Why It Matters | Reference |
|------------|---------------|-----------|
| **Two-layer lineage architecture** (Marquez + MLflow traces) | Solves the query-time provenance problem that Marquez alone cannot | DEC-009, ADR-004 |
| **MCP tool integration** | OGX uses MCP via SSE for agentic tool calling. Shapes the entire query architecture. | M5, DEC-012 (POC repo) |
| **Provenance portal** (Registry UI federating 3 systems) | Document provenance, trace detail, impact analysis, app discovery | `src/registry/`, `src/registry-ui/` |
| **Two query paths** (deterministic + agentic) with tracing | Validates lineage works for both simple RAG and multi-tool agent workflows | M4 (LangGraph), M5 (OGX) |
| **`pipeline_run_id` across 5+ systems** | Universal correlation key from KFP through Milvus to MLflow | `identity-correlation.md` |
| **Codified naming conventions** (`naming.py` helpers) | Prevents the "naming breaks graphs" problem programmatically | DEC-014 |
| **Connector framework** (S3, Confluence, SharePoint) with acquisition lineage | Enterprise data source ingestion with upstream lineage | M6, DEC-027–DEC-030 |
| **LLM tool-calling validation** | Granite doesn't work; Hermes 70B FP8 does. Critical for any agentic architecture on RHOAI. | M5, DEC-013 (POC repo) |
| **Marquez auth analysis** with MLflow prior art mapping | Three options for productising Marquez on RHOAI | `lineage-next-steps.md` |
| **MLflow autolog for RAG** with SA token auth | Custom `RequestHeaderProvider` for RHOAI MLflow Operator compatibility | PG-060 (closed) |

## What They Built That We Didn't

| Capability | Why It Matters | Our Status | Reference |
|------------|---------------|------------|-----------|
| **Lineage operator** (Go, watches pods, AgentCard CRD) | Automatic discovery of deployed services and their data dependencies | Deferred (PG-023). Our app registration is manual (one OL event per app). | `lineage-operator/` |
| **MLflow-Marquez bridge** (tracking store adapter) | Automatic lineage from any MLflow experiment without code changes | Available in `rhoai-lineage` but OFF by default. Direct OL emission preferred. | `openlineage-oai/adapters/mlflow/` |
| **Feast OpenLineage emitter** | Native lineage from feature engineering pipelines | Not applicable (no Feast in Scenario B) | |
| **Spark OpenLineage listener** | Config-only lineage from Spark jobs (no code changes) | Not applicable (no Spark in Scenario B) | |
| **Production error handling** in bridge | Thread-safe, failure-tolerant OL emission | Our emission is simpler but less hardened. Should adopt their patterns. | `OpenLineageTrackingStore` |
| **`URIDatasetSource`** for MLflow | Arbitrary URIs in `mlflow.data.from_pandas()` lineage | Not adopted yet. Would clean up ingest pipeline MLflow logging. | `mlflow/dataset_source.py` |

---

## Convergence: What a Shared Recommendation Looks Like

Both teams' work converges on the same target architecture for RHOAI lineage. The pieces fit together:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RHOAI Lineage Architecture                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PIPELINE-TIME (batch, dataset-level)                              │
│  ┌────────────────────────────────────────────────────┐            │
│  │  KFP Components emit OL events (Pattern 2)  [US]  │            │
│  │  ────────────────────────────────────────────────── │            │
│  │  MLflow Bridge (opt-in for training)         [ET]  │            │
│  │  ────────────────────────────────────────────────── │            │
│  │  Spark Listener (config-only)                [ET]  │            │
│  │  ────────────────────────────────────────────────── │            │
│  │  Feast native emission                       [ET]  │            │
│  │  ────────────────────────────────────────────────── │            │
│  │  Connector acquisition lineage               [US]  │            │
│  └──────────────────────┬─────────────────────────────┘            │
│                         ▼                                           │
│  ┌──────────────────────────────────┐                              │
│  │       Marquez (lineage backend)  │ ◄── Naming conventions [BOTH]│
│  │       + Auth (operator/proxy)    │     pipeline_run_id    [US]  │
│  └──────────────────────────────────┘                              │
│                                                                     │
│  QUERY-TIME (per-request, per-span)                                │
│  ┌────────────────────────────────────────────────────┐            │
│  │  MLflow GenAI autolog (LangChain, OpenAI)    [US]  │            │
│  │  ────────────────────────────────────────────────── │            │
│  │  Provenance tags (collection, query, answer) [US]  │            │
│  │  ────────────────────────────────────────────────── │            │
│  │  MCP tool call capture                       [US]  │            │
│  └──────────────────────┬─────────────────────────────┘            │
│                         ▼                                           │
│  ┌──────────────────────────────────┐                              │
│  │       MLflow Traces              │                              │
│  └──────────────────────────────────┘                              │
│                                                                     │
│  DEPLOYMENT-TIME (service discovery)                               │
│  ┌────────────────────────────────────────────────────┐            │
│  │  Lineage Operator (pod annotations → Marquez) [ET] │            │
│  │  ────────────────────────────────────────────────── │            │
│  │  App registration OL events (startup)         [US] │            │
│  └──────────────────────────────────────────────────── │            │
│                                                                     │
│  PROVENANCE FEDERATION (unified view)                              │
│  ┌────────────────────────────────────────────────────┐            │
│  │  Registry/Portal federating MLflow + Marquez  [US] │            │
│  └────────────────────────────────────────────────────┘            │
│                                                                     │
│  LIBRARY                                                           │
│  ┌────────────────────────────────────────────────────┐            │
│  │  rhoai-lineage (naming, emitter, adapters)  [BOTH] │            │
│  └────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

### To converge, these questions need answers:

1. **Operator + app registration: complement or redundant?** The operator auto-discovers pods; our OL events explicitly register apps. For production, both may be needed (operator for discovery, OL events for explicit declarations). Or the operator subsumes our pattern.

2. **MLflow bridge: when to use it?** We turned it OFF for RAG (cleaner Marquez graph). The ET team uses it for training. The answer may be: ON for training pipelines (where MLflow is the primary tracking tool), OFF for data pipelines (where KFP components emit directly).

3. **`rhoai-lineage` library ownership.** Currently our fork. If both teams contribute, it becomes a shared RHOAI asset. Needs: unified import paths, published package, CI, and documentation.

4. **Marquez auth: who builds it?** The analysis is done (`lineage-next-steps.md`). The MLflow prior art is mapped. Someone needs to build Option C (operator + oauth-proxy) as a starting point.

5. **Naming convention spec.** Both teams agree naming is the #1 issue. The `naming.py` helpers should be the authoritative implementation. Need to validate they cover the ET team's Feast/Spark dataset patterns.

---

## Upstream Contributions

If our combined work proves valuable, these could be contributed upstream:

| Contribution | Source | Target |
|-------------|--------|--------|
| `pipelineRunId` run facet pattern | Our POC | OpenLineage custom facets / `rhoai-lineage` |
| `naming.py` helpers | Our POC + ET normalisation rules | `rhoai-lineage` (shared) |
| SA token auth workaround for RHOAI MLflow | Our POC | `rhoai-lineage` |
| Bridge feature flag | Our POC | `rhoai-lineage` |
| MLflow REST tracker for KFP pods | Our POC | `rhoai-lineage` |
| `RequestHeaderProvider` for RHOAI MLflow Operator | Our POC | MLflow upstream (similar to `KubernetesRequestAuthProvider` in PR #21176) |
| Per-KFP-component OL emission pattern | Our POC | RHOAI documentation / reference architecture |
| Two-layer lineage architecture (Marquez + MLflow traces) | Our POC (DEC-009/ADR-004) | RHOAI reference architecture |

---

## References

| Source | Link |
|--------|------|
| ET team repo | [rh-waterford-et/lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline) |
| rhoai-lineage | [briangallagher/rhoai-lineage](https://github.com/briangallagher/rhoai-lineage) |
| data-strat-poc | [briangallagher/data-strat-poc](https://github.com/briangallagher/data-strat-poc) |
| ET team lessons learned | [docs/intro-and-lessons-learned.md](https://github.com/rh-waterford-et/lineage-demo-pipeline/blob/main/docs/intro-and-lessons-learned.md) |
| ADR-004 (lineage architecture) | `docs/architecture/adrs/ADR-004-lineage-architecture.md` |
| Prior-art synthesis | `docs/working/prior-art-synthesis.md` |
| ET team questions | `docs/assessment/et-team-questions.md` |
| Integration patterns assessment | work-knowledge `projects/data-strategy/docs/poc/lineage/integration-patterns.md` |
| Identity correlation assessment | work-knowledge `projects/data-strategy/docs/poc/lineage/identity-correlation.md` |
| Lineage next steps | work-knowledge `projects/data-strategy/docs/poc/lineage/lineage-next-steps.md` |
| Lineage library design | work-knowledge `projects/data-strategy/docs/poc/lineage/lineage-library-design.md` |
