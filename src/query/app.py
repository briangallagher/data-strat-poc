"""Chainlit chat application for the underwriting knowledge assistant."""

import json
import logging
import os

import chainlit as cl
import mlflow

from agent import build_agent, format_config, format_input

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_EXPERIMENT_NAME = os.environ.get("MLFLOW_EXPERIMENT_NAME", "underwriter-chat")

if MLFLOW_TRACKING_URI:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    logger.info(f"MLflow tracking URI: {MLFLOW_TRACKING_URI}")

mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)
mlflow.langchain.autolog(run_tracer_inline=True)


@cl.set_starters
async def set_starters():
    """Conversation starters demonstrating Workflow A queries."""
    return [
        cl.Starter(
            label="Flood Coverage",
            message="Does our commercial property form cover flood damage for a property in a high-risk flood zone?",
            icon="/public/sparkle.svg",
        ),
        cl.Starter(
            label="Referral Threshold",
            message="What's the referral threshold for a general liability submission over $5M?",
            icon="/public/sparkle.svg",
        ),
        cl.Starter(
            label="California Regulations",
            message="What recent California regulatory bulletins affect our property insurance program?",
            icon="/public/sparkle.svg",
        ),
    ]


@cl.on_chat_start
async def start_chat():
    """Initialize chat session."""
    agent = await build_agent()
    cl.user_session.set("agent", agent)


async def display_tool_call(token):
    """Render tool call details in the Chainlit UI."""
    if hasattr(token, "tool_calls") and token.tool_calls:
        tool_calls = token.tool_calls
    elif hasattr(token, "tool_call_chunks") and token.tool_call_chunks:
        tool_calls = token.tool_call_chunks
    else:
        return

    for tool in tool_calls:
        name = tool.get("name", "unknown")
        args = tool.get("args", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                pass

        async with cl.Step(name=f"Tool: {name}") as step:
            step.output = f"```json\n{json.dumps(args, indent=2)}\n```"


async def display_tool_response(token, node: str):
    """Show tool response in a collapsible step."""
    if token.content and "tools" in node:
        content = token.content
        if len(content) > 500:
            content = content[:500] + "\n... (truncated)"
        async with cl.Step(name="Search Results") as step:
            step.output = f"```\n{content}\n```"


@cl.on_message
async def on_message(message: cl.Message):
    """Handle user message: deterministic RAG (retrieve → generate)."""
    agent = cl.user_session.get("agent")
    if not agent:
        agent = await build_agent()
        cl.user_session.set("agent", agent)

    input_data = format_input(content=message.content)
    config = format_config(thread_id=message.thread_id)

    msg = None
    search_metadata = {}
    chunks_raw = ""
    answer_text = ""

    async for event in agent.astream(input=input_data, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "retrieve":
                chunks_raw = node_output.get("retrieved_chunks", "")
                search_metadata = node_output.get("search_metadata", {})
                doc_ids = search_metadata.get("doc_ids", [])
                total = search_metadata.get("total_results", 0)

                async with cl.Step(name="Milvus Search") as step:
                    step.output = f"Retrieved **{total}** chunks from documents: {', '.join(doc_ids)}"

            elif node_name == "generate":
                new_messages = node_output.get("messages", [])
                for ai_msg in new_messages:
                    content = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
                    if content:
                        msg = cl.Message(content=content)
                        await msg.send()
                        answer_text = content

    _enrich_trace_metadata_from_search(search_metadata, chunks_raw=chunks_raw, answer=answer_text)


def _enrich_trace_metadata_from_search(search_metadata: dict, chunks_raw: str = "", answer: str = ""):
    """Add doc_ids, pipeline_run_ids, chunk details, and answer preview as trace tags.
    
    Tags are not truncated by the MLflow API (unlike request_metadata values),
    so we store provenance data here for the Registry provenance portal.
    """
    try:
        doc_ids = search_metadata.get("doc_ids", [])
        pipeline_run_ids = search_metadata.get("pipeline_run_ids", [])
        collection = search_metadata.get("collection", "")
        total = search_metadata.get("total_results", 0)

        tags = {
            "doc_ids_cited": ",".join(sorted(doc_ids)),
            "pipeline_run_ids": ",".join(sorted(pipeline_run_ids)),
            "collection_queried": collection,
            "chunks_retrieved_count": str(total),
        }
        if answer:
            tags["answer_preview"] = answer[:500]

        if chunks_raw:
            try:
                parsed = json.loads(chunks_raw) if isinstance(chunks_raw, str) else chunks_raw
                if isinstance(parsed, dict):
                    chunk_summaries = []
                    for c in parsed.get("chunks", []):
                        chunk_summaries.append({
                            "doc_id": c.get("doc_id", ""),
                            "chunk_index": c.get("chunk_index", 0),
                            "pipeline_run_id": c.get("pipeline_run_id", ""),
                            "score": c.get("score", 0),
                            "text_preview": (c.get("text", "") or "")[:150],
                            "section_path": c.get("section_path", ""),
                            "page_numbers": c.get("page_numbers", ""),
                        })
                    tags["chunks_detail"] = json.dumps(chunk_summaries)
            except (json.JSONDecodeError, TypeError):
                pass

        mlflow.update_current_trace(tags=tags)
    except Exception as e:
        logger.warning(f"Failed to enrich trace metadata: {e}")
