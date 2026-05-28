# Milestones

Execution plan for the Data Strategy POC v2. Each milestone builds incrementally, with E2E verification before advancing. Drill into each folder for the full plan and checkpoint.

## Status

| Milestone | Status | Summary | Dates |
|-----------|--------|---------|-------|
| [M0: Foundation](M0-foundation/) | **Complete** | Documentation structure, ADRs, tooling, M1 plan | May 22-23 |
| [M1: Ingest Pipeline](M1-ingest-pipeline/) | **Complete** | RayData + Docling + KFP + Milvus with Scenario B metadata | May 23-25 |
| [M2: MLflow + Lineage](M2-mlflow/) | **Complete** | rhoai-lineage library, Marquez, MLflow, OL emission, E2E lineage graph | May 25 |
| [M3: Connectors](M3-connectors/) | **Complete** | Document Registry + acquire_documents + 3-collection ingest (DEC-008) | May 26 |
| [M4: Query](M4-query/) | **Complete** | LangGraph + MCP + MLflow autolog + Chainlit for deterministic RAG (Workflow A); queries `underwriting_guidelines`; full answer provenance via Chain 1; Marquez graph completion; unified provenance portal | May 27 |
| [M5: Agentic + Hardening](M5-agentic-hardening/) | **Active** | OGX Responses API + server-side Tool Runtime for agentic RAG (Workflow B), multi-hop across all 3 collections, MLflow tracing, Registry UI views (Collection Health, App Overview, Impact Analysis, Register Documents), gap closure | May 28+ |

## M1 Progress Detail

M1 follows a three-phase approach: validate Saad's baseline first, then adapt for Scenario B, then scale up.

| Phase | Status | What Was Done | Key Findings |
|-------|--------|---------------|--------------|
| Phase 0: Baseline | **Complete** | Ran Saad's pipeline as-is on our cluster | K8s auth broken in KFP pods (7 iterations to fix); codeflare SDK bypassed; `_VLLM_IMAGE` constant outside KFP scope; Milvus service name mismatch. See [lessons learned](../working/m1-phase0-lessons-learned.md). |
| Phase 1: Scenario B | **Complete** | Added `pipeline_run_id`, `source_document_id`, LOB, doc_type, effective_date to Milvus schema. HNSW index. Metadata flows through RayJob env vars → JSONL → Milvus. | All metadata verified on vectors. Per-document metadata is pipeline-level only (PG-020). See [ADR-002](../architecture/adrs/ADR-002-chunking-milvus-schema.md). |
| Phase 2: Scale Up | **Complete** | 11 PDFs (12MB corpus including 6.9MB FEMA manual), 312 vectors, ~7 min e2e. Idempotency verified. | All documents processed without failure. Deterministic chunking confirmed (same counts on re-run). |
| Phase 3: Pipeline Split | **Complete** | Data-chain-only `rag_ingest_pipeline` created and verified. Removes model deployment steps ([DEC-007](../decisions.md)). | Cleaner pipeline for M1–M3 — fewer params, no GPU needs, faster runs. Full pipeline retained for M4+. |

## M2 Progress Detail

M2 adds pipeline observability and data lineage via `rhoai-lineage` library, Marquez, and MLflow.

| Phase | Status | What Was Done | Key Findings |
|-------|--------|---------------|--------------|
| Phase 0: Seed rhoai-lineage | **Complete** | Forked ET team's openlineage-oai + sdk into standalone package. Naming helpers, Marquez client, bridge support. | Clean separation from ET concerns; installable via git URL. |
| Phase 1: Deploy Marquez + infra | **Complete** | PostgreSQL + Marquez API + Web UI deployed. DSP namespace injection via downward API. | fsGroup needed for PG PVC; MARQUEZ_CONFIG env var required (not inline); WEB_PORT not PORT for Web UI. |
| Phase 2: Deploy MLflow + config | **Complete** | MLflow already available via RHOAI Operator. ConfigMap centralises lineage config. Bridge OFF by default. | MLflow tracking from KFP pods needs SA token + workspace header (PG-024). |
| Phase 3: Add OL emission | **Complete** | parse_and_chunk and ingest_to_milvus emit START/COMPLETE events. Pipeline run SUCCEEDED. | Full lineage graph verified: PVC → parse → S3 → ingest → Milvus. Custom facets present. |
| Phase 4: E2E verification + docs | **Complete** | ADR-004, technical deep dives, user journey, production gaps documented. All repos tagged. | MLflow tracking not working (PG-024). pipeline_run_id not in Marquez facets (PG-025). 5 new PGs added. |

## Principles

- **Verify Before You Advance** — no milestone signs off without E2E verification at two scales
- **Production-Grade from Day One** — deviations tracked in [production-gaps.md](../production-gaps.md) (53 gaps, 10 closed/mitigated)
- **Document as You Go** — each milestone produces ADRs, technical deep dives, and runbooks alongside the code
- **Pause/Resume Friendly** — each checkpoint has enough context for a cold start

## Execution Pattern

Every milestone follows the same cycle:

```
Plan (plan.md) → Build → Test (small scale) → Fix → Test (full scale) → Document → Checkpoint
```

The plan is written before building starts. The checkpoint is written after verification passes. Both live in the milestone folder.

## Key Decisions

| ADR/DEC | Decision | Milestone |
|---------|----------|-----------|
| [ADR-002](../architecture/adrs/ADR-002-chunking-milvus-schema.md) | HNSW index, 10-field schema with lineage + P&C metadata | M1 |
| [ADR-003](../architecture/adrs/ADR-003-ogx-role.md) | Direct Milvus writes for ingest; OGX reserved for query path (amended by DEC-010) | M0 |
| [ADR-004](../architecture/adrs/ADR-004-lineage-architecture.md) | Fork-and-adapt rhoai-lineage; bridge OFF by default; operator deferred | M2 |
| [ADR-007](../architecture/adrs/ADR-007-multi-repo-strategy.md) | Start in integration hub; extract when interfaces stabilise | M0 |
| [DEC-009](../decisions.md) | Two-layer lineage: Marquez for ingest, MLflow traces for query | M4 |
| [DEC-010](../decisions.md) | LangGraph + MCP + MLflow autolog for M4; OGX reserved for M5 agentic RAG | M4 |
| [DEC-011](../decisions.md) | Registry UI as unified provenance portal | M4 |

## Where Things Live

| Artifact | Location |
|----------|----------|
| Pipeline component code (with fixes) | [briangallagher/pipelines-components:data-strat-poc](https://github.com/briangallagher/pipelines-components/tree/data-strat-poc) |
| rhoai-lineage library | [briangallagher/rhoai-lineage](https://github.com/briangallagher/rhoai-lineage) (`~/dev/git-repos/rhoai-lineage`) |
| Compiled pipeline YAML (ingest only, M1–M3) | `rag_ingest_pipeline.yaml` (repo root) |
| Compiled pipeline YAML (full, M4+) | `rag_multistep_pipeline.yaml` (repo root) |
| Infrastructure manifests | `manifests/` |
| Marquez manifests | `manifests/marquez/` |
| Production gaps | [production-gaps.md](../production-gaps.md) |
| Prior art synthesis | [prior-art-synthesis.md](../working/prior-art-synthesis.md) |
| Phase 0 lessons learned | [m1-phase0-lessons-learned.md](../working/m1-phase0-lessons-learned.md) |
| Query service (MCP + LangGraph + Chainlit) | `src/query/` |
| Registry provenance endpoints | `src/registry/provenance.py` |
| Registry UI (with provenance portal) | `src/registry-ui/` |
| Model serving manifests | `manifests/model-serving/` |
| Assessment docs (Scenario B, feedback, ET questions) | `docs/assessment/` |
| Marquez Web UI | https://marquez-web-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| Marquez API | https://marquez-data-strat-poc.apps.dev.aip-ft.rh-ods.com |
| MLflow UI | https://mlflow-ui-redhat-ods-applications.apps.dev.aip-ft.rh-ods.com |
