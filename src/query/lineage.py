"""Application-level OpenLineage emission for Marquez graph completion.

Emits a single OL event on startup to register this query application
as a downstream consumer of the Milvus collection in the Marquez graph.
Per DEC-009: one event per application, not per query.
"""

import logging
import os
import uuid
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

MARQUEZ_API_URL = os.environ.get("MARQUEZ_API_URL", "http://marquez:5000")
MARQUEZ_NAMESPACE = os.environ.get("MARQUEZ_NAMESPACE", "data-strat-poc")
MILVUS_NAMESPACE = os.environ.get(
    "MILVUS_NAMESPACE", "milvus://milvus.data-strat-poc.svc.cluster.local:19530"
)
APP_NAME = os.environ.get("APP_NAME", "underwriter_chat")
COLLECTION_NAME = os.environ.get("DEFAULT_COLLECTION", "underwriting_guidelines")

PRODUCER = "https://github.com/briangallagher/data-strat-poc/query"
SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"


def emit_application_registration(
    app_name: str = APP_NAME,
    collection_names: list[str] | None = None,
):
    """
    Emit an OL COMPLETE event registering this app as a consumer of Milvus collections.

    Creates a job node in Marquez with the Milvus collections as inputs.
    Called once on application startup.
    """
    if collection_names is None:
        collection_names = [COLLECTION_NAME]

    run_id = str(uuid.uuid4())

    inputs = [
        {
            "namespace": MILVUS_NAMESPACE,
            "name": coll_name,
            "facets": {},
        }
        for coll_name in collection_names
    ]

    event = {
        "eventType": "COMPLETE",
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "run": {
            "runId": run_id,
            "facets": {
                "processing_engine": {
                    "_producer": PRODUCER,
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ProcessingEngineFacet.json",
                    "version": "1.0.0",
                    "name": "langgraph",
                },
            },
        },
        "job": {
            "namespace": MARQUEZ_NAMESPACE,
            "name": app_name,
            "facets": {
                "jobType": {
                    "_producer": PRODUCER,
                    "_schemaURL": "https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json",
                    "processingType": "STREAMING",
                    "integration": "CUSTOM",
                    "jobType": "APPLICATION",
                },
            },
        },
        "inputs": inputs,
        "outputs": [],
        "producer": PRODUCER,
        "schemaURL": SCHEMA_URL,
    }

    try:
        resp = httpx.post(
            f"{MARQUEZ_API_URL}/api/v1/lineage",
            json=event,
            timeout=5.0,
        )
        resp.raise_for_status()
        logger.info(
            f"Registered application '{app_name}' in Marquez "
            f"(consuming: {collection_names}, run_id: {run_id})"
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to register application in Marquez: {e}")
        return False
