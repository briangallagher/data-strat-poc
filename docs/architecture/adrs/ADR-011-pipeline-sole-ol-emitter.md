# ADR-011: Pipeline is the Sole OpenLineage Emitter

**Date:** 2026-05-26
**Status:** Accepted
**Milestone:** M3

## Context

Both the registry service and the pipeline could emit OpenLineage events to Marquez. If both emit for the same dataset, you get either duplicate nodes or naming mismatches (fragile coupling). We needed to decide who emits.

## Decision

Only the pipeline (specifically the acquire_documents component) emits OpenLineage events to Marquez. The registry service itself does NOT emit to Marquez — it stores identity and metadata but is not a lineage participant.

The OL identity (namespace + name) is derived from the registry's `ol_namespace` and `ol_name` fields (based on `doc_id`). Each document becomes an InputDataset node in Marquez when the pipeline runs, not when the doc is registered.

## Consequences

- No duplicate nodes, no naming mismatch risk
- Single emitter simplifies debugging
- Registry can be deployed/restarted without affecting Marquez state
- Lineage only appears for docs that were actually processed (not just registered)
- Registration without pipeline run = no Marquez node (acceptable — lineage tracks processing, not existence)
