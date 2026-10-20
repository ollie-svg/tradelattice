"""Validation of incoming records using the spec validator."""
from __future__ import annotations

from fastapi import HTTPException

from spec.validate import validate_record


def validate_records(records: list) -> None:
    """Raise HTTP 422 listing every error if any record is invalid."""
    errors: list[str] = []
    for i, rec in enumerate(records):
        errors.extend(f"[{i}] {m}" for m in validate_record(rec))
    if errors:
        raise HTTPException(status_code=422, detail=errors)
