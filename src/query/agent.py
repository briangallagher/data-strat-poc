"""LangGraph agent for the underwriting knowledge assistant.

Deterministic RAG (Workflow A): the application controls retrieval,
not the model. Every query follows a fixed path:
  1. User asks a question
  2. Application calls milvus_search (always — no LLM decision)
  3. Retrieved chunks are injected into the LLM prompt
  4. LLM generates a cited answer grounded in the retrieved context

This avoids PG-047 (LLM skipping tool calls) by design.
For M5 agentic RAG (Workflow B), the agent decides what to retrieve.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import TypedDict, Annotated

import mlflow
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://granite-llm-predictor.data-strat-poc.svc.cluster.local/v1")
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "granite-llm")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "unused")

SYSTEM_PROMPT = """You are an underwriting knowledge assistant for a property and casualty insurance company.
You answer questions using ONLY the retrieved document chunks provided below.

RULES:
1. Base your answer ONLY on the retrieved chunks. Never use your own knowledge.
2. For every claim, cite the source document ID (e.g., [ug-003]).
3. If the retrieved chunks don't contain relevant information, say so clearly.
4. Format citations at the end as a Sources list.

CITATION FORMAT:
Use [doc_id] inline, then list all sources at the end:

Sources:
- [ug-003] Commercial Property Underwriting Guidelines (category: commercial_property)
- [ug-007] Workers Compensation Guidelines (category: workers_comp)
""".strip()

_mcp_client = None
_mcp_tools = None


def _get_llm() -> ChatOpenAI:
    import httpx
    return ChatOpenAI(
        base_url=LLM_BASE_URL,
        model=LLM_MODEL_NAME,
        api_key=LLM_API_KEY,
        temperature=0.0,
        http_client=httpx.Client(verify=False),
        http_async_client=httpx.AsyncClient(verify=False),
    )


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    retrieved_chunks: str
    search_metadata: dict


async def _get_mcp_tools():
    """Lazy-init MCP client and return tools."""
    global _mcp_client, _mcp_tools
    if _mcp_tools is None:
        mcp_env = os.environ.copy()
        mcp_server_path = str(Path(__file__).parent / "mcp_server.py")
        _mcp_client = MultiServerMCPClient(
            {
                "knowledge_base": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [mcp_server_path],
                    "env": mcp_env,
                }
            }
        )
        _mcp_tools = await _mcp_client.get_tools()
    return _mcp_tools


async def retrieve(state: AgentState) -> dict:
    """Always retrieve from Milvus. Application-controlled, not LLM-decided."""
    messages = state["messages"]
    user_question = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            user_question = msg.content if hasattr(msg, "content") else msg.get("content", "")
            break

    if not user_question:
        return {"retrieved_chunks": "", "search_metadata": {}}

    tools = await _get_mcp_tools()
    search_tool = next((t for t in tools if t.name == "milvus_search"), None)

    if search_tool is None:
        logger.error("milvus_search tool not found")
        return {"retrieved_chunks": "Error: search tool unavailable", "search_metadata": {}}

    raw_result = await search_tool.ainvoke({"query": user_question})

    # MCP tools return a list of content blocks: [{"type": "text", "text": "..."}]
    if isinstance(raw_result, list):
        result_text = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw_result
        )
    elif isinstance(raw_result, str):
        result_text = raw_result
    else:
        result_text = str(raw_result)

    metadata = {}
    try:
        parsed = json.loads(result_text)
        if isinstance(parsed, dict):
            metadata = {
                "collection": parsed.get("collection", ""),
                "total_results": parsed.get("total_results", 0),
                "doc_ids": list(set(c.get("doc_id", "") for c in parsed.get("chunks", []))),
                "pipeline_run_ids": list(set(c.get("pipeline_run_id", "") for c in parsed.get("chunks", []))),
            }
    except (json.JSONDecodeError, TypeError):
        pass

    return {"retrieved_chunks": result_text, "search_metadata": metadata}


async def generate(state: AgentState) -> dict:
    """Generate a cited answer using retrieved chunks as context."""
    messages = state["messages"]
    chunks = state.get("retrieved_chunks", "")

    user_question = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("role") == "user"):
            user_question = msg.content if hasattr(msg, "content") else msg.get("content", "")
            break

    prompt_messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"""RETRIEVED DOCUMENT CHUNKS:
{chunks}

USER QUESTION:
{user_question}

Answer the question using ONLY the retrieved chunks above. Cite sources by doc_id."""),
    ]

    llm = _get_llm()
    response = await llm.ainvoke(prompt_messages)

    return {"messages": [response]}


async def build_agent():
    """Build the deterministic RAG graph: retrieve → generate."""
    await _get_mcp_tools()

    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)

    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    checkpointer = InMemorySaver()
    return graph.compile(checkpointer=checkpointer)


def format_input(content: str) -> dict:
    """Format agent input."""
    return {"messages": [HumanMessage(content=content)]}


def format_config(thread_id: str) -> dict:
    """Format agent config with MLflow tracer."""
    from mlflow.langchain.langchain_tracer import MlflowLangchainTracer
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": [MlflowLangchainTracer(run_inline=True)],
    }
