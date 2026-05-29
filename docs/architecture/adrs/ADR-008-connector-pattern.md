# ADR-008: Connector ABC Pattern (authenticate/fetch only)

**Date:** 2026-05-26
**Status:** Accepted
**Milestone:** M3

## Context

The prior POC had connectors with three methods: authenticate, resolve, fetch_to_staging. For M3, the ingest pipeline needs connectors but the resolve method (source discovery) is reserved for a separate discovery workflow. We needed to decide whether to split the interface or keep it unified.

## Decision

Keep the existing ABC unchanged (3 methods). In the ingest workflow, acquire_documents only calls authenticate + fetch. The resolve method exists but is unused in M3 — reserved for the discovery workflow (PG-033).

No interface refactoring until discovery is built and the boundary is proven. Connectors have no knowledge of collections, Milvus, or routing — they are pure source-system adapters that authenticate and retrieve content.

## Consequences

- Simple implementation — no refactoring of the existing connector interface needed
- `connector.resolve()` is unused code in the ingest path (acceptable tech debt)
- Interface split deferred to PG-035 once discovery workflow proves the boundary
- S3Connector works against MinIO for POC
- Confluence mock connector included as stretch goal
