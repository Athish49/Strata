from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Integer, String, Text, Date, DateTime, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class RegulatoryAction(Base):
    __tablename__ = "regulatory_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)  # federal_register
    jurisdiction_level: Mapped[str] = mapped_column(String, nullable=False)
    jurisdiction_geo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action_text: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agency: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    date_published: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_effective: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_comment_close: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_filed: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    docket_ids: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    rin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cfr_references: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    legal_refs: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    affected_entities: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    related_actions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    full_text_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    adapter_version: Mapped[str] = mapped_column(String, nullable=False, default="1.0")

    __table_args__ = (
        UniqueConstraint("source_system", "source_id", name="uq_regulatory_action_key"),
        Index("ix_regulatory_action_agency", "source_system", "agency"),
        Index("ix_regulatory_action_status", "status"),
        Index("ix_regulatory_action_date_published", "date_published"),
    )
