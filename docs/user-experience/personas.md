# Personas

Persona definitions for the Scenario B P&C Underwriting Knowledge Assistant. Each persona represents a distinct user type with different goals, technical literacy, and interaction patterns.

**Last Updated:** 2026-05-22 (M0 — initial draft from Scenario B spec)

---

## Underwriter

**Role:** P&C insurance underwriter evaluating risks and writing policies.

**Goal:** Quickly find accurate, cited answers from underwriting guidelines, ISO forms, and regulatory bulletins without manually searching document repositories.

**Technical Literacy:** Low-to-moderate. Uses web UIs, not CLIs. Expects a chat-like interface.

**Pain Points:**
- Spends ~40% of time on manual document lookup
- Documents scattered across SharePoint, email, shared drives
- Version inconsistency — unsure if using the current guideline
- Role-siloed access — can't see documents from other departments

**Key Interactions:** UC-002 (Deterministic RAG), UJ-001

---

## Compliance Officer

**Role:** Reviews underwriting practices against regulatory requirements and internal standards.

**Goal:** Run structured compliance reviews across multiple document collections, identifying deviations between internal guidelines and regulatory standards.

**Technical Literacy:** Moderate. Comfortable with structured reports but not technical tooling.

**Pain Points:**
- Multi-document comparison is manual and time-consuming
- Regulatory changes require re-reviewing all affected guidelines
- Audit trail requirements mean every finding must be traceable to source documents

**Key Interactions:** UC-003 (Agentic Review), UJ-003

---

## Data Engineer

**Role:** Manages the document processing pipeline — ingestion, processing, storage, monitoring.

**Goal:** Run and monitor the ingest pipeline reliably, troubleshoot failures, and ensure data quality.

**Technical Literacy:** High. Uses CLI, Kubernetes, KFP, monitoring tools.

**Pain Points:**
- Pipeline failures require manual investigation
- No lineage visibility — hard to trace what data is in which Milvus collection
- Scaling from small corpus to enterprise corpus is manual

**Key Interactions:** UC-001 (Document Ingest), UJ-002

---

## Platform Administrator

**Role:** Manages the RHOAI cluster, deploys and maintains infrastructure components.

**Goal:** Deploy, configure, and maintain all system components with production-grade security, monitoring, and RBAC.

**Technical Literacy:** High. OpenShift, Kubernetes, operators, Helm.

**Pain Points:**
- Multiple components with different deployment mechanisms
- Security and RBAC configuration across components
- Resource management (GPU allocation, storage, compute)

**Key Interactions:** Operations docs (prerequisites, getting started, troubleshooting)
