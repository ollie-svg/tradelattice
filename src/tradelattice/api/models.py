"""ORM models."""
from __future__ import annotations

from sqlalchemy import JSON, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Record(Base):
    __tablename__ = "records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        Index("ix_records_type", "type"),
        Index("ix_records_type_source", "type", "source"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "observed_at": self.observed_at,
            "jurisdiction": self.jurisdiction,
            "attributes": self.attributes,
        }
