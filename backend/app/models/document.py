import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, now_ts, uuid_pk


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    doc_number: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)

    revisions = relationship("DocRevision", back_populates="document", cascade="all, delete-orphan")


class DocRevision(Base):
    __tablename__ = "doc_revisions"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    revision: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    change_reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = now_ts()

    document = relationship("Document", back_populates="revisions")
    files = relationship("DocFile", back_populates="doc_rev", cascade="all, delete-orphan")


class DocFile(Base):
    __tablename__ = "doc_files"

    id: Mapped[uuid.UUID] = uuid_pk()
    doc_rev_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doc_revisions.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    preview_file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("doc_files.id"), nullable=True)

    doc_rev = relationship("DocRevision", back_populates="files")


class DocLink(Base):
    __tablename__ = "doc_links"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parts.id"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String, nullable=False)
