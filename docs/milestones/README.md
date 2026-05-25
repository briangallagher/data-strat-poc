# Milestones

Execution plan for the Data Strategy POC v2. Each milestone builds incrementally, with E2E verification before advancing. Drill into each folder for the full plan and checkpoint.

## Status

| Milestone | Status | Summary | Dates |
|-----------|--------|---------|-------|
| [M0: Foundation](M0-foundation/) | **Complete** | Documentation structure, ADRs, tooling, M1 plan | May 22-23 |
| [M1: Ingest Pipeline](M1-ingest-pipeline/) | **Active** (Phase 3 complete) | RayData + Docling + KFP + Milvus with Scenario B metadata | May 23-25 |
| [M2: MLflow](M2-mlflow/) | Planned | Experiment tracking + lineage instrumentation | — |
| [M3: Connectors](M3-connectors/) | Planned | Data source acquisition layer | — |
| [M4: Query](M4-query/) | Planned | OGX Responses API + deterministic RAG | — |
| [M5: Agentic + Hardening](M5-agentic-hardening/) | Planned | Multi-hop retrieval, RBAC, production gap closure | — |

## M1 Progress Detail

M1 follows a three-phase approach: validate Saad's baseline first, then adapt for Scenario B, then scale up.

| Phase | Status | What Was Done | Key Findings |
|-------|--------|---------------|--------------|
| Phase 0: Baseline | **Complete** | Ran Saad's pipeline as-is on our cluster | K8s auth broken in KFP pods (7 iterations to fix); codeflare SDK bypassed; `_VLLM_IMAGE` constant outside KFP scope; Milvus service name mismatch. See [lessons learned](../working/m1-phase0-lessons-learned.md). |
| Phase 1: Scenario B | **Complete** | Added `pipeline_run_id`, `source_document_id`, LOB, doc_type, effective_date to Milvus schema. HNSW index. Metadata flows through RayJob env vars → JSONL → Milvus. | All metadata verified on vectors. Per-document metadata is pipeline-level only (PG-020). See [ADR-002](../architecture/adrs/ADR-002-chunking-milvus-schema.md). |
| Phase 2: Scale Up | **Complete** | 11 PDFs (12MB corpus including 6.9MB FEMA manual), 312 vectors, ~7 min e2e. Idempotency verified. | All documents processed without failure. Deterministic chunking confirmed (same counts on re-run). |
| Phase 3: Pipeline Split | **Complete** | Data-chain-only `rag_ingest_pipeline` created and verified. Removes model deployment steps ([DEC-007](../decisions.md)). | Cleaner pipeline for M1–M3 — fewer params, no GPU needs, faster runs. Full pipeline retained for M4+. |

## Principles

- **Verify Before You Advance** — no milestone signs off without E2E verification at two scales
- **Production-Grade from Day One** — deviations tracked in [production-gaps.md](../production-gaps.md) (20 gaps, 2 mitigated)
- **Document as You Go** — each milestone produces ADRs, technical deep dives, and runbooks alongside the code
- **Pause/Resume Friendly** — each checkpoint has enough context for a cold start

## Execution Pattern

Every milestone follows the same cycle:

```
Plan (plan.md) → Build → Test (small scale) → Fix → Test (full scale) → Document → Checkpoint
```

The plan is written before building starts. The checkpoint is written after verification passes. Both live in the milestone folder.

## Key Decisions

| ADR | Decision | Milestone |
|-----|----------|-----------|
| [ADR-002](../architecture/adrs/ADR-002-chunking-milvus-schema.md) | HNSW index, 10-field schema with lineage + P&C metadata | M1 |
| [ADR-003](../architecture/adrs/ADR-003-ogx-role.md) | Direct Milvus writes for ingest; OGX reserved for query (M4) | M0 |
| [ADR-007](../architecture/adrs/ADR-007-multi-repo-strategy.md) | Start in integration hub; extract when interfaces stabilise | M0 |

## Where Things Live

| Artifact | Location |
|----------|----------|
| Pipeline component code (with fixes) | [briangallagher/pipelines-components:data-strat-poc](https://github.com/briangallagher/pipelines-components/tree/data-strat-poc) |
| Compiled pipeline YAML (ingest only, M1–M3) | `rag_ingest_pipeline.yaml` (repo root) |
| Compiled pipeline YAML (full, M4+) | `rag_multistep_pipeline.yaml` (repo root) |
| Infrastructure manifests | `manifests/` |
| Production gaps | [production-gaps.md](../production-gaps.md) |
| Prior art synthesis | [prior-art-synthesis.md](../working/prior-art-synthesis.md) |
| Phase 0 lessons learned | [m1-phase0-lessons-learned.md](../working/m1-phase0-lessons-learned.md) |
