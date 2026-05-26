"""Document Registry API — FastAPI application."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .db import (
    CollectionDocumentRow,
    CollectionRow,
    DocumentRow,
    derive_ol_identity,
    get_db,
    init_db,
)
from .enrichment import enrich_document
from .models import (
    BulkSeedResponse,
    Collection,
    CollectionAssign,
    CollectionCreate,
    CollectionList,
    CollectionMember,
    CollectionUpdate,
    Document,
    DocumentCreate,
    DocumentIngestionUpdate,
    DocumentList,
    DocumentResolve,
    DocumentUpdate,
    LineageInfo,
    SupersedeRequest,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document Registry",
    description="Canonical identity and collection membership for the Data Strategy POC",
    version="0.1.0",
)


@app.on_event("startup")
def startup():
    init_db()


DbSession = Annotated[Session, Depends(get_db)]


def _row_to_document(row: DocumentRow, db: Session) -> Document:
    collections = [
        link.collection.name
        for link in row.collection_links
        if link.collection is not None
    ]
    return Document(
        id=row.id,
        doc_id=row.doc_id,
        name=row.name,
        source_system=row.source_system,
        source_url=row.source_url,
        document_type=row.document_type,
        line_of_business=row.line_of_business,
        jurisdiction=row.jurisdiction,
        effective_date=row.effective_date,
        superseded_date=row.superseded_date,
        superseded_by=row.superseded_by,
        status=row.status,
        ol_namespace=row.ol_namespace,
        ol_name=row.ol_name,
        content_hash=row.content_hash,
        file_format=row.file_format,
        page_count=row.page_count,
        file_size_bytes=row.file_size_bytes,
        collections=collections,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _generate_doc_id(db: Session, collection_name: str) -> str:
    """Auto-generate a doc_id from the collection's prefix + next sequence."""
    coll = db.query(CollectionRow).filter(CollectionRow.name == collection_name).first()
    if coll is None:
        raise HTTPException(404, f"Collection '{collection_name}' not found")
    doc_id = f"{coll.doc_id_prefix}-{coll.next_sequence:03d}"
    coll.next_sequence += 1
    return doc_id


def _assign_to_collections(db: Session, doc_row: DocumentRow, collection_names: list[str], added_by: str = "system"):
    """Assign a document to one or more collections."""
    for cname in collection_names:
        coll = db.query(CollectionRow).filter(CollectionRow.name == cname).first()
        if coll is None:
            logger.warning("Collection '%s' not found, skipping assignment", cname)
            continue
        existing = (
            db.query(CollectionDocumentRow)
            .filter(CollectionDocumentRow.collection_id == coll.id, CollectionDocumentRow.document_id == doc_row.id)
            .first()
        )
        if existing:
            continue
        link = CollectionDocumentRow(
            collection_id=coll.id,
            document_id=doc_row.id,
            added_by=added_by,
        )
        db.add(link)


# --- Document Endpoints ---


@app.post("/api/v1/documents", response_model=Document, status_code=201)
def create_document(body: DocumentCreate, db: DbSession):
    existing = db.query(DocumentRow).filter(DocumentRow.source_url == body.source_url).first()
    if existing:
        raise HTTPException(409, f"Document with source_url already exists: doc_id={existing.doc_id}")

    doc_id = body.doc_id
    if not doc_id:
        if body.collections:
            doc_id = _generate_doc_id(db, body.collections[0])
        else:
            raise HTTPException(400, "Either doc_id or collections must be provided for ID generation")

    ol_ns, ol_name = derive_ol_identity(doc_id, body.source_system)

    enrichment = enrich_document(body.name if "/" not in body.name else body.name.rsplit("/", 1)[-1], body.collections)

    row = DocumentRow(
        doc_id=doc_id,
        name=body.name,
        source_system=body.source_system,
        source_url=body.source_url,
        document_type=body.document_type,
        line_of_business=body.line_of_business,
        jurisdiction=body.jurisdiction,
        effective_date=body.effective_date,
        status="active",
        ol_namespace=ol_ns,
        ol_name=ol_name,
        content_hash=enrichment.get("content_hash"),
        file_format=body.format or enrichment.get("file_format"),
        page_count=body.page_count or enrichment.get("page_count"),
        file_size_bytes=enrichment.get("file_size_bytes"),
    )
    db.add(row)
    db.flush()

    if body.collections:
        _assign_to_collections(db, row, body.collections)

    db.commit()
    db.refresh(row)
    return _row_to_document(row, db)


@app.post("/api/v1/documents/resolve", response_model=Document)
def resolve_document(body: DocumentResolve, db: DbSession):
    """Lookup by source_url. Returns existing document or creates new."""
    existing = db.query(DocumentRow).filter(DocumentRow.source_url == body.source_url).first()
    if existing:
        return _row_to_document(existing, db)

    collection = body.suggested_collection
    if not collection:
        raise HTTPException(
            400,
            "Document not found and no suggested_collection provided for auto-registration",
        )

    doc_id = _generate_doc_id(db, collection)
    ol_ns, ol_name = derive_ol_identity(doc_id, body.source_system)

    meta = body.suggested_metadata or {}
    row = DocumentRow(
        doc_id=doc_id,
        name=meta.get("name", body.source_url.rsplit("/", 1)[-1]),
        source_system=body.source_system,
        source_url=body.source_url,
        document_type=meta.get("document_type", "unknown"),
        line_of_business=meta.get("line_of_business", "unknown"),
        jurisdiction=meta.get("jurisdiction", "unknown"),
        effective_date=meta.get("effective_date"),
        status="active",
        ol_namespace=ol_ns,
        ol_name=ol_name,
        file_format=meta.get("format"),
    )
    db.add(row)
    db.flush()

    _assign_to_collections(db, row, [collection])
    db.commit()
    db.refresh(row)
    return _row_to_document(row, db)


@app.get("/api/v1/documents/{doc_id}", response_model=Document)
def get_document(doc_id: str, db: DbSession):
    row = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
    if not row:
        raise HTTPException(404, f"Document not found: {doc_id}")
    return _row_to_document(row, db)


@app.get("/api/v1/documents", response_model=DocumentList)
def list_documents(
    db: DbSession,
    collection: str | None = None,
    status: str | None = None,
    source_system: str | None = None,
    needs_processing: bool = False,
):
    query = db.query(DocumentRow)

    if collection:
        query = query.join(DocumentRow.collection_links).join(CollectionDocumentRow.collection).filter(
            CollectionRow.name == collection
        )
    if status:
        query = query.filter(DocumentRow.status == status)
    if source_system:
        query = query.filter(DocumentRow.source_system == source_system)
    if needs_processing and collection:
        query = query.join(DocumentRow.collection_links).filter(
            CollectionDocumentRow.last_ingested.is_(None)
        )

    rows = query.all()
    docs = [_row_to_document(r, db) for r in rows]
    return DocumentList(documents=docs, total=len(docs))


@app.patch("/api/v1/documents/{doc_id}", response_model=Document)
def update_document(doc_id: str, body: DocumentUpdate, db: DbSession):
    row = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
    if not row:
        raise HTTPException(404, f"Document not found: {doc_id}")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _row_to_document(row, db)


@app.post("/api/v1/documents/{doc_id}/ingestion", response_model=Document)
def update_ingestion(doc_id: str, body: DocumentIngestionUpdate, db: DbSession):
    """Update ingestion stats for a document in a specific collection."""
    row = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
    if not row:
        raise HTTPException(404, f"Document not found: {doc_id}")

    coll = db.query(CollectionRow).filter(CollectionRow.name == body.collection).first()
    if not coll:
        raise HTTPException(404, f"Collection not found: {body.collection}")

    link = (
        db.query(CollectionDocumentRow)
        .filter(CollectionDocumentRow.collection_id == coll.id, CollectionDocumentRow.document_id == row.id)
        .first()
    )
    if not link:
        raise HTTPException(404, f"Document {doc_id} not in collection {body.collection}")

    link.last_ingested = datetime.now(timezone.utc)
    link.last_pipeline_run = body.pipeline_run_id
    link.vector_count = body.vector_count
    db.commit()
    db.refresh(row)
    return _row_to_document(row, db)


@app.post("/api/v1/documents/{doc_id}/supersede", response_model=Document)
def supersede_document(doc_id: str, body: SupersedeRequest, db: DbSession):
    row = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
    if not row:
        raise HTTPException(404, f"Document not found: {doc_id}")

    row.status = "superseded"
    row.superseded_by = body.new_doc_id
    row.superseded_date = body.superseded_date or datetime.now(timezone.utc).date()
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _row_to_document(row, db)


@app.get("/api/v1/documents/{doc_id}/lineage", response_model=LineageInfo)
def get_document_lineage(doc_id: str, db: DbSession):
    row = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
    if not row:
        raise HTTPException(404, f"Document not found: {doc_id}")

    ingested_by = []
    for link in row.collection_links:
        if link.last_pipeline_run:
            ingested_by.append({
                "pipeline_run_id": link.last_pipeline_run,
                "collection": link.collection.name,
                "date": link.last_ingested.isoformat() if link.last_ingested else None,
                "vector_count": link.vector_count,
            })

    return LineageInfo(
        doc_id=row.doc_id,
        ol_namespace=row.ol_namespace,
        ol_name=row.ol_name,
        ingested_by=ingested_by,
        consumed_by=[],
    )


@app.post("/api/v1/documents/bulk", response_model=BulkSeedResponse)
def bulk_seed(documents: list[DocumentCreate], db: DbSession):
    """Seed multiple documents from a manifest.json-style payload."""
    created = 0
    skipped = 0
    errors: list[str] = []

    for doc in documents:
        try:
            existing = db.query(DocumentRow).filter(DocumentRow.source_url == doc.source_url).first()
            if existing:
                skipped += 1
                continue

            doc_id = doc.doc_id
            if not doc_id and doc.collections:
                doc_id = _generate_doc_id(db, doc.collections[0])
            elif not doc_id:
                errors.append(f"No doc_id or collection for: {doc.source_url}")
                continue

            ol_ns, ol_name = derive_ol_identity(doc_id, doc.source_system)
            filename = doc.name if "/" not in doc.name else doc.name.rsplit("/", 1)[-1]
            enrichment = enrich_document(filename, doc.collections)

            row = DocumentRow(
                doc_id=doc_id,
                name=doc.name,
                source_system=doc.source_system,
                source_url=doc.source_url,
                document_type=doc.document_type,
                line_of_business=doc.line_of_business,
                jurisdiction=doc.jurisdiction,
                effective_date=doc.effective_date,
                status="active",
                ol_namespace=ol_ns,
                ol_name=ol_name,
                content_hash=enrichment.get("content_hash"),
                file_format=doc.format or enrichment.get("file_format"),
                page_count=doc.page_count or enrichment.get("page_count"),
                file_size_bytes=enrichment.get("file_size_bytes"),
            )
            db.add(row)
            db.flush()

            if doc.collections:
                _assign_to_collections(db, row, doc.collections)

            created += 1
        except Exception as e:
            errors.append(f"{doc.source_url}: {str(e)}")

    db.commit()
    return BulkSeedResponse(created=created, skipped=skipped, errors=errors)


# --- Collection Endpoints ---


@app.post("/api/v1/collections", response_model=Collection, status_code=201)
def create_collection(body: CollectionCreate, db: DbSession):
    existing = db.query(CollectionRow).filter(CollectionRow.name == body.name).first()
    if existing:
        raise HTTPException(409, f"Collection already exists: {body.name}")

    row = CollectionRow(
        name=body.name,
        description=body.description,
        doc_id_prefix=body.doc_id_prefix,
        next_sequence=1,
        created_by="system",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return Collection(
        id=row.id,
        name=row.name,
        description=row.description,
        doc_id_prefix=row.doc_id_prefix,
        next_sequence=row.next_sequence,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        document_count=0,
    )


@app.get("/api/v1/collections", response_model=CollectionList)
def list_collections(db: DbSession):
    rows = db.query(CollectionRow).all()
    collections = []
    for row in rows:
        doc_count = (
            db.query(func.count(CollectionDocumentRow.document_id))
            .filter(CollectionDocumentRow.collection_id == row.id)
            .scalar()
        )
        collections.append(Collection(
            id=row.id,
            name=row.name,
            description=row.description,
            doc_id_prefix=row.doc_id_prefix,
            next_sequence=row.next_sequence,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
            document_count=doc_count or 0,
        ))
    return CollectionList(collections=collections, total=len(collections))


@app.get("/api/v1/collections/{name}", response_model=Collection)
def get_collection(name: str, db: DbSession):
    row = db.query(CollectionRow).filter(CollectionRow.name == name).first()
    if not row:
        raise HTTPException(404, f"Collection not found: {name}")

    links = db.query(CollectionDocumentRow).filter(CollectionDocumentRow.collection_id == row.id).all()
    members = []
    for link in links:
        doc = link.document
        members.append(CollectionMember(
            doc_id=doc.doc_id,
            name=doc.name,
            document_type=doc.document_type,
            status=doc.status,
            added_at=link.added_at,
            added_by=link.added_by,
            last_ingested=link.last_ingested,
            last_pipeline_run=link.last_pipeline_run,
            vector_count=link.vector_count,
        ))

    return Collection(
        id=row.id,
        name=row.name,
        description=row.description,
        doc_id_prefix=row.doc_id_prefix,
        next_sequence=row.next_sequence,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        document_count=len(members),
        members=members,
    )


@app.post("/api/v1/collections/{name}/assign", status_code=200)
def assign_to_collection(name: str, body: CollectionAssign, db: DbSession):
    coll = db.query(CollectionRow).filter(CollectionRow.name == name).first()
    if not coll:
        raise HTTPException(404, f"Collection not found: {name}")

    assigned = 0
    for doc_id in body.doc_ids:
        doc = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
        if not doc:
            continue
        existing = (
            db.query(CollectionDocumentRow)
            .filter(CollectionDocumentRow.collection_id == coll.id, CollectionDocumentRow.document_id == doc.id)
            .first()
        )
        if existing:
            continue
        link = CollectionDocumentRow(
            collection_id=coll.id,
            document_id=doc.id,
            added_by="human",
        )
        db.add(link)
        assigned += 1

    db.commit()
    return {"assigned": assigned, "collection": name}


@app.delete("/api/v1/collections/{name}/documents/{doc_id}", status_code=200)
def remove_from_collection(name: str, doc_id: str, db: DbSession):
    coll = db.query(CollectionRow).filter(CollectionRow.name == name).first()
    if not coll:
        raise HTTPException(404, f"Collection not found: {name}")

    doc = db.query(DocumentRow).filter(DocumentRow.doc_id == doc_id).first()
    if not doc:
        raise HTTPException(404, f"Document not found: {doc_id}")

    link = (
        db.query(CollectionDocumentRow)
        .filter(CollectionDocumentRow.collection_id == coll.id, CollectionDocumentRow.document_id == doc.id)
        .first()
    )
    if not link:
        raise HTTPException(404, f"Document {doc_id} not in collection {name}")

    db.delete(link)
    db.commit()
    return {"removed": doc_id, "collection": name}
