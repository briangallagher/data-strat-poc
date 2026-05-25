# Decision Log

High-level decisions made during the project. For significant architectural decisions with detailed context and alternatives analysis, use [ADRs](architecture/adrs/).

---

## Template

```
### DEC-NNN: Title
**Date:** YYYY-MM-DD
**Milestone:** M<N>
**Status:** Proposed | Decided | Superseded by DEC-NNN

**Context:** What prompted the decision.

**Decision:** What was decided.

**Consequences:** What follows — trade-offs, follow-up work, risks accepted.
```

---

## Decisions

### DEC-001: Self-contained documentation in code repo
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** v1 split planning documentation across work-knowledge and the code repo. This created context-switching overhead and made it harder for new contributors to find things.

**Decision:** All documentation lives in `data-strat-poc` — architecture, technical, functional, UX, operations, milestones. The work-knowledge repo tracks this as a project entry but doesn't host the planning docs.

**Consequences:** Single source of truth. Documentation ships with the code. Trade-off: no cross-project knowledge aggregation in work-knowledge (mitigated by linking from projects/index.md).

### DEC-002: Production-grade from day one with explicit gap tracking
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** v1 built quickly and deferred production concerns (auth, RBAC, TLS, error handling). Gaps were discovered but not systematically tracked, making it hard to assess production readiness.

**Decision:** Enterprise standard is the default expectation. Every deviation is logged in `production-gaps.md` with: what the gap is, why it exists, what production-grade looks like, and the path to close it. Updated at every milestone checkpoint.

**Consequences:** Slower initial velocity but clearer production readiness posture. Nothing is silently accepted. Gap register serves as a backlog for hardening work.

### DEC-003: E2E verification at every milestone
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** v1 built features sequentially without re-verifying previous phases. Regressions were discovered late.

**Decision:** Every milestone includes an E2E verification gate. New capabilities are verified (small scale first, then scaled up) and all previous milestone capabilities are re-verified. Milestone checkpoint documents record verification evidence.

**Consequences:** Higher confidence in system integrity at each stage. Additional verification effort per milestone. Forces clean, repeatable deployment.

### DEC-004: Multi-level documentation structure
**Date:** 2026-05-22
**Milestone:** M0
**Status:** Decided

**Context:** v1 had flat docs/ with no clear separation between architecture, operations, and user-facing content. Finding the right document required knowing the project well.

**Decision:** Six documentation tiers: Architecture (ADRs, system overview), Technical (component deep dives), Functional (use cases, requirements), User Experience (personas, journeys), Operations (prerequisites, runbooks, getting started), Milestones (plans, checkpoints). Conventions in `doc-standards.md`.

**Consequences:** Clear navigation for different audiences. Template overhead for new docs. Technical writer skill automates enforcement.

### DEC-005: Namespace prefix convention (`data-strat-`)
**Date:** 2026-05-23
**Milestone:** M0
**Status:** Decided

**Context:** Multiple namespaces will be created on the cluster as the project grows (core workloads, MLflow, Marquez, connectors, etc.). It needs to be immediately obvious which namespaces belong to this project when looking at `oc get namespaces`.

**Decision:** All OpenShift namespaces created by this project must be prefixed with `data-strat-`. The primary namespace is `data-strat-poc`. Additional namespaces (if needed for isolation) follow the pattern `data-strat-<component>` (e.g. `data-strat-mlflow`, `data-strat-lineage`).

**Consequences:** Easy identification of project resources at a glance. Simplifies cleanup (`oc get ns | grep data-strat-`). Consistent with the repo name. All manifests, getting-started docs, runbooks, and scripts must use this prefix — never hardcode a namespace without it.

### DEC-007: Data-chain-only ingest pipeline for M1–M3
**Date:** 2026-05-25
**Milestone:** M1
**Status:** Decided

**Context:** The full `rag_multistep_pipeline` includes both a data chain (parse → ingest) and a model chain (download LLM → deploy). For M1–M3 the focus is on the data pipeline — parsing, chunking, embedding, and vector storage. Model deployment (LLM + optional embedding service) is only needed from M4 onward when the query layer lands. Running unnecessary model deployment steps wastes GPU resources and adds failure modes during early milestones.

**Decision:** Split into two pipeline files in `pipelines-components`:
- `ingest_pipeline.py` — data-chain-only: `parse_and_chunk` → `ingest_to_milvus`. No model deployment parameters, no If/Else branching for embedding deployment. Used for M1–M3.
- `pipeline.py` — full multi-step pipeline with both chains. Retained for M4+ when LLM deployment is needed.

Both pipelines are exported from the same package. The compiled YAML for the ingest pipeline is `rag_ingest_pipeline.yaml`.

**Consequences:** Simpler pipeline for early milestones — fewer parameters, no GPU requirements, faster runs. The full pipeline remains available and tested. When M4 starts, the team switches back to `rag_multistep_pipeline` (or extends the ingest pipeline with query steps).

### DEC-008: Multi-collection architecture for Scenario B
**Date:** 2026-05-25
**Milestone:** M2 (captured for M3 execution)
**Status:** Decided

**Context:** Scenario B specifies three document collections for the P&C underwriting knowledge assistant, each serving different personas and query patterns. M1-M2 used a single `underwriting_guidelines` collection with all 11 test PDFs mixed together. The compliance review agent (UC-003) requires multi-hop retrieval across all three collections.

**Decision:** Run the ingest pipeline **separately per collection** with different parameters:

| Pipeline Run | Collection | Input Documents | Category |
|-------------|------------|-----------------|----------|
| Run 1 | `underwriting_guidelines` | Company guidelines by LOB | Per-LOB (commercial_property, workers_comp, etc.) |
| Run 2 | `iso_forms` | ISO/ACORD standard forms | Per form series |
| Run 3 | `regulatory_bulletins` | State DOI bulletins, NAIC guidance | Per jurisdiction |

Each run gets its own `pipeline_run_id`, lineage graph, and MLflow experiment run. The collections share the same schema (ADR-002) but contain different document types.

At M3, connectors route documents from different sources to the appropriate collection. At M4, OGX queries across all three collections for the compliance review agent.

**Consequences:** The pipeline already supports this -- `collection_name` is a parameter. No code changes needed. M3 must implement: (a) corpus organisation by collection, (b) per-collection pipeline runs, (c) per-document metadata from manifests (PG-020). The compliance review agent (M5) depends on all three collections being populated.

### DEC-006: Git tagging convention for milestones and phases
**Date:** 2026-05-25
**Milestone:** M1
**Status:** Decided

**Context:** The project spans multiple repos (`data-strat-poc` for docs/manifests and `pipelines-components` fork for component code). When a milestone or phase is verified, we need a way to recreate that exact state across all repos — for rollback, comparison, or onboarding.

**Decision:** Use lightweight git tags with the pattern `m<N>-p<P>` (e.g., `m1-p0`, `m1-p2`, `m1-complete`) applied simultaneously to all project repos at each verified checkpoint. Tags are permanent and never moved.

**Consequences:** Any checkpoint can be recreated by checking out the same tag across all repos. Enables rollback after broken changes. Makes it easy to diff between phases (`git diff m1-p1..m1-p2`). Requires discipline to tag all repos together — a missed tag on one repo breaks the contract.
