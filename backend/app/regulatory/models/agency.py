from typing import Optional
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class Agency(Base):
    __tablename__ = "agencies"

    agency_id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. ferc, epa, puco
    name: Mapped[str] = mapped_column(String, nullable=False)
    aliases: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
    jurisdiction_level: Mapped[str] = mapped_column(String, nullable=False)  # federal, state
    jurisdiction_geo: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    codebook_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    domain: Mapped[Optional[list]] = mapped_column(ARRAY(String), nullable=True)
