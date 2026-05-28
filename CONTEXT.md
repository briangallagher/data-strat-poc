# Data Strategy POC v2

The data platform proving enterprise RAG patterns on RHOAI: document ingestion, vector storage, lineage, and governance for a P&C underwriting knowledge assistant.

## Language

### Core Entities

**Document**:
A single file (PDF, DOCX, HTML) with a stable identity (`doc_id`) in the Document Registry. A Document is always a file — 1:1 mapping between `doc_id` and a physical file artifact.
_Avoid_: Dataset (too broad — used in OpenLineage for any data artifact), Asset, Record

**Collection**:
A logical grouping of **Documents** that will be ingested into a single Milvus vector collection. A Document can belong to multiple Collections. A Collection is the unit of pipeline execution — one pipeline run per Collection.
_Avoid_: Corpus (historical term from v1 — replaced by Collection), Index, Bucket

**Document Registry**:
The FastAPI + PostgreSQL service that owns canonical **Document** identity, stores metadata, and tracks **Collection** membership. The registry is a claim about what exists — not a guarantee. It is the authority the ingest pipeline trusts.
_Avoid_: Catalog (implies browsing/discovery — that's a future concern), Index, Metadata Store

### Identity

**doc_id**:
A stable, human-friendly identifier for a **Document** (e.g., `ug-005`). Persists across pipeline runs, file moves, and source system changes. Auto-generated from the Collection's `doc_id_prefix` + sequential number. The OpenLineage dataset name is derived from `doc_id`.
_Avoid_: source_document_id (v1/v2 legacy — filename-derived, fragile), file_id, asset_id

**source_url**:
The canonical external URL where a **Document** physically lives (S3 key, SharePoint URL, Confluence page URL). Can change when documents move — the `doc_id` remains stable.
_Avoid_: URI (too generic), path, location

**pipeline_run_id**:
A UUID generated once per pipeline execution. The cross-system correlation key linking KFP, Marquez, MLflow, and Milvus vectors. Every vector in Milvus carries its `pipeline_run_id`.
_Avoid_: run_id (ambiguous — KFP has its own run_id), execution_id, trace_id

### Concerns

**Connecting**:
The capability of accessing remote source systems — authenticate, fetch files to staging. Implemented by the Connector ABC. Connectors have no knowledge of Collections, Milvus, or routing.
_Avoid_: Ingestion (too broad — includes parsing and embedding), Acquisition (legacy v1 term that implied routing)

**Registering**:
The capability of assigning stable identity, storing metadata, and tracking Collection membership. Implemented by the Document Registry service.
_Avoid_: Cataloging (implies discovery, which is a separate workflow)

**Building a Collection**:
The human or agent decision about which **Documents** belong in a **Collection**. A curation step separate from Connecting and Registering.
_Avoid_: Routing (implies automation — building is a deliberate decision), Curating (acceptable synonym but "building" is our canonical term)

### Workflows

**Discovery Workflow**:
An operational workflow that uses **Connecting** to scan source systems and **Registering** to update the registry. Detects new, changed, or removed documents. Not built in M3 (PG-033).
_Avoid_: Sync, Crawl (implies web crawling)

**Ingest Workflow**:
An operational workflow that uses **Connecting** to fetch documents and **Registering** for identity/metadata. Processes documents into Milvus. One pipeline run per **Collection**.
_Avoid_: Pipeline (too generic — we use "pipeline" for the KFP DAG, "ingest workflow" for the broader concern)

**Manifest**:
A JSON file written to S3 staging by `acquire_documents` containing per-document metadata for the current pipeline run. The transfer mechanism between the registry and the Ray workers. Currently a pass-through; versioned record is a future concern (PG-034).
_Avoid_: Config, Metadata file

### Pipeline Components

**acquire_documents**:
The first KFP component in the ingest pipeline. Queries the registry for collection members, fetches files from source systems, writes the manifest. Does NOT discover new documents — only fetches what the registry explicitly lists (ADR-010). Sole emitter of OpenLineage events to Marquez (ADR-011).
_Avoid_: fetch_documents (acceptable but "acquire" is our canonical term from v1)

**parse_and_chunk**:
The second KFP component. Uses RayData + Docling to parse documents and create chunks. Reads per-document metadata from the manifest.
_Avoid_: process_documents

**ingest_to_milvus**:
The third KFP component. Embeds chunks and writes vectors to the target Milvus collection.
_Avoid_: embed_and_store, vectorize

### Query

**Application**:
A named query service that consumes one or more **Collections** via Milvus search and serves answers to users. Each Application is registered in Marquez as an OpenLineage job with its consumed Collections as inputs. Examples: `underwriter_chat`, `compliance_review_agent`.
_Avoid_: Agent (overloaded — refers to the LLM orchestration pattern, not the deployed service), Service (too generic)

**Deterministic Query Workflow**:
A query workflow where the application controls retrieval — the code decides what to search, when, and how many times. The LLM generates an answer from the retrieved context but does not decide the retrieval strategy. Workflow A in Scenario B.
_Avoid_: Simple RAG, Basic RAG (implies inferior — deterministic is a deliberate design choice)

**Agentic Query Workflow**:
A query workflow where the LLM autonomously decides what to retrieve. The agent plans a retrieval strategy, executes multiple searches across different **Collections**, cross-references results, and synthesizes an answer. Workflow B in Scenario B.
_Avoid_: Multi-hop RAG (describes one technique, not the full pattern), Advanced RAG

## Example Dialogues

### Ingest

**Domain expert (underwriting ops):** "We just got 3 new California bulletins from the DOI. They need to go into the regulatory collection."

**Developer:** "I'll register them in the Document Registry — they'll get doc_ids with the `rb-` prefix. Then I'll assign them to the `regulatory_bulletins` collection via the UI. Next time the ingest pipeline runs for that collection, `acquire_documents` will pick them up."

**Domain expert:** "What if one of those bulletins is also relevant to the underwriting guidelines?"

**Developer:** "I can assign it to both collections. It'll get processed in both pipeline runs and its vectors will exist in both Milvus collections. The lineage graph will show it feeding into two separate paths."

**Domain expert:** "And if California moves the bulletin URL next month?"

**Developer:** "The `doc_id` stays the same — we just update the `source_url` in the registry. All existing lineage and vectors still reference the same identity. That's what the registry is for."

### Query

**Compliance officer:** "The agent reviewed our GL guidelines and flagged 3 deviations from the ISO CG 00 01 standard. How do I know it actually checked the right documents?"

**Developer:** "Every query creates an MLflow trace. Open the Registry UI, go to Queries, and click the trace. It shows which collections were searched — in this case `underwriting_guidelines` and `iso_forms` — which doc_ids were cited, and the pipeline_run_id for each retrieved chunk."

**Compliance officer:** "And the pipeline_run_id tells me what?"

**Developer:** "It links back to the exact ingest run that created those vectors. Click through to the Marquez lineage graph and you can see the full chain — which source files were fetched, when they were parsed, and when they were embedded into Milvus. So you can verify the agent was working with the January 2026 version of the GL guidelines, not an older one."

**Compliance officer:** "What if I want to know every query that ever cited a specific document?"

**Developer:** "That's the reverse lookup. Go to the document's provenance page in the Registry UI — it shows every query trace that cited that doc_id. You can see who asked what, when, and what answer they got."
