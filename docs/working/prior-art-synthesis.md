# Prior Art Synthesis

Actionable patterns from all 5 context sources, distilled for decision-making.

**Date:** 2026-05-23
**Purpose:** Inform ADR-003 (OGX role), ADR-007 (multi-repo), M1 planning, and component design.

---

## 1. data-strategy-poc (Prior POC)

### What Worked

| Pattern | Detail | Carry Forward |
|---------|--------|---------------|
| OGX Vector I/O for embedding + insert | Single API call handles embedding and Milvus write. Simplifies pipeline code. | **Evaluate** — ADR-003. May be too opaque for production (no control over embedding model, batching, error handling) |
| `pipeline_run_id` on every vector | Every Milvus vector carries the KFP/pipeline run ID. Enables lineage bridge at query time. | **Yes** — foundational for Chain 1 (Answer Provenance) |
| Marquez for pipeline lineage | `lineage_emitter.py` (400 lines) emits OpenLineage events; 29-node graph in Marquez covering acquire → parse → embed → insert → collections | **Adapt** — extract into `rhoai-lineage` library; reduce per-pipeline boilerplate |
| Two-layer lineage architecture | Marquez for pipeline-time (batch), MLflow for query-time (interactive). Bridge via `pipeline_run_id`. DEC-022 | **Yes** — validated design. Query-time tracing not yet implemented (JSONL audit log is the gap) |
| Serial ingest path (`ingest-corpus.py`) | ~600 lines. Docling + OGX. Works but slow (~9 min for 15 docs). Good for validation. | **Adapt** — useful as a non-KFP fallback for debugging; not the primary path |
| RayData ingest (`ray-ingest.py`) | Distributed parsing via RayJob. ~6.4 min for same corpus. Uses same OGX Vector I/O pattern. | **Adapt** — align with the Ray team's `parse_and_chunk` RayJob pattern |
| Connector package (`dsp-connectors`) | Base class + S3/Confluence/SharePoint connectors. Acquisition lineage emission. pip-installable. | **Adapt** — good interface design. Needs real OAuth, pagination, error handling (PG-010) |
| KFP pipeline components | 6 components (acquire, parse, embed, insert, lineage, rayjob). Each ~30-100 lines. | **Adapt** — compare with the Ray team's 5-component structure; the Ray team's is more mature |
| Registry API + Data Hub UI | FastAPI registry for datasets/collections/sources + React/PatternFly SPA | **Defer** — not needed for M1-M4. Evaluate at M5 alongside catalog discussion |
| Gradio demo app | RAG query UI with citations, audit tab, compliance report | **Adapt** — reuse at M4 for query path verification |

### What Didn't Work

| Issue | Detail | Approach |
|-------|--------|-------------|
| Monolithic scripts | `ingest-corpus.py` (600 lines) mixes parsing, embedding, lineage, error handling | Component-per-concern in KFP pipeline |
| Manual OpenLineage emission in every script | Each script hardcodes Marquez URL, namespace, naming conventions | `rhoai-lineage` library encodes conventions |
| JSONL audit log for query tracing | File on PVC, not queryable, `pipeline_run_id` always null, no RBAC, no hierarchy | MLflow GenAI traces from M2 |
| Single deploy.sh for everything | Order-dependent, fragile, manual steps | Manifest-per-component, runbook-per-use-case |
| Retrospective documentation | Docs written after building, often stale | Document-as-you-go (DEC-004) |

### Key Decisions to Carry Forward

| Prior Decision | Carry Forward | Notes |
|-------------|---------------|-------|
| DEC-002: OGX in MVP | **Re-evaluate** | ADR-003 — the Ray team's approach bypasses OGX for ingest |
| DEC-004: Granite 8B initially, 70B later | **Yes** | 8B sufficient for deterministic RAG; 70B needed for agentic (M5) |
| DEC-005: Self-serve document corpus | **Yes** | Public-domain P&C docs; no dependency on real customer data |
| DEC-014: OpenLineage naming conventions | **Yes** | `s3://`, `milvus://`, `feast://` namespace patterns. Encode in library. |
| DEC-022: MLflow/Marquez two-layer lineage | **Yes** | Proven architecture. Complete the query-time side. |

---

## 2. the Ray team's PRs (pipelines-components #53 + red-hat-ai-examples #78)

### Patterns to Adopt

| Pattern | Detail | Adoption |
|---------|--------|----------|
| 5-component KFP structure | `parse_and_chunk`, `ingest_to_milvus`, `download_model`, `deploy_embedding_model`, `model_deployment`. Clean separation. | **Adopt** — adapt component boundaries for our needs |
| S3 as intermediate store | Chunks written to S3/MinIO as JSONL between parse and ingest steps. Keeps data PVC read-only. | **Adopt** — decouples parsing from embedding; enables retry of ingest without re-parsing |
| Parallel pipeline chains | Data chain (parse → ingest) and model chain (download → deploy) run independently | **Adopt** — reduces end-to-end pipeline time |
| RayJob + Docling actor pool | `parse_and_chunk` submits a RayJob with configurable worker/actor sizing, Docling actors | **Adopt** — production-oriented Ray pattern |
| Dual embedding modes | Local `sentence-transformers` vs remote vLLM `/v1/embeddings` endpoint | **Adopt** — flexibility for different cluster configurations |
| `RELATED_IMAGE_*` env var pattern | Base images configurable via environment variables, consistent with RHOAI operator pattern | **Adopt** — production-grade image management |
| `metadata.yaml` + stability banners | Each component has metadata and an `experimental` stability banner | **Adopt** — good practice for reusable components |
| Cache-skip with sentinel file | `download_model` uses `.download_complete` to avoid re-downloading weights | **Adopt** — simple and effective |
| `RAGSetup` K8s provisioning library | ~815 lines. Idempotent Secret/PVC/RBAC/KServe creation. `oc whoami -t` auth. | **Reference** — useful patterns for getting-started automation |

### Key Differences from the Prior POC

| Aspect | Prior POC | Ray Team | Decision |
|--------|-----|------|-------------|
| OGX for ingest | Yes (Vector I/O) | No (direct Milvus writes) | **ADR-003** |
| Embedding | OGX handles it | Local sentence-transformers or vLLM endpoint | Prefer vLLM endpoint (production-grade, consistent) |
| Intermediate storage | In-memory | S3 JSONL | S3 JSONL (the Ray team's pattern) |
| Pipeline orchestration | Custom KFP components | Reusable KFP components in shared repo | Reusable components (the Ray team's pattern) |
| Model deployment | Separate from ingest | Part of pipeline (parallel chain) | Part of pipeline |

---

## 3. Waterford ET lineage-demo-pipeline

### Patterns to Adopt

| Pattern | Detail | Adoption |
|---------|--------|----------|
| Namespace injection for OpenLineage | Patches Argo workflow controller ConfigMap to inject `OPENLINEAGE_NAMESPACE` from pod `metadata.namespace` | **Adopt** — elegant solution for KFP/DSP environments |
| `openlineage-oai` KFP adapter | Context manager wrapping KFP steps with automatic OL event emission. Handles START/COMPLETE/FAIL lifecycle. | **Evaluate** — may be simpler than per-component emission |
| `openlineage-oai` MLflow tracking store | Custom MLflow tracking URI (`openlineage+http://...`) emits OL events alongside MLflow logging | **Evaluate** — interesting pattern for MLflow ↔ lineage bridge |
| Dataset naming normalisation | PostgreSQL `postgresql://` → `postgres://`, Spark `s3a://` → `s3://`. Without this, lineage graphs break. | **Adopt** — encode in rhoai-lineage library's naming.py |
| Single-manifest deploy with staged bootstrap | One YAML, rendered per-namespace, with ordered Jobs | **Reference** — we prefer manifest-per-component but the namespace rendering is useful |
| `AgentCard` CRD | Go operator watches annotated pods, queries Marquez, builds K8s CRs for lineage cards | **Defer** — stretch goal for M5+. Interesting for agent lineage but heavy lift (Go operator). |
| `dataset-registry` | FastAPI + PatternFly UI for canonical dataset identity, correlates with Marquez | **Reference** — similar concept to prior registry-api. Evaluate at M5 alongside catalog. |

### Lessons Learned (from their docs)

| Lesson | Detail | Impact |
|--------|--------|-------------|
| Dataset naming is the #1 lineage pitfall | Inconsistent `namespace:name` strings break the graph silently. No error — just disconnected nodes. | Encode all naming conventions in `rhoai-lineage` library. Never construct dataset strings by hand. |
| Feast project-scoped namespaces are intentional | Feast appends project name to OL namespace. Not a bug — design for multi-project isolation. | Understand before integrating; don't try to "fix" it. |
| Marquez namespace scoping question is unresolved | Should lineage be per-K8s-namespace or cluster-wide? Determines multi-tenancy model. | Start single-namespace (data-strat-poc), defer multi-tenancy to M5+ hardening. |
| OpenLineage on KFP requires platform patching | KFP/DSP doesn't emit OL natively. Either patch the DSP controller or emit from within components. | Emit from within components (Pattern 2 from integration-patterns.md). Namespace injection helps. |

---

## 4. DataStrategy Repo

### Strategic Framing

| Item | Key Takeaway | Impact |
|------|-------------|-------------|
| Scenario B is the non-Feast path | No ML models, no feature engineering. Stack: KFP → RayData+Docling → Milvus → OGX. | Confirms our component choices |
| 13 platform-integration gaps | Mostly at integration layer, not individual components | Our gap register (PG-001 through PG-013) tracks these |
| Pillar 4 feasibility = indeterminate | Conflates collection, aggregation, governance. Marquez productisation is multi-quarter. | Don't over-invest in Marquez infra; focus on emission patterns that work with any backend |
| Lineage for RAG is harder than for feature stores | Manual instrumentation at 3 levels (pipeline, query, agent) vs. Feast's native emission | Lineage library is essential — can't rely on native integration |
| Complementary architecture (Feast+MLflow → Marquez) | Not competitive tools; each has a role | Two-layer model (DEC-009) is correct |
| No lakehouse/Iceberg strategy | RHOAI has no position on open table formats | Out of scope but worth noting as a strategic gap |

### Research Findings That Inform This Project

| Finding | Source | Impact |
|---------|--------|--------|
| OpenMetadata + Feast is the recommended catalog hybrid | Catalog comparison report | Defer catalog integration to post-M5. Don't build a registry; evaluate OpenMetadata. |
| Marquez has no auth, single maintainer, 18-month release stall | Marquez SWOT | Don't couple tightly to Marquez. Abstract behind rhoai-lineage library. Be ready to swap backends. |
| MLflow has no OpenLineage support (bridge needed) | Lineage deep report | Evaluate ET team's `openlineage-oai` MLflow adapter as the bridge |
| Spark OL is config-only (not in RHOAI images) | Lineage deep report | Not relevant for Scenario B (no Spark) but good to note for broader strategy |

---

## 5. Work-Knowledge Lineage Docs

### Key Designs to Carry Forward

| Design | Source | Status | Impact |
|--------|--------|--------|--------|
| `rhoai-lineage` library spec | `lineage-library-design.md` | Design notes (not implemented) | Primary reference for M2 lineage library extraction |
| Two entry points: `PipelineLineage` + `extract_lineage_refs()` | `lineage-library-design.md` | Designed | Pipeline-time emission + query-time bridge data |
| Naming convention helpers (`naming.py`) | `lineage-library-design.md` | Designed | `s3_dataset()`, `milvus_dataset()` — encode DEC-014 conventions |
| Option 1 (convention-based identity) recommended over Option 2 (registry) | `identity-correlation.md` | Assessed | Start with conventions; build registry only if graphs break at component boundaries |
| Three lineage chains (P0/P1/P2 priority) | `lineage-scenarios.md` | Defined | Chain 1 (Answer Provenance) is the M4 verification target |
| Per-KFP-component emission (Pattern 2) is the right default | `integration-patterns.md` | Assessed | Don't try to auto-instrument; emit from within each pipeline component |
| Marquez auth: start with Option C (operator + oauth-proxy) | `lineage-next-steps.md` | Assessed | Minimum viable Marquez auth for M2 |

---

## Synthesis: Key Decisions

### Resolved

| Decision | Resolution | Basis |
|----------|-----------|-------|
| Pipeline component structure | Adopt the Ray team's 5-component pattern, adapted | PR #53 is more mature than the prior POC's components |
| Intermediate storage | S3 JSONL between parse and ingest | the Ray team's pattern; decouples parsing from embedding |
| Embedding approach | vLLM endpoint via KServe (primary), local sentence-transformers (fallback) | the Ray team's dual-mode pattern; production-grade |
| OpenLineage emission pattern | Per-KFP-component emission (Pattern 2) + namespace injection | ET team + integration-patterns.md assessment |
| Dataset naming | Convention-based identity (Option 1), encoded in library | identity-correlation.md recommendation |
| Multi-repo | Start in integration hub, extract when boundaries prove stable | ADR-007 |

### Requires ADR (Open)

| Decision | ADR | Key Question | Options |
|----------|-----|-------------|---------|
| OGX role in ingest | ADR-003 | Use OGX Vector I/O for embedding+insert, or direct Milvus writes? | A: OGX (prior pattern), B: Direct (the Ray team's pattern), C: OGX for embed only |
| Lineage backend | Future ADR | Marquez standalone, or evaluate OpenMetadata as combined catalog+lineage? | Defer to M2; start with Marquez, evaluate alternatives later |

---

## References

| Source | Location |
|--------|----------|
| Prior POC | `~/dev/git-repos/data-strategy-poc/` |
| Prior POC decisions | `~/dev/git-repos/data-strategy-poc/docs/decisions.md` |
| Prior POC learnings | `~/dev/git-repos/data-strategy-poc/docs/learnings.md` |
| the Ray team's PR #53 | [pipelines-components #53](https://github.com/opendatahub-io/pipelines-components/pull/53) |
| the Ray team's PR #78 | [red-hat-ai-examples #78](https://github.com/red-hat-data-services/red-hat-ai-examples/pull/78) |
| ET lineage demo | [lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline) |
| DataStrategy | `~/dev/git-repos/DataStrategy/` |
| Lineage library design | work-knowledge `projects/data-strategy/docs/poc/lineage/lineage-library-design.md` |
| Lineage scenarios | work-knowledge `projects/data-strategy/docs/poc/lineage/lineage-scenarios.md` |
| Integration patterns | work-knowledge `projects/data-strategy/docs/poc/lineage/integration-patterns.md` |
| Identity correlation | work-knowledge `projects/data-strategy/docs/poc/lineage/identity-correlation.md` |
