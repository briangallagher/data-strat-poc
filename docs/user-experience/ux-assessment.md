# UX Assessment — Lineage and Provenance

Post-M3 assessment of the user experience for answering provenance questions across the three-system lineage architecture. Rates each system, identifies gaps, and recommends the path forward for M4.

---

## Current UX Rating by System

| System | What It Provides | UX Rating | Limitation |
|--------|-----------------|-----------|------------|
| **Registry API** | Document identity, collection membership, source URLs, ingestion history | ★★★☆☆ (3/5) | REST-only for most queries; useful but requires tooling or scripting to consume |
| **Registry UI** (`localhost:8080`) | Browse documents, collections, ingestion status; PatternFly-based | ★★★☆☆ (3/5) | Functional for browsing but no tracing/provenance views; localhost-only |
| **Marquez Web UI** | Pipeline lineage graph, job runs, dataset relationships | ★★★★☆ (4/5) | Best visual experience; limited by namespace scattering and no document-level context |
| **MLflow UI** | Experiment tracking, nested run timing, parameters, metrics | ★★★☆☆ (3/5) | Requires knowing which workspace/experiment to look in; no direct link from pipeline run ID |
| **Milvus** (pymilvus) | Vector-level metadata queries, identity fields on every vector | ★★☆☆☆ (2/5) | No UI; requires Python client and port-forward; raw query interface |
| **`trace.py`** | End-to-end provenance chain: vector → document → source → pipeline | ★★☆☆☆ (2/5) | Automates the multi-hop lookup but CLI-only, requires port-forward to multiple services |
| **`vector-provenance.py`** | Batch provenance export, collection-level provenance summary | ★★☆☆☆ (2/5) | Batch-oriented; useful for audits but not interactive; CLI-only |

**Overall median: 3/5** — engineering-usable, not business-user-ready.

---

## UX Gaps

### Gap 1: No Unified Provenance UI

Answering "full provenance of this vector" requires three systems (Milvus → Registry → Marquez). Each has its own interface, authentication, and mental model. A single **Provenance Dashboard** — or extension to the Registry UI that federates all three — would bring this from 2/5 to 5/5.

**Impact:** High — this is the most common compliance/audit question.

### Gap 2: Marquez Datasets Scattered Across Namespaces

The Marquez Web UI requires switching the namespace dropdown to find documents. Datasets created by different pipeline runs land in different namespaces. Non-obvious for anyone who didn't set up the system.

**Options:**
- Consolidate to a single namespace (simplest, may lose useful separation)
- Build a custom lineage viewer that queries across namespaces
- Add namespace guidance to Marquez UI via a landing page or README

### Gap 3: No Query-Time Tracing (M4)

The most important business question — *"what documents informed this answer?"* — cannot be answered until M4 adds query audit logging. This is the gap between "data lineage" (what we have) and "answer provenance" (what business users want).

**Impact:** Critical — blocks the primary compliance use case.

### Gap 4: CLI-Only for Vector-Level Tracing

`trace.py` and `vector-provenance.py` work correctly but require:
- Port-forwarding to Milvus, Registry, and Marquez
- Python environment with pymilvus installed
- Knowledge of document IDs and chunk indices

This excludes non-developer personas entirely.

### Gap 5: MLflow Workspace Navigation

Users must know to select the `data-strat-poc` workspace in MLflow, then find the right experiment. Parent run naming (`ingest/{collection}/{timestamp}`) helps but only if you know which experiment to look in. No deep-link from a pipeline run ID.

---

## Recommendations

### Option A: Extend Registry UI *(recommended for M4)*

Add pages to the existing PatternFly UI:

| Page | Function |
|------|----------|
| **Trace Document** | Enter `doc_id` → see all collections, vector count, pipeline runs, source URL, ingestion history |
| **Trace Vector** | Enter `doc_id` + chunk index → full provenance chain with text preview and Marquez lineage link |
| **Collection Health** | Per-collection stats: document count, vector count, last ingested, staleness indicators |
| **Lineage Graph** | Embed Marquez lineage view (iframe or API-driven render; page scaffold already exists) |

**Pros:** Lowest incremental effort — Registry UI already exists with PatternFly, has API access to all backend systems, and is the natural "entry point" for provenance questions.

**Cons:** Couples the Registry UI to Marquez and MLflow APIs; needs careful error handling when backends are unavailable.

### Option B: Dedicated Provenance App

Separate service that federates Registry + Marquez + MLflow + Milvus behind a unified GraphQL or REST API with its own UI.

**Pros:** Clean separation of concerns; could serve multiple projects.
**Cons:** Significant additional build/maintain cost; premature for a PoC.

### Option C: Status Quo (MLflow + Marquez + CLI)

For engineering teams comfortable with multiple tools, the current setup is functional.

**Pros:** No additional build.
**Cons:** Not suitable for business users, compliance officers, or demo audiences. Limits the PoC's ability to demonstrate enterprise-readiness.

### Recommendation

**Option A for M4.** The Registry UI already exists, has the API connections, and PatternFly supports the additional pages with minimal framework overhead. The Registry becomes the single pane of glass for provenance questions. Marquez and MLflow remain as backend systems, but users interact primarily through the Registry UI.

---

## What Needs a UI vs What's Fine as API/CLI

| Capability | Needs UI? | Why |
|------------|-----------|-----|
| Document lookup (by ID or source URL) | **Yes** | Most common entry point; used by all personas |
| Collection browsing | **Yes** | Frequent; needs filtering, sorting, status indicators |
| Full provenance tracing (vector → source) | **Yes** | Multi-hop; impossible to expect non-developers to chain API calls |
| Pipeline run monitoring | **No** — MLflow/KFP sufficient | Engineers already use these tools; duplicating adds maintenance |
| Vector-level search/query | **No** — API/CLI acceptable | Low-frequency, developer-only use case |
| Lineage graph visualisation | **Yes** (embed) | Visual by nature; Marquez graph is good but needs to be reachable from Registry UI |
| MLflow metrics/parameters | **No** — MLflow UI sufficient | MLflow's own UI handles this well; link to it from Registry |
| Batch provenance export (audit) | **No** — CLI acceptable | Infrequent, typically scripted into CI/compliance pipelines |
| Document staleness/freshness | **Yes** | Operational monitoring; should be visible at a glance on Collection Health page |
