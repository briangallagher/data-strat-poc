# Lineage Questions — What Can Be Answered Today

The M3 milestone established a three-system lineage architecture (Registry + Marquez + MLflow) with per-document identity on every Milvus vector. This doc catalogues the business-level questions that can now be answered, which system answers them, and how accessible the answer is.

**UX Rating Scale:** 5 = seamless self-service UI · 4 = UI with minor friction · 3 = API call or simple UI lookup · 2 = CLI/script required · 1 = developer with multi-system knowledge required

---

## Questions Answerable Today

### 1. Which Milvus collections use this remote document?

| | |
|---|---|
| **Persona** | Data Engineer, Compliance Officer |
| **How** | Registry API `GET /documents/{doc_id}` — returns `collections` array |
| **UX** | ★★★☆☆ (3/5) — API call, or browse in Registry UI at `localhost:8080` |

### 2. Which vectors came from this document?

| | |
|---|---|
| **Persona** | Data Engineer |
| **How** | Milvus query: `source_document_id == "{doc_id}"` via pymilvus |
| **UX** | ★★☆☆☆ (2/5) — requires pymilvus client or a custom script; no UI path |

### 3. What document and chunk does this vector come from?

| | |
|---|---|
| **Persona** | Data Engineer, ML Engineer |
| **How** | Read vector metadata (`source_document_id`, `chunk_index`) → Registry `GET /documents/{doc_id}` |
| **UX** | ★★☆☆☆ (2/5) — `trace.py` script automates the multi-hop lookup |

### 4. What's the full provenance chain of a vector?

| | |
|---|---|
| **Persona** | Compliance Officer, Data Engineer |
| **How** | `trace.py --vector X --chunk N` — chains vector → document → source URL → pipeline run → Marquez lineage |
| **UX** | ★★☆☆☆ (2/5) — CLI-only, requires port-forward to Milvus and Registry |

### 5. What documents are in this collection?

| | |
|---|---|
| **Persona** | Data Engineer, Data Scientist |
| **How** | Registry API `GET /collections/{name}` — returns document list with metadata |
| **UX** | ★★★☆☆ (3/5) — API call or Registry UI collection browser |

### 6. Which pipeline run created these vectors?

| | |
|---|---|
| **Persona** | ML Engineer, Data Engineer |
| **How** | Read `pipeline_run_id` from vector metadata → look up in KFP, MLflow, or Marquez |
| **UX** | ★★☆☆☆ (2/5) — cross-system manual lookup; no single place to paste a run ID |

### 7. What was the data flow for a pipeline run?

| | |
|---|---|
| **Persona** | ML Engineer, Platform Engineer |
| **How** | Marquez Web UI → select job → view lineage graph (input datasets → job → output datasets) |
| **UX** | ★★★★☆ (4/5) — Marquez lineage graph is visual and navigable |

### 8. How long did each step take?

| | |
|---|---|
| **Persona** | ML Engineer, Platform Engineer |
| **How** | MLflow UI → select experiment → expand parent run → nested child runs show per-step duration |
| **UX** | ★★★☆☆ (3/5) — MLflow UI works well once you find the right experiment/workspace |

### 9. Is this document used in multiple collections?

| | |
|---|---|
| **Persona** | Data Engineer, Compliance Officer |
| **How** | Registry `GET /documents/{doc_id}` → check `collections` array length. Marquez unified graph also shows cross-collection edges. |
| **UX** | ★★★☆☆ (3/5) — straightforward API check; Marquez graph gives visual confirmation |

### 10. What's the source system URL for any vector?

| | |
|---|---|
| **Persona** | Data Engineer, Compliance Officer |
| **How** | Vector metadata → `source_document_id` → Registry `GET /documents/{doc_id}` → `source_url` |
| **UX** | ★★☆☆☆ (2/5) — multi-hop lookup; `trace.py` automates but still CLI-only |

### 11. Has this document been re-ingested?

| | |
|---|---|
| **Persona** | Data Engineer |
| **How** | Registry `GET /documents/{doc_id}` → `last_ingested` timestamp + `ingestion_count` |
| **UX** | ★★★☆☆ (3/5) — single API call or Registry UI lookup |

---

## Summary

| UX Rating | Count | Questions |
|-----------|-------|-----------|
| ★★★★☆ (4/5) | 1 | Pipeline data flow (Marquez graph) |
| ★★★☆☆ (3/5) | 5 | Collection contents, document lookup, re-ingestion, step timing, cross-collection usage |
| ★★☆☆☆ (2/5) | 5 | Vector-level queries, provenance chains, source URL tracing, pipeline run lookup |

**Median UX: 3/5** — most questions are answerable but require API calls, CLI scripts, or cross-system lookups. Only pipeline-level lineage (Marquez) has a genuinely good UI experience.

---

## Questions NOT Yet Answerable

| Question | Why Not | When |
|----------|---------|------|
| Which documents answered this specific user query? | No query audit logging — RAG queries are not traced | M4 |
| What answer was generated from these documents? | No RAG query layer capturing generated responses | M4 |
| Is this document outdated or superseded? | Document versioning exists (PG-026) but not exercised in pipelines | M5 |
| Which users accessed this document via AI assistant? | No RBAC or user-level access tracking | M5 |
| Are there new docs in the source we haven't registered? | No source discovery/sync mechanism (PG-033) | M5 |
