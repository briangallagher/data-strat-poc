#!/usr/bin/env python3
"""Multi-collection orchestrator: triggers one pipeline run per collection.

Reads config/collections.yaml, submits a KFP pipeline run for each collection,
and monitors them sequentially. Each run gets its own pipeline_run_id.

Usage:
    python scripts/run-multi-collection.py [--config config/collections.yaml] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import yaml


def get_token() -> str:
    result = subprocess.run(["oc", "whoami", "-t"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Failed to get OC token. Run 'oc login' first.")
    return result.stdout.strip()


def get_dsp_host(namespace: str, route_name: str) -> str:
    result = subprocess.run(
        ["oc", "get", "route", route_name, "-n", namespace, "-o", "jsonpath={.spec.host}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get DSP route '{route_name}' in namespace '{namespace}'")
    return f"https://{result.stdout.strip()}"


def get_pipeline_id(dsp_host: str, token: str) -> tuple[str, str]:
    """Get the latest pipeline and version IDs."""
    import requests
    r = requests.get(
        f"{dsp_host}/apis/v2beta1/pipelines",
        headers={"Authorization": f"Bearer {token}"},
        verify=False, timeout=30,
    )
    r.raise_for_status()
    pipelines = r.json().get("pipelines", [])
    if not pipelines:
        raise RuntimeError("No pipelines found. Upload the pipeline first.")

    pipeline_id = pipelines[0]["pipeline_id"]

    r = requests.get(
        f"{dsp_host}/apis/v2beta1/pipelines/{pipeline_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
        verify=False, timeout=30,
    )
    r.raise_for_status()
    versions = r.json().get("pipeline_versions", [])
    if not versions:
        raise RuntimeError(f"No versions found for pipeline {pipeline_id}")

    version_id = versions[0]["pipeline_version_id"]
    return pipeline_id, version_id


def submit_run(
    dsp_host: str,
    token: str,
    pipeline_id: str,
    version_id: str,
    collection_name: str,
    pipeline_run_id: str,
    config: dict,
    pipeline_config: dict,
) -> str:
    """Submit a pipeline run for a single collection."""
    import requests

    params = {
        "namespace": config["namespace"],
        "registry_url": config["registry_url"],
        "connector_type": collection_name,
        "collection_name": collection_name,
        "s3_endpoint": config["s3_endpoint"],
        "s3_bucket": config["s3_bucket"],
        "s3_staging_prefix": f"staging/{collection_name}",
        "s3_prefix": f"chunks/{collection_name}",
        "s3_secret_name": config["s3_secret_name"],
        "milvus_host": config["milvus_host"],
        "milvus_port": str(config["milvus_port"]),
        "pipeline_run_id": pipeline_run_id,
        "pvc_name": "data-pvc",
        "pvc_mount_path": "/mnt/data",
        "input_path": f"corpus/{collection_name}",
        "ray_image": pipeline_config["ray_image"],
        "embedding_model": pipeline_config["embedding_model"],
        "embedding_dim": str(pipeline_config["embedding_dim"]),
        "chunk_max_tokens": str(pipeline_config["chunk_max_tokens"]),
        "num_workers": str(pipeline_config["num_workers"]),
        "worker_cpus": str(pipeline_config["worker_cpus"]),
        "worker_memory_gb": str(pipeline_config["worker_memory_gb"]),
        "bypass_kueue": str(pipeline_config["bypass_kueue"]).lower(),
        "drop_existing": "true",
        "num_files": "0",
        "index_type": "HNSW",
    }

    # Override connector_type from collection config
    params["connector_type"] = "s3"

    body = {
        "display_name": f"m3-{collection_name}-{time.strftime('%Y%m%d-%H%M%S')}",
        "pipeline_version_reference": {
            "pipeline_id": pipeline_id,
            "pipeline_version_id": version_id,
        },
        "runtime_config": {"parameters": params},
    }

    r = requests.post(
        f"{dsp_host}/apis/v2beta1/runs",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        verify=False, timeout=30,
    )
    r.raise_for_status()
    run_id = r.json().get("run_id")
    print(f"  Submitted: run_id={run_id}")
    return run_id


def wait_for_run(dsp_host: str, token: str, run_id: str, timeout: int = 1800) -> str:
    """Wait for a pipeline run to complete."""
    import requests

    start = time.time()
    last_status = ""
    while True:
        r = requests.get(
            f"{dsp_host}/apis/v2beta1/runs/{run_id}",
            headers={"Authorization": f"Bearer {token}"},
            verify=False, timeout=30,
        )
        r.raise_for_status()
        state = r.json().get("state", "UNKNOWN")

        if state != last_status:
            elapsed = time.time() - start
            print(f"  [{elapsed:.0f}s] State: {state}")
            last_status = state

        if state == "SUCCEEDED":
            return "SUCCEEDED"
        elif state in ("FAILED", "ERROR", "SKIPPED", "CANCELED"):
            return state

        if time.time() - start > timeout:
            return "TIMEOUT"

        time.sleep(15)


def main():
    parser = argparse.ArgumentParser(description="Run ingest pipeline for all collections")
    parser.add_argument("--config", default="config/collections.yaml", help="Config file path")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be submitted without running")
    parser.add_argument("--collection", help="Run only a specific collection (skip others)")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    config = yaml.safe_load(config_path.read_text())
    cluster = config["cluster"]
    pipeline_config = config["pipeline"]
    collections = config["collections"]

    if args.collection:
        collections = [c for c in collections if c["name"] == args.collection]
        if not collections:
            print(f"Collection '{args.collection}' not found in config")
            sys.exit(1)

    print("=" * 60)
    print("MULTI-COLLECTION ORCHESTRATOR")
    print("=" * 60)
    print(f"Config:      {config_path}")
    print(f"Namespace:   {cluster['namespace']}")
    print(f"Collections: {len(collections)}")
    for c in collections:
        print(f"  - {c['name']} (connector: {c['connector_type']})")
    print()

    if args.dry_run:
        print("[DRY RUN] Would submit the following pipeline runs:")
        for coll in collections:
            run_id = str(uuid.uuid4())
            print(f"\n  Collection: {coll['name']}")
            print(f"  Pipeline Run ID: {run_id}")
            print(f"  Connector: {coll['connector_type']}")
            print(f"  Staging: s3://{cluster['s3_bucket']}/staging/{coll['name']}")
            print(f"  Chunks: s3://{cluster['s3_bucket']}/chunks/{coll['name']}")
            print(f"  Milvus: {coll['name']}")
        print("\n[DRY RUN] No runs submitted.")
        return

    import requests  # noqa: F811

    token = get_token()
    dsp_host = get_dsp_host(cluster["namespace"], cluster["dsp_route"])
    pipeline_id, version_id = get_pipeline_id(dsp_host, token)

    print(f"DSP Host:    {dsp_host}")
    print(f"Pipeline:    {pipeline_id}")
    print(f"Version:     {version_id}")
    print()

    results = {}
    for i, coll in enumerate(collections, 1):
        collection_name = coll["name"]
        pipeline_run_id = str(uuid.uuid4())

        print(f"\n{'─' * 60}")
        print(f"[{i}/{len(collections)}] Collection: {collection_name}")
        print(f"  Pipeline Run ID: {pipeline_run_id}")
        print(f"{'─' * 60}")

        run_id = submit_run(
            dsp_host=dsp_host,
            token=token,
            pipeline_id=pipeline_id,
            version_id=version_id,
            collection_name=collection_name,
            pipeline_run_id=pipeline_run_id,
            config=cluster,
            pipeline_config=pipeline_config,
        )

        status = wait_for_run(dsp_host, token, run_id)
        results[collection_name] = {
            "status": status,
            "pipeline_run_id": pipeline_run_id,
            "kfp_run_id": run_id,
        }

        if status != "SUCCEEDED":
            print(f"  WARNING: {collection_name} finished with status {status}")

    print(f"\n{'=' * 60}")
    print("ORCHESTRATION SUMMARY")
    print(f"{'=' * 60}")
    all_success = True
    for name, result in results.items():
        icon = "PASS" if result["status"] == "SUCCEEDED" else "FAIL"
        print(f"  [{icon}] {name}: {result['status']} (pipeline_run_id: {result['pipeline_run_id'][:8]}...)")
        if result["status"] != "SUCCEEDED":
            all_success = False
    print(f"{'=' * 60}")

    if not all_success:
        print("\nSome collections failed. Check KFP UI for details.")
        sys.exit(1)
    else:
        print("\nAll collections ingested successfully.")


if __name__ == "__main__":
    main()
