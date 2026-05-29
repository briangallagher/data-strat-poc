# UC-002: Deterministic RAG Query

**Primary Actor:** Underwriter
**Goal:** Get a cited answer to a question about underwriting guidelines, ISO forms, or regulatory bulletins
**Scope:** Query path (user question → retrieval → cited answer)
**Level:** User goal
**Milestone:** M4

## Preconditions

- Document corpus ingested into Milvus (UC-001 complete)
- LangGraph agent with MCP tool access to Milvus
- LLM deployed and serving (Hermes-3-Llama-3.1-70B-FP8 in POC)
- Chainlit query interface available

## Main Success Scenario

1. Underwriter enters a natural language question in the query interface
2. LangGraph agent receives the query via Chainlit
3. Agent invokes MCP `milvus_search` tool — query is embedded and searched against the target collection
4. Milvus similarity search retrieves the top-K relevant chunks
5. Retrieved chunks (with metadata and citations) are passed to the LLM
6. LLM generates a cited answer, referencing specific source documents and sections
7. Answer is returned to the underwriter with inline citations
8. Query-time trace is recorded in MLflow (query text, retrieved chunks, cited sources, `pipeline_run_id` bridge)

## Extensions (Alternate Flows)

- **4a.** No relevant chunks found (low similarity scores): Return "No relevant information found" with suggestion to check document coverage
- **6a.** LLM generates answer without proper citations: System enforces citation format; if citations are missing, flag the response
- **8a.** MLflow unavailable: Query still succeeds; tracing is best-effort, not blocking

## Postconditions

### Success

- Underwriter receives a factually grounded answer with citations to specific documents and sections
- Full provenance chain is traceable: answer → chunks → pipeline run → source documents (Chain 1: Answer Provenance)

### Failure

- No incorrect answers served without citation — system fails safe (no answer rather than wrong answer)

## Related

- **ADRs:** ADR-003 (OGX role)
- **Technical:** `docs/technical/ogx.md`
- **User Journey:** UJ-001 (Underwriter Query)
- **Requirements:** FR-009, FR-010
- **Persona:** Underwriter

**Implementation:** M4 — verified E2E with LangGraph + MCP + `mlflow.langchain.autolog()`. MLflow experiment: `underwriter-chat-v3`.
