"""Database models and session management for the Document Registry."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://registry:registry@localhost:5432/doc_registry",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    doc_id = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    source_system = Column(String, nullable=False)
    source_url = Column(String, nullable=False)
    document_type = Column(String, nullable=False)
    line_of_business = Column(String, nullable=False)
    jurisdiction = Column(String, nullable=False)
    effective_date = Column(DateTime, nullable=True)
    superseded_date = Column(DateTime, nullable=True)
    superseded_by = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    ol_namespace = Column(String, nullable=False)
    ol_name = Column(String, nullable=False)
    content_hash = Column(String, nullable=True)
    file_format = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    collection_links = relationship("CollectionDocumentRow", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_documents_source_url", "source_url"),
        Index("idx_documents_status", "status"),
    )


class CollectionRow(Base):
    __tablename__ = "collections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(String, nullable=True)
    doc_id_prefix = Column(String, nullable=False)
    next_sequence = Column(Integer, nullable=False, default=1)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    document_links = relationship("CollectionDocumentRow", back_populates="collection", cascade="all, delete-orphan")


class CollectionDocumentRow(Base):
    __tablename__ = "collection_documents"

    collection_id = Column(UUID(as_uuid=True), ForeignKey("collections.id"), primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True)
    added_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    added_by = Column(String, nullable=False, default="system")
    last_ingested = Column(DateTime(timezone=True), nullable=True)
    last_pipeline_run = Column(String, nullable=True)
    vector_count = Column(Integer, nullable=True)

    collection = relationship("CollectionRow", back_populates="document_links")
    document = relationship("DocumentRow", back_populates="collection_links")

    __table_args__ = (
        UniqueConstraint("collection_id", "document_id", name="uq_collection_document"),
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)


def derive_ol_identity(doc_id: str, source_system: str) -> tuple[str, str]:
    """Derive OpenLineage namespace and name from doc_id and source_system."""
    ol_namespace = f"registry://{source_system}"
    ol_name = doc_id
    return ol_namespace, ol_name
