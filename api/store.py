"""Shared persistence helpers."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from .models import Record


def upsert_records(session: Session, records: Iterable[dict]) -> int:
    n = 0
    for rec in records:
        row = session.get(Record, rec["id"])
        if row is None:
            row = Record(id=rec["id"])
            session.add(row)
        row.type = rec["type"]
        row.source = rec["source"]
        row.jurisdiction = rec["jurisdiction"]
        row.observed_at = rec["observed_at"]
        row.attributes = rec["attributes"]
        n += 1
    session.flush()
    return n
