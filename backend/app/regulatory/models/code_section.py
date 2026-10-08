from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Integer, String, Text, Date, DateTime, UniqueConstraint, Index, ForeignKey
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class CodeSection(Base):
    __tablename__ = "code_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    citation: Mapped[str] = mapped_column(String, nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)  # cfr
    jurisdiction_level: Mapped[str] = mapped_column(String, nullable=False)  # federal, state, local, international
    jurisdiction_geo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    part: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    section_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subpart: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    heading: Mapped[str] = mapped_column(String, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    owning_agency: Mapped[str] = mapped_column(String, nullable=False)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # in_progress, approved, blocked_suspended
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    amendment_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prior_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("code_sections.id"), nullable=True
    )
    superseded_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    repealed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    diff_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    agency_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("agencies.agency_id"), nullable=True)

    # Cross-citations extracted from IAC section body text
    federal_refs: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    iac_cross_refs: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)
    dins: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String), nullable=True)

    prior_version: Mapped[Optional["CodeSection"]] = relationship(
        "CodeSection", remote_side="CodeSection.id", foreign_keys=[prior_version_id]
    )

    __table_args__ = (
        UniqueConstraint("source_system", "citation", "snapshot_date", name="uq_code_section_key"),
        Index("ix_code_section_lookup", "source_system", "citation"),
    )
