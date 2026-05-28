# ADR-004: OGX for Agentic RAG

**Date:** 2026-05-28
**Status:** Decided
**Milestone:** M5
**Supersedes:** Evaluates and refines ADR-003's query-path reservation

## Context

ADR-003 reserved OGX Responses API for the query path. DEC-010 deferred OGX from M4 to M5, using LangGraph for M4's deterministic RAG. M5 is the evaluation milestone — the system now has both query services running, enabling a direct comparison.

### What We Evaluated

1. **OGX Responses API** — server-side orchestration for agentic, multi-hop retrieval across 3 collections
2. **MCP tool integration** — OGX discovers and calls custom MCP servers during the agent loop
3. **Observability** — how MLflow tracing works when OGX owns the agent loop (DEC-012)
4. **Production readiness** — Dev Preview status, Granite compatibility, reliability

### M4 vs M5 Comparison

| Dimension | M4 (LangGraph) | M5 (OGX Responses API) |
|-----------|----------------|------------------------|
| **Architecture** | Client-side orchestration (graph nodes) | Server-side orchestration (agent loop) |
| **Tool protocol** | MCP via stdio (LangGraph spawns MCP server) | MCP via SSE (OGX connects at startup) |
| **Retrieval** | Deterministic: application controls when/what to search | Agentic: LLM decides when/what to search |
| **Collections** | Single (underwriting_guidelines) | Multi (all 3 — agent chooses) |
| **Tracing** | `mlflow.langchain.autolog()` — full graph visibility | `mlflow.openai.autolog()` — response-level; OGX internals partially opaque |
| **Client complexity** | Moderate (build LangGraph graph, manage MCP lifecycle) | Low (thin OpenAI client, one API call) |
| **Tool service** | MCP server (stdio) spawned per session | MCP server (SSE) deployed as persistent pod |
| **Framework deps** | LangGraph, LangChain, langchain-mcp-adapters | openai (standard Python client) |

## Decision

**OGX Responses API is validated for agentic RAG workflows.** Both approaches are valid for different use cases and can coexist.

### When to Use OGX (Agentic)

- Multi-collection queries where the agent must plan a retrieval strategy
- Cross-referencing across knowledge sources (compliance review, impact analysis)
- Workflows where the retrieval pattern varies by query (not predictable)
- Teams that want thin clients with server-side orchestration

### When to Use LangGraph (Deterministic)

- Fixed retrieval patterns (always search this collection, then generate)
- Maximum observability and debugging (full graph visibility in traces)
- Workflows where the retrieval strategy must be auditable and repeatable
- Teams that need fine-grained control over the agent graph

### Architecture Going Forward

The platform supports both query patterns:

```
User ─→ Underwriter Chat (LangGraph, deterministic)
         └─→ MCP Server (stdio) → Milvus (1 collection)
         └─→ mlflow.langchain.autolog()

User ─→ Compliance Review Agent (OGX, agentic)
         └─→ OGX Responses API → MCP Server (SSE) → Milvus (3 collections)
         └─→ mlflow.openai.autolog()

Both ─→ Registry UI (unified provenance portal, same trace tag contract)
```

## Findings

### Strengths

1. **Server-side MCP integration is production-grade.** OGX connects to MCP servers via SSE, discovers tools at startup, and routes tool calls during the agent loop. The `rh-ai-quickstart/llama-stack-mcp-server` pattern works well for custom enterprise tools.

2. **OpenAI client compatibility is excellent.** Using the standard OpenAI Python client (`openai.OpenAI`) against OGX's endpoint is seamless. This means existing OpenAI-based tooling (MLflow autolog, LangChain, etc.) works with minimal configuration.

3. **Multi-hop retrieval works.** The agent autonomously decides which collections to search, makes multiple tool calls, and cross-references results before synthesizing. This is a significant step up from M4's single-collection deterministic retrieval.

4. **Response includes full tool call details.** The Responses API response contains `function_call` and `function_call_output` items, giving the client complete visibility into the agent's actions. This enables client-side trace reconstruction (DEC-012).

### Limitations

1. **Dev Preview status.** OGX Responses API is marked as experimental in RHOAI 3.4. API surface may change.

2. **No OpenTelemetry trace context propagation.** OGX does not forward `traceparent` headers to MCP tool calls (PG-055). Distributed tracing requires client-side reconstruction from the response, not span correlation. Mitigated by DEC-012.

3. **Agent reasoning is partially opaque.** When OGX decides which tool to call next, the intermediate LLM reasoning happens server-side and may not be fully visible in the response. M4's LangGraph makes every decision point a span.

4. **Tool reliability depends on LLM quality.** The agent may skip tool calls and answer from parametric knowledge (PG-057). System prompt engineering and `tool_choice` settings mitigate this but don't eliminate it. M4's deterministic graph avoids this entirely.

### Trace Correlation (DEC-012)

The critical concern — how to trace agentic queries — is resolved. The Responses API response includes all tool call details (Q1=Yes), so the client reconstructs the full trace from the response. This is architecturally different from M4 (where autolog captures the graph execution) but achieves the same outcome: full provenance in MLflow.

The trace tag contract (`doc_ids_cited`, `pipeline_run_ids`, `collection_queried`, etc.) is shared between M4 and M5, so the Registry provenance portal works with both query services.

## Consequences

1. **ADR-003 is refined, not replaced.** OGX is validated for the query path — specifically for agentic workflows. The ingest-path decision (direct Milvus writes) is unchanged and correct.

2. **Both query services are maintained.** The platform is multi-application. Production would likely expose one unified chat interface with workflow selection rather than separate apps (PG-059).

3. **OGX maturity gates production adoption.** Until the Responses API reaches GA in RHOAI, OGX-based services should be treated as evaluation-grade. M4's LangGraph stack is production-viable today.

4. **MCP is the standard tool integration pattern.** Both M4 (stdio) and M5 (SSE) use MCP for tool integration. The Milvus search logic (pymilvus, embedding, ChunkResult) is shared. MCP is the right abstraction for enterprise tool integration with LLM orchestrators.

5. **Observability comparison is documented.** See `docs/technical/observability-comparison.md` for the detailed breakdown of what each stack captures.

## References

| Source | Location |
|--------|----------|
| ADR-003 (OGX role — original) | `docs/architecture/adrs/ADR-003-ogx-role.md` |
| DEC-010 (LangGraph for M4, OGX for M5) | `docs/decisions.md` |
| DEC-012 (OGX trace correlation strategy) | `docs/decisions.md` |
| Observability comparison | `docs/technical/observability-comparison.md` |
| M5 plan | `docs/milestones/M5-agentic-hardening/plan.md` |
| OGX knowledge doc | `work-knowledge/knowledge/rhoai/ogx/ogx.md` |
| Responses API flow (upstream) | https://llamastack.github.io/docs/api-openai/responses-flow |
| Red Hat Developer article | https://developers.redhat.com/articles/2025/08/20/your-agent-your-rules-deep-dive-responses-api-llama-stack |
| MCP server reference architecture | https://github.com/rh-ai-quickstart/llama-stack-mcp-server |
