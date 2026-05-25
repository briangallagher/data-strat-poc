---
name: technical-writer
description: >-
  Create and verify project documentation following doc-standards.md conventions.
  Produces ADRs, use cases, user journeys, technical deep dives, milestone plans,
  checkpoints, runbooks, and operations docs. Verifies existing documents against
  templates and cross-referencing rules. Use when creating or reviewing any
  documentation in the data-strat-poc project.
---

# Technical Writer

## Purpose

Create, update, and verify project documentation for the data-strat-poc project following the conventions in `docs/doc-standards.md`. Ensures consistency across all document tiers and enforces cross-referencing between them.

## When to Use

- Creating any new document (ADR, use case, user journey, technical deep dive, milestone plan, checkpoint, runbook)
- Reviewing or verifying existing documentation for completeness and consistency
- Updating the architecture overview after component changes
- Flagging missing documentation for implemented features
- Writing milestone checkpoints after milestone completion

## Process

### 1. Read the Standards

**Always start by reading `docs/doc-standards.md`** from the project root. This file contains:
- Templates for every document type
- Naming conventions
- Quality checklist
- Cross-referencing rules

Do not rely on memory — read the file every time to catch any updates.

### 2. Determine Document Type

| If the user asks for... | Create this | Template in doc-standards.md |
|------------------------|-------------|------------------------------|
| An architecture decision | ADR | Architecture Decision Record |
| A component explanation | Technical Deep Dive | Technical Deep Dive |
| A use case or user story | Use Case Specification | Use Case Specification |
| A user journey or persona flow | User Journey Map | User Journey Map |
| A milestone plan | Milestone Plan | Milestone Plan |
| A milestone completion report | Milestone Checkpoint | Milestone Checkpoint |
| How to run something | Runbook | Runbook |
| What's needed before deployment | Prerequisites update | Prerequisites |
| Step-by-step setup | Getting Started update | (extend existing) |

### 3. Create the Document

1. **Use the correct template** from `doc-standards.md` — every section is mandatory
2. **Follow naming conventions** — `ADR-NNN-kebab-case.md`, `UC-NNN-kebab-case.md`, etc.
3. **Place in the correct directory** per the documentation structure
4. **Use `<!-- TODO -->` comments** for sections that need content but can't be filled yet
5. **Include Mermaid diagrams** where the document describes architecture, data flows, or sequences

### 4. Create Diagrams

For all diagrams, use the **mermaid-technical-diagrams** skill:

1. Read the skill at `~/.cursor/skills/mermaid-technical-diagrams/SKILL.md`
2. Follow its Phase A (diagram plan) and Phase B (Mermaid + prose) workflow
3. Ensure diagrams render in GitHub-flavored Markdown
4. Apply the architecture pastel skin for flowcharts with subgraphs
5. Respect complexity limits (~12-15 nodes per diagram, ~8 sequence participants)

**Every architecture-level document and every technical deep dive must have at least one Mermaid diagram.** Milestone plans should have a diagram if the milestone involves multiple interacting components.

### 5. Enforce Cross-References

Documents must link to related documents in other tiers:

| Document Type | Must Reference |
|---------------|---------------|
| ADR | Related technical deep dives, use cases affected, milestone |
| Technical Deep Dive | Relevant ADRs, architecture overview, production gap IDs |
| Use Case | Related ADRs, technical docs, user journeys, functional requirements |
| User Journey | Related use cases, workflows |
| Milestone Plan | Relevant ADRs to produce, use cases in scope, runbooks to write |
| Runbook | Prerequisites, related use case, troubleshooting |
| Checkpoint | Production gaps found, verification results, previous milestones |

### 6. Verify (for review mode)

When asked to verify or review documentation, check against this list:

**Structure check:**
- [ ] Document follows the correct template from `doc-standards.md`
- [ ] All required sections present (or marked `<!-- TODO -->` with justification)
- [ ] Naming convention followed (ADR-NNN, UC-NNN, UJ-NNN, PG-NNN, etc.)
- [ ] File is in the correct directory

**Content check:**
- [ ] Future Considerations section is substantive, not placeholder
- [ ] Production gaps referenced by ID (PG-NNN) where applicable
- [ ] No duplicated content — links to source of truth instead
- [ ] Dates and status fields are current
- [ ] Mermaid diagrams present where required (architecture, technical, milestone)
- [ ] Diagrams render correctly (no syntax errors)

**Cross-reference check:**
- [ ] Links to related documents in other tiers are present and correct
- [ ] Relative paths resolve correctly from the document's location
- [ ] Referenced ADR/UC/UJ/FR IDs exist in the target documents

**Completeness check:**
- [ ] Every implemented feature has a corresponding technical deep dive
- [ ] Every significant decision has an ADR
- [ ] Every milestone has both a plan.md and (if completed) checkpoint.md
- [ ] Production gaps register is current (check milestone checkpoints against register)

### 7. Update Architecture Overview

When components are added, removed, or significantly changed:

1. Read `docs/architecture/overview.md`
2. Update the system context diagram (C4 Context level)
3. Update the container diagram (C4 Container level)
4. Update the component inventory table
5. Verify all cross-references from technical deep dives still point correctly

## Quality Standards

These are non-negotiable:

- **No documentation debt without tracking** — if a section can't be filled, add `<!-- TODO: reason -->` and log in the milestone's task list
- **Diagrams are not optional** — architecture and technical docs require Mermaid diagrams
- **Future Considerations is not optional** — every design or decision doc must address what changes at scale
- **Production gaps are not optional** — if something isn't enterprise-grade, reference PG-NNN

## Examples of Good vs. Bad

**Good Future Considerations:**
> At enterprise scale (10K+ documents, multi-tenant), the single Milvus collection design would need partition-per-tenant isolation. The current HNSW index performs well up to ~1M vectors; beyond that, evaluate IVF_FLAT or DiskANN. See ADR-002 for the decision context.

**Bad Future Considerations:**
> We should improve this in the future.

**Good Production Gap Reference:**
> Error handling uses basic try/except with logging. No retry logic, no dead-letter queue, no alerting. See PG-003.

**Bad Production Gap Reference:**
> This could be better.
