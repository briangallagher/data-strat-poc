#!/usr/bin/env python3
"""Seed the Document Registry from corpus/manifest/manifest.json.

Creates collections first, then bulk-seeds documents.
Usage:
    python scripts/seed-registry.py [--registry-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

MANIFEST_PATH = Path(__file__).parent.parent / "corpus" / "manifest" / "manifest.json"

COLLECTIONS = [
    {"name": "underwriting_guidelines", "description": "Company underwriting guidelines, DOI bulletins, NAIC model laws", "doc_id_prefix": "ug"},
    {"name": "regulatory_bulletins", "description": "State regulatory bulletins, filing instructions, NAIC state action pages", "doc_id_prefix": "rb"},
    {"name": "iso_forms", "description": "ISO/ACORD standard forms, endorsements, and applications", "doc_id_prefix": "if"},
]


def seed(registry_url: str) -> None:
    client = httpx.Client(base_url=registry_url, timeout=30.0, verify=False)

    print("=== Creating collections ===")
    for coll in COLLECTIONS:
        r = client.post("/api/v1/collections", json=coll)
        if r.status_code == 201:
            print(f"  Created: {coll['name']}")
        elif r.status_code == 409:
            print(f"  Exists:  {coll['name']}")
        else:
            print(f"  ERROR creating {coll['name']}: {r.status_code} {r.text}")

    print("\n=== Seeding documents ===")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    payload = []
    for doc in manifest:
        payload.append({
            "doc_id": doc["doc_id"],
            "name": doc.get("description", doc["filename"]),
            "source_system": doc["source_system"],
            "source_url": doc["source_url"],
            "document_type": doc["document_type"],
            "line_of_business": doc["line_of_business"],
            "jurisdiction": doc["jurisdiction"],
            "effective_date": doc.get("effective_date"),
            "collections": doc["collections"],
            "format": doc.get("format"),
            "page_count": doc.get("page_count"),
        })

    r = client.post("/api/v1/documents/bulk", json=payload)
    if r.status_code == 200:
        result = r.json()
        print(f"  Created: {result['created']}")
        print(f"  Skipped: {result['skipped']}")
        if result["errors"]:
            print(f"  Errors:  {len(result['errors'])}")
            for err in result["errors"][:5]:
                print(f"    - {err}")
    else:
        print(f"  ERROR: {r.status_code} {r.text}")
        sys.exit(1)

    print("\n=== Assigning multi-collection documents ===")
    for doc in manifest:
        if len(doc["collections"]) > 1:
            for coll_name in doc["collections"][1:]:
                r = client.post(
                    f"/api/v1/collections/{coll_name}/assign",
                    json={"doc_ids": [doc["doc_id"]]},
                )
                if r.status_code == 200:
                    print(f"  {doc['doc_id']} -> {coll_name}")
                else:
                    print(f"  ERROR assigning {doc['doc_id']} to {coll_name}: {r.status_code}")

    print("\n=== Verification ===")
    r = client.get("/api/v1/collections")
    if r.status_code == 200:
        for coll in r.json()["collections"]:
            print(f"  {coll['name']}: {coll['document_count']} documents")

    print("\nSeed complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Document Registry")
    parser.add_argument("--registry-url", default="http://localhost:8080", help="Registry base URL")
    args = parser.parse_args()
    seed(args.registry_url)
