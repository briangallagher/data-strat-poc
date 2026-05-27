"""Configure MLflow to work with the RHOAI MLflow Operator.

RHOAI MLflow requires:
1. Bearer token auth (SA token or oc whoami -t)
2. X-Mlflow-Workspace header on every request
3. TLS (ignore verification for dev routes)

Usage:
    from mlflow_config import configure_mlflow
    configure_mlflow()
    # Now all mlflow calls include the workspace header
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

MLFLOW_WORKSPACE = os.environ.get("MLFLOW_WORKSPACE", "data-strat-poc")


def configure_mlflow():
    """Patch MLflow HTTP layer to inject the X-Mlflow-Workspace header."""
    import mlflow.utils.rest_utils as ru

    _orig_request = ru.http_request

    def _workspace_request(*args, **kwargs):
        if "extra_headers" not in kwargs:
            kwargs["extra_headers"] = {}
        kwargs["extra_headers"]["X-Mlflow-Workspace"] = MLFLOW_WORKSPACE
        return _orig_request(*args, **kwargs)

    ru.http_request = _workspace_request

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if tracking_uri:
        import mlflow
        mlflow.set_tracking_uri(tracking_uri)

    logger.info(f"MLflow configured for RHOAI (workspace={MLFLOW_WORKSPACE})")
