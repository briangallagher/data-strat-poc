# RAG Ingest Pipeline: Documents → Collections → Vector DB

## Pipeline Flow

```mermaid
flowchart LR
    %% ── Source Documents ──
    subgraph docs["Source Documents (S3/MinIO)"]
        direction TB
        ug_docs["📄 Underwriting Guidelines<br/><i>NY DFS circulars, rating manuals,<br/>program bulletins</i><br/><b>10 documents</b>"]
        iso_docs["📄 ISO / ACORD Forms<br/><i>CG 00 01, CP 00 10,<br/>endorsements, applications</i><br/><b>5 documents</b>"]
        rb_docs["📄 Regulatory Bulletins<br/><i>State DOI bulletins, NAIC<br/>model laws, filing instructions</i><br/><b>7 documents</b>"]
    end

    %% ── Collection Grouping ──
    subgraph groups["Logical Collections"]
        direction TB
        ug_col["underwriting_guidelines<br/><code>prefix: ug</code>"]
        iso_col["iso_forms<br/><code>prefix: if</code>"]
        rb_col["regulatory_bulletins<br/><code>prefix: rb</code>"]
    end

    %% ── Pipeline (one run per collection) ──
    subgraph pipeline["KFP Pipeline (per collection)"]
        direction TB
        step1["<b>1. Acquire Documents</b><br/>Pull from S3 → staging<br/>Register in Doc Registry<br/>Emit OpenLineage → Marquez"]
        step2["<b>2. Parse & Chunk</b><br/>RayData + Docling<br/>Layout-aware parsing<br/>Section-level chunking<br/>256 max tokens/chunk"]
        step3["<b>3. Ingest to Milvus</b><br/>Embed with Granite 125M<br/>768-dim vectors<br/>Store vectors + metadata"]
        step1 --> step2 --> step3
    end

    %% ── Vector DB ──
    subgraph milvus["Milvus (Single Instance)"]
        direction TB
        m_ug["<b>underwriting_guidelines</b><br/>363 entities<br/>HNSW index, cosine"]
        m_iso["<b>iso_forms</b><br/>11 entities<br/>HNSW index, cosine"]
        m_rb["<b>regulatory_bulletins</b><br/>93 entities<br/>HNSW index, cosine"]
    end

    %% ── Connections ──
    ug_docs --> ug_col
    iso_docs --> iso_col
    rb_docs --> rb_col

    ug_col --> step1
    iso_col --> step1
    rb_col --> step1

    step3 --> m_ug
    step3 --> m_iso
    step3 --> m_rb

    %% ── Styling ──
    classDef source fill:#f9f0ff,stroke:#7c3aed
    classDef collection fill:#eff6ff,stroke:#2563eb
    classDef pipeline fill:#f0fdf4,stroke:#16a34a
    classDef vectordb fill:#fef3c7,stroke:#d97706

    class ug_docs,iso_docs,rb_docs source
    class ug_col,iso_col,rb_col collection
    class step1,step2,step3 pipeline
    class m_ug,m_iso,m_rb vectordb
```

## Key Points

- **One Milvus instance**, three collections — not three separate databases
- **One pipeline definition**, run three times (once per collection) with different parameters
- Each collection has its own schema, lifecycle, and doc ID prefix
- The agent later performs **multi-hop retrieval** by searching across collections independently and cross-referencing results

## Entity Per Collection

| Collection | Documents | Chunks (Entities) | Doc ID Prefix |
|---|---|---|---|
| `underwriting_guidelines` | 10 | 363 | `ug-` |
| `iso_forms` | 5 | 11 | `if-` |
| `regulatory_bulletins` | 7 | 93 | `rb-` |

## Each Entity Stores

```
┌─────────────────────────────────────────────────┐
│ Milvus Entity (one per chunk)                   │
├─────────────────────────────────────────────────┤
│ embedding        float[768]  ← Granite 125M    │
│ text             varchar     ← raw chunk text   │
│ doc_id           varchar     ← e.g. "ug-001"   │
│ pipeline_run_id  varchar     ← provenance link  │
│ chunk_index      int         ← position in doc  │
│ section_path     varchar     ← heading hierarchy│
│ page_numbers     varchar     ← source pages     │
│ category         varchar     ← document category│
│ subcategory      varchar     ← sub-classification│
└─────────────────────────────────────────────────┘
```
