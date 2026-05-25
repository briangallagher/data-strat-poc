# ADR-002: Chunking Strategy and Milvus Collection Design

**Date:** 2026-05-25
**Status:** Decided
**Milestone:** M1

## Context

The ingest pipeline parses PDF documents with Docling and stores vector embeddings in Milvus for retrieval. Two design decisions are tightly coupled:

1. **How documents are chunked** — determines the granularity and quality of retrieval results
2. **What the Milvus collection schema looks like** — determines what metadata is stored per vector and how it can be queried

Saad's baseline (PR #53) uses a minimal schema: `id`, `source_file`, `chunk_index`, `text`, `embedding` with an IVF_FLAT index. This is sufficient for a generic RAG demo but lacks the metadata needed for Scenario B's lineage, regulatory compliance, and multi-collection architecture.

v1 POC used OGX Vector I/O which abstracted the schema — we had less control over what was stored. Moving to direct Milvus writes (ADR-003) gives us full control.

### Requirements from Scenario B

- **Lineage traceability (Chain 1):** Given an AI-generated answer, trace backward through retrieved chunks → pipeline run → source documents. Requires `pipeline_run_id` on every vector.
- **Document identity:** Stable identifier per source document, independent of pipeline runs or filenames. Enables impact analysis (Chain 2): "which chunks came from this document?"
- **P&C metadata:** Line of business, document type, effective date. Enables filtered retrieval (e.g., "only commercial property guidelines that are currently effective") and partitioned collections.
- **Multi-collection architecture:** Scenario B specifies three collections: `underwriting_guidelines`, `iso_forms`, `regulatory_bulletins`. Each collection has the same schema but different content.

## Decision

### Chunking Strategy

**Use Docling's HybridChunker** with these settings:
- `max_tokens=256` — chunk size limit (configurable per pipeline run)
- Tokenizer: `ibm-granite/granite-embedding-125m-english` — matches the embedding model
- Structure-aware: Docling preserves document structure (sections, tables, paragraphs) and HybridChunker respects these boundaries

This is Saad's default chunking approach, unchanged. The chunking itself works well — Docling's layout detection (97.9% table accuracy per the DataStrategy research) combined with HybridChunker produces clean, structure-aware chunks.

**What we did not change:** chunk overlap, chunk merging, or table-specific chunking strategies. These are optimisation targets for M4 (query quality) or M5 (hardening), not M1.

### Milvus Collection Schema

```
Collection: underwriting_guidelines (or iso_forms, regulatory_bulletins)

Fields:
  id                  INT64       primary key, auto-generated
  source_file         VARCHAR(512)  original filename (e.g., "ca-doi-bulletin-2024-7.pdf")
  source_document_id  VARCHAR(256)  stable document identifier (filename stem, lowercase, kebab-case)
  pipeline_run_id     VARCHAR(64)   UUID linking to the KFP pipeline run — enables lineage bridging
  chunk_index         INT64         position of chunk within the source document
  text                VARCHAR(32768) raw chunk text (for retrieval display and re-embedding)
  lob                 VARCHAR(128)  line of business (e.g., "commercial_property", "workers_comp")
  doc_type            VARCHAR(128)  document type (e.g., "regulatory_bulletin", "iso_form")
  effective_date      VARCHAR(32)   document effective date (ISO 8601)
  embedding           FLOAT_VECTOR(768)  dense vector from Granite Embedding 125M
```

### Index

**HNSW** (Hierarchical Navigable Small World) with:
- `M=16` — connections per node (balances recall vs memory)
- `efConstruction=256` — build-time quality (higher = better index, slower build)
- `metric_type=COSINE` — cosine similarity (normalised embeddings)

Changed from Saad's IVF_FLAT. HNSW is better for our use case:
- No training step required (IVF_FLAT needs `nlist` tuning based on data size)
- Better recall at low latency for collections under 1M vectors
- Supports incremental inserts without re-indexing (IVF_FLAT degrades with appends)

### Metadata Flow

```
Pipeline parameters (doc_lob, doc_type, doc_effective_date, pipeline_run_id)
    │
    ▼
parse_and_chunk (RayJob env vars → Docling workers → JSONL output)
    │  Each chunk: {source_file, source_document_id, chunk_index, text, lob, doc_type, effective_date}
    ▼
S3 (JSONL files per source document)
    │
    ▼
ingest_to_milvus (reads JSONL, adds pipeline_run_id, embeds, inserts)
    │  Each vector: all JSONL fields + pipeline_run_id + embedding
    ▼
Milvus collection
```

### Collection Naming

Collections follow the Scenario B document type naming:

| Collection | Content | LOB Partitioning |
|------------|---------|-----------------|
| `underwriting_guidelines` | Internal company underwriting guidelines | By LOB (commercial_property, workers_comp, etc.) |
| `iso_forms` | ISO/ACORD standard forms | By form series |
| `regulatory_bulletins` | State DOI bulletins, NAIC guidance | By jurisdiction |

For M1, only `underwriting_guidelines` is created. Others are added when relevant documents are available.

## Alternatives Considered

| Option | Pros | Cons | Why Not |
|--------|------|------|---------|
| Saad's minimal schema (source_file, chunk_index, text) | Simple, proven | No lineage, no metadata filtering, no multi-collection | Doesn't meet Scenario B requirements |
| Single collection with partition key on doc_type | Fewer collections to manage | Milvus partition keys have cardinality limits; mixing doc types complicates schema | Separate collections are cleaner for different document types |
| Store metadata in a separate registry (not in Milvus) | Keeps vectors lean | Requires join at query time; `pipeline_run_id` must be on the vector for lineage bridging | Performance and complexity cost outweighs storage savings |
| IVF_FLAT index (Saad's default) | Fast builds, good for large collections | Requires training step, degrades with incremental inserts | HNSW is better for our collection sizes (<1M vectors) |
| HNSW with higher M (32) | Better recall | ~2x memory per vector | M=16 is sufficient for our embedding dimension (768) |

## Consequences

- Every vector carries enough metadata for Chain 1 (Answer Provenance) lineage without external lookups
- Metadata filtering at query time is possible (`lob="commercial_property" AND effective_date >= "2024-01-01"`)
- Collection creation is idempotent (drop_existing=true recreates; drop_existing=false appends)
- Schema migration requires collection drop + re-ingest (Milvus doesn't support ALTER TABLE)
- `pipeline_run_id` enables Marquez bridging in M2 without changing the schema
- `source_document_id` enables document impact analysis (Chain 2) in future milestones

**Current limitation (PG-020):** All documents in a single pipeline run receive the same `lob`, `doc_type`, and `effective_date` from pipeline parameters. Per-document metadata requires a manifest file approach (v1 pattern). This is acceptable for M1 verification but needs refinement for M3 (connectors) or Phase 2 (full corpus).

## Future Considerations

- **Per-document metadata from manifest:** Replace pipeline-level env vars with a JSON manifest file on the PVC or in S3, keyed by filename. Each document gets its own LOB, doc_type, effective_date. The `parse_and_chunk` component reads the manifest instead of env vars.
- **Chunk deduplication:** Add `chunk_hash` (SHA-256 of text) for idempotent upserts. Currently, re-running with `drop_existing=false` creates duplicates.
- **Hybrid search:** Add a sparse vector field (BM25) alongside the dense embedding for hybrid retrieval. Milvus 2.4+ supports this. Tracked as PG-007.
- **Partition key:** If a single collection grows beyond ~1M vectors, evaluate Milvus partition keys on `lob` or `doc_type` for query performance.
- **Schema versioning:** No mechanism to version the collection schema. If fields change, must drop and re-ingest. Consider tracking schema version in collection description or a metadata table.
- **Embedding model migration:** Changing the embedding model (e.g., from 768-dim Granite to 1024-dim) requires full re-embedding. The `embedding_dim` parameter on the collection prevents dimension mismatches.

## References

| Source | Link |
|--------|------|
| Saad's ingest component (baseline schema) | [pipelines-components PR #53](https://github.com/opendatahub-io/pipelines-components/pull/53) |
| v1 POC collection design | `data-strategy-poc/docs/architecture.md` |
| Scenario B document types | [DataStrategy scenario-b-underwriting-knowledge.md](https://github.com/abiazett/DataStrategy/blob/main/data-strategy-proposal/scenarios/scenario-b-underwriting-knowledge/scenario-b-underwriting-knowledge.md) |
| Milvus HNSW index docs | [milvus.io/docs/index.md](https://milvus.io/docs/index.md) |
| Lineage scenarios (Chain 1, Chain 2) | work-knowledge `projects/data-strategy/docs/poc/lineage/lineage-scenarios.md` |
| DEC-014 naming conventions (v1) | `data-strategy-poc/docs/decisions.md` |
| PG-007 (hybrid search gap) | `docs/production-gaps.md` |
