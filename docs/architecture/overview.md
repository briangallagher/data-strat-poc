# Architecture Overview

High-level architecture for the Scenario B P&C Underwriting Knowledge Assistant on RHOAI.

**Last Updated:** 2026-05-28 (M5 complete)

## System Context (C4 Level 1)

What the system is, who uses it, and what external systems it interacts with.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#E8F4FD', 'secondaryColor': '#FFF3E0', 'tertiaryColor': '#E8F5E9', 'lineColor': '#546E7A', 'textColor': '#212121'}, 'flowchart': {'curve': 'linear', 'rankSpacing': 60, 'padding': 20}}}%%
flowchart TB
    subgraph users ["Users"]
        UW["Underwriter"]
        CO["Compliance Officer"]
        DE["Data Engineer"]
        PA["Platform Admin"]
    end

    subgraph system ["Scenario B Knowledge Assistant"]
        KB["Knowledge Assistant\n(RHOAI on OpenShift)"]
    end

    subgraph sources ["Document Sources"]
        SP["SharePoint"]
        CF["Confluence"]
        S3["S3 / MinIO"]
        DMS["Document Mgmt Systems"]
    end

    subgraph external ["External Services"]
        HF["HuggingFace\n(model downloads)"]
        REG["Container Registries\n(quay.io, registry.redhat.io)"]
    end

    UW -->|"query guidelines"| KB
    CO -->|"request compliance review"| KB
    DE -->|"run ingest pipeline"| KB
    PA -->|"deploy and manage"| KB

    sources -->|"documents"| KB
    KB -->|"cited answers"| UW
    KB -->|"compliance reports"| CO

    HF -->|"model weights"| KB
    REG -->|"container images"| KB

    classDef userNode fill:#E3F2FD,stroke:#1565C0,color:#212121
    classDef systemNode fill:#E8F5E9,stroke:#2E7D32,color:#212121
    classDef sourceNode fill:#FFF3E0,stroke:#E65100,color:#212121
    classDef extNode fill:#F3E5F5,stroke:#6A1B9A,color:#212121

    class UW,CO,DE,PA userNode
    class KB systemNode
    class SP,CF,S3,DMS sourceNode
    class HF,REG extNode
```

**Reading guide:**
- Green = the system boundary (what we're building)
- Blue = user personas (see `docs/user-experience/personas.md`)
- Orange = document sources (connectors, M3)
- Purple = external dependencies

## Container View (C4 Level 2)

Deployable units within the system and how they interact.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#E8F4FD', 'secondaryColor': '#FFF3E0', 'tertiaryColor': '#E8F5E9', 'lineColor': '#546E7A', 'textColor': '#212121'}, 'flowchart': {'curve': 'linear', 'rankSpacing': 50, 'padding': 15}}}%%
flowchart TB
    subgraph ingest ["Ingest Pipeline (M1)"]
        KFP["KFP Pipeline\n(DSPA)"]
        RAY["RayData + Docling\n(KubeRay)"]
        EMB_SVC["Embedding Service\n(vLLM / KServe)"]
    end

    subgraph storage ["Data Storage"]
        MILVUS["Milvus\n(Vector DB)"]
        MINIO["MinIO / S3\n(Object Store)"]
        PG["PostgreSQL\n(Metadata)"]
    end

    subgraph query ["Query Path (M4 + M5)"]
        LANG["LangGraph Agent\n(Deterministic RAG)"]
        MCP_Q["MCP Server\n(Milvus tools)"]
        OGX["OGX\n(Agentic RAG via vLLM)"]
        LLM["Hermes 70B FP8\n(vLLM Deployment)"]
        UI["Chainlit\n(Compliance Review)"]
    end

    subgraph registry ["Registry"]
        REG_SVC["Document Registry\n(FastAPI + React)"]
    end

    subgraph observability ["Observability (M2)"]
        MLFLOW["MLflow\n(Tracking)"]
        MARQUEZ["Marquez\n(Lineage)"]
    end

    subgraph connectors ["Connectors (M3)"]
        CONN["Connector Framework\n(S3, Confluence, SharePoint)"]
    end

    CONN -->|"documents"| MINIO
    MINIO -->|"staged docs"| KFP
    KFP -->|"orchestrates"| RAY
    RAY -->|"parsed chunks"| MINIO
    MINIO -->|"chunks"| KFP
    KFP -->|"embed + insert"| MILVUS
    KFP -->|"embed"| EMB_SVC

    UI -->|"deterministic query"| LANG
    UI -->|"agentic query"| OGX
    LANG -->|"tool call"| MCP_Q
    OGX -->|"tool call (MCP/SSE)"| MCP_Q
    MCP_Q -->|"search"| MILVUS
    LANG -->|"generate"| LLM
    OGX -->|"generate"| LLM

    KFP -->|"run tracking"| MLFLOW
    KFP -->|"lineage events"| MARQUEZ
    OGX -->|"query traces"| MLFLOW
    LANG -->|"query traces"| MLFLOW

    REG_SVC -->|"read"| PG
    REG_SVC -->|"provenance"| MLFLOW
    REG_SVC -->|"lineage"| MARQUEZ

    MLFLOW --> PG
    MARQUEZ --> PG

    classDef ingestNode fill:#E3F2FD,stroke:#1565C0,color:#212121
    classDef storageNode fill:#FFF3E0,stroke:#E65100,color:#212121
    classDef queryNode fill:#E8F5E9,stroke:#2E7D32,color:#212121
    classDef obsNode fill:#F3E5F5,stroke:#6A1B9A,color:#212121
    classDef connNode fill:#FFEBEE,stroke:#C62828,color:#212121
    classDef regNode fill:#FFF8E1,stroke:#F9A825,color:#212121

    class KFP,RAY,EMB_SVC ingestNode
    class MILVUS,MINIO,PG storageNode
    class LANG,MCP_Q,OGX,LLM,UI queryNode
    class MLFLOW,MARQUEZ obsNode
    class CONN connNode
    class REG_SVC regNode
```

**Reading guide:**
- Blue = ingest pipeline components (M1)
- Orange = storage layer
- Green = query path components (M4 + M5)
- Yellow/Amber = registry
- Purple = observability (M2)
- Red = connectors (M3)
- Data flows left-to-right for ingest, top-to-bottom for query

## Component Inventory

| Component | Technology | Milestone | Deployment | Purpose |
|-----------|-----------|-----------|------------|---------|
| KFP Pipeline | Kubeflow Pipelines v2 | M1 | DSPA (RHOAI) | Orchestrates ingest workflow |
| RayData + Docling | Ray 2.x, Docling | M1 | RayJob (KubeRay) | Distributed PDF parsing and chunking |
| Embedding Service | vLLM, Granite Embedding | M1 | KServe InferenceService | Vector embedding generation |
| Milvus | Milvus 2.4+ | M1 | Helm (Certified Partner) | Vector storage and similarity search |
| MinIO / S3 | MinIO | M1 | Deployment | Object storage for documents and artifacts |
| MLflow | MLflow 2.x | M2 | Deployment | Experiment tracking, query-time tracing |
| Marquez | Marquez 0.51+ | M2 | Deployment | OpenLineage backend, lineage graph |
| PostgreSQL | PostgreSQL 15+ | M2 | Deployment | Backend for MLflow and Marquez |
| Connector Framework | Python (pip package) | M3 | KFP component | Data source acquisition |
| OGX | OGX (RHOAI) | M5 | RHOAI managed | Agentic RAG via Responses API with server-side MCP tool execution |
| Hermes 70B FP8 | NousResearch/Hermes-3-Llama-3.1-70B-FP8, vLLM | M5 | Raw Kubernetes Deployment | LLM inference for answer generation (native tool calling) |
| Chainlit | Chainlit 1.x | M4 | Deployment | Chat-based UI for both deterministic and agentic RAG |
| LangGraph Agent | LangGraph, LangChain | M4 | Part of Chainlit pod | Deterministic RAG agent with fixed retrieve-then-generate graph |
| MCP Server | FastMCP (Python) | M4 | Deployment | Tool server exposing Milvus search via SSE for both LangGraph and OGX |
| Document Registry | FastAPI, PostgreSQL, React | M3 | Deployment | Document identity, collection management, provenance portal |

## Data Flow

### Ingest Path (M1 + M3)

```
Document Sources → [Connectors] → S3 Staging → [KFP] → RayData+Docling (parse/chunk)
    → S3 (JSONL chunks) → [KFP] → Embedding Service → Milvus (vectors + metadata)
```

Each vector in Milvus carries:
- `pipeline_run_id` — links to KFP run and lineage graph
- `source_document_id` — links to source document
- `chunk_text` — raw text for retrieval
- Standard metadata (LOB, doc type, effective date, etc.)

### Query Path (M4 + M5)

```
Workflow A (Deterministic RAG — M4):
User Query → Chainlit → LangGraph Agent → MCP Server → Milvus (single collection)
    → Hermes 70B FP8 (cited answer generation) → User

Workflow B (Agentic RAG — M5):
User Query → Chainlit → OGX Responses API → MCP Server (SSE) → Milvus (all 3 collections, multi-hop)
    → Hermes 70B FP8 (synthesized compliance review) → User
```

### Lineage Path (M2+)

```
Pipeline time: KFP steps → OpenLineage events → Marquez (pipeline lineage graph)
Query time: OGX queries → MLflow spans (with pipeline_run_id bridge) → MLflow
Auditor: MLflow trace → pipeline_run_id → Marquez graph → source documents
```

## Key Design Decisions

| Decision | ADR | Summary |
|----------|-----|---------|
| RayData + Docling pipeline design | ADR-001 | <!-- TODO: decided in M0/M1 --> |
| Chunking strategy and Milvus ingestion | ADR-002 | <!-- TODO: decided in M1 --> |
| OGX role (ingest vs query) | ADR-003 | <!-- TODO: decided in M0/M1 --> |
| Lineage architecture | ADR-004 | <!-- TODO: decided in M2 --> |
| Connector architecture | ADR-005 | <!-- TODO: decided in M3 --> |
| MLflow integration approach | ADR-006 | <!-- TODO: decided in M2 --> |
| Multi-repo strategy | ADR-007 | <!-- TODO: decided in M0 --> |

## Future Considerations

- **Multi-tenancy:** current design is single-namespace. Production would need namespace-per-tenant or Milvus partition-per-tenant with RBAC.
- **Hybrid search:** Milvus supports both dense and sparse vectors. Current design uses dense only. Hybrid search (BM25 + dense) improves recall for keyword-heavy queries.
- **Catalog integration:** OpenMetadata or Unity Catalog for dataset discovery. Deferred to post-M5 evaluation.
- **Lineage operator:** Kubernetes operator for Marquez lifecycle (CRD + Helm rendering, following MLflow operator pattern). Stretch goal.
- **Incremental processing:** Re-process only changed documents. Requires document version tracking and change detection.

## References

| Source | Link |
|--------|------|
| DataStrategy Scenario B | [scenario-b-underwriting-knowledge.md](https://github.com/abiazett/DataStrategy/blob/main/data-strategy-proposal/scenarios/scenario-b-underwriting-knowledge/scenario-b-underwriting-knowledge.md) |
| Five-pillar strategy | [RHAI-data-strategy-proposal.md](https://github.com/abiazett/DataStrategy/blob/main/data-strategy-proposal/RHAI-data-strategy-proposal.md) |
| v1 POC architecture | [data-strategy-poc/docs/architecture.md](https://github.com/briangallagher/data-strategy-poc/blob/main/docs/architecture.md) |
| Saad's pipeline components | [pipelines-components #53](https://github.com/opendatahub-io/pipelines-components/pull/53) |
| ET lineage demo | [lineage-demo-pipeline](https://github.com/rh-waterford-et/lineage-demo-pipeline) |
