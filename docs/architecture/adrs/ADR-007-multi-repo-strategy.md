# ADR-007: Multi-Repo Strategy

**Date:** 2026-05-23
**Status:** Decided
**Milestone:** M0

## Context

The prior POC was a single monorepo containing manifests, scripts, custom images, pipeline components, a connector package, a registry API, and a Data Hub UI. This made rapid prototyping easy but created a tightly coupled codebase where changes to one component (e.g., the connector library) required touching the POC repo.

This project aims to be production-shaped. The question is: what warrants its own repository, PyPI package, or container image versus living in the integration hub?

Inputs:
- the Ray team's PR #53 contributes pipeline components to `opendatahub-io/pipelines-components` — a shared repo for reusable KFP components
- The ET team's `lineage-demo-pipeline` keeps everything in one repo but ships in-repo libraries (`openlineage-oai`, `openlineage-sdk`, `dataset-registry`) as separate Python packages
- The prior POC's `connectors/` package (`dsp-connectors`) was pip-installable from MinIO wheel store but lived in the POC repo

## Decision

**Start with everything in `data-strat-poc` and extract when the component proves its boundaries.**

Specifically:

| Component | Location | Extraction Trigger | Target When Extracted |
|-----------|---------------|-------------------|----------------------|
| Manifests, e2e tests, demo scripts | `data-strat-poc` (permanent) | Never — this is the integration hub | — |
| KFP pipeline definitions | `data-strat-poc/pipelines/` | If adopted by other teams | Contribute to `opendatahub-io/pipelines-components` |
| Pipeline component code | `data-strat-poc/pipelines/components/` | If reused outside this project | PR to `opendatahub-io/pipelines-components` (the Ray team's pattern) |
| `rhoai-lineage` library | `data-strat-poc/src/rhoai_lineage/` | After M2 (proven API surface) | Dedicated repo + PyPI package |
| Connector package | `data-strat-poc/src/connectors/` | After M3 (proven connector interface) | Dedicated repo + PyPI package |
| Lineage operator | Not started in current scope | If built (M5+ stretch) | Dedicated repo (Go, operator-sdk) |
| Custom container images | `data-strat-poc/images/` | When image has its own CI/release cycle | Dedicated repo per image |

**The rule:** a component stays in the integration hub until it has:
1. A **stable interface** (API, CLI, or manifest contract) that other consumers depend on
2. An **independent release cadence** (needs versioning separate from the POC)
3. A **different tech stack** (Go operator in a Python-dominated repo)

Until all three criteria are met, extraction adds overhead without value.

## Alternatives Considered

| Option | Pros | Cons | Why Not |
|--------|------|------|---------|
| Multi-repo from day one | Clean separation, independent CI | Overhead of managing 4-5 repos before APIs are stable; premature abstraction | Too early — APIs will change during M1-M3 |
| Monorepo permanently | Simplest to manage; single CI | Coupling; hard for other teams to adopt individual components | Doesn't match production-shaped goal |
| Fork the Ray team's components | Builds on proven code | Creates divergence from upstream pipelines-components | Better to contribute back than fork |

## Consequences

- M1-M3 development is fast — single repo, single CI, no cross-repo coordination
- Component boundaries crystallise through usage before extraction
- When extraction happens, it's based on proven interfaces rather than speculative design
- Risk: components become coupled to the integration hub and are harder to extract later
- Mitigation: maintain clean package boundaries (`src/rhoai_lineage/`, `src/connectors/`) with no imports across packages from day one

## Future Considerations

- **Lineage library** is the most likely first extraction candidate — it's designed to be reusable across all RHOAI pipelines (see `lineage-library-design.md` from work-knowledge)
- **Connector package** follows if the connector interface stabilises and other teams adopt it
- **Pipeline components** should be contributed to `opendatahub-io/pipelines-components` rather than maintained in a separate personal repo — aligns with the Ray team's pattern and gets community review
- If the project spawns a real lineage operator, it must be a separate Go repo from the start (criterion #3: different tech stack)

## References

| Source | Link |
|--------|------|
| the Ray team's pipeline components (upstream pattern) | [pipelines-components #53](https://github.com/opendatahub-io/pipelines-components/pull/53) |
| ET team in-repo libraries | [lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline) |
| Prior POC connector package | `data-strategy-poc/connectors/` + `pyproject.toml` |
| Lineage library design | work-knowledge `projects/data-strategy/docs/poc/lineage/lineage-library-design.md` |
