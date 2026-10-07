from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class ActionRelationship(Base):
    __tablename__ = "action_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_action_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regulatory_actions.id"), nullable=False
    )
    to_action_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("regulatory_actions.id"), nullable=False
    )
    # relationship_type values: amends, corrects, supersedes, withdraws, extends,
    # responds_to, implements, related_to, redesignated_as, split_from, merged_into
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    from_action = relationship(
        "RegulatoryAction", foreign_keys=[from_action_id], backref="outgoing_relationships"
    )
    to_action = relationship(
        "RegulatoryAction", foreign_keys=[to_action_id], backref="incoming_relationships"
    )

    __table_args__ = (
        UniqueConstraint(
            "from_action_id", "to_action_id", "relationship_type",
            name="uq_action_relationship"
        ),
    )
