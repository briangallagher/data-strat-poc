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
