# Production Gap Register

Every deviation from enterprise/production standard is tracked here. Nothing is silently accepted.

**Updated at:** every milestone checkpoint.
**Last Updated:** 2026-05-23 (M1 Phase 0 complete — 19 gaps tracked)

## How to Use

When implementing something that falls short of production-grade:
1. Add a row to the register below
2. Reference the gap ID (PG-NNN) in the relevant technical doc or milestone checkpoint
3. Update the status as gaps are addressed

---

## KFP / Pipelines Platform

Issues with Kubeflow Pipelines, DSPA, and the pipeline execution environment.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-014 | KFP pods lack K8s API access by default | RHOAI strips `KUBERNETES_SERVICE_HOST` from user containers for security isolation | SA token auth works transparently in pipeline pods | Fix in codeflare-sdk upstream or document manual SA token pattern | **Mitigated** (workaround on fork) |
| PG-015 | No RBAC automation for pipeline SA | Pipeline SA needs RayJob, KServe, HardwareProfile permissions; created manually via `oc` | RBAC manifests shipped with deployment and automated | Add Role/RoleBinding to manifests + getting-started guide | Open |

## Ray / RayData / Docling

Issues with distributed compute, RayJob submission, and document processing.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-004 | Token auth disabled on RHOAI (affects Ray) | Systemic RHOAI platform blocker — token auth disabled, blocking secure data access for Ray/Spark/Feast | Token auth enabled and tested for all compute engines | Platform team dependency; track status | Open — platform dep |
| PG-006 | No incremental processing | v1 re-processed full corpus on every run | Change detection + re-process only modified documents | Document fingerprinting + delta processing | Open |

## Milvus / Vector Storage

Issues with vector database deployment, schema, and query capabilities.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-003 | No retry/dead-letter on Milvus writes | v1 used basic try/except; no retry logic | Configurable retry with exponential backoff + dead-letter collection | Implement in pipeline component or rhoai-lineage library | Open |
| PG-007 | No hybrid search in Milvus | v1 used dense-only similarity search | Hybrid search (BM25 sparse + dense) for better keyword recall | Milvus 2.4+ supports hybrid; implement dual-vector schema | Open |
| PG-008 | No document-level RBAC | v1 had no access control on which documents a user can query | Partition-level or metadata-filter RBAC per user role | Evaluate Milvus partition-key isolation + query-time filtering | Open |
| PG-016 | Milvus deployed with anyuid SCC | Helm chart requires anyuid for Milvus pods | Restricted SCC or operator-managed deployment | Evaluate Milvus Operator or restricted-SCC Helm values | Open |
| PG-017 | 500Gi MinIO PVC from Milvus Helm defaults | Helm default for Milvus internal MinIO — way oversized | Right-sized storage (10-50Gi for POC) | Redeploy with `minio.persistence.size=10Gi` | Open |

## Embedding / Model Serving

Issues with embedding model deployment and inference services.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-018 | RHOAI 3.4 vLLM lacks `--task=embedding` | vLLM version in RHOAI 3.4 predates embedding task support | Dedicated embedding InferenceService via KServe | Upgrade to RHOAI 3.5+ or use local sentence-transformers | **Mitigated** (local works) |
| PG-019 | Local sentence-transformers downloads model every run | `ingest_to_milvus` downloads Granite Embedding 125M from HuggingFace each time | Pre-loaded model on PVC or cached embedding service | PVC-mounted model or embedding ISVC when RHOAI supports it | Open |

## Lineage / Observability

Issues with OpenLineage, Marquez, MLflow, and audit logging.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-001 | No auth/RBAC on Marquez | Marquez has no built-in auth; upstream Shiro never shipped | mTLS + K8s RBAC proxy (MLflow operator pattern) | Sidecar OAuth proxy or in-process plugin | Open |
| PG-002 | No auth on MLflow | MLflow upstream has no real auth system | RHOAI MLflow operator with K8s auth plugin | Adopt `opendatahub-io/mlflow-kubernetes-plugins` | Open |
| PG-009 | No query/response audit logging (production) | v1 used JSONL file on PVC; `pipeline_run_id` always null | MLflow GenAI traces with structured spans and bridge | Port to MLflow (v1 DEC-022 completion) | Open |
| PG-013 | OpenLineage emission is manual | No RHOAI component emits OL natively; all explicit in code | Auto-instrumentation or SDK-level emission | rhoai-lineage library abstracts this | Open |

## Connectors / Data Ingestion

Issues with document source acquisition and connectivity.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-005 | No document version tracking | v1 tracked dates in schema but never exercised | Automated staleness detection when docs are superseded | Version tracking in connector + Milvus metadata | Open |
| PG-010 | Mock connectors only | v1 built mock Confluence/SharePoint; real connectors need OAuth, pagination | Production connectors with OAuth2, incremental sync | Build real connectors or adopt dlt | Open |
| PG-020 | Pipeline-level metadata only (no per-document) | All docs in a run get same LOB/doc_type/effective_date from pipeline params | Per-document metadata from manifest file keyed by filename | Read manifest in parse_and_chunk instead of env vars. See ADR-002. | Open |

## Security / Platform

Cross-cutting security and platform infrastructure gaps.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-011 | No TLS between internal services | POC scope — no cert-manager setup | mTLS between all services via OpenShift service-ca | Deploy service-ca certificates | Open |
| PG-012 | No namespace isolation for multi-tenancy | Single-namespace deployment | Per-tenant namespace or partition isolation | Evaluate at M5; depends on Marquez + Milvus support | Open |

---

## Summary by Area

| Area | Count | Mitigated | Open |
|------|-------|-----------|------|
| KFP / Pipelines Platform | 2 | 1 | 1 |
| Ray / RayData / Docling | 2 | 0 | 2 |
| Milvus / Vector Storage | 5 | 0 | 5 |
| Embedding / Model Serving | 2 | 1 | 1 |
| Lineage / Observability | 4 | 0 | 4 |
| Connectors / Data Ingestion | 3 | 0 | 3 |
| Security / Platform | 2 | 0 | 2 |
| **Total** | **20** | **2** | **18** |
