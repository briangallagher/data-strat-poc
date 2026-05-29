# UC-003: Agentic Compliance Review

**Primary Actor:** Compliance Officer
**Goal:** Request a structured compliance review that cross-references internal guidelines against regulatory standards and ISO forms
**Scope:** Agentic workflow (multi-hop retrieval across collections → structured report)
**Level:** User goal
**Milestone:** M5

## Preconditions

- Multiple document collections ingested (underwriting guidelines, ISO forms, regulatory bulletins)
- OGX agent capabilities available (agentic RAG, multi-step tool calling)
- LLM with native tool calling support (Hermes-3-Llama-3.1-70B-FP8 in POC)

## Main Success Scenario

1. Compliance Officer requests a compliance review for a specific line of business and jurisdiction
2. Agent decomposes the request into sub-tasks (retrieve guidelines, retrieve ISO forms, retrieve bulletins, compare, report)
3. Agent executes multi-hop retrieval across multiple Milvus collections
4. Agent compares retrieved content, identifies deviations between internal guidelines and regulatory standards
5. Agent generates a structured compliance report with deviations, severity, recommendations, and citations
6. Each retrieval step is traced independently in MLflow with `pipeline_run_id` bridge per collection
7. Full agent session trace is recorded for audit

## Extensions (Alternate Flows)

- **3a.** If agent encounters context length limits, reduce `top_k` per collection and re-execute searches
- **5a.** If partial collections fail, agent flags incomplete coverage in the report rather than silently omitting

## Postconditions

### Success

- Compliance Officer receives a structured report with traceable citations across all consulted document collections
- Full agent reasoning provenance is auditable (Chain 3: Agent Reasoning Provenance)

### Failure

- Partial results are clearly marked as incomplete rather than presented as comprehensive

## Related

- **ADRs:** ADR-003 (OGX role)
- **Technical:** `docs/technical/ogx.md`
- **User Journey:** UJ-003 (Compliance Review)
- **Requirements:** FR-011
- **Persona:** Compliance Officer

**Implementation:** M5 — verified E2E with 4 tool calls across 3 collections using Hermes 70B FP8 via vLLM.
