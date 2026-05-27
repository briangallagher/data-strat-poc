#!/usr/bin/env python3
"""Vector Provenance Report — trace every vector back to its source document.

Shows the relationship between Milvus vectors, registry documents, and source systems.
Requires: port-forward to Milvus (19530) and registry accessible.

Usage:
    oc port-forward svc/milvus 19530:19530 -n data-strat-poc
    python scripts/vector-provenance.py [--registry-url URL] [--collection NAME]
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx
from pymilvus import connections, Collection, utility


def get_provenance(milvus_host: str, milvus_port: int, registry_url: str, collection_name: str | None):
    connections.connect(host=milvus_host, port=milvus_port)

    collections = [collection_name] if collection_name else utility.list_collections()
    if not collections:
        print("No Milvus collections found.")
        return

    registry = httpx.Client(base_url=registry_url, timeout=10, verify=False)

    print("=" * 100)
    print("VECTOR PROVENANCE REPORT")
    print("=" * 100)
    print()

    total_vectors = 0
    total_docs = 0

    for coll_name in sorted(collections):
        col = Collection(coll_name)
        col.flush()
        col.load()
        count = col.num_entities

        results = col.query(
            expr="chunk_index >= 0",
            output_fields=["source_document_id", "pipeline_run_id", "category", "subcategory", "document_date", "chunk_index", "source_file"],
            limit=10000,
        )

        docs: dict[str, dict] = {}
        for r in results:
            doc_id = r["source_document_id"]
            if doc_id not in docs:
                docs[doc_id] = {
                    "vectors": 0,
                    "category": r.get("category", ""),
                    "subcategory": r.get("subcategory", ""),
                    "date": r.get("document_date", ""),
                    "pipeline_run_id": r.get("pipeline_run_id", "")[:8],
                    "source_file": r.get("source_file", ""),
                }
            docs[doc_id]["vectors"] += 1

        print(f"┌{'─' * 98}┐")
        print(f"│ Collection: {coll_name:<84} │")
        print(f"│ Vectors: {count:<87} │")
        print(f"│ Documents: {len(docs):<85} │")
        print(f"├{'─' * 98}┤")
        print(f"│ {'Doc ID':<10} {'Vectors':>7}  {'Category':<16} {'Type':<20} {'Date':<12} {'Source File':<28} │")
        print(f"├{'─' * 98}┤")

        for doc_id in sorted(docs.keys()):
            d = docs[doc_id]
            source_file = d["source_file"][:26] + ".." if len(d["source_file"]) > 28 else d["source_file"]
            print(f"│ {doc_id:<10} {d['vectors']:>7}  {d['category']:<16} {d['subcategory']:<20} {d['date']:<12} {source_file:<28} │")

            # Look up in registry for source_url
            try:
                resp = registry.get(f"/api/v1/documents/{doc_id}")
                if resp.status_code == 200:
                    reg_doc = resp.json()
                    source_url = reg_doc.get("source_url", "")
                    short_url = source_url[:90] + "..." if len(source_url) > 93 else source_url
                    print(f"│ {'':>10} {'↳ Registry':>7}  {short_url:<78} │")
                else:
                    print(f"│ {'':>10} {'↳':>7}  {'(not found in registry)':<78} │")
            except Exception:
                print(f"│ {'':>10} {'↳':>7}  {'(registry unavailable)':<78} │")

        print(f"├{'─' * 98}┤")
        print(f"│ Pipeline Run: {docs[list(docs.keys())[0]]['pipeline_run_id'] if docs else 'N/A':<82}... │")
        print(f"└{'─' * 98}┘")
        print()

        total_vectors += count
        total_docs += len(docs)

    print(f"{'=' * 100}")
    print(f"SUMMARY: {total_vectors} vectors from {total_docs} documents across {len(collections)} collection(s)")
    print(f"{'=' * 100}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vector Provenance Report")
    parser.add_argument("--milvus-host", default="localhost")
    parser.add_argument("--milvus-port", type=int, default=19530)
    parser.add_argument("--registry-url", default="https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com")
    parser.add_argument("--collection", default=None, help="Specific collection (default: all)")
    args = parser.parse_args()

    get_provenance(args.milvus_host, args.milvus_port, args.registry_url, args.collection)
