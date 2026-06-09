# Multi-Hop Retrieval and the Role of OGX

## What "Multi-Hop" Means

Multi-hop retrieval means the agent makes **multiple independent search calls across different knowledge sources** and synthesises the combined results into a single answer.

In this POC, that means:

1. Agent calls `milvus_search(collection="underwriting_guidelines", query="...")`
2. Agent calls `milvus_search(collection="iso_forms", query="...")`
3. Agent calls `milvus_search(collection="regulatory_bulletins", query="...")`
4. Agent **cross-references** the results — comparing what the guidelines say vs what the ISO standard says vs what regulators require

A human doing this manually would open three different document libraries, run a search in each, read the results side by side, and write a comparison. The agent replicates that workflow autonomously.

### Multi-hop vs single-hop

| | Underwriter Chat (Workflow A) | Compliance Review Agent (Workflow B) |
|---|---|---|
| Retrieval | Single collection, always `underwriting_guidelines` | Multiple collections, agent decides which |
| Control | **Application-controlled** — code always calls search | **LLM-controlled** — model decides when/what to search |
| Hops | 1 (fixed) | 2-4 (dynamic, based on the question) |
| Answer type | Cited lookup from one source | Cross-referenced analysis across sources |

### What we proved

- An LLM with tool-calling can autonomously decide which sources to consult
- Separate collections give the agent natural decision boundaries ("should I check ISO forms for this?")
- The MLflow trace captures exactly which collections and documents were consulted (provenance)
- Lineage connects from source documents → through the pipeline → into the specific collections the agent searched

---

## The Role of OGX

### What OGX is in this POC

OGX is a **vLLM model server** running Hermes-70B (a Llama-based instruction-tuned model). It exposes an OpenAI-compatible API:

```
POST http://llama-70b-vllm:8080/v1/chat/completions
```

"OGX running vLLM" means: the OGX Operator deployed a vLLM instance (the high-performance model serving engine) as the inference backend. OGX is the RHOAI-managed layer that handles model deployment, scaling, and routing. vLLM is the engine that actually runs the model on GPU.

Think of it as:
- **OGX** = the platform service (deploys, manages, routes to model servers)
- **vLLM** = the model execution engine (loads weights, runs inference on GPU, serves the API)
- **Hermes-70B** = the specific model weights loaded into vLLM

In this POC, the app hits the vLLM endpoint directly. OGX provided the deployment but isn't actively involved at query time.

### What OGX does for us

- Deploys and manages the vLLM instance on GPU
- Provides the OpenAI-compatible `/v1/chat/completions` endpoint
- Handles model loading, GPU scheduling, batching
- The model supports **tool calling** — it can return structured tool_call responses instead of just text

### What OGX does NOT do (that Scenario B asked for)

Scenario B's design specified OGX/AIGW Agentic APIs as the **orchestration runtime** — meaning OGX would:

| Capability | Scenario B design | POC reality |
|---|---|---|
| Manage the agentic loop | OGX autonomously iterates (call tools, get results, decide next step) | **App code manages the loop** (Python while loop in Chainlit) |
| Route tool calls to MCP | OGX discovers and executes MCP tools | **App discovers and calls MCP directly** |
| Built-in file search | OGX Responses API handles RAG natively | **Not used** — app does retrieval via MCP tools |
| Safety guardrails | OGX applies content filtering and grounding checks | **Not implemented** |
| Streaming orchestration | Single API call, OGX streams intermediate steps | **App streams manually** via iteration |

### Why the gap exists

From the Scenario B document:

> "AIGW/OGX agentic RAG — Exists RHAI (Dev Preview) — Not yet GA"

At the time of implementation, OGX's agentic orchestration APIs weren't production-ready. The POC hand-rolls the agentic loop to prove the **data architecture** works (collections, lineage, traces, multi-hop retrieval) — independent of which orchestration layer drives it.

### What stays the same when OGX goes GA

```
                        POC (today)              Target (OGX GA)
                        ───────────              ────────────────
Orchestration:          Chainlit app code   →    OGX Agentic APIs
Model serving:          vLLM (same)              vLLM (same)
Tool interface:         MCP (same)               MCP (same)
Vector search:          Milvus (same)            Milvus (same)
Lineage:                OpenLineage (same)       OpenLineage (same)
Traces:                 MLflow (same)            MLflow (same)
Collections:            3 in Milvus (same)       3 in Milvus (same)
```

The orchestration layer is the only thing that changes. Everything underneath — the data platform — is proven and stays in place.

---

## Architecture: What's Actually Happening at Query Time

```
┌──────────────────────────────────────────────────────────────────────┐
│  Chainlit App (compliance-review-ui)                                 │
│                                                                      │
│  1. User sends question                                              │
│  2. App sends messages + tool_definitions → vLLM                     │
│  3. vLLM returns: tool_call(list_collections)                        │
│  4. App executes tool_call against MCP server                        │
│  5. App appends result to messages, sends back to vLLM               │
│  6. vLLM returns: tool_call(milvus_search, collection=X)             │
│     +            tool_call(milvus_search, collection=Y)              │
│  7. App executes both against MCP server                             │
│  8. App appends results, sends back to vLLM                          │
│  9. vLLM returns: final_answer (cross-referenced analysis)           │
│  10. App displays answer, enriches MLflow trace with provenance      │
│                                                                      │
└───────────┬───────────────────────────────────┬──────────────────────┘
            │                                   │
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────────┐
│  vLLM (Hermes-70B)    │           │  MCP Server               │
│  ───────────────────  │           │  (mcp-knowledge-base pod) │
│  • Inference only     │           │  ───────────────────────  │
│  • Tool-call support  │           │  • Embeds query (Granite) │
│  • No state           │           │  • Searches Milvus        │
│  • No orchestration   │           │  • Returns chunks + meta  │
└───────────────────────┘           └───────────────┬───────────┘
                                                    │
                                                    ▼
                                        ┌───────────────────────┐
                                        │  Milvus               │
                                        │  (3 collections)      │
                                        └───────────────────────┘
```

The app is doing what OGX Agentic APIs will eventually do — but in application code rather than as a platform service.
