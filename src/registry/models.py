"""Pydantic models for the Document Registry API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    doc_id: str | None = None
    name: str
    source_system: str
    source_url: str
    document_type: str
    line_of_business: str
    jurisdiction: str
    effective_date: date | None = None
    collections: list[str] = Field(default_factory=list)
    format: str | None = None
    page_count: int | None = None
    description: str | None = None


class DocumentResolve(BaseModel):
    source_url: str
    source_system: str
    suggested_collection: str | None = None
    suggested_metadata: dict | None = None


class DocumentUpdate(BaseModel):
    name: str | None = None
    source_url: str | None = None
    document_type: str | None = None
    line_of_business: str | None = None
    jurisdiction: str | None = None
    effective_date: date | None = None
    status: str | None = None
    description: str | None = None


class DocumentIngestionUpdate(BaseModel):
    collection: str
    pipeline_run_id: str
    vector_count: int


class Document(BaseModel):
    id: UUID
    doc_id: str
    name: str
    source_system: str
    source_url: str
    document_type: str
    line_of_business: str
    jurisdiction: str
    effective_date: date | None = None
    superseded_date: date | None = None
    superseded_by: str | None = None
    status: str
    ol_namespace: str
    ol_name: str
    content_hash: str | None = None
    file_format: str | None = None
    page_count: int | None = None
    file_size_bytes: int | None = None
    collections: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    documents: list[Document]
    total: int


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None
    doc_id_prefix: str


class CollectionUpdate(BaseModel):
    description: str | None = None


class CollectionAssign(BaseModel):
    doc_ids: list[str]


class CollectionMember(BaseModel):
    doc_id: str
    name: str
    document_type: str
    status: str
    added_at: datetime
    added_by: str
    last_ingested: datetime | None = None
    last_pipeline_run: str | None = None
    vector_count: int | None = None


class Collection(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    doc_id_prefix: str
    next_sequence: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    members: list[CollectionMember] | None = None

    model_config = {"from_attributes": True}


class CollectionList(BaseModel):
    collections: list[Collection]
    total: int


class LineageInfo(BaseModel):
    doc_id: str
    ol_namespace: str
    ol_name: str
    ingested_by: list[dict] = Field(default_factory=list)
    consumed_by: list[dict] = Field(default_factory=list)


class SupersedeRequest(BaseModel):
    new_doc_id: str
    superseded_date: date | None = None


class BulkSeedResponse(BaseModel):
    created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)
