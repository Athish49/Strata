from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    cursor_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
