# Observability Comparison: M4 (LangGraph) vs M5 (OGX)

**Date:** 2026-05-28
**Milestone:** M5

## Purpose

Honest comparison of what each query stack captures for observability, where the gaps are, and what's inside OGX's black box. This document supports the ADR: OGX for Agentic RAG (Phase 5).

## Summary

| Capability | M4 (LangGraph + MLflow autolog) | M5 (OGX Responses API + autolog) |
|------------|--------------------------------|----------------------------------|
| Trace capture method | `mlflow.langchain.autolog()` | `mlflow.openai.autolog()` |
| Agent orchestration visible | Full — every graph node is a span | Partial — tool calls visible in response, but OGX internal reasoning is opaque |
| Tool call details | LLM reasoning → tool selection → execution → result, all as separate spans | `function_call` and `function_call_output` items in response; may appear as child spans (pending autolog verification) |
| LLM prompt/completion | Captured in LangGraph spans | Captured as OpenAI request/response |
| Chunk-level provenance | doc_id, pipeline_run_id, score per chunk in tool output span | Same data available in `function_call_output` items |
| Trace tag contract | Implemented (`doc_ids_cited`, `pipeline_run_ids`, etc.) | Same contract implemented in `_enrich_trace_metadata()` |
| OL application registration | Single OL event on startup (1 collection) | Single OL event on startup (3 collections) |

## What M4 Captures Well

1. **Full graph visibility:** LangGraph models the agent as a state graph. Each node (retrieve, generate) is a distinct span. The trace shows the exact sequence of operations.

2. **LLM decision transparency:** The LLM's reasoning about whether to use a tool, which tool to use, and what arguments to pass is captured in the LangGraph spans.

3. **Deterministic flow:** Since LangGraph controls the flow (retrieve → generate), there's no ambiguity about what happened. The graph is the execution.

4. **Autolog quality:** `mlflow.langchain.autolog()` is mature and well-tested. Captures span trees with minimal configuration.

## What M5 Captures Well

1. **Multi-collection retrieval:** The agent searches across multiple collections autonomously. Each search is a separate `function_call` in the response, making cross-collection queries visible.

2. **Agent autonomy visible:** The sequence of tool calls reveals the agent's retrieval strategy — which collections it chose, in what order, and whether it did follow-up searches.

3. **Thin client simplicity:** All orchestration is server-side. The client only needs to parse the response and enrich the trace. No custom graph to maintain.

4. **OpenAI compatibility:** Uses standard OpenAI client, so `mlflow.openai.autolog()` should work without framework-specific configuration.

## Gaps and Black Box Areas

### M5 gaps relative to M4:

1. **OGX internal reasoning is opaque.** When OGX decides which tool to call next, the intermediate LLM reasoning (chain-of-thought, tool selection logic) happens server-side and may not be included in the response. M4's LangGraph makes every decision point a span.

2. **No trace context propagation to MCP tools.** OGX calls the MCP server but doesn't forward OpenTelemetry headers. If the MCP server emitted its own spans, they'd be orphaned. (Mitigated: DEC-012 chose client-side reconstruction, so MCP server spans aren't needed.)

3. **Autolog maturity for Responses API.** `mlflow.openai.autolog()` may not yet fully support the Responses API response format (which is newer than the Chat Completions API). If autolog only captures the outer request/response, tool call rounds would need manual span creation.

4. **Error visibility.** If OGX encounters an error during a tool call (MCP server timeout, malformed response), the error may be handled internally and not surfaced in the response. M4's LangGraph raises exceptions that become error spans.

### M4 gaps relative to M5:

1. **Single collection only.** M4's deterministic graph searches one collection. Multi-collection queries aren't supported without graph modification.

2. **No agent autonomy.** The retrieval strategy is hardcoded in the graph. The agent can't decide to do follow-up searches or cross-reference collections.

3. **Framework coupling.** LangGraph + LangChain MCP adapters add dependency overhead. OGX is a single server endpoint.

## Trace Structure Comparison

### M4 Trace (Deterministic RAG)

```
Root: LangGraph Agent
├── Retrieve (graph node)
│   └── MCP Tool Call: milvus_search
│       ├── input: {query, collection: "underwriting_guidelines"}
│       └── output: {chunks: [...], doc_ids: [...]}
└── Generate (graph node)
    ├── LLM Prompt (with retrieved context)
    └── LLM Response (answer with citations)
Tags: doc_ids_cited, pipeline_run_ids, collection_queried, ...
```

### M5 Trace (Agentic RAG)

```
Root: OpenAI Responses API Call
├── function_call: list_collections
│   └── arguments: {}
├── function_call_output: [{name, description}, ...]
├── function_call: milvus_search
│   └── arguments: {query, collection: "underwriting_guidelines"}
├── function_call_output: {chunks: [...]}
├── function_call: milvus_search
│   └── arguments: {query, collection: "iso_forms"}
├── function_call_output: {chunks: [...]}
└── message: "Based on my analysis of the GL guidelines and ISO CG 00 01..."
Tags: doc_ids_cited, pipeline_run_ids, collection_queried, ...
```

## Recommendation

Both stacks achieve the Pillar 4 (lineage & governance) requirements: every query has a trace with full chunk-level provenance, and the Registry provenance portal works with both via the shared tag contract. The difference is in the depth of orchestration visibility:

- **M4 is better for debugging** — full graph visibility, mature autolog, every decision point is a span.
- **M5 is better for agentic workflows** — multi-collection retrieval, autonomous strategy, simpler client code.

For production, the choice depends on whether the workflow is deterministic or agentic. Both can coexist (as demonstrated in this POC with two query services). The full assessment is captured in the M5 ADR.
