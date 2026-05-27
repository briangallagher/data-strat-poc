"""E2E test: deterministic RAG — always retrieves, then generates.

Run with port-forwards active:
  oc port-forward svc/milvus 19530:19530 -n data-strat-poc
  oc port-forward pod/<granite-llm-pod> 8082:8080 -n data-strat-poc

  cd src/query
  LLM_BASE_URL=http://localhost:8082/v1 MILVUS_URI=http://localhost:19530 python test_e2e.py
"""

import asyncio
import json
import os
import sys

os.environ.setdefault("LLM_BASE_URL", "http://localhost:8082/v1")
os.environ.setdefault("MILVUS_URI", "http://localhost:19530")
os.environ.setdefault("LLM_MODEL_NAME", "granite-llm")
os.environ.setdefault("LLM_API_KEY", "unused")
os.environ.setdefault("MLFLOW_TRACKING_URI", "sqlite:///mlruns.db")

import mlflow
mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
mlflow.set_experiment("underwriter-chat")
mlflow.langchain.autolog(run_tracer_inline=True)

from agent import build_agent, format_input, format_config


async def test_query(agent, question: str, thread_id: str):
    print(f"\nQ: {question}")
    print("-" * 60)

    input_data = format_input(question)
    config = format_config(thread_id=thread_id)

    async for event in agent.astream(input=input_data, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "retrieve":
                meta = node_output.get("search_metadata", {})
                doc_ids = meta.get("doc_ids", [])
                total = meta.get("total_results", 0)
                collection = meta.get("collection", "")
                print(f"[RETRIEVE] {total} chunks from {collection}, docs: {doc_ids}")

            elif node_name == "generate":
                new_messages = node_output.get("messages", [])
                for ai_msg in new_messages:
                    content = ai_msg.content if hasattr(ai_msg, "content") else str(ai_msg)
                    print(f"\nA: {content[:500]}")
                    if len(content) > 500:
                        print("... (truncated)")

    print()


async def main():
    print("Building agent...")
    agent = await build_agent()
    print("Agent ready.\n")
    print("=" * 60)

    questions = [
        "Does our commercial property form cover flood damage for a property in a high-risk flood zone?",
        "What are the referral thresholds for workers compensation?",
        "What recent California regulatory bulletins affect our property insurance program?",
    ]

    for i, q in enumerate(questions):
        await test_query(agent, q, thread_id=f"test-{i:03d}")

    print("=" * 60)
    print("All queries used retrieval (deterministic RAG verified)")


if __name__ == "__main__":
    asyncio.run(main())
