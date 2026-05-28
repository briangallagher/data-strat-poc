"""Chainlit chat application for the agentic compliance review assistant.

Workflow B: The agent autonomously decides which collections to search,
performs multi-hop retrieval, cross-references findings, and produces a
structured compliance analysis.

Uses OGX (LlamaStack) as the inference + MCP tool runtime. The client
manages the agentic loop: each iteration sends context to OGX, which
returns either a tool call or a final answer. Tool calls are executed
against the MCP server, and results are fed back for the next iteration.

Architecture: Chainlit → OGX (Responses API + MCP discovery) → Granite vLLM
                                    ↕
                              MCP Server (SSE) → Milvus
"""

import json
import logging
import os
import re

import chainlit as cl
import mlflow
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

OGX_BASE_URL = os.environ.get("OGX_BASE_URL", "http://localhost:8321/v1")
OGX_API_KEY = os.environ.get("OGX_API_KEY", "fake")
OGX_MODEL = os.environ.get("OGX_MODEL", "granite-3.3-8b-instruct")
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8000/sse")
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_EXPERIMENT_NAME = os.environ.get("MLFLOW_EXPERIMENT_NAME", "compliance-review-agent")
MAX_INFER_ITERS = int(os.environ.get("MAX_INFER_ITERS", "10"))

TOOL_CALL_PATTERN = re.compile(r"<\|tool_call\|>\s*(\[.*?\])", re.DOTALL)

MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_collections",
            "description": (
                "List available document collections in the underwriting knowledge base. "
                "Returns collection names and descriptions. Call this first to understand "
                "what knowledge sources are available before searching."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "milvus_search",
            "description": (
                "Search a document collection using semantic similarity. "
                "Returns document chunks ranked by relevance, with full metadata "
                "including doc_id, pipeline_run_id, and source text for citation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language question to search for.",
                    },
                    "collection": {
                        "type": "string",
                        "description": (
                            "Collection to search. Must be one of: underwriting_guidelines, "
                            "iso_forms, regulatory_bulletins."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results (1-50). Defaults to 10.",
                        "default": 10,
                    },
                    "category_filter": {
                        "type": "string",
                        "description": "Optional filter by document category.",
                        "default": "",
                    },
                    "subcategory_filter": {
                        "type": "string",
                        "description": "Optional filter by subcategory.",
                        "default": "",
                    },
                },
                "required": ["query", "collection"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are an expert insurance compliance review agent. Your job is to analyze
underwriting guidelines against ISO standard forms and regulatory requirements.

When asked to review guidelines or check compliance:

1. ALWAYS start by calling list_collections() to understand what knowledge sources are available.
2. Search the relevant collections — typically you need to check at least TWO sources:
   - underwriting_guidelines: for the company's internal rules
   - iso_forms: for the ISO standard being referenced
   - regulatory_bulletins: for any state-specific regulatory requirements
3. Cross-reference findings across collections. Look for:
   - Deviations from ISO standards
   - Missing regulatory requirements
   - Inconsistencies between internal guidelines and external standards
4. Present your findings in a structured format with specific citations.

For each finding, cite the source document (doc_id) and the relevant text.
Be thorough but concise. If you can't find relevant information in a collection,
say so explicitly rather than guessing."""

MLFLOW_ENABLED = False
try:
    if MLFLOW_TRACKING_URI:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        logger.info(f"MLflow tracking URI: {MLFLOW_TRACKING_URI}")
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
    mlflow.openai.autolog()
    MLFLOW_ENABLED = True
    logger.info("MLflow tracking enabled")
except Exception as e:
    logger.warning(f"MLflow initialization failed (tracing disabled): {e}")


def get_ogx_client() -> OpenAI:
    return OpenAI(base_url=OGX_BASE_URL, api_key=OGX_API_KEY)


def _parse_tool_calls(text: str) -> list[dict]:
    """Parse Granite's <|tool_call|> format from model output."""
    match = TOOL_CALL_PATTERN.search(text)
    if not match:
        return []
    try:
        calls = json.loads(match.group(1))
        return calls if isinstance(calls, list) else [calls]
    except (json.JSONDecodeError, TypeError):
        return []


def _strip_tool_call_text(text: str) -> str:
    """Remove <|tool_call|> markers and JSON from display text."""
    return TOOL_CALL_PATTERN.sub("", text).strip()


async def _execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool call against the MCP server via SSE transport."""
    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            texts = [c.text for c in result.content if hasattr(c, "text")]
            return "\n".join(texts) if texts else json.dumps({"status": "no content"})


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="GL Compliance Review",
            message=(
                "Review our general liability underwriting guidelines against "
                "ISO form CG 00 01. Flag any deviations from the standard."
            ),
            icon="/public/sparkle.svg",
        ),
        cl.Starter(
            label="Property Coverage Gaps",
            message=(
                "Compare our commercial property coverage guidelines with "
                "ISO CP 00 10. Are there any coverage gaps or non-standard exclusions?"
            ),
            icon="/public/sparkle.svg",
        ),
        cl.Starter(
            label="California Regulatory Check",
            message=(
                "Check our GL guidelines for compliance with recent California "
                "DOI regulatory bulletins. Are we meeting all state-specific requirements?"
            ),
            icon="/public/sparkle.svg",
        ),
    ]


@cl.on_chat_start
async def start_chat():
    client = get_ogx_client()
    cl.user_session.set("ogx_client", client)


@cl.on_message
async def on_message(message: cl.Message):
    """Agentic compliance review with client-side tool execution loop."""
    client: OpenAI = cl.user_session.get("ogx_client")
    if not client:
        client = get_ogx_client()
        cl.user_session.set("ogx_client", client)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message.content},
    ]

    tool_calls_seen = []
    search_results_raw = []

    try:
        for iteration in range(MAX_INFER_ITERS):
            response = client.chat.completions.create(
                model=OGX_MODEL,
                messages=messages,
                tools=MCP_TOOLS,
                tool_choice="auto",
                temperature=0,
                max_tokens=4096,
            )

            choice = response.choices[0]
            text = choice.message.content or ""

            parsed_calls = _parse_tool_calls(text)

            if not parsed_calls:
                clean_text = _strip_tool_call_text(text)
                if clean_text:
                    await cl.Message(content=clean_text).send()
                else:
                    await cl.Message(content="No response generated.").send()
                break

            messages.append({"role": "assistant", "content": text})

            for call in parsed_calls:
                name = call.get("name", "unknown")
                arguments = call.get("arguments", {})

                tool_calls_seen.append({"name": name, "arguments": arguments})

                try:
                    args_display = json.dumps(arguments, indent=2)
                except (TypeError, ValueError):
                    args_display = str(arguments)

                async with cl.Step(name=f"Tool: {name}") as step:
                    step.output = f"```json\n{args_display}\n```"

                try:
                    result = await _execute_tool(name, arguments)
                except Exception as e:
                    result = json.dumps({"error": str(e)})
                    logger.error(f"Tool execution failed: {e}", exc_info=True)

                try:
                    parsed = json.loads(result)
                    search_results_raw.append(parsed)
                except (json.JSONDecodeError, TypeError):
                    search_results_raw.append({"raw": result})

                preview = result[:500] + "..." if len(result) > 500 else result
                async with cl.Step(name=f"Result: {name}") as step:
                    step.output = f"```\n{preview}\n```"

                messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": f"call_{name}_{iteration}",
                })

            logger.info(f"Iteration {iteration}: {len(parsed_calls)} tool calls executed")
        else:
            await cl.Message(
                content="Reached maximum iterations without a final answer."
            ).send()

        if MLFLOW_ENABLED:
            _enrich_trace_metadata(tool_calls_seen, search_results_raw, text)

    except Exception as e:
        logger.error(f"Agent loop failed: {e}", exc_info=True)
        await cl.Message(content=f"Error: {e}").send()


def _enrich_trace_metadata(
    tool_calls: list[dict],
    search_results: list[dict],
    answer: str,
):
    """Add provenance tags to the MLflow trace."""
    try:
        doc_ids = set()
        pipeline_run_ids = set()
        collections = set()
        all_chunks = []
        total_chunks = 0

        for result in search_results:
            if not isinstance(result, dict):
                continue
            if result.get("status") != "success":
                continue

            collection = result.get("collection", "")
            if collection:
                collections.add(collection)

            for chunk in result.get("chunks", []):
                doc_id = chunk.get("doc_id", "")
                prun_id = chunk.get("pipeline_run_id", "")
                if doc_id:
                    doc_ids.add(doc_id)
                if prun_id:
                    pipeline_run_ids.add(prun_id)

                all_chunks.append({
                    "doc_id": doc_id,
                    "chunk_index": chunk.get("chunk_index", 0),
                    "pipeline_run_id": prun_id,
                    "score": chunk.get("score", 0),
                    "text_preview": (chunk.get("text", "") or "")[:150],
                    "section_path": chunk.get("section_path", ""),
                    "page_numbers": chunk.get("page_numbers", ""),
                })
                total_chunks += 1

        tags = {
            "doc_ids_cited": ",".join(sorted(doc_ids)),
            "pipeline_run_ids": ",".join(sorted(pipeline_run_ids)),
            "collection_queried": ",".join(sorted(collections)),
            "chunks_retrieved_count": str(total_chunks),
            "app_name": "compliance_review_agent",
            "workflow": "agentic",
            "tool_calls_count": str(len(tool_calls)),
        }

        if answer:
            tags["answer_preview"] = answer[:500]

        if all_chunks:
            tags["chunks_detail"] = json.dumps(all_chunks)

        mlflow.update_current_trace(tags=tags)
        logger.info(
            f"Trace enriched: {len(doc_ids)} doc_ids, {len(collections)} collections, "
            f"{total_chunks} chunks, {len(tool_calls)} tool calls"
        )

    except Exception as e:
        logger.warning(f"Failed to enrich trace metadata: {e}")
