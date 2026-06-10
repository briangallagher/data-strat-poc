# ADR-011: Pipeline and Application Code Emit OpenLineage; Registry Does Not

**Date:** 2026-05-26 (revised 2026-06-10)
**Status:** Accepted
**Milestone:** M3 (refined M4/M5)

## Context

Both the registry service and the pipeline could emit OpenLineage events to Marquez. If both emit for the same dataset, you get either duplicate nodes or naming mismatches (fragile coupling). We needed to decide who emits.

Additionally, DEC-009 (M4) introduced application-level OL registration — query services register themselves as consumers of Milvus collections in Marquez. This extends the original M3 decision.

## Decision

**Ingest-time:** All three KFP pipeline steps (`acquire_documents`, `parse_and_chunk`, `ingest_to_milvus`) emit OpenLineage events to Marquez via `rhoai-lineage`. Each step emits START/COMPLETE events for its job, with input/output datasets.

**Application-level:** Query services (`underwriter_chat`, `compliance_review_agent`) emit a one-time COMPLETE event on startup registering themselves as OL jobs that consume Milvus collections. This closes the Marquez graph from source documents through ingest to application consumption (DEC-009).

**Registry does NOT emit.** The registry stores identity and metadata but is not a lineage participant. OL identity (namespace + name) is derived from the registry's `ol_namespace` and `ol_name` fields (based on `doc_id`). Nodes appear in Marquez when the pipeline runs, not when a document is registered.

**Query-time lineage goes to MLflow traces, not Marquez** (DEC-009). Per-request provenance (which chunks answered which question) is captured in MLflow spans, not as OL events.

## Consequences

- No duplicate nodes, no naming mismatch risk between registry and pipeline
- Pipeline steps produce a complete ingest lineage graph (source → staging → chunks → vectors)
- Application-level registration closes the consumption side of the graph
- Registry can be deployed/restarted without affecting Marquez state
- Lineage only appears for docs that were actually processed (not just registered)
- Registration without pipeline run = no Marquez node (acceptable — lineage tracks processing, not existence)
- Query-time provenance lives in MLflow traces with `pipeline_run_id` bridging back to the Marquez ingest graph
