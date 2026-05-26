# ADR-010: Registry is Authoritative for Ingest Pipeline

**Date:** 2026-05-26
**Status:** Accepted
**Milestone:** M3

## Context

The acquire_documents component needs to know what to fetch. It could either scan the source system (discover what's there) or ask the registry (fetch what's registered). These are fundamentally different approaches with different failure modes.

## Decision

The ingest pipeline fetches ONLY what the registry explicitly lists for a given collection. `connector.resolve()` (source scanning/discovery) is NOT used in the ingest pipeline.

The acquire component queries the registry: `GET /documents?collection=X&status=active` and fetches those specific source URLs. Unknown files in the source system are ignored — that's the discovery workflow's job (PG-033). This makes ingestion predictable and deterministic: the same registry state always produces the same result.

## Consequences

- Ingest is deterministic — same registry state = same result
- Unknown docs in source systems are not auto-ingested
- Discovery is explicitly separate (PG-033)
- If registry is stale, pipeline skips unavailable docs gracefully (no crash)
- `connector.resolve()` exists but is unused in the ingest path
