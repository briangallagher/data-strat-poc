"""Chainlit chat application for the agentic compliance review assistant.

Workflow B: The OGX agent autonomously decides which collections to search,
performs multi-hop retrieval, cross-references findings, and produces a
structured compliance analysis. The client is thin — OGX handles the entire
agent loop server-side via its Responses API.

Uses the OpenAI Python client against OGX's OpenAI-compatible endpoint.
"""

import json
import logging
import os

import chainlit as cl
import mlflow
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

if MLFLOW_TRACKING_URI:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    logger.info(f"MLflow tracking URI: {MLFLOW_TRACKING_URI}")

mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
mlflow.openai.autolog()


def get_ogx_client() -> OpenAI:
    return OpenAI(base_url=OGX_BASE_URL, api_key=OGX_API_KEY)


@cl.set_starters
async def set_starters():
    """Conversation starters demonstrating Workflow B (agentic compliance review)."""
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
    """Initialize the OGX client for this session."""
    client = get_ogx_client()
    cl.user_session.set("ogx_client", client)


@cl.on_message
async def on_message(message: cl.Message):
    """Handle user message: agentic compliance review via OGX Responses API."""
    client: OpenAI = cl.user_session.get("ogx_client")
    if not client:
        client = get_ogx_client()
        cl.user_session.set("ogx_client", client)

    tool_calls_seen = []
    search_results_raw = []

    try:
        response = client.responses.create(
            model=OGX_MODEL,
            instructions=SYSTEM_PROMPT,
            input=message.content,
            tools=[
                {
                    "type": "mcp",
                    "server_label": "knowledge_base",
                    "server_url": MCP_SERVER_URL,
                }
            ],
            tool_choice="auto",
            temperature=0,
        )

        # Walk the response output items to extract tool calls and final text
        answer_text = ""
        for item in response.output:
            item_type = getattr(item, "type", None)

            if item_type == "function_call":
                name = getattr(item, "name", "unknown")
                arguments = getattr(item, "arguments", "{}")
                call_id = getattr(item, "call_id", "")

                tool_calls_seen.append({
                    "name": name,
                    "arguments": arguments,
                    "call_id": call_id,
                })

                try:
                    args_display = json.dumps(json.loads(arguments), indent=2)
                except (json.JSONDecodeError, TypeError):
                    args_display = str(arguments)

                async with cl.Step(name=f"Tool: {name}") as step:
                    step.output = f"```json\n{args_display}\n```"

            elif item_type == "function_call_output":
                output = getattr(item, "output", "")
                call_id = getattr(item, "call_id", "")

                try:
                    parsed = json.loads(output) if isinstance(output, str) else output
                    search_results_raw.append(parsed)
                except (json.JSONDecodeError, TypeError):
                    search_results_raw.append({"raw": output})

                preview = output[:300] + "..." if len(str(output)) > 300 else str(output)
                async with cl.Step(name="Tool Result") as step:
                    step.output = f"```\n{preview}\n```"

            elif item_type == "message":
                content = ""
                for content_item in getattr(item, "content", []):
                    if getattr(content_item, "type", None) == "output_text":
                        content += getattr(content_item, "text", "")
                if content:
                    answer_text += content

        if answer_text:
            await cl.Message(content=answer_text).send()
        elif hasattr(response, "output_text") and response.output_text:
            answer_text = response.output_text
            await cl.Message(content=answer_text).send()
        else:
            await cl.Message(content="No response generated.").send()

        _enrich_trace_metadata(tool_calls_seen, search_results_raw, answer_text)

    except Exception as e:
        logger.error(f"OGX request failed: {e}", exc_info=True)
        await cl.Message(content=f"Error: {e}").send()


def _enrich_trace_metadata(
    tool_calls: list[dict],
    search_results: list[dict],
    answer: str,
):
    """Add provenance tags to the MLflow trace.

    MUST match M4's tag schema exactly — the Registry provenance portal
    (src/registry/provenance.py) parses these tags by name. Breaking this
    contract breaks the portal for M5 queries.

    Contract tags: doc_ids_cited, pipeline_run_ids, collection_queried,
                   chunks_detail, answer_preview, chunks_retrieved_count
    """
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
