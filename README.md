# Data Strategy POC

Production-shaped implementation of **Scenario B** (P&C Underwriting Knowledge Assistant) from the [RHOAI Data Strategy](https://github.com/abiazett/DataStrategy). Synthesises learnings from [the Ray team's pipeline components](https://github.com/opendatahub-io/pipelines-components/pull/53) and the [ET lineage demo](https://github.com/rh-waterford-et/lineage-demo-pipeline).

## What This Is

An integration hub that brings together dedicated components for a RAG knowledge assistant on RHOAI:

- **RayData + Docling** — distributed document parsing and chunking
- **Milvus** — vector storage with partition-by-LOB design
- **KFP Pipelines** — orchestrated ingest flow as reusable components
- **OGX** — Responses API for RAG retrieval and generation
- **MLflow** — experiment tracking and query-time tracing
- **OpenLineage + Marquez** — end-to-end lineage (source → pipeline → vector → query → answer)
- **Connectors** — data source acquisition (S3, Confluence, SharePoint)

Where a component warrants its own repo, PyPI package, or container image, it is split out. This repo is the integration point: manifests, e2e tests, demo scripts, and documentation.

## Key Principles

- **Production-grade from day one** — enterprise standard is the default; deviations tracked in [`docs/production-gaps.md`](docs/production-gaps.md)
- **Document, test, verify at every milestone** — no milestone signs off without E2E verification
- **Pause/resume friendly** — milestone checkpoints contain full context for resuming from cold
- **Lineage-first** — lineage woven through every milestone, not bolted on at the end

## Status

| Milestone | Status | Summary |
|-----------|--------|---------|
| M0: Foundation | **Complete** | Documentation structure, ADRs, prerequisites, tooling |
| M1: Ingest Pipeline | **Complete** | RayData + Docling + KFP + Milvus (single collection) |
| M2: MLflow + Lineage | **Complete** | Experiment tracking + OpenLineage/Marquez instrumentation |
| M3: Connectors + Multi-Collection | **Complete** | Document Registry, multi-collection ingest, source acquisition |
| M4: Query (Deterministic) | **Complete** | LangGraph + MCP + MLflow tracing + Chainlit UI |
| M5: Agentic + Hardening | **Complete** | OGX Responses API, multi-hop RAG, provenance portal |

## Documentation

| Tier | Location | Purpose |
|------|----------|---------|
| Architecture | [`docs/architecture/`](docs/architecture/) | System overview, ADRs |
| Technical | [`docs/technical/`](docs/technical/) | Per-component deep dives |
| Functional | [`docs/functional/`](docs/functional/) | Use cases, requirements |
| User Experience | [`docs/user-experience/`](docs/user-experience/) | Personas, journeys, workflows |
| Operations | [`docs/operations/`](docs/operations/) | Prerequisites, getting started, runbooks |
| Milestones | [`docs/milestones/`](docs/milestones/) | Plans, checkpoints, verification |
| Decisions | [`docs/decisions.md`](docs/decisions.md) | High-level decision log |
| Production Gaps | [`docs/production-gaps.md`](docs/production-gaps.md) | Enterprise-grade gap register |
| Doc Standards | [`docs/doc-standards.md`](docs/doc-standards.md) | Templates and conventions |

## Quick Start

See [`docs/operations/prerequisites.md`](docs/operations/prerequisites.md) for cluster requirements, then [`docs/operations/getting-started.md`](docs/operations/getting-started.md) for deployment steps.

## Context

This project implements [Scenario B](https://github.com/abiazett/DataStrategy/blob/main/data-strategy-proposal/scenarios/scenario-b-underwriting-knowledge/scenario-b-underwriting-knowledge.md) from the RHOAI five-pillar data strategy. It validates Pillars 1-5 for an unstructured document / RAG workload without Feast or feature engineering.

### Prior Art

| Source | What It Provides |
|--------|------------------|
| [DataStrategy repo](https://github.com/abiazett/DataStrategy) | Five-pillar strategy, Scenario B spec, lineage/catalog research |
| [pipelines-components #53](https://github.com/opendatahub-io/pipelines-components/pull/53) | 5 reusable KFP components (Ray+Docling+Milvus+vLLM) |
| [red-hat-ai-examples #78](https://github.com/red-hat-data-services/red-hat-ai-examples/pull/78) | RAGSetup library + 3 notebooks |
| [lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline) | Lineage operator, OpenLineage adapters, dataset registry |
| [projects/data-strategy](https://github.com/briangallagher/work-knowledge/tree/main/projects/data-strategy) | Lineage library design, scenarios, integration patterns |
