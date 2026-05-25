# ADR-003: OGX Role in the System

**Date:** 2026-05-23
**Status:** Decided
**Milestone:** M0 (unblocks M1)

## Context

OGX has two potential roles in the Scenario B architecture:

1. **Ingest path** — OGX Vector I/O API accepts raw text, handles embedding and Milvus writes in a single API call. Used in v1.
2. **Query path** — OGX Responses API handles RAG retrieval (Milvus similarity search) and LLM generation with citations. This is OGX's strongest differentiator.

v1 used OGX for both. Saad's PR #53 (merged, 4K+ lines, reviewed by 3 engineers) bypasses OGX entirely for ingest — it writes directly to Milvus using local `sentence-transformers` or a vLLM `/v1/embeddings` endpoint. OGX is not even a dependency in his pipeline.

The question: should v2 use OGX for the ingest path, the query path, both, or neither?

### OGX Vector I/O (Ingest Path) — Pros

- Single API call for embed + insert (less pipeline code)
- Consistent embedding model management through OGX
- OGX handles Milvus connection pooling
- v1 proved it works

### OGX Vector I/O (Ingest Path) — Cons

- **Opaque**: no control over batching, retry logic, or error handling at the embedding/insert level
- **Coupling**: pipeline depends on OGX being deployed and configured before ingest can run
- **Not what Saad's team ships**: the merged pipeline components don't use OGX; adopting their pattern means diverging from v1 but aligning with the upstream community
- **Dev Preview**: OGX Vector I/O is not GA; API may change
- **Single point of failure**: if OGX is down, the entire ingest pipeline stops (embedding AND storage)
- **No batch embedding control**: can't tune batch sizes for GPU memory optimization
- **Harder to debug**: embedding failures and Milvus write failures are conflated behind one API call

### Direct Milvus Writes (Saad's Pattern) — Pros

- Full control over embedding (model choice, batch size, retry)
- Full control over Milvus writes (error handling, idempotency, upsert)
- Decoupled: pipeline runs without OGX dependency for ingest
- Aligns with the merged upstream components (community support, review)
- Clearer debugging: embedding failures and write failures are separate steps
- Supports dual embedding modes (local for dev, vLLM endpoint for production)

### Direct Milvus Writes — Cons

- More pipeline code (separate embed step + insert step)
- Must manage embedding model deployment separately (KServe InferenceService)
- Must manage Milvus connection directly (pymilvus)

## Decision

**Use direct Milvus writes for the ingest path (Saad's pattern). Reserve OGX for the query path (M4).**

Specifically:
- **M1 (Ingest):** Adopt Saad's `parse_and_chunk` → S3 → `ingest_to_milvus` pattern. Embedding via vLLM endpoint (KServe InferenceService) or local sentence-transformers as fallback. Direct pymilvus writes to Milvus.
- **M4 (Query):** Use OGX Responses API for RAG retrieval and generation. This is where OGX's value is clearest — it handles the retrieval → LLM → cited answer flow with custom tools for Milvus search.
- **OGX Vector I/O is not used.** If Ana's team or the OGX team later GA the Vector I/O API with batch control and error handling, re-evaluate.

## Alternatives Considered

| Option | Pros | Cons | Why Not |
|--------|------|------|---------|
| **A: OGX for both (v1 pattern)** | Simpler pipeline; proven in v1 | Opaque, coupled, Dev Preview, diverges from Saad's merged code | Control and debuggability matter for production-grade |
| **B: Direct writes for both (no OGX)** | Maximum control, no OGX dependency at all | Loses OGX's strongest value (Responses API for RAG) | OGX Responses API is the right abstraction for query |
| **C: OGX for embedding only, direct Milvus writes** | OGX handles embedding model; we handle writes | Still coupled to OGX for ingest; not what Saad ships | Half-measure; doesn't solve the core coupling issue |
| **D: Direct writes for ingest, OGX for query (chosen)** | Production-grade ingest control + OGX's best feature for query | Two different embedding paths (ingest vs query must match) | Alignment risk mitigated by using same embedding model for both |

## Consequences

- M1 can start without OGX deployed. Only need: Milvus, KubeRay, DSPA, embedding InferenceService.
- Must ensure the embedding model used in the ingest pipeline (vLLM) matches what OGX uses at query time in M4. If they differ, retrieval quality degrades.
- Pipeline code is more verbose (explicit embed + insert steps) but more debuggable and testable.
- Aligns with Saad's components — potential to contribute improvements back to `pipelines-components`.
- OGX deployment deferred to M4, reducing M1 complexity.

## Future Considerations

- If OGX Vector I/O reaches GA with batch control, retry policies, and pluggable embedding models, re-evaluate for ingest. The benefit of a single API for embed+insert is real — the current implementation just isn't production-ready.
- If the project needs to support non-OGX query paths (e.g., direct Milvus search without OGX), the ingest path is already decoupled from OGX and would still work.
- Ana's Scenario B spec assumes OGX for both ingest and query. v2 deviates on ingest for production-grade reasons but should document this clearly when presenting to stakeholders.

## References

| Source | Link |
|--------|------|
| v1 OGX usage (serial ingest) | `data-strategy-poc/scripts/ingest-corpus.py` |
| v1 OGX usage (Ray ingest) | `data-strategy-poc/scripts/ray-ingest.py` |
| Saad's ingest components (no OGX) | [pipelines-components #53](https://github.com/opendatahub-io/pipelines-components/pull/53) |
| v1 DEC-002 (OGX in MVP) | `data-strategy-poc/docs/decisions.md` |
| OGX knowledge doc | work-knowledge `knowledge/rhoai/ogx/ogx.md` |
| Prior-art synthesis | `docs/working/prior-art-synthesis.md` |
