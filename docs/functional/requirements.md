# Functional Requirements

Structured requirements with traceability to use cases and milestones.

**Last Updated:** 2026-05-22 (M0 — initial structure)

## Requirements

| ID | Requirement | Use Case | Milestone | Priority | Status |
|----|-------------|----------|-----------|----------|--------|
| FR-001 | System shall parse PDF documents using Docling, extracting text, tables, and structure | UC-001 | M1 | Must | Planned |
| FR-002 | System shall chunk parsed documents using structure-aware chunking (section, table, paragraph) | UC-001 | M1 | Must | Planned |
| FR-003 | System shall generate dense vector embeddings for each chunk | UC-001 | M1 | Must | Planned |
| FR-004 | System shall store embeddings with metadata in Milvus collections partitioned by line of business | UC-001 | M1 | Must | Planned |
| FR-005 | System shall orchestrate the ingest pipeline via KFP as reusable components | UC-001 | M1 | Must | Planned |
| FR-006 | System shall track pipeline runs with parameters and metrics in MLflow | UC-001 | M2 | Must | Planned |
| FR-007 | System shall emit OpenLineage events for pipeline-time lineage | UC-001 | M2 | Must | Planned |
| FR-008 | System shall acquire documents from configurable data sources (S3, Confluence, SharePoint) | UC-001 | M3 | Must | Planned |
| FR-009 | System shall return cited answers to user queries via RAG retrieval | UC-002 | M4 | Must | Planned |
| FR-010 | System shall trace query-time lineage bridged to pipeline lineage via pipeline_run_id | UC-002 | M4 | Must | Planned |
| FR-011 | System shall perform multi-hop retrieval across document collections for compliance review | UC-003 | M5 | Should | Planned |

<!-- Extended as milestones are planned in detail -->
