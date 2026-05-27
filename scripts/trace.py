#!/usr/bin/env python3
"""Trace provenance in both directions.

Usage:
    # Where is this document used? (which collections, how many vectors)
    python scripts/trace.py --doc ug-008

    # Where did this vector come from? (which document, which chunk, source URL)
    python scripts/trace.py --vector ug-003 --chunk 5

    # What's in this collection? (all documents and their vector counts)
    python scripts/trace.py --collection underwriting_guidelines

Requires: port-forward to Milvus (19530) and registry accessible.
"""

from __future__ import annotations

import argparse
import sys

import httpx
from pymilvus import connections, Collection, utility


def trace_document(doc_id: str, registry_url: str, milvus_host: str, milvus_port: int):
    """Question 1: Which collections/vectors use this remote document?"""
    registry = httpx.Client(base_url=registry_url, timeout=10, verify=False)

    # Get doc from registry
    resp = registry.get(f"/api/v1/documents/{doc_id}")
    if resp.status_code != 200:
        print(f"Document '{doc_id}' not found in registry.")
        return
    doc = resp.json()

    print(f"{'=' * 70}")
    print(f"DOCUMENT TRACE: {doc_id}")
    print(f"{'=' * 70}")
    print()
    print(f"  Name:          {doc['name']}")
    print(f"  Source System:  {doc['source_system']}")
    print(f"  Source URL:     {doc['source_url']}")
    print(f"  Type:           {doc['document_type']}")
    print(f"  LOB:            {doc['line_of_business']}")
    print(f"  Jurisdiction:   {doc['jurisdiction']}")
    print(f"  Effective Date: {doc.get('effective_date', '-')}")
    print(f"  Status:         {doc['status']}")
    print(f"  Collections:    {doc['collections']}")
    print()

    # Query Milvus for vectors from this doc
    connections.connect(host=milvus_host, port=milvus_port)
    print(f"  {'Collection':<30} {'Vectors':>8}  {'Chunk Range'}")
    print(f"  {'─' * 30} {'─' * 8}  {'─' * 15}")

    total_vectors = 0
    for coll_name in utility.list_collections():
        col = Collection(coll_name)
        col.load()
        results = col.query(
            expr=f'source_document_id == "{doc_id}"',
            output_fields=["chunk_index"],
            limit=10000,
        )
        if results:
            chunks = sorted(r["chunk_index"] for r in results)
            print(f"  {coll_name:<30} {len(results):>8}  chunks {chunks[0]}-{chunks[-1]}")
            total_vectors += len(results)

    print(f"  {'─' * 30} {'─' * 8}")
    print(f"  {'TOTAL':<30} {total_vectors:>8}")
    print()
    print(f"  This document from {doc['source_system']} ({doc['source_url'][:50]}...)")
    print(f"  is used in {len(doc['collections'])} collection(s) with {total_vectors} total vectors.")
    print()


def trace_vector(doc_id: str, chunk_index: int, registry_url: str, milvus_host: str, milvus_port: int):
    """Question 2: Which document and chunk does this vector come from?"""
    connections.connect(host=milvus_host, port=milvus_port)
    registry = httpx.Client(base_url=registry_url, timeout=10, verify=False)

    print(f"{'=' * 70}")
    print(f"VECTOR TRACE: {doc_id} chunk {chunk_index}")
    print(f"{'=' * 70}")
    print()

    # Find the vector in Milvus
    found_in = []
    for coll_name in utility.list_collections():
        col = Collection(coll_name)
        col.load()
        results = col.query(
            expr=f'source_document_id == "{doc_id}" and chunk_index == {chunk_index}',
            output_fields=["text", "category", "subcategory", "document_date", "pipeline_run_id", "source_file"],
            limit=5,
        )
        if results:
            found_in.append((coll_name, results[0]))

    if not found_in:
        print(f"  Vector not found: doc_id={doc_id}, chunk_index={chunk_index}")
        return

    for coll_name, vec in found_in:
        print(f"  Found in:       {coll_name}")
        print(f"  Doc ID:         {doc_id}")
        print(f"  Chunk Index:    {chunk_index}")
        print(f"  Category:       {vec.get('category', '-')}")
        print(f"  Type:           {vec.get('subcategory', '-')}")
        print(f"  Date:           {vec.get('document_date', '-')}")
        print(f"  Pipeline Run:   {vec.get('pipeline_run_id', '-')}")
        print(f"  Source File:    {vec.get('source_file', '-')}")
        print()
        text = vec.get("text", "")
        print(f"  Chunk Text ({len(text)} chars):")
        print(f"  ┌{'─' * 66}┐")
        for line in text[:500].split("\n")[:10]:
            print(f"  │ {line[:64]:<64} │")
        if len(text) > 500:
            print(f"  │ {'...':<64} │")
        print(f"  └{'─' * 66}┘")
        print()

    # Get source document from registry
    resp = registry.get(f"/api/v1/documents/{doc_id}")
    if resp.status_code == 200:
        doc = resp.json()
        print(f"  Source Document:")
        print(f"    Name:       {doc['name']}")
        print(f"    System:     {doc['source_system']}")
        print(f"    URL:        {doc['source_url']}")
        print(f"    Format:     {doc.get('file_format', '-')}")
        print()
        print(f"  Provenance chain:")
        print(f"    Remote: {doc['source_url']}")
        print(f"      → Registered as: {doc_id} in registry")
        print(f"      → Chunked: chunk {chunk_index} of this document")
        print(f"      → Embedded: vector in Milvus '{coll_name}'")
        print(f"      → Pipeline: {vec.get('pipeline_run_id', '?')[:8]}...")
    print()


def trace_collection(collection_name: str, registry_url: str, milvus_host: str, milvus_port: int):
    """What documents are in this collection and how many vectors each?"""
    connections.connect(host=milvus_host, port=milvus_port)
    registry = httpx.Client(base_url=registry_url, timeout=10, verify=False)

    print(f"{'=' * 70}")
    print(f"COLLECTION TRACE: {collection_name}")
    print(f"{'=' * 70}")
    print()

    # Get from registry
    resp = registry.get(f"/api/v1/collections/{collection_name}")
    if resp.status_code != 200:
        print(f"  Collection '{collection_name}' not found in registry.")
        return
    coll = resp.json()
    print(f"  Description:  {coll.get('description', '-')}")
    print(f"  Prefix:       {coll['doc_id_prefix']}")
    print(f"  Members:      {coll['document_count']}")
    print()

    # Get vectors from Milvus
    if collection_name in utility.list_collections():
        col = Collection(collection_name)
        col.flush()
        col.load()
        results = col.query(
            expr="chunk_index >= 0",
            output_fields=["source_document_id", "chunk_index"],
            limit=10000,
        )

        docs = {}
        for r in results:
            did = r["source_document_id"]
            docs.setdefault(did, 0)
            docs[did] += 1

        print(f"  Milvus:       {len(results)} vectors from {len(docs)} documents")
        print()
        print(f"  {'Doc ID':<12} {'Vectors':>8}  {'Source'}")
        print(f"  {'─' * 12} {'─' * 8}  {'─' * 45}")

        for did in sorted(docs.keys()):
            source = ""
            r = registry.get(f"/api/v1/documents/{did}")
            if r.status_code == 200:
                source = r.json().get("source_url", "")[:45]
            print(f"  {did:<12} {docs[did]:>8}  {source}")
    else:
        print(f"  Milvus collection '{collection_name}' not yet created (no pipeline run).")

    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trace provenance between documents, vectors, and collections")
    parser.add_argument("--doc", help="Trace a document: which collections/vectors use it")
    parser.add_argument("--vector", help="Trace a vector: doc_id of the vector to trace")
    parser.add_argument("--chunk", type=int, default=0, help="Chunk index (used with --vector)")
    parser.add_argument("--collection", help="Trace a collection: what documents and vectors are in it")
    parser.add_argument("--registry-url", default="https://doc-registry-data-strat-poc.apps.dev.aip-ft.rh-ods.com")
    parser.add_argument("--milvus-host", default="localhost")
    parser.add_argument("--milvus-port", type=int, default=19530)
    args = parser.parse_args()

    if not any([args.doc, args.vector, args.collection]):
        parser.print_help()
        sys.exit(1)

    if args.doc:
        trace_document(args.doc, args.registry_url, args.milvus_host, args.milvus_port)
    elif args.vector:
        trace_vector(args.vector, args.chunk, args.registry_url, args.milvus_host, args.milvus_port)
    elif args.collection:
        trace_collection(args.collection, args.registry_url, args.milvus_host, args.milvus_port)
