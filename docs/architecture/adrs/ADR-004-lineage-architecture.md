# ADR-004: Lineage Architecture

**Date:** 2026-05-25
**Status:** Decided
**Milestone:** M2

## Context

The Data Strategy POC requires end-to-end data lineage to satisfy enterprise audit requirements (traceability of every vector back to its source document and processing step). The Waterford ET team had a working `openlineage-oai` + SDK prototype that emits OpenLineage events from KFP components to Marquez. The DataStrategy research proposed an MLflow-Marquez bridge as the primary lineage mechanism (combining experiment tracking with lineage in a single system).

Key constraints:
- RHOAI has no native OpenLineage emission from KFP components (PG-013)
- Marquez has no built-in auth (PG-001)
- MLflow in RHOAI uses an operator-managed instance with SA token auth and workspace headers
- The bridge adds complexity and potential noise to the Marquez graph
- Pipeline components need a clean library API, not raw OpenLineage protocol handling

## Decision

**Fork and adapt the ET team's code into `rhoai-lineage`, a standalone Python package. Use Marquez directly for pipeline-time lineage with the MLflow-Marquez bridge OFF by default.**

Specific choices:

1. **rhoai-lineage as a library, not a wrapper.** The ET team's code was restructured into a proper installable package with naming convention helpers (DEC-014), Marquez client, and MLflow bridge support. This is a fork-and-adapt, not a thin wrapper — we own the code and evolve it independently.

2. **Bridge OFF by default** (`MLFLOW_BRIDGE_ENABLED=false` in ConfigMap). The bridge (`openlineage+https://` tracking URI) sends MLflow events to Marquez, which creates additional nodes and edges. For pipeline-time lineage (M1–M3), direct OL emission from components is cleaner and more predictable. The bridge is available as an opt-in for evaluation and will be assessed for query-time tracing in M4.

3. **Deliberate deviation from DataStrategy research.** The research proposed the bridge as the primary mechanism. We instead use it as a supplement because: (a) direct OL emission gives us full control over naming conventions, (b) the bridge creates duplicate/synthetic nodes in Marquez for MLflow experiments, (c) pipeline-time lineage doesn't benefit from the bridge since we control both the OL emission and the MLflow logging.

4. **Lineage operator deferred** (not in critical path). The operator (AgentCard CRD, pod-watching) was designed for agent-level lineage in M4/M5. Infrastructure was prepared but deployment deferred since it has no role in pipeline-time lineage.

5. **`pipeline_run_id` as cross-system correlation key.** The KFP `pipeline_run_id` is injected into Milvus metadata, MLflow run tags, and intended for Marquez run facets. This allows cross-referencing between KFP UI, MLflow, and Marquez for any given pipeline execution.

6. **Naming conventions enforced by library (DEC-014).** The `rhoai-lineage` naming module generates OpenLineage-compliant URIs:
   - Datasets: `<scheme>://<host>:<port>/<path>` (e.g., `s3://minio-service...:9000/rag-chunks/chunks-m2`)
   - Jobs: `<namespace>/<job_name>` (e.g., `data-strat-poc/parse_and_chunk`)
   - Namespaces: Kubernetes namespace from downward API (`OPENLINEAGE_NAMESPACE`)

7. **Lineage config centralised in ConfigMap** (`data-strat-lineage-config`). All lineage configuration — Marquez URL, bridge toggle, namespace — lives in a single ConfigMap injected as env vars into pipeline pods via DSP's `configMapAsEnv` feature.

8. **DSP namespace injection via downward API.** The `OPENLINEAGE_NAMESPACE` is set from `metadata.namespace` via the Kubernetes downward API, patched into the DSPA CR. This ensures portability across namespace renames.

## Alternatives Considered

| Option | Pros | Cons | Why Not |
|--------|------|------|---------|
| Bridge as primary (DataStrategy proposal) | Single integration point; MLflow handles both tracking + lineage | Creates synthetic nodes; naming not controllable; adds latency; bridge is experimental upstream | Noisy graph, less control, harder to debug |
| Raw OpenLineage SDK (no library) | No dependency on rhoai-lineage | Every component reimplements naming, facets, error handling | DRY violation; naming drift guaranteed |
| Wrap ET code without forking | Less code to maintain | Can't evolve independently; ET team's concerns differ from ours | We need production naming, bridge toggles, DSP integration |
| OpenMetadata instead of Marquez | Richer UI, built-in auth | Much heavier deploy (Airflow, ES, MySQL); overkill for POC | Complexity; evaluate at M5+ |

## Consequences

- `rhoai-lineage` is a new repo (`briangallagher/rhoai-lineage`) that must be maintained
- Pipeline components have a git-install dependency on rhoai-lineage (PG-021 — slow installs)
- Marquez graph is clean and predictable (5 nodes: 3 datasets + 2 jobs)
- Bridge evaluation becomes a documented Phase 4 activity, not an implicit assumption
- MLflow and Marquez are independent systems with correlation via `pipeline_run_id`
- Lineage operator can be deployed later without changing the pipeline-time architecture
- `pipeline_run_id` correlation requires explicit facet emission (currently a gap — PG-025)

## Future Considerations

- **Bridge evaluation (M4):** When query-time tracing is implemented via MLflow GenAI spans, re-evaluate the bridge for combining inference traces with pipeline lineage in a single Marquez view.
- **Marquez auth (M5):** Deploy OAuth proxy sidecar for production multi-tenant access (PG-001).
- **PyPI package (post-POC):** Replace git-install with published wheel once rhoai-lineage API stabilises (closes PG-021).
- **Parent run facet:** Emit KFP `pipeline_run_id` as an OpenLineage `parent` run facet to enable cross-system correlation in Marquez (closes PG-025).
- **Lineage operator (M4/M5):** Deploy for agent-level lineage when OGX query path is implemented.
- **OpenMetadata evaluation (M5+):** If Marquez's lack of auth and limited UI become blockers, evaluate OpenMetadata as a replacement.

## References

| Source | Link |
|--------|------|
| DataStrategy research (lineage pillar) | `knowledge/rhoai/data-strategy/data-strategy.md` |
| ET team openlineage-oai repo | https://github.com/redhat-et/openlineage-oai |
| rhoai-lineage repo | https://github.com/briangallagher/rhoai-lineage |
| OpenLineage spec | https://openlineage.io/spec/2-0-2/ |
| Marquez docs | https://marquezproject.ai/docs |
| DEC-014 (naming conventions) | `docs/decisions.md` |
| PG-001 (Marquez auth) | `docs/production-gaps.md` |
| PG-021 (git install) | `docs/production-gaps.md` |
| PG-025 (pipeline_run_id facet) | `docs/production-gaps.md` |
