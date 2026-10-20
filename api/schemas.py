"""Pydantic response/request models."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RecordOut(BaseModel):
    id: str
    type: str
    source: str
    observed_at: str
    jurisdiction: str
    attributes: dict[str, Any]


class UpsertResult(BaseModel):
    count: int
    ids: list[str]


class Money(BaseModel):
    amount: float
    currency: str


class LandedCostIn(BaseModel):
    hs_code: str
    origin_country: str
    declared_value: Money
    treatment: str | None = None


class LandedCostOut(BaseModel):
    hs_code: str
    matched_hs_code: str
    treatment: str
    duty_rate: float
    duty: float
    total: float
    currency: str
