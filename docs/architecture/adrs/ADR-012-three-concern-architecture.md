# ADR-007: Three-Concern Architecture with Two Workflows

**Status:** Accepted (M3)

## Context

M3 adds document acquisition from source systems. The design must cleanly separate responsibilities so each can evolve independently. We evaluated:

- **ET team's approach** — single pipeline, Feast handles everything
- **v1's approach** — connectors did routing
- **DataStrategy mapping** — how this maps to the five pillars

## Decision

Three architectural **concerns** (things you build) and two operational **workflows** (things you run).

### Concerns

1. **Connecting** — Pluggable connectors that access remote systems (authenticate, fetch). No knowledge of collections or routing. Maps to P1 (Data Ingestion & Connectivity).
2. **Registering** — Document Registry service owning identity, metadata, and collection membership. Maps to P4 (Lineage & Governance).
3. **Building Collections** — Human or agent curation deciding what documents belong in each logical collection. Maps to P5 (Unified Experience).

### Workflows

- **Discovery workflow** — Scans sources and updates registry. Keeps registry honest. Not built in M3 (deferred — see PG-033).
- **Ingest workflow** — Fetches what registry says and processes into Milvus. Pipeline per collection.

### Key Principle

Concerns are services/capabilities you build. Workflows are processes that exercise those capabilities.

## Consequences

- Clear ownership: connectors don't route, registry doesn't fetch, curators don't process
- Discovery is explicitly a separate operational concern (not conflated with ingestion)
- The registry is a claim about reality, not a guarantee — pipeline handles mismatches
- Aligns with DataStrategy pillars P1, P2, P4, P5
- Differs from ET team: they have no multi-collection routing, no discovery, no curation step
