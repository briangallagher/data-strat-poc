# Collection Lifecycle

## What This Is

A collection is a logical grouping of documents that maps 1:1 to a Milvus vector collection. Collections have an explicit lifecycle — they are created, populated with documents, processed by pipelines, and kept current through re-runs. This doc covers how collections are defined, built, processed, and maintained.

## The Three-Step Lifecycle

| Step | What Happens | Data Movement |
|------|-------------|---------------|
| **1. Register** | Declare a document's existence in the system. Store its identity (`doc_id`), source URL, metadata. | None — this is just metadata. The document stays in the remote system. |
| **2. Build Collection** | Assign registered documents to a collection. Declare intent to query them together. | None — this is just membership assignment in the registry. |
| **3. Pipeline Run (Acquire)** | Execute the ingest workflow. Bytes flow from remote to cluster to Milvus. | Remote → S3 staging → parsed → embedded → Milvus vectors |

Nothing moves until step 3. Registration and collection building are declarations of existence and intent. The pipeline is when data actually enters the cluster.

## Data Flow (Design A: S3 as Staging Surface)

```
Remote Sources                         Cluster (MinIO/S3)                    Vector Store
─────────────────                      ──────────────────                    ────────────
SharePoint / S3 / Confluence           
        │                              
        │ acquire_documents            
        │ (connector fetches)          
        ▼                              
                                       staging/<collection>/
                                         ├── doc1.pdf
                                         ├── doc2.pdf
                                         └── manifest.json
                                              │
                                              │ parse_and_chunk
                                              │ (downloads from S3, Docling parses)
                                              ▼
                                       chunks/<collection>/
                                         ├── doc1.jsonl
                                         └── doc2.jsonl
                                              │
                                              │ ingest_to_milvus
                                              │ (embed + insert)
                                              ▼
                                                                             Milvus: <collection>
                                                                               └── vectors with
                                                                                   per-doc metadata
```

S3 is the sole staging surface. All three pipeline steps read/write via S3. PVC is not used (see PG-039 for future PVC option).

## What a Collection Is

A collection is a named container in the registry that groups documents for a specific retrieval purpose:

| Property | Description |
|----------|-------------|
| `name` | Unique identifier. Also the Milvus collection name (no indirection). |
| `doc_id_prefix` | Prefix for auto-generated doc_ids (e.g., `ug` → `ug-001`, `ug-002`) |
| `description` | Human-readable purpose |
| `created_by` | Who created it: `system`, `human:brian`, `agent:discovery` |

**Many-to-many:** A document can belong to multiple collections. A collection contains multiple documents. The `collection_documents` join table tracks membership, with per-collection ingestion stats (`last_ingested`, `vector_count`).

**M3 collections:**

| Collection | Prefix | Docs | Vectors | Purpose |
|------------|--------|------|---------|---------|
| `underwriting_guidelines` | `ug` | 8 | 27 | State DOI bulletins, carrier guidelines |
| `regulatory_bulletins` | `rb` | 7 | 93 | Regulatory filings and notices |
| `iso_forms` | `if` | 5 | 11 | ISO/ACORD standard forms (mock) |

Two documents (`ug-008` and one other) appear in both `underwriting_guidelines` and `regulatory_bulletins`, validating many-to-many.

## Building a Collection

Collection creation and document assignment is an explicit curation step, performed by a human or agent via the registry UI or API.

**Via UI:**
1. Navigate to `/collections/new`
2. Set name, description, prefix
3. Browse registered documents, assign to collection
4. Or go to an existing collection and assign/remove documents

**Via API/SDK:**
```python
client.create_collection(
    name="iso_forms",
    description="ISO/ACORD standard forms",
    doc_id_prefix="if"
)
client.assign_to_collection("iso_forms", doc_ids=["if-001", "if-002"])
```

**Key point:** Collection membership is a human/agent decision. The system does not auto-assign documents to collections — that requires routing rules (PG-028, not built).

## Pipeline Execution per Collection

Each pipeline run targets a single collection (DEC-008). The multi-collection orchestrator triggers one run per collection:

```
Orchestrator reads config/collections.yaml
    │
    ├── Run pipeline for underwriting_guidelines
    │   └── acquire → parse → ingest → Milvus(underwriting_guidelines)
    │
    ├── Run pipeline for regulatory_bulletins
    │   └── acquire → parse → ingest → Milvus(regulatory_bulletins)
    │
    └── Run pipeline for iso_forms
        └── acquire → parse → ingest → Milvus(iso_forms)
```

Each run:
1. `acquire_documents` queries registry: `GET /documents?collection=<name>&status=active`
2. Fetches all listed documents to S3 staging
3. Writes `manifest.json` with per-doc metadata
4. `parse_and_chunk` reads manifest, processes docs, writes chunks
5. `ingest_to_milvus` embeds and stores in the named Milvus collection
6. Post-ingest: registry updated with `last_ingested`, `last_pipeline_run`, `vector_count` per doc

Each run gets its own `pipeline_run_id`. Marquez records a separate lineage graph per collection run.

## Re-running and Incremental Processing

Re-running a collection pipeline is safe and expected:

- **Current (M3):** Full re-ingest each time (`drop_existing=true` on Milvus collection). Simple, deterministic, correct.
- **Future (PG-006):** Incremental processing. The registry tracks `last_ingested` per document per collection. The pipeline could check `content_hash` to skip unchanged docs.

The registry provides the data needed for incremental processing — `last_ingested` timestamps and `content_hash` — but the pipeline doesn't use them yet.

## Discovery Workflow

**Status:** PG-033 — not built in M3. Essential for production.

Discovery is a separate process that keeps the registry in sync with reality:

```
connector.resolve() → scan source system
    │
    ├── New doc found → register in registry
    ├── Known doc changed (hash mismatch) → update registry, flag for re-ingest
    └── Known doc missing → flag as unavailable
```

Discovery uses `connector.resolve()`, which the ingest pipeline deliberately does NOT call (ADR-010). The two workflows have distinct responsibilities:

| | Discovery | Ingest |
|---|-----------|--------|
| **Purpose** | Keep registry accurate | Process documents into Milvus |
| **Trigger** | Scheduled (cron) or manual | Orchestrator per collection |
| **Connector method** | `resolve()` | `fetch_to_staging()` |
| **Registry interaction** | Writes (register, update, flag) | Reads (list docs) + writes (post-ingest stats) |

## The Registry Can Be Wrong

The registry is a claim about what exists — not a guarantee. Source files can be moved, deleted, or renamed after registration. The ingest pipeline handles this gracefully:

| Scenario | Pipeline Behaviour |
|----------|-------------------|
| File exists at `source_url` | Fetch, process, ingest normally |
| File missing (404) | Skip, log error, flag `status: unavailable` in registry |
| File changed since registration | Fetch current version (hash mismatch detected but not blocked in M3) |
| Registry lists 0 docs for collection | Pipeline runs with empty set, no error |

The next discovery cycle investigates `unavailable` documents and either re-registers them at new URLs or confirms removal.

## Design Decisions

- **ADR-009:** Collection as a living dataset with explicit lifecycle
- **ADR-010:** Registry authoritative for ingest
- **ADR-012:** Three-concern architecture — building collections is a distinct concern from connecting and registering
- **DEC-008:** Three Milvus collections for the POC

## References

| Source | Link |
|--------|------|
| Collections config | `config/collections.yaml` |
| Orchestrator | `scripts/run-multi-collection.py` |
| Registry API | `src/registry/app.py` |
| M3 Plan | `docs/milestones/M3-connectors/plan.md` |
