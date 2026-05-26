"""Registry SDK client — typed wrapper over the Document Registry REST API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .models import BulkSeedResult, Collection, Document, LineageInfo


class RegistryClient:
    """Client for the Document Registry API.

    Usage:
        client = RegistryClient("http://doc-registry:8080")
        doc = client.resolve(source_url="s3://bucket/file.pdf", source_system="s3")
        docs = client.list_documents(collection="underwriting_guidelines", status="active")
    """

    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 30.0):
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _raise_for_status(self, r: httpx.Response) -> None:
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{r.status_code}: {r.text}",
                request=r.request,
                response=r,
            )

    # --- Documents ---

    def create_document(
        self,
        *,
        name: str,
        source_system: str,
        source_url: str,
        document_type: str,
        line_of_business: str,
        jurisdiction: str,
        doc_id: str | None = None,
        effective_date: str | None = None,
        collections: list[str] | None = None,
        format: str | None = None,
        page_count: int | None = None,
    ) -> Document:
        payload: dict[str, Any] = {
            "name": name,
            "source_system": source_system,
            "source_url": source_url,
            "document_type": document_type,
            "line_of_business": line_of_business,
            "jurisdiction": jurisdiction,
        }
        if doc_id:
            payload["doc_id"] = doc_id
        if effective_date:
            payload["effective_date"] = effective_date
        if collections:
            payload["collections"] = collections
        if format:
            payload["format"] = format
        if page_count:
            payload["page_count"] = page_count

        r = self._client.post("/api/v1/documents", json=payload)
        self._raise_for_status(r)
        return Document.model_validate(r.json())

    def resolve(
        self,
        *,
        source_url: str,
        source_system: str,
        suggested_collection: str | None = None,
        suggested_metadata: dict | None = None,
    ) -> Document:
        payload: dict[str, Any] = {
            "source_url": source_url,
            "source_system": source_system,
        }
        if suggested_collection:
            payload["suggested_collection"] = suggested_collection
        if suggested_metadata:
            payload["suggested_metadata"] = suggested_metadata

        r = self._client.post("/api/v1/documents/resolve", json=payload)
        self._raise_for_status(r)
        return Document.model_validate(r.json())

    def get_document(self, doc_id: str) -> Document:
        r = self._client.get(f"/api/v1/documents/{doc_id}")
        self._raise_for_status(r)
        return Document.model_validate(r.json())

    def list_documents(
        self,
        *,
        collection: str | None = None,
        status: str | None = None,
        source_system: str | None = None,
        needs_processing: bool = False,
    ) -> list[Document]:
        params: dict[str, Any] = {}
        if collection:
            params["collection"] = collection
        if status:
            params["status"] = status
        if source_system:
            params["source_system"] = source_system
        if needs_processing:
            params["needs_processing"] = "true"

        r = self._client.get("/api/v1/documents", params=params)
        self._raise_for_status(r)
        data = r.json()
        return [Document.model_validate(d) for d in data["documents"]]

    def update_document(self, doc_id: str, **kwargs) -> Document:
        r = self._client.patch(f"/api/v1/documents/{doc_id}", json=kwargs)
        self._raise_for_status(r)
        return Document.model_validate(r.json())

    def update_ingestion(
        self,
        doc_id: str,
        *,
        collection: str,
        pipeline_run_id: str,
        vector_count: int,
    ) -> Document:
        payload = {
            "collection": collection,
            "pipeline_run_id": pipeline_run_id,
            "vector_count": vector_count,
        }
        r = self._client.post(f"/api/v1/documents/{doc_id}/ingestion", json=payload)
        self._raise_for_status(r)
        return Document.model_validate(r.json())

    def supersede(self, doc_id: str, *, new_doc_id: str, superseded_date: str | None = None) -> Document:
        payload: dict[str, Any] = {"new_doc_id": new_doc_id}
        if superseded_date:
            payload["superseded_date"] = superseded_date
        r = self._client.post(f"/api/v1/documents/{doc_id}/supersede", json=payload)
        self._raise_for_status(r)
        return Document.model_validate(r.json())

    def get_lineage(self, doc_id: str) -> LineageInfo:
        r = self._client.get(f"/api/v1/documents/{doc_id}/lineage")
        self._raise_for_status(r)
        return LineageInfo.model_validate(r.json())

    def bulk_seed(self, documents: list[dict]) -> BulkSeedResult:
        r = self._client.post("/api/v1/documents/bulk", json=documents)
        self._raise_for_status(r)
        return BulkSeedResult.model_validate(r.json())

    def bulk_seed_from_manifest(self, manifest_path: str | Path) -> BulkSeedResult:
        """Seed from a manifest.json file (corpus/manifest/manifest.json format)."""
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload = []
        for doc in data:
            payload.append({
                "doc_id": doc["doc_id"],
                "name": doc.get("description", doc["filename"]),
                "source_system": doc["source_system"],
                "source_url": doc["source_url"],
                "document_type": doc["document_type"],
                "line_of_business": doc["line_of_business"],
                "jurisdiction": doc["jurisdiction"],
                "effective_date": doc.get("effective_date"),
                "collections": doc.get("collections", []),
                "format": doc.get("format"),
                "page_count": doc.get("page_count"),
            })
        return self.bulk_seed(payload)

    # --- Collections ---

    def create_collection(
        self,
        *,
        name: str,
        description: str | None = None,
        doc_id_prefix: str,
    ) -> Collection:
        payload: dict[str, Any] = {"name": name, "doc_id_prefix": doc_id_prefix}
        if description:
            payload["description"] = description
        r = self._client.post("/api/v1/collections", json=payload)
        self._raise_for_status(r)
        return Collection.model_validate(r.json())

    def list_collections(self) -> list[Collection]:
        r = self._client.get("/api/v1/collections")
        self._raise_for_status(r)
        data = r.json()
        return [Collection.model_validate(c) for c in data["collections"]]

    def get_collection(self, name: str) -> Collection:
        r = self._client.get(f"/api/v1/collections/{name}")
        self._raise_for_status(r)
        return Collection.model_validate(r.json())

    def assign_to_collection(self, collection_name: str, *, doc_ids: list[str]) -> dict:
        r = self._client.post(
            f"/api/v1/collections/{collection_name}/assign",
            json={"doc_ids": doc_ids},
        )
        self._raise_for_status(r)
        return r.json()

    def remove_from_collection(self, collection_name: str, doc_id: str) -> dict:
        r = self._client.delete(f"/api/v1/collections/{collection_name}/documents/{doc_id}")
        self._raise_for_status(r)
        return r.json()
