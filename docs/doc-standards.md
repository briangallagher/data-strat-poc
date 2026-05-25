# Documentation Standards

Conventions and templates for all documentation in this project. The [technical-writer skill](../.cursor/skills/technical-writer/SKILL.md) enforces these standards.

## Principles

1. **Right document for the right purpose** — don't mix architecture decisions with operational guides
2. **Cross-reference, don't duplicate** — link between tiers; one source of truth per fact
3. **Diagrams via Mermaid** — all diagrams use the [mermaid-technical-diagrams skill](~/.cursor/skills/mermaid-technical-diagrams/SKILL.md); no external image files unless unavoidable
4. **Future considerations in every document** — every doc that describes a design or decision must include what we'd do differently at scale or with more time
5. **Production gaps called out inline** — when documenting something that falls short of enterprise standard, reference the gap ID from `production-gaps.md`

## Document Tiers

| Tier | Directory | Audience | Question Answered |
|------|-----------|----------|-------------------|
| Architecture | `docs/architecture/` | Engineers, architects | "How is the system structured and why?" |
| Technical | `docs/technical/` | Engineers | "How does this component work?" |
| Functional | `docs/functional/` | Engineers, PMs, stakeholders | "What does the system do?" |
| User Experience | `docs/user-experience/` | PMs, designers, field teams | "Who uses it and what's their experience?" |
| Operations | `docs/operations/` | Engineers, operators, field teams | "How do I run it?" |
| Milestones | `docs/milestones/` | Project team | "What are we building and when?" |

---

## Templates

### Architecture Decision Record (ADR)

Location: `docs/architecture/adrs/ADR-NNN-<short-name>.md`

```markdown
# ADR-NNN: <Title>

**Date:** YYYY-MM-DD
**Status:** Proposed | Decided | Superseded by ADR-NNN
**Milestone:** M<N>

## Context

What prompted this decision. Include the specific problem, constraints, and options considered.

## Decision

What was decided and why this option was chosen over alternatives.

## Alternatives Considered

| Option | Pros | Cons | Why Not |
|--------|------|------|---------|
| ... | ... | ... | ... |

## Consequences

What follows from this decision — trade-offs accepted, follow-up work required, risks.

## Future Considerations

What would change at production scale, with more time, or if constraints shift.
How this decision should be revisited and under what conditions.

## References

| Source | Link |
|--------|------|
| ... | ... |
```

### Technical Deep Dive

Location: `docs/technical/<component-name>.md`

```markdown
# <Component Name>

## What This Is

One paragraph: what is this component, what role does it play in the system.

## Architecture Context

How this component fits into the overall system. Reference the architecture overview.
Include a Mermaid diagram showing this component's boundaries and interfaces.

## How It Works

Detailed explanation of the component's behavior, data flows, and integration points.

### Configuration

Key configuration parameters, environment variables, and manifest values.

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| ... | ... | ... |

## Design Decisions

Link to relevant ADRs. Summarise key choices that shaped this component.

## Known Limitations

What doesn't work, what's fragile, what's untested. Reference production gap IDs where applicable.

## Future Considerations

What would change at scale. What's deferred and why.

## References

| Source | Link |
|--------|------|
| ... | ... |
```

### Use Case Specification

Location: `docs/functional/use-cases/UC-NNN-<short-name>.md`

Format: Cockburn fully-dressed use case.

```markdown
# UC-NNN: <Title>

**Primary Actor:** <who initiates this>
**Goal:** <what the actor is trying to achieve>
**Scope:** <system boundary>
**Level:** User goal | Sub-function
**Milestone:** M<N>

## Preconditions

- What must be true before this use case can start

## Main Success Scenario

1. Step 1
2. Step 2
3. ...

## Extensions (Alternate Flows)

- **2a.** If condition X: ...
- **3a.** If condition Y: ...

## Postconditions

### Success

- What is true after successful completion

### Failure

- What is true after failure (system state, data state)

## Related

- **ADRs:** ADR-NNN
- **Technical:** `docs/technical/<component>.md`
- **User Journey:** UJ-NNN
- **Requirements:** FR-NNN
```

### User Journey Map

Location: `docs/user-experience/journeys/UJ-NNN-<short-name>.md`

```markdown
# UJ-NNN: <Journey Title>

**Persona:** <name from personas.md>
**Goal:** <what the persona is trying to accomplish>
**Trigger:** <what initiates this journey>

## Journey Steps

| Step | Action | System Response | Touchpoint | Pain Point | Opportunity |
|------|--------|-----------------|------------|------------|-------------|
| 1 | ... | ... | ... | ... | ... |
| 2 | ... | ... | ... | ... | ... |

## Current State vs. Target State

What the experience is today (if applicable) vs. what this project delivers.

## Related

- **Use Cases:** UC-NNN
- **Workflows:** `docs/user-experience/workflows.md#<section>`
```

### Milestone Plan

Location: `docs/milestones/M<N>-<name>/plan.md`

```markdown
# M<N>: <Milestone Name>

**Status:** Planning | Active | Verification | Complete
**Started:** YYYY-MM-DD
**Completed:** YYYY-MM-DD

## Goal

One sentence: what this milestone achieves.

## Objectives

1. Measurable outcome 1
2. Measurable outcome 2
3. ...

## Scope

### In Scope

- ...

### Out of Scope

- ...

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] ...

## Tasks

| # | Task | Effort | Status | Notes |
|---|------|--------|--------|-------|
| 1 | ... | ... | ... | ... |

## Dependencies

| Dependency | Owner | Status |
|------------|-------|--------|
| ... | ... | ... |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ... | ... | ... | ... |

## Resource Requirements

| Resource | Specification | Purpose |
|----------|--------------|---------|
| ... | ... | ... |

## Verification Plan

### What Will Be Tested

- ...

### How

- ...

### Pass/Fail Criteria

- ...

### Regression Checks

- Re-verify M<N-1> capabilities: ...

## Documentation Deliverables

- [ ] ADR-NNN: ...
- [ ] Technical deep dive: ...
- [ ] Runbook: ...
- [ ] ...
```

### Milestone Checkpoint

Location: `docs/milestones/M<N>-<name>/checkpoint.md`

Written on milestone completion.

```markdown
# M<N> Checkpoint: <Milestone Name>

**Date:** YYYY-MM-DD
**Status:** Complete | Complete with gaps

## What Was Built

Summary of deliverables and their state.

## Verification Results

| Test | Method | Result | Evidence |
|------|--------|--------|----------|
| ... | ... | Pass/Fail | Link or description |

### Regression Results

| Previous Milestone | Result | Notes |
|--------------------|--------|-------|
| M<N-1> | Pass/Fail | ... |

## Production Gaps Identified

| Gap ID | Description | Logged in production-gaps.md |
|--------|-------------|------------------------------|
| PG-NNN | ... | Yes |

## Cluster State

Current state of the cluster after this milestone. What's deployed, what's running.

## How to Resume

Context needed to pick up work from this checkpoint. Key files, cluster state, next steps.

## Lessons Learned

What went well, what didn't, what to change for next milestone.
```

### Runbook

Location: `docs/operations/runbooks/<name>.md`

```markdown
# Runbook: <Title>

**Last Verified:** YYYY-MM-DD (M<N>)
**Prerequisites:** Link to prerequisites.md

## What This Does

One paragraph explaining the use case this runbook covers.

## Prerequisites

- [ ] Prerequisite 1 (link to verification command)
- [ ] Prerequisite 2

## Steps

### 1. <Step Title>

```bash
# commands
```

**Expected output:** ...

**If it fails:** ...

### 2. <Step Title>

...

## Verification

How to confirm the operation succeeded.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| ... | ... | ... |
```

### Prerequisites

Location: `docs/operations/prerequisites.md`

```markdown
# Prerequisites

## Cluster Requirements

| Requirement | Specification | Notes |
|-------------|--------------|-------|
| OpenShift | ... | ... |
| RHOAI | ... | ... |
| ... | ... | ... |

## GPU / Compute Resources

| Resource | Specification | Purpose |
|----------|--------------|---------|
| ... | ... | ... |

## Operators

| Operator | Version | Purpose |
|----------|---------|---------|
| ... | ... | ... |

## Storage

| Storage | Size | Purpose |
|---------|------|---------|
| ... | ... | ... |

## Network

| Requirement | Detail |
|-------------|--------|
| ... | ... |

## External Dependencies

| Dependency | Purpose | How to Obtain |
|------------|---------|---------------|
| ... | ... | ... |
```

---

## Naming Conventions

### Documents

| Item | Pattern | Example |
|------|---------|---------|
| ADRs | `ADR-NNN-<kebab-case>.md` | `ADR-001-raydata-docling-pipeline.md` |
| Use Cases | `UC-NNN-<kebab-case>.md` | `UC-001-document-ingest.md` |
| User Journeys | `UJ-NNN-<kebab-case>.md` | `UJ-001-underwriter-query.md` |
| Runbooks | `run-<kebab-case>.md` | `run-ingest-pipeline.md` |
| Technical | `<kebab-case>.md` | `raydata-docling.md` |
| Production Gaps | `PG-NNN` | `PG-001` |
| Decisions | `DEC-NNN` | `DEC-001` |
| Functional Reqs | `FR-NNN` | `FR-001` |

### OpenShift Namespaces (DEC-005)

All namespaces must be prefixed with `data-strat-` so project resources are immediately identifiable on the cluster.

| Namespace | Purpose |
|-----------|---------|
| `data-strat-poc` | Primary namespace — pipelines, ingest, query |
| `data-strat-mlflow` | MLflow tracking server (if isolated) |
| `data-strat-lineage` | Marquez / lineage backend (if isolated) |
| `data-strat-<component>` | Pattern for any additional isolation needs |

When writing manifests, runbooks, getting-started docs, or scripts, always use the `data-strat-` prefix. Never hardcode a namespace without it.

### Git Tags (DEC-006)

All repos in this project use a consistent tagging convention to mark milestone and phase completions. Tags are applied to **all repos simultaneously** at each checkpoint so the full system state can be recreated.

**Pattern:** `m<milestone>-p<phase>[-<qualifier>]`

| Tag | Meaning | Example |
|-----|---------|---------|
| `m<N>-p<P>` | Milestone N, Phase P complete | `m1-p0`, `m1-p1`, `m1-p2` |
| `m<N>-p<P>-<qualifier>` | With qualifier for special states | `m1-p0-baseline` |
| `m<N>-complete` | Full milestone sign-off | `m1-complete` |

**Rules:**
- Tags are applied to **all project repos at the same time** — never tag one repo without tagging the others
- A tag represents a **verified checkpoint** — the system was tested and working at this point
- Tags are lightweight (not annotated) unless the milestone checkpoint warrants a release note
- Never move or delete tags — they are permanent reference points

**Repos that get tagged:**

| Repo | What's Tagged |
|------|---------------|
| `data-strat-poc` | Docs, manifests, compiled pipeline YAML, scripts |
| `briangallagher/pipelines-components` (branch `data-strat-poc`) | Pipeline component code with fixes |

**To recreate a checkpoint:**

```bash
# Check out a specific milestone/phase across all repos
git -C ~/dev/git-repos/data-strat-poc checkout m1-p2
git -C ~/dev/odh/pipelines-components checkout m1-p2

# Recompile the pipeline from that state
pip install -e ~/dev/odh/pipelines-components  # or /tmp clone
python3 -c "from kfp import compiler; ..."

# Redeploy using the manifests from that tag
oc apply -f manifests/base/namespace-setup.yaml
# ... etc (see getting-started.md)
```

**To fall back after a broken change:**

```bash
# Revert both repos to the last known-good checkpoint
git -C ~/dev/git-repos/data-strat-poc checkout m1-p1
git -C ~/dev/odh/pipelines-components checkout m1-p1
# Recompile and redeploy from that state
```

## Quality Checklist

Run before finalising any document:

- [ ] Document follows the correct template for its type
- [ ] All required sections are present (use `<!-- TODO -->` for sections awaiting content)
- [ ] Cross-references to other docs use relative links and are correct
- [ ] Mermaid diagrams render correctly in GitHub preview
- [ ] Future Considerations section is present and substantive (not placeholder)
- [ ] Production gaps referenced by ID where applicable
- [ ] No duplicated content — link to the source of truth instead
- [ ] Date and status fields are current
