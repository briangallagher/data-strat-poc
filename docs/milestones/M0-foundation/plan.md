# M0: Foundation

**Status:** Complete
**Started:** 2026-05-22
**Completed:** 2026-05-23

## Goal

Establish the project structure, documentation standards, key architectural decisions, and tooling foundation so that M1 can start building with clear direction and no ambiguity.

## Objectives

1. Complete documentation structure with all tiers, templates, and conventions
2. Document cluster prerequisites with concrete resource specifications
3. Decide OGX role for ingest path (ADR-003) to unblock M1
4. Synthesise learnings from all 5 context sources into actionable prior-art analysis
5. Write the M1 milestone plan with full task breakdown, acceptance criteria, and verification plan

## Scope

### In Scope

- Repository structure (directories, CI baseline, linting, formatting)
- Full documentation skeleton (all tiers, all templates in `doc-standards.md`)
- Technical writer skill creation and verification
- `docs/operations/prerequisites.md` with concrete GPU/resource/operator specs
- `docs/operations/getting-started.md` initial version (M0 baseline setup)
- Initial ADRs: ADR-003 (OGX role), ADR-007 (multi-repo strategy)
- Initial personas and use case drafts (UC-001 document ingest — enough to frame M1)
- Prior-art synthesis (`docs/working/prior-art-synthesis.md`)
- Production-grade definition for this project
- `production-gaps.md` seeded with known gaps from prior work and DataStrategy feasibility
- M1 milestone plan (`docs/milestones/M1-ingest-pipeline/plan.md`)
- Project README with status table, doc index, and quick start links

### Out of Scope

- Cluster deployment (no manifests applied, no pods running)
- Code implementation
- KFP pipeline development
- Component-specific ADRs (ADR-001, ADR-002 — deferred to M1 planning/execution)

## Acceptance Criteria

- [ ] Documentation folder structure matches the tree in the plan
- [ ] `doc-standards.md` contains templates for all document types (ADR, use case, user journey, technical deep dive, milestone plan, checkpoint, runbook, prerequisites)
- [ ] Technical writer skill created and references doc-standards.md
- [ ] `docs/architecture/overview.md` has system context and container diagrams
- [ ] `docs/operations/prerequisites.md` has concrete resource specs (GPU type, memory, operators, storage)
- [ ] `docs/decisions.md` has at least DEC-001 through DEC-004 (foundation decisions)
- [ ] ADR-003 (OGX role) is at least Proposed with options analysis
- [ ] `docs/user-experience/personas.md` defines at least 4 personas
- [ ] UC-001 (document ingest) use case drafted
- [ ] `docs/working/prior-art-synthesis.md` covers all 5 context sources
- [ ] `production-gaps.md` seeded with known gaps
- [ ] M1 plan.md written with full structure (goal, objectives, tasks, acceptance criteria, verification plan)
- [ ] README.md serves as project entry point with status, doc index, quick start

## Tasks

| # | Task | Effort | Status | Notes |
|---|------|--------|--------|-------|
| 1 | Create directory structure and .gitkeep files | 15 min | Done | All tiers: architecture, technical, functional, UX, operations, milestones |
| 2 | Write `doc-standards.md` with all templates | 1 hr | Done | ADR, use case, journey, deep dive, milestone plan, checkpoint, runbook, prerequisites |
| 3 | Write `decisions.md` with DEC-001 through DEC-004 | 30 min | Done | Foundation decisions (self-contained docs, production-grade, e2e verification, multi-level docs) |
| 4 | Write `production-gaps.md` with register template | 15 min | Done | Seeded during prior-art synthesis |
| 5 | Create technical writer skill | 1 hr | Done | `.cursor/skills/technical-writer/SKILL.md` |
| 6 | Write `architecture/overview.md` with C4 diagrams | 1 hr | Done | System context + container view + component inventory |
| 7 | Write `operations/prerequisites.md` | 30 min | Done | GPU, operators, storage, network, dev environment |
| 8 | Write `operations/getting-started.md` (M0 baseline) | 30 min | Done | Namespace, secrets, base verification |
| 9 | Write `user-experience/personas.md` | 30 min | Done | Underwriter, compliance officer, data engineer, platform admin |
| 10 | Write `functional/requirements.md` initial set | 30 min | Done | FR-001 through FR-011 |
| 11 | Write project README.md | 30 min | Done | Status table, doc index, prior art table, quick start |
| 12 | Write prior-art synthesis | 2 hr | Done | All 5 sources synthesised into actionable patterns |
| 13 | Write ADR-003 (OGX role) | 1 hr | Done | Decided: direct Milvus writes for ingest, OGX for query (M4) |
| 14 | Write ADR-007 (multi-repo strategy) | 1 hr | Done | Start in hub, extract when boundaries prove stable |
| 15 | Draft UC-001 (document ingest) + UC-002/UC-003 stubs | 30 min | Done | Cockburn format; UC-002/UC-003 as lightweight stubs |
| 16 | Seed production-gaps.md with known gaps | 30 min | Done | PG-001 through PG-013 from prior work + DataStrategy |
| 17 | Write M1 plan.md | 1.5 hr | Done | 26 tasks, two-phase verification, resource requirements |
| 18 | Review and sign off M0 | 30 min | Done | All acceptance criteria verified |

## Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| Access to all 5 context source repos | Brian | Available |
| Cluster access for prerequisites verification | Brian | Available |
| DataStrategy repo for Scenario B spec | Data Strategy team | Available (read-only) |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ADR-003 (OGX) decision blocks on unclear OGX roadmap | Medium | High | Time-box to 2 hours; if unclear, decide "no OGX for ingest, re-evaluate at M4" |
| Prior-art synthesis takes too long (5 large repos) | Medium | Low | Focus on actionable patterns, not exhaustive coverage |
| Prerequisites specs are wrong (GPU, storage) | Low | Medium | Validated during M1 cluster deployment; update prerequisites as needed |

## Resource Requirements

| Resource | Specification | Purpose |
|----------|--------------|---------|
| Local dev machine | macOS, Python 3.11+, `oc` CLI | Documentation, planning, repo setup |
| Read access to context repos | 5 repos (see Context Sources) | Prior-art synthesis |

No cluster resources needed for M0.

## Verification Plan

### What Will Be Tested

- Documentation structure completeness (all directories, all template files)
- Technical writer skill creates a sample document correctly
- Architecture overview diagrams render in GitHub
- Prerequisites document has no TBD placeholders for critical specs
- Cross-references between documents resolve correctly

### How

- Manual walkthrough of all acceptance criteria
- GitHub preview of Mermaid diagrams
- Follow getting-started.md on a fresh namespace (M0 baseline only)

### Pass/Fail Criteria

- All acceptance criteria checked off
- M1 plan.md is actionable (a fresh agent session could start M1 from it)

### Regression Checks

N/A — first milestone.

## Documentation Deliverables

- [x] `docs/doc-standards.md` — templates and conventions
- [x] `docs/decisions.md` — DEC-001 through DEC-004
- [x] `docs/production-gaps.md` — register template
- [x] `docs/architecture/overview.md` — C4 diagrams
- [x] `docs/operations/prerequisites.md` — cluster requirements
- [x] `docs/operations/getting-started.md` — M0 baseline
- [x] `docs/user-experience/personas.md` — 4 personas
- [x] `docs/functional/requirements.md` — initial requirements
- [x] README.md — project entry point
- [x] `docs/working/prior-art-synthesis.md` — context source analysis
- [x] `docs/architecture/adrs/ADR-003-ogx-role.md` — OGX decision (direct writes for ingest, OGX for query)
- [x] `docs/architecture/adrs/ADR-007-multi-repo-strategy.md` — repo/package strategy
- [x] `docs/functional/use-cases/UC-001-document-ingest.md` — ingest use case (+ UC-002, UC-003 stubs)
- [x] `docs/production-gaps.md` — seeded with PG-001 through PG-013
- [x] `docs/milestones/M1-ingest-pipeline/plan.md` — M1 plan (26 tasks, two-phase verification)
