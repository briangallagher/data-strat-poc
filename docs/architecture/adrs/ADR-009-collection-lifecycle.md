# ADR-009: Collection as a Living Dataset with Explicit Lifecycle

**Date:** 2026-05-26
**Status:** Accepted
**Milestone:** M3

## Context

DEC-008 specifies 3 Milvus collections. We needed to define what a "collection" is architecturally — who creates them, how documents get assigned, and how they stay current over time.

## Decision

A Collection is a logical grouping of documents that maps 1:1 to a Milvus vector collection. Collections have an explicit lifecycle:

1. **Created** by a human or agent via registry API/UI
2. **Documents assigned** to collections (many-to-many — a doc can be in multiple collections)
3. **Pipeline runs** per-collection to populate Milvus
4. **Scheduled re-runs** keep collections current as new docs arrive

The registry owns collection definitions and membership. The collection name IS the Milvus collection name (no indirection). Auto-generated doc_ids use the collection's prefix (e.g., `ug-`, `rb-`, `if-`).

## Consequences

- Collections are first-class entities (not just a field on a document)
- Many-to-many allows flexible grouping without duplicating content
- Pipeline is stateless — processes what the registry says belongs to the collection
- Re-runs are safe and expected (idempotent by design)
- Collection curation is an explicit human/agent step, separate from ingestion
