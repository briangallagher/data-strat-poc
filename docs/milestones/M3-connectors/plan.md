# M3: Connectors — Plan

**Date:** 2026-05-26
**Status:** In Progress
**Depends on:** M2 Complete (all infrastructure running, lineage verified)

---

## Objective

Add a **three-concern architecture** with **two operational workflows** between source systems and the ingest pipeline:

**Three architectural concerns (things we build):**
1. **Connecting** — Pluggable connectors access remote systems (authenticate, fetch). A capability used by multiple workflows.
2. **Registering** — A Document Registry (FastAPI + PostgreSQL + SDK + UI) assigns stable identity, stores metadata, links back to source systems, and tracks collection membership.
3. **Building Collections** — A human (or agent) defines what documents belong in each logical collection; the registry stores this membership.

**Two operational workflows (things we run):**
- **Discovery workflow** — uses Connectors to scan sources + Registry to compare/update. Keeps registry in sync with reality. (PG-033: not built in M3, essential for production.)
- **Ingest workflow** — uses Connectors to fetch + Registry for identity/metadata. Processes documents into Milvus. Triggered per-collection by an orchestrator.

**The registry is a claim about what exists — not a guarantee.** The discovery workflow keeps that claim honest. The ingest pipeline trusts the registry but handles failures gracefully (missing files are skipped and flagged, not fatal).

### What M3 Proves

- Every document has a **stable canonical identity** (`doc_id`) persisting across pipeline runs, file moves, and source system changes
- Documents are acquired from configured sources (S3/MinIO for POC, Confluence mock as stretch)
- Each document gets **per-document metadata** from the registry (closing PG-020)
- Pipeline runs are **per-collection** (executing DEC-008 with all 3 collections)
- The system can answer: "which pipelines and applications use this document?"
- Collections are living datasets that grow over time via scheduled re-runs

### Alignment with DataStrategy Pillars

| Layer | DataStrategy Pillar | What it handles |
|-------|--------------------|----|
| Connecting (capability) | P1: Data Ingestion & Connectivity | Source system access, credential management, fetch to staging |
| Registering (capability) | P4: Lineage & Governance | Stable identity, provenance, source linkage, OL emission |
| Building Collections (capability) | P5: Unified Data & AI Experience | Curation, membership criteria, browsing collections |
| Discovery workflow | P1: Data Ingestion & Connectivity | Scan sources, detect new/changed/removed docs, update registry |
| Ingest workflow | P2: Compute Engine Strategy | KFP per-collection runs, scheduled re-processing |

### How This Builds on the ET Team's Work

| Aspect | ET Team (dataset-registry) | Our Architecture |
|--------|---------|-----------------|
| Granularity | Coarse-grained (tables, feature views) | Fine-grained (individual documents with per-doc metadata) |
| Multi-collection | Not needed (single pipeline output) | Three collections, many-to-many doc ↔ collection |
| Connecting | Implicit in Feast | Explicit connector ABC (pluggable, per source system) |
| Building Collections | N/A — no routing problem | Distinct curation step: human/agent defines membership |
| Discovery | Not needed (Feast handles sync) | Separate workflow (PG-033) |
| Registry staleness | Not a concern | Registry is a claim; pipeline handles mismatches gracefully |
| Tech stack | FastAPI + PostgreSQL + PatternFly + OL emission | Same stack, extended model |
| SDK | Python `RegistryClient` | Same pattern, extended for collections and batch operations |

---

## Architecture

```
                    ┌─────────────────────┐
                    │     CONNECTING      │
                    │    (connectors)     │
                    │  authenticate       │
                    │  fetch_to_staging   │
                    │  [resolve — for     │
                    │   discovery only]   │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
      ┌─────────▼─────┐  ┌────▼──────┐  ┌───▼───────────┐
      │  Discovery    │  │  Ingest   │  │  Build        │
      │  Workflow     │  │  Pipeline  │  │  Collection   │
      │  (scan+sync) │  │  (KFP)    │  │  (human/agent)│
      │  [PG-033]    │  │           │  │               │
      └─────────┬─────┘  └────┬──────┘  └───┬───────────┘
                │              │              │
                └──────────────┼──────────────┘
                               │
                    ┌──────────▼──────────┐
                    │     REGISTERING     │
                    │     (registry)      │
                    │  identity (doc_id)  │
                    │  metadata           │
                    │  collection membership │
                    │  OL identity derivation │
                    └─────────────────────┘
```

### Ingest Pipeline Flow (Per Collection)

```
Orchestrator: "Run pipeline for collection = underwriting_guidelines"
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  acquire_documents (KFP component)                       │
│                                                          │
│  1. Query registry: GET /documents for this collection   │
│     (registry is authoritative — ADR-010)                │
│  2. Connector.authenticate(credentials)                  │
│  3. For each doc: Connector.fetch(source_url, staging)   │
│  4. Skip unavailable docs gracefully (flag in registry)  │
│  5. Write manifest.json to S3 staging                    │
│  6. Emit per-doc OL InputDataset (ADR-011: sole emitter) │
│  7. Log to MLflow                                        │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  parse_and_chunk (RayData + Docling)                     │
│                                                          │
│  Reads manifest.json for per-document metadata           │
│  Each chunk inherits its parent doc's metadata           │
└─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  ingest_to_milvus (embed + store)                        │
│                                                          │
│  Writes to the target Milvus collection                  │
│  Each vector carries doc_id + per-doc metadata           │
└─────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### D1: Three concerns, two workflows

**Three architectural concerns (things you build):**
- **Connectors** — only know how to talk to source systems. No knowledge of collections, Milvus, or routing.
- **Document Registry** — owns identity (`doc_id`), stores metadata, provides collection membership. The source of truth the pipeline trusts.
- **Collection builder** — the human/agent decision about what belongs in each collection.

**Two operational workflows (things you run):**
- **Discovery workflow** — uses connectors to scan sources + registry to compare/update. PG-033: not built in M3.
- **Ingest workflow** — uses connectors to fetch + registry for identity/metadata. Pipeline per collection.

**Key principle:** The registry can be wrong. `acquire_documents` handles reality mismatches gracefully — if a source file is missing (404), it skips that document, logs the error, flags it in the registry (`status: unavailable`). The pipeline does not crash because the registry is stale.

### D2: Document Registry as canonical identity and collection authority

A Document is a **file** — 1:1 mapping between `doc_id` and a physical file artifact. Logical grouping is handled by collections and shared metadata.

Documents can belong to **multiple collections** (many-to-many). A collection is a logical grouping of documents that will be ingested into a Milvus collection.

### D3: Registry is authoritative for ingest (ADR-010)

The ingest pipeline fetches **only what the registry explicitly lists** for a given collection. `connector.resolve()` (source system discovery) is NOT used in the ingest pipeline — it's reserved for the discovery workflow (PG-033).

This means `acquire_documents` does not scan sources. It asks the registry "what active docs belong to this collection?" and fetches those URLs.

### D4: Pipeline is the sole OpenLineage emitter (ADR-011)

The registry service itself does NOT emit to Marquez. Only the pipeline (`acquire_documents`) emits OL events. This avoids duplicate dataset nodes, naming mismatches, and fragile coupling between registry and Marquez. The OL identity (namespace + name) is derived from the registry's `ol_namespace` and `ol_name` fields.

### D5: Pipeline per collection, re-runnable

Each pipeline run targets a single collection (DEC-008). The orchestrator triggers runs per collection. Re-running is expected and safe:
- Registry tracks `last_ingested` per document per collection
- For POC: full re-ingest each time (`drop_existing=true`)
- For production: incremental processing based on registry state (PG-006)

### D6: S3Connector (real) + Confluence mock

S3Connector works against MinIO (primary connector for M3). Confluence mock included as stretch — code exists from v1, low effort to port.

---

## Data Model

```sql
-- Document identity and metadata
CREATE TABLE documents (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id            VARCHAR NOT NULL UNIQUE,  -- stable human-friendly (ug-005)
    name              VARCHAR NOT NULL,          -- human-readable title
    source_system     VARCHAR NOT NULL,          -- ca_doi, naic, sharepoint, s3, etc.
    source_url        VARCHAR NOT NULL,          -- canonical external URL
    document_type     VARCHAR NOT NULL,          -- bulletin, guideline, form, manual
    line_of_business  VARCHAR NOT NULL,          -- commercial_property, flood, all_p_and_c
    jurisdiction      VARCHAR NOT NULL,          -- CA, NY, national, federal
    effective_date    DATE,                      -- when this version became effective
    superseded_date   DATE,                      -- null if current
    superseded_by     VARCHAR,                   -- doc_id of replacement (FK)
    status            VARCHAR NOT NULL DEFAULT 'active',  -- active | superseded | archived | unavailable
    ol_namespace      VARCHAR NOT NULL,          -- derived OL namespace for Marquez
    ol_name           VARCHAR NOT NULL,          -- derived OL name (= doc_id)
    content_hash      VARCHAR,                   -- SHA-256 (auto-enriched)
    file_format       VARCHAR,                   -- pdf, docx, html (auto-detected)
    page_count        INTEGER,                   -- auto-enriched from file
    file_size_bytes   INTEGER,                   -- auto-enriched from file
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_url) -- per active status
);

-- Collection definitions
CREATE TABLE collections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              VARCHAR NOT NULL UNIQUE,   -- also the Milvus collection name
    description       VARCHAR,
    doc_id_prefix     VARCHAR NOT NULL,          -- prefix for auto-generated doc_ids (ug, rb, if)
    next_sequence     INTEGER NOT NULL DEFAULT 1, -- next sequence number
    created_by        VARCHAR NOT NULL,          -- free-text: "system", "human:brian", "agent:discovery"
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Many-to-many: documents can belong to multiple collections
CREATE TABLE collection_documents (
    collection_id     UUID NOT NULL REFERENCES collections(id),
    document_id       UUID NOT NULL REFERENCES documents(id),
    added_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    added_by          VARCHAR NOT NULL,          -- who assigned it
    last_ingested     TIMESTAMPTZ,               -- last pipeline run for THIS collection
    last_pipeline_run VARCHAR,                   -- pipeline_run_id of last ingest
    vector_count      INTEGER,                   -- chunks in Milvus for this doc in this collection
    UNIQUE (collection_id, document_id)
);
```

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/documents` | Register a new document (triggers auto-enrichment) |
| `POST` | `/api/v1/documents/resolve` | Lookup by source_url; returns existing or creates new |
| `GET` | `/api/v1/documents/{doc_id}` | Get by stable doc_id |
| `GET` | `/api/v1/documents` | List (filter by collection, status, source_system) |
| `PATCH` | `/api/v1/documents/{doc_id}` | Update metadata, status, post-ingest stats |
| `POST` | `/api/v1/documents/{doc_id}/supersede` | Mark superseded, link to replacement |
| `GET` | `/api/v1/documents/{doc_id}/lineage` | Query Marquez for pipelines/consumers |
| `POST` | `/api/v1/documents/bulk` | Seed from manifest.json (with auto-enrichment) |
| `GET` | `/api/v1/collections` | List collections with doc counts |
| `POST` | `/api/v1/collections` | Create a new collection |
| `GET` | `/api/v1/collections/{name}` | Get collection detail with members |
| `POST` | `/api/v1/collections/{name}/assign` | Assign documents to a collection |
| `DELETE` | `/api/v1/collections/{name}/documents/{doc_id}` | Remove a document from a collection |

### Auto-Enrichment

On registration (or bulk seed), if the file is accessible in staging, the registry computes:
- `content_hash` — SHA-256 of file content
- `file_format` — from extension and MIME type
- `file_size_bytes` — from file stat
- `page_count` — from PDF metadata if available

### Python SDK

```python
from registry_sdk import RegistryClient

client = RegistryClient(base_url="http://doc-registry:8080")

# Resolve a document (lookup or create)
doc = client.resolve(source_url="s3://corpus/underwriting_guidelines/ca-doi-2025-3.pdf",
                     source_system="s3")

# Get all active docs in a collection
docs = client.list_documents(collection="regulatory_bulletins", status="active")

# Build a collection
client.create_collection(name="iso_forms", description="ISO/ACORD standard forms",
                         doc_id_prefix="if")
client.assign_to_collection("iso_forms", doc_ids=["if-001", "if-002", "if-003"])

# Update after pipeline run
client.update_ingestion("ug-004", collection="underwriting_guidelines",
                        pipeline_run_id=run_id, vector_count=27)
```

### PatternFly UI

| Route | Page | Purpose |
|-------|------|---------|
| `/documents` | Document List | Browse, filter, search all registered documents |
| `/documents/:doc_id` | Document Detail | Metadata, source link, lineage, collection memberships |
| `/collections` | Collection List | All collections with doc counts, last ingested |
| `/collections/:name` | Collection Detail | Members, assign/remove docs, trigger pipeline |
| `/collections/new` | Create Collection | Name, description, prefix, initial doc selection |
| `/lineage` | Lineage View | Marquez Web UI iframe with deep-links |

---

## Phases

### Phase 0: Corpus Organisation + Third Collection

- Rename `regulatory_filings` to `regulatory_bulletins` (match DEC-008)
- Create ~5 mock docs for `iso_forms` collection (representative ISO/ACORD form content)
- Final corpus: ~20 docs across 3 collections
- Update `manifest.json` to cover all 3 collections
- Upload full corpus to MinIO on cluster: `corpus/<collection>/<filename>`
- Intentionally assign 1-2 docs to multiple collections for verification

### Phase 1: Document Registry (API + SDK + UI)

**Phase 1a: Backend (FastAPI + PostgreSQL)**
- FastAPI application: `src/registry/` (app.py, models.py, db.py, lineage.py, enrichment.py)
- PostgreSQL: share Marquez PG instance, separate `doc_registry` database
- Data model: documents + collections + collection_documents tables
- All API endpoints implemented
- Auto-enrichment on registration (content_hash, file_format, file_size_bytes, page_count)
- `doc_id` auto-generation from collection prefix + sequence
- OpenShift manifests: `manifests/registry/`

**Phase 1b: Python SDK (parallel with 1c once API contract stable)**
- `registry-sdk/` package (client.py, models.py, pyproject.toml)
- Typed Pydantic models for Document, Collection, LineageInfo
- `RegistryClient` class wrapping all endpoints
- Installable via `pip install -e registry-sdk/`

**Phase 1c: PatternFly UI (parallel with 1b once API contract stable)**
- React SPA: `src/registry-ui/` (PatternFly 6)
- Pages: Document List, Document Detail, Collection List, Collection Detail, Create Collection, Lineage
- Nginx proxy deployment
- OpenShift route

**Deploy and verify:**
- Deploy all components to `data-strat-poc` namespace
- Seed documents from manifest via SDK
- Create 3 collections, assign documents via UI
- Verify API, auto-enrichment, OL identity derivation

### Phase 2: Manifest-Driven parse_and_chunk (Close PG-020)

- Modify `parse_and_chunk` in `pipelines-components` to read per-document metadata from staging manifest
- Each chunk inherits parent document's metadata (`doc_id`, `line_of_business`, `jurisdiction`, `effective_date`, `document_type`)
- Remove reliance on pipeline-level `doc_category`/`doc_subcategory`/`doc_date` for per-doc metadata
- Keep pipeline-level params as defaults (fallback if doc not in manifest)
- Verify: run pipeline, check Milvus vectors have per-document metadata

### Phase 3: acquire_documents KFP Component

- New KFP component in `pipelines-components` fork
- Params: `connector_type`, `connector_credentials_secret`, `staging_s3_path`, `collection_name`, `registry_url`
- Uses registry SDK (not raw HTTP)
- Logic: query registry → authenticate → fetch each doc → handle failures gracefully → write manifest → emit OL → log MLflow
- `connector.resolve()` NOT used (ADR-010)
- OL emission from pipeline only (ADR-011)
- Include Confluence mock connector as stretch
- Pipeline: `acquire_documents` → `parse_and_chunk` → `ingest_to_milvus`
- Post-ingest: update registry with ingestion stats per doc per collection

### Phase 4: Multi-Collection Orchestration

- `scripts/run-multi-collection.py` orchestrator
- Reads `config/collections.yaml` (collection → connector_type + source_uri + credentials)
- Triggers one pipeline run per collection via KFP API
- Each run gets its own `pipeline_run_id`
- Run all 3 collections: `underwriting_guidelines`, `iso_forms`, `regulatory_bulletins`
- Verify: all 3 Milvus collections populated, Marquez shows 3 lineage graphs, MLflow shows 3 parent runs

### Phase 5: E2E Verification, Documentation + Checkpoint

**Verification:**
- Per-document metadata differs within a single collection run
- Lineage graph: per-doc → acquire → parse → ingest → Milvus
- `GET /documents/{doc_id}/lineage` returns full pipeline chain
- MLflow has acquisition metrics
- Cross-run identity: re-run pipeline, same `doc_id` in both runs
- Many-to-many: doc in 2 collections appears in both Milvus collections with correct lineage
- Registry UI functional: browse, assign, create collections
- Regression: M1 pipeline + M2 lineage still work

**ADRs:**
- ADR-006: Document Identity and Registry
- ADR-007: Three-Concern Architecture
- ADR-008: Connector Pattern
- ADR-009: Collection Lifecycle
- ADR-010: Registry Authoritative for Ingest
- ADR-011: Pipeline is Sole OL Emitter

**Technical docs:**
- `docs/technical/document-registry.md`
- `docs/technical/connectors.md`
- `docs/technical/collection-lifecycle.md`
- Update: architecture overview, getting-started, run-ingest-pipeline runbook

**Production gaps:** Update with PG-026 through PG-035

**Checkpoint:** Full verification evidence, cluster state, lessons learned, how to resume for M4

**Tag:** All repos `m3-complete`

---

## Collection Lifecycle

```
    ┌─────────────────────────────────────────────────┐
    │  Discovery Workflow (PG-033 — not built in M3)  │
    │  Scan sources → compare with registry →         │
    │  register new / flag missing / detect changes   │
    └─────────────────────┬───────────────────────────┘
                          │
                          ▼
    ┌─────────────────────────────────────────────────┐
    │  Build Collection (human or agent via UI)        │
    │  Assign discovered docs to collections           │
    │  based on business criteria                      │
    └─────────────────────┬───────────────────────────┘
                          │
                          ▼
    ┌─────────────────────────────────────────────────┐
    │  Ingest Workflow (pipeline per collection)        │
    │  Orchestrator queries registry → acquire →       │
    │  parse → ingest → update registry stats          │
    └─────────────────────┬───────────────────────────┘
                          │
                          ▼
    ┌─────────────────────────────────────────────────┐
    │  Scheduled Re-run                                │
    │  (weekly/monthly — keeps collections current)    │
    └─────────────────────────────────────────────────┘
```

**For M3:** Build Collection + Ingest Workflow exercised. Discovery deferred (PG-033). Scheduled re-runs proven structurally.

**What happens when the registry is wrong:**
- `acquire_documents` attempts to fetch a file the registry claims exists
- Source returns 404 → skip, log, flag as `status: unavailable`
- Pipeline continues with remaining docs
- Next discovery cycle investigates

---

## Production Gaps (New for M3)

| ID | Gap | Path to Close |
|----|-----|---------------|
| PG-026 | Document versioning not exercised | Content-hash comparison in connector; exercise with a doc update |
| PG-027 | Identity drift detection not implemented | Hash-based dedup in registry `/resolve` |
| PG-028 | No routing rules in registry | Rules table + matching logic for auto-assignment |
| PG-029 | Registry has no HA/failover | Standard K8s HA patterns |
| PG-030 | No deep schema introspection | Docling metadata extraction as enrichment step |
| PG-031 | Registry UI has no auth | OAuth proxy or K8s auth plugin |
| PG-032 | Multiple standalone SDKs | Unified `rhoai-data-sdk` post-M3 |
| PG-033 | No discovery/sync process | Separate KFP pipeline or cron job |
| PG-034 | Manifest not treated as versioned record | Version and store per pipeline_run_id |
| PG-035 | Connector ABC not split into Fetcher/Discoverer | Refactor when discovery workflow lands |

**Questions for ET team:**
- How does the dataset-registry handle document versioning?
- Have you encountered identity drift (same dataset, different URI after a move)?
- Any pattern for routing rules (auto-assigning datasets to categories)?

---

## Resolved Design Decisions

1. **A Document is a file** — 1:1 mapping between `doc_id` and physical file artifact
2. **Third collection (`iso_forms`)** — ~5 mock docs, representative ISO/ACORD content
3. **Pipeline topology** — one 3-step DAG per collection (acquire → parse → ingest)
4. **Confluence mock** — included in M3 Phase 3 as stretch
5. **Registry hosting** — share Marquez PostgreSQL, separate `doc_registry` database
6. **Many-to-many** — documents can belong to multiple collections (join table)
7. **`created_by`** — free-text string, no auth integration
8. **`doc_id` auto-generation** — from collection `doc_id_prefix` + sequential number
9. **Collection name = Milvus collection name** — no indirection
10. **Registry authoritative for ingest (ADR-010)** — pipeline fetches only what registry lists
11. **Pipeline sole OL emitter (ADR-011)** — registry doesn't emit to Marquez directly
12. **Phase 1 sequence** — API contract first → SDK + UI parallel → deploy together

---

## Success Criteria

- [ ] Registry API operational: `/resolve` returns doc_id + metadata for all seeded documents
- [ ] Auto-enrichment: seeded docs have content_hash, file_format, file_size_bytes
- [ ] SDK works: `RegistryClient` resolves, lists, updates documents and manages collections
- [ ] UI functional: browse documents, view collections, assign docs, create collections
- [ ] "Build Collection" workflow: human creates collection + assigns documents via UI
- [ ] Per-doc identity in Marquez: each document is an individual InputDataset node
- [ ] PG-020 closed: vectors have per-document metadata (different docs = different metadata)
- [ ] DEC-008 executed: all 3 collections populated with appropriate documents
- [ ] Lineage graph extends: per-doc → acquire → parse → ingest → Milvus
- [ ] Cross-run identity: re-run shows same doc_id in both runs' lineage
- [ ] "Used by" query: `GET /documents/{doc_id}/lineage` returns pipeline runs
- [ ] MLflow tracks acquisition: document count, bytes fetched, connector type
- [ ] Orchestrator: runs all 3 collections without manual intervention
- [ ] Many-to-many verified: doc in 2 collections processed in both pipeline runs
- [ ] No regression: M1/M2 capabilities still pass

---

## Key Files

| File | Action | Location |
|------|--------|----------|
| Registry FastAPI backend | Create | `data-strat-poc/src/registry/` |
| Registry Python SDK | Create | `data-strat-poc/registry-sdk/` |
| Registry PatternFly UI | Create | `data-strat-poc/src/registry-ui/` |
| Registry OpenShift manifests | Create | `data-strat-poc/manifests/registry/` |
| `acquire_documents` KFP component | Create | `pipelines-components` fork |
| `parse_and_chunk` manifest support | Modify | `pipelines-components` fork |
| `ingest_pipeline.py` (3-step) | Modify | `pipelines-components` fork |
| Corpus with 3 collections | Create | `data-strat-poc/corpus/` |
| `manifest.json` (full 3-collection) | Update | `data-strat-poc/corpus/manifest/` |
| `config/collections.yaml` | Create | `data-strat-poc/` |
| `scripts/run-multi-collection.py` | Create | `data-strat-poc/` |
| ADR-006 through ADR-011 | Create | `data-strat-poc/docs/architecture/adrs/` |
| Technical docs (registry, connectors, lifecycle) | Create | `data-strat-poc/docs/technical/` |
| CONTEXT.md | Create | `data-strat-poc/` |
