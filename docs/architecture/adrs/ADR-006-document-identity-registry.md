# ADR-006: Document Identity via Registry Service

**Date:** 2026-05-26
**Status:** Accepted
**Milestone:** M3

## Context

The POC needs stable document identity that persists across pipeline runs, file moves, and source system changes. Without this, lineage graphs break when filenames change, and you cannot answer "which pipelines use this document?"

### Options Considered

**Option 1: Convention-based identity (filename stems)**
The convention-based approach — derive identity from filenames or URL slugs. Fragile: renaming a file or changing a source URL silently creates a new identity, orphaning all downstream lineage edges and Milvus vectors tied to the old name.

**Option 2: Manifest-only identity (static JSON)**
Assign a `doc_id` in checked-in JSON manifest files. Better than convention, but no API surface — discoverability requires reading files, there's no way to query "all documents in collection X" at runtime, and no enforcement of uniqueness or format.

**Option 3: Registry service (FastAPI + PostgreSQL)**
Deploy a dedicated service as the canonical identity authority. Auto-generates stable `doc_id` values, exposes a query API, and stores the metadata needed to link documents to external systems and collections.

## Decision

**Option 3** — deploy a Document Registry (FastAPI + PostgreSQL) as the canonical identity layer.

Each document gets a stable `doc_id` (e.g., `ug-005`) that is auto-generated from the collection's prefix + sequence number. The registry stores:

- **source_url** — linking back to external systems (Git repos, Google Docs, Confluence)
- **collection membership** — many-to-many (a document can belong to multiple collections)
- **per-document metadata** — title, format, content hash, last-fetched timestamp
- **OL identity derivation** — the registry is the authority for how a document maps to an OpenLineage dataset name

This extends the ET team's dataset-registry pattern with document-level granularity.

## Consequences

- Every document has a stable identity that survives file moves and URL changes
- The system can answer "which pipelines and apps use this document?" via Marquez graph traversal
- Additional operational complexity: +1 service to deploy, monitor, and maintain
- Registry can be wrong (stale) — pipeline handles gracefully (skip + flag unavailable docs)
- SDK and UI needed to make it usable (both built in M3)
- Versioning and drift detection deferred (PG-026, PG-027)
