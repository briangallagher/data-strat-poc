# Document Registry

## What This Is

The Document Registry is a FastAPI service backed by PostgreSQL that provides stable canonical identity for every document in the system. It stores metadata, tracks collection membership, and derives OpenLineage identity — making it the single source of truth the ingest pipeline consults before processing (ADR-010). Starting in M4, the registry also serves as a unified provenance portal — federating MLflow traces, Marquez lineage data, and external observability links into a single UI. It includes a Python SDK for programmatic access and a PatternFly UI for browsing, collection management, and provenance exploration.

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  PatternFly UI   │     │  Registry SDK    │     │  acquire_docs    │
│  (React SPA)     │     │  (Python client) │     │  (KFP component) │
└────────┬─────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │ HTTP
                           ┌──────▼──────┐
                           │  FastAPI    │
                           │  :8080      │
                           └──┬────┬───┬─┘
                              │    │   │
                 ┌────────────┘    │   └────────────┐
                 ▼                 ▼                 ▼
           ┌──────────┐     ┌──────────┐     ┌──────────┐
           │PostgreSQL│     │  MLflow   │     │ Marquez  │
           │doc_regist│     │ (traces)  │     │(lineage) │
           └──────────┘     └──────────┘     └──────────┘
```

- **FastAPI backend** — `src/registry/` (app.py, models.py, db.py, enrichment.py, lineage.py)
- **PostgreSQL** — shares the Marquez PG instance; separate `doc_registry` database
- **Python SDK** — `registry-sdk/` package, installable via `pip install -e registry-sdk/`
- **PatternFly 6 UI** — `src/registry-ui/`, served via nginx, proxied to API

## Data Model

### documents

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Internal PK |
| `doc_id` | VARCHAR UNIQUE | Stable human-friendly ID (`ug-005`, `rb-012`) |
| `name` | VARCHAR | Human-readable title |
| `source_system` | VARCHAR | Origin: `s3`, `confluence`, `sharepoint`, etc. |
| `source_url` | VARCHAR | Canonical external URL (S3 key, Confluence page URL) |
| `document_type` | VARCHAR | `bulletin`, `guideline`, `form`, `manual` |
| `line_of_business` | VARCHAR | `commercial_property`, `flood`, `all_p_and_c` |
| `jurisdiction` | VARCHAR | `CA`, `NY`, `national`, `federal` |
| `effective_date` | DATE | When this version became effective |
| `status` | VARCHAR | `active`, `superseded`, `archived`, `unavailable` |
| `superseded_by` | VARCHAR | `doc_id` of replacement (null if current) |
| `ol_namespace` | VARCHAR | Derived OL namespace for Marquez |
| `ol_name` | VARCHAR | Derived OL name (= `doc_id`) |
| `content_hash` | VARCHAR | SHA-256 (auto-enriched) |
| `file_format` | VARCHAR | `pdf`, `docx`, `html` (auto-detected) |
| `file_size_bytes` | INTEGER | Auto-enriched from file |
| `page_count` | INTEGER | Auto-enriched from PDF metadata |

### collections

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Internal PK |
| `name` | VARCHAR UNIQUE | Also the Milvus collection name |
| `description` | VARCHAR | Human-readable purpose |
| `doc_id_prefix` | VARCHAR | Prefix for auto-generated doc_ids (`ug`, `rb`, `if`) |
| `next_sequence` | INTEGER | Next sequence number for auto-generation |
| `created_by` | VARCHAR | Free-text: `system`, `human:brian`, `agent:discovery` |

### collection_documents

| Column | Type | Purpose |
|--------|------|---------|
| `collection_id` | UUID FK | References `collections.id` |
| `document_id` | UUID FK | References `documents.id` |
| `added_by` | VARCHAR | Who assigned it |
| `last_ingested` | TIMESTAMPTZ | Last pipeline run for this doc in this collection |
| `last_pipeline_run` | VARCHAR | `pipeline_run_id` of last ingest |
| `vector_count` | INTEGER | Chunks in Milvus for this doc in this collection |

## API Reference

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/documents` | Register a new document (triggers auto-enrichment) |
| `POST` | `/api/v1/documents/resolve` | Lookup by `source_url`; returns existing or creates new |
| `GET` | `/api/v1/documents/{doc_id}` | Get by stable doc_id |
| `GET` | `/api/v1/documents` | List (filter by `collection`, `status`, `source_system`) |
| `PATCH` | `/api/v1/documents/{doc_id}` | Update metadata, status, post-ingest stats |
| `POST` | `/api/v1/documents/{doc_id}/supersede` | Mark superseded, link to replacement |
| `GET` | `/api/v1/documents/{doc_id}/lineage` | Query Marquez for pipelines/consumers |
| `POST` | `/api/v1/documents/bulk` | Seed from manifest.json (with auto-enrichment) |
| `GET` | `/api/v1/collections` | List collections with doc counts |
| `POST` | `/api/v1/collections` | Create a new collection |
| `GET` | `/api/v1/collections/{name}` | Get collection detail with members |
| `POST` | `/api/v1/collections/{name}/assign` | Assign documents to a collection |
| `DELETE` | `/api/v1/collections/{name}/documents/{doc_id}` | Remove a document from a collection |
| `GET` | `/api/v1/provenance/traces` | List MLflow traces across experiments |
| `GET` | `/api/v1/provenance/traces/{trace_id}` | Detailed trace with spans |
| `GET` | `/api/v1/provenance/apps` | List applications (from MLflow tags + Marquez) |
| `GET` | `/api/v1/provenance/collection/{name}/health` | Collection health metrics |
| `GET` | `/api/v1/provenance/links` | External observability URLs (Marquez, MLflow) |

## Identity Resolution

The `/resolve` endpoint is the primary entry point for document registration:

1. Caller provides `source_url` + `source_system`
2. Registry checks for an existing active document with that `source_url`
3. **If found:** returns the existing document (idempotent)
4. **If not found:** creates a new document with auto-generated `doc_id`

### doc_id Auto-Generation

The `doc_id` is generated from the collection's `doc_id_prefix` and a monotonic sequence:

```
collection.doc_id_prefix + "-" + zero_padded(collection.next_sequence)
```

Example: collection `underwriting_guidelines` has prefix `ug` → first doc gets `ug-001`, next gets `ug-002`.

The sequence is per-collection, incremented atomically on each new registration via that collection's `/resolve` path.

## Auto-Enrichment

When a document is registered (via `/documents`, `/resolve`, or `/bulk`) and the file is accessible in S3 staging, the registry computes:

| Field | Source | Method |
|-------|--------|--------|
| `content_hash` | File content | SHA-256 digest |
| `file_format` | File extension + MIME | `python-magic` detection |
| `file_size_bytes` | File stat | `os.path.getsize` equivalent via S3 HEAD |
| `page_count` | PDF metadata | PyPDF2 page count (PDF only) |

Auto-enrichment is best-effort: if the file is not in staging, these fields remain null and are populated on the next pipeline run.

## OL Identity Derivation

Each document gets a deterministic OpenLineage identity for use in Marquez:

```
ol_namespace = "registry://<source_system>"
ol_name      = "<doc_id>"
```

Example: `ug-005` from source system `s3` → namespace `registry://s3`, name `ug-005`.

The `acquire_documents` pipeline component reads these fields from the registry and uses them when emitting per-doc `InputDataset` events to Marquez (ADR-011). The registry itself does NOT emit to Marquez — only the pipeline does.

## SDK Usage

```python
from registry_sdk import RegistryClient

client = RegistryClient(base_url="http://doc-registry:8080")

# Resolve (idempotent lookup-or-create)
doc = client.resolve(
    source_url="s3://corpus/underwriting_guidelines/ca-doi-2025-3.pdf",
    source_system="s3"
)
print(doc.doc_id)  # "ug-005"

# List active docs in a collection
docs = client.list_documents(collection="regulatory_bulletins", status="active")

# Update post-ingest stats
client.update_ingestion(
    "ug-005",
    collection="underwriting_guidelines",
    pipeline_run_id=run_id,
    vector_count=27
)

# Create and populate a collection
client.create_collection(
    name="iso_forms",
    description="ISO/ACORD standard forms",
    doc_id_prefix="if"
)
client.assign_to_collection("iso_forms", doc_ids=["if-001", "if-002", "if-003"])
```

## Deployment

- **Pod:** Single FastAPI pod + nginx sidecar for UI static files
- **PostgreSQL:** Shared with Marquez (`marquez-postgres:5432`), separate `doc_registry` database
- **Init container:** `git-clone` with sparse checkout — pulls only `src/registry/` and `registry-sdk/` to avoid cloning the full repo (corpus data, docs)
- **Manifests:** `manifests/registry/` (Deployment, Service, Route, PG init Job)
- **Route:** `doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com`

## Provenance Portal (M4/M5)

The registry aggregates provenance data from three sources: its own PostgreSQL database (document metadata, collections), MLflow (execution traces), and Marquez (dataset/job lineage). This federation gives users a single place to understand what happened to a document — from registration through ingest, chunking, embedding, and downstream consumption.

### Application Discovery

Applications are discovered by merging two signals:

- **MLflow trace tags** — traces tagged with `app_name` and `workflow` identify which application produced the trace
- **Marquez APPLICATION jobs** — jobs of type `APPLICATION` in Marquez represent deployed consumers

The registry merges these into a unified application list exposed via `/api/v1/provenance/apps`.

### Trace Extraction

Trace data is extracted from MLflow experiments and normalised into a common span model. Two primary formats are handled:

- **OpenAI chat format** — used by agentic workflows; spans contain `messages[]` arrays with role/content pairs
- **LangChain format** — used by deterministic chains; spans follow the LangChain callback structure

MLflow truncates span input/output attributes to 250 characters. The extraction layer applies regex fallbacks to reconstruct full payloads where possible (e.g. extracting a complete `query` string from a truncated JSON blob).

### Multi-Experiment Support

The registry can federate traces across multiple MLflow experiments. Configure via the `MLFLOW_EXPERIMENT_NAMES` environment variable (comma-separated list). When set, the provenance endpoints query all listed experiments and merge results.

### UI Integration

The PatternFly sidebar includes external links to:

- **Marquez Lineage UI** — deep-link to the lineage graph for a given dataset or job
- **MLflow UI** — deep-link to the experiment/trace view

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `MLFLOW_TRACKING_URI` | MLflow server URL for trace queries |
| `MARQUEZ_URL` | Marquez API base URL for lineage queries |
| `MARQUEZ_WEB_URL` | Marquez web UI base URL for external links |
| `MLFLOW_EXPERIMENT_NAMES` | Comma-separated list of experiments to federate |

## Production Gaps

| ID | Gap | Impact |
|----|-----|--------|
| PG-026 | Document versioning not exercised | Can't detect when a doc is updated at source |
| PG-027 | Identity drift detection not implemented | Same doc at a new URL gets a new `doc_id` |
| PG-028 | No routing rules in registry | Collection assignment is fully manual |
| PG-029 | Registry has no HA/failover | Single PG, shared with Marquez |
| PG-030 | No deep schema introspection | Only file-level metadata; no content-level extraction |
| PG-031 | Registry UI has no auth | Anyone with route access can modify data |
| PG-057 | Provenance queries are synchronous | High trace volume could slow registry API |

## Design Decisions

- **ADR-006:** Document Identity and Registry
- **ADR-010:** Registry is authoritative for ingest
- **ADR-011:** Pipeline is sole OL emitter
- **ADR-012:** Three-concern architecture

## References

| Source | Link |
|--------|------|
| Registry API | `src/registry/app.py` |
| Registry SDK | `registry-sdk/` |
| Registry UI | `src/registry-ui/` |
| Manifests | `manifests/registry/` |
| M3 Plan | `docs/milestones/M3-connectors/plan.md` |
