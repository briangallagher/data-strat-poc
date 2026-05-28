# Production Gap Register

Every deviation from enterprise/production standard is tracked here. Nothing is silently accepted.

**Updated at:** every milestone checkpoint.
**Last Updated:** 2026-05-28 (M5 in progress — 60 gaps tracked; M5 added PG-054–PG-060, closed PG-037)

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
| PG-018 | RHOAI 3.4 vLLM lacks `--task=embedding` | vLLM version in RHOAI 3.4 predates embedding task support | Dedicated embedding InferenceService via KServe | Upgrade to RHOAI 3.5+ or use local sentence-transformers | **Mitigated** (local works; confirmed blocking in M4 — MCP server uses local sentence-transformers) |
| PG-019 | Local sentence-transformers downloads model every run | `ingest_to_milvus` and MCP server download Granite Embedding 125M from HuggingFace each restart | Pre-loaded model on PVC or cached embedding service | PVC-mounted model or embedding ISVC when RHOAI supports it | Open (confirmed in M4 — MCP server downloads on each startup) |

## Lineage / Observability

Issues with OpenLineage, Marquez, MLflow, and audit logging.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-001 | No auth/RBAC on Marquez | Marquez has no built-in auth; upstream Shiro never shipped | mTLS + K8s RBAC proxy (MLflow operator pattern) | Sidecar OAuth proxy or in-process plugin | Open |
| PG-002 | No auth on MLflow | MLflow upstream has no real auth system | RHOAI MLflow operator with K8s auth plugin | Adopt `opendatahub-io/mlflow-kubernetes-plugins` | Open |
| PG-009 | No query/response audit logging (production) | v1 used JSONL file on PVC; `pipeline_run_id` always null | MLflow GenAI traces with structured spans and bridge | **Fixed:** M4 — `mlflow.langchain.autolog()` captures full query traces with doc_ids, pipeline_run_ids, chunks, and scores. Trace tags enable search/filter. | **Closed** (M4) |
| PG-013 | OpenLineage emission is manual | No RHOAI component emits OL natively; all explicit in code | Auto-instrumentation or SDK-level emission | rhoai-lineage library abstracts this | Open |
| PG-021 | rhoai-lineage installed via git URL | No PyPI package; `pip install git+https://...` is slow (~30s) in KFP pods | Published wheel on PyPI or internal registry | Build and publish wheel once API stabilises | Open |
| PG-022 | Marquez deployed in same namespace | No network isolation between lineage backend and pipeline workloads | Separate namespace (`data-strat-lineage`) with NetworkPolicy | Redeploy Marquez to isolated namespace | Open |
| PG-023 | Lineage operator not deployed | Deferred from M2 — not in critical path for pipeline-time lineage | Operator deployed for agent-level lineage (M4/M5) | Deploy when OGX query path is implemented | Open |
| PG-024 | MLflow tracking from KFP pods | RHOAI MLflow Operator requires SA token + workspace header | Transparent auth via K8s auth plugin | **Fixed:** REST API with explicit SA token + K8s RBAC for `mlflow.kubeflow.org` resources. Requires Role/RoleBinding in manifests. | **Closed** |
| PG-025 | pipeline_run_id not in Marquez run facets | OL events didn't include pipeline_run_id as a custom facet | Cross-system correlation via pipeline_run_id | **Fixed:** Added `pipelineRunId` custom run facet in rhoai-lineage OL emission. Also logged as MLflow param. | **Closed** |

## Connectors / Data Ingestion

Issues with document source acquisition and connectivity.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-005 | No document version tracking | v1 tracked dates in schema but never exercised | Automated staleness detection when docs are superseded | Version tracking in connector + Milvus metadata | Open |
| PG-010 | Mock connectors only | v1 built mock Confluence/SharePoint; real connectors need OAuth, pagination | Production connectors with OAuth2, incremental sync | Build real connectors or adopt dlt | Open |
| PG-020 | Pipeline-level metadata only (no per-document) | All docs in a run get same category/subcategory/document_date from pipeline params | Per-document metadata from manifest file keyed by filename | **Fixed:** M3 Phase 2 — `parse_and_chunk` reads per-document metadata from staging `manifest.json`. Each chunk inherits parent document's `doc_id`, `line_of_business`, `jurisdiction`, `effective_date`, `document_type`. | **Closed** (M3) |

## Security / Platform

Cross-cutting security and platform infrastructure gaps.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-011 | No TLS between internal services | POC scope — no cert-manager setup | mTLS between all services via OpenShift service-ca | Deploy service-ca certificates | Open |
| PG-012 | No namespace isolation for multi-tenancy | Single-namespace deployment | Per-tenant namespace or partition isolation | Evaluate at M5; depends on Marquez + Milvus support | Open |

## Document Registry / Identity

Issues with document identity, the Document Registry service, and collection management.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-026 | Document versioning not exercised | `supersede` API exists but never tested in a pipeline re-run | Superseded doc triggers re-ingest; old vectors removed, new version indexed | Exercise with a doc update in M5 | Open |
| PG-027 | Identity drift detection not implemented | No hash-based dedup in registry `/resolve` | Detect when two doc_ids point to the same content (duplicate registration) | Hash-based dedup in registry `/resolve` | Open |
| PG-028 | No routing rules in registry | Collection membership is manual (API/UI) | Rules engine for auto-assigning documents to collections based on metadata | Rules table + matching logic in registry | Open |
| PG-029 | Registry has no HA/failover | Single-pod FastAPI deployment, shared PG | Standard K8s HA: replicas, readiness probes, separate PG instance | Standard K8s HA patterns; separate PG user at minimum | Open |
| PG-030 | No deep schema introspection | Document metadata (page_count, file_format) is surface-level | Docling metadata extraction as enrichment (table counts, section headers, etc.) | Enrichment step post-parse | Open |
| PG-031 | Registry UI has no auth | No login or access control on the Registry UI | OAuth proxy or K8s auth plugin | OAuth proxy sidecar (same pattern as Marquez auth, PG-001) | Open |
| PG-032 | Multiple standalone SDKs | Separate `registry-sdk` and `rhoai-lineage` packages | Unified `rhoai-data-sdk` for all POC libraries | Post-M5 consolidation | Open |
| PG-033 | No discovery/sync process | Documents must be manually registered; no auto-scan of source systems | Separate KFP pipeline or cron job that scans sources and registers new documents | Build discovery workflow (depends on PG-035) | Open |
| PG-034 | Manifest not treated as versioned record | Manifest is transient (written to S3 staging, consumed, forgotten) | Version and store manifests per `pipeline_run_id` for audit trail | Store in Registry or dedicated artifact store | Open |
| PG-035 | Connector ABC not split into Fetcher/Discoverer | Single ABC handles both fetch and discover (only fetch implemented) | Separate concerns: `Fetcher` (download known files) and `Discoverer` (scan for new files) | Refactor when discovery workflow lands (PG-033) | Open |
| PG-036 | Registry models "Document" not generic "Dataset" | Built for Scenario B (PDF-centric) | Generalise to Dataset with type discrimination (document, table, feature_set, model) | Refactor when Scenario A or cross-scenario use cases arrive | Open |
| PG-037 | Registry UI lacks registration form | Documents registered only via API/SDK, not UI | "Register Document" page with form fields | **Fixed:** M5 — `RegisterDocumentsPage.tsx` added to Registry UI | **Closed** (M5) |
| PG-038 | Registry UI lacks discovery/re-scan trigger | No way to trigger source system scan from the UI | "Scan Source" button on collection detail page | Depends on PG-033 (discovery workflow) | Open |

## Infrastructure / Operations

Infrastructure sizing, staging, and operational concerns.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-039 | PVC not supported as staging surface | Design uses S3 exclusively; some users may need PVC-based staging (air-gapped) | Configurable staging: S3 or PVC | Add `staging_type` param; `parse_and_chunk` already has PVC fallback path | Open |
| PG-040 | Single shared Milvus instance for all collections | POC uses one Milvus with separate collections; different apps may need physical isolation | Per-app Milvus or partition-key isolation | Add optional `milvus_endpoint` to collections table; orchestrator routes to correct instance | Open |
| PG-041 | Marquez job naming: unified graph vs per-job run history | Collection-specific job names (acquire_documents/underwriting_guidelines) give unified graph but lose run-over-run comparison | Support both views | Evaluate in production; may need Marquez UI customisation | Open |

## Query / Chat

Issues with the RAG query service, chat UI, LLM serving, and provenance portal.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-042 | No auth on Chainlit beyond basic | POC scope — no OIDC setup | OAuth proxy or OIDC for Chainlit | Deploy OAuth proxy sidecar | Open |
| PG-043 | Single LLM instance, no HA | One vLLM pod on A100 | Scaled/failover LLM serving (multiple replicas, load balancing) | KServe scaling configuration | Open |
| PG-044 | No rate limiting on query service | No protection against abuse or runaway queries | Rate limiting (per-user, per-minute) on query endpoint | API gateway or middleware rate limiter | Open |
| PG-045 | No response caching | Repeated identical queries hit LLM each time | Semantic cache or exact-match cache for common queries | Cache layer in front of LLM (evaluate Redis or in-memory) | Open |
| PG-046 | No guardrails/safety filters | LLM can be prompted outside underwriting domain | Domain boundary enforcement, PII filtering, toxicity detection | Guardrails framework (e.g., NeMo Guardrails) or system prompt hardening | Open |
| PG-047 | LLM occasionally skipped tool call (ReAct agent) | Granite 8B sometimes answered from parametric knowledge without searching | Deterministic retrieval pipeline — application always retrieves first | **Resolved:** Restructured from ReAct agent to deterministic RAG graph (retrieve → generate). No LLM decision on whether to search. | **Closed** (M4) |
| PG-048 | RHOAI MLflow lacks trace delete API | MLflow Operator does not expose trace deletion; stale traces accumulate | Trace lifecycle management (TTL, manual delete, archival) | Upstream MLflow Operator feature request | Open |
| PG-049 | RHOAI MLflow `traceOutputs` metadata truncated at 250 chars | MLflow UI/API truncates trace output metadata at 250 characters | Full trace output preserved and searchable | Upstream MLflow Operator bug/feature — may need custom trace storage | Open |
| PG-050 | Chainlit incompatible with Python 3.14 | asyncio changes in Python 3.14 break Chainlit's event loop | Chainlit runs on Python 3.14 without workarounds | Upstream Chainlit fix; pin to Python 3.12/3.13 as workaround | Open |
| PG-051 | MLflow workspace header requires monkeypatch | RHOAI MLflow Operator requires `X-Mlflow-Workspace` header; no clean injection point in MLflow client | MLflow client supports custom headers natively | Upstream feature request to MLflow; or RHOAI MLflow Operator removes requirement | **Mitigated** (`mlflow_config.py` monkeypatch) |
| PG-052 | Port-forward instability for local dev | Services drop idle connections; port-forwards need restarting frequently during development | Stable dev connectivity | Deploy query service on cluster (removes local port-forward dependency) or use persistent tunnel | Open |
| PG-053 | Query service not yet deployed on cluster | Runs locally with port-forwards to cluster services | Deployed as pod with route in `data-strat-poc` namespace | M5 adds deployment manifests for both M4 (underwriter_chat) and M5 (compliance_review_agent). MCP server deploys as separate pod. | Open |

## OGX / Agentic RAG

Issues with OGX (Llama Stack) deployment, agentic query orchestration, and MCP tool integration.

| ID | Gap | Why It Exists | Production Standard | Path to Close | Status |
|----|-----|---------------|---------------------|---------------|--------|
| PG-054 | OGX Responses API is Dev Preview | RHOAI 3.4 marks Responses API as experimental/dev preview | GA Responses API with stable OpenAI compatibility | Track OGX maturity in RHOAI releases | Open |
| PG-055 | No OTel trace context propagation to MCP tools | OGX has `forward_headers` for auth but no automatic OpenTelemetry `traceparent` forwarding | Full distributed tracing across OGX → MCP tool calls | Upstream feature request to Llama Stack; or client-side reconstruction (DEC-012 strategy) | **Mitigated** (DEC-012) |
| PG-056 | MCP server downloads embedding model on startup | Same as PG-019 — `sentence-transformers` downloads from HuggingFace on each pod restart | Pre-loaded model on PVC | Share PVC-cached model between M4 MCP server and M5 MCP server | Open |
| PG-057 | OGX agent may skip tool calls (like PG-047) | LLMs may answer from parametric knowledge without searching, bypassing retrieval | Mandatory retrieval before generation | Monitor via MLflow traces; system prompt hardening; evaluate `tool_choice: "required"` | Open |
| PG-058 | No streaming support in M5 Chainlit app | M5 app uses non-streaming Responses API call | Streaming responses for better UX | Add `stream=True` to `client.responses.create()` and stream chunks to Chainlit | Open |
| PG-059 | Two separate Chainlit apps for POC | M4 (underwriter_chat) and M5 (compliance_review_agent) are separate apps | Single app with workflow selector | Combine into one Chainlit app with dropdown: deterministic vs agentic | Open |
| PG-060 | No autolog verification for Responses API | `mlflow.openai.autolog()` may not fully capture Responses API tool call rounds | Verified autolog coverage with child spans for each tool call | Hands-on verification; fall back to manual spans if needed | Open |

---

## Summary by Area

| Area | Count | Closed/Mitigated | Open |
|------|-------|------------------|------|
| KFP / Pipelines Platform | 2 | 1 (mitigated) | 1 |
| Ray / RayData / Docling | 2 | 0 | 2 |
| Milvus / Vector Storage | 5 | 0 | 5 |
| Embedding / Model Serving | 2 | 1 (mitigated) | 1 |
| Lineage / Observability | 9 | 4 (PG-009, PG-024, PG-025 closed; PG-023 deferred) | 5 |
| Connectors / Data Ingestion | 3 | 1 (PG-020 closed) | 2 |
| Security / Platform | 2 | 0 | 2 |
| Document Registry / Identity | 13 | 1 (PG-037 closed) | 12 |
| Infrastructure / Operations | 3 | 0 | 3 |
| Query / Chat | 12 | 3 (PG-047 closed, PG-051 mitigated) | 9 |
| OGX / Agentic RAG | 7 | 1 (PG-055 mitigated) | 6 |
| **Total** | **60** | **12** | **48** |
