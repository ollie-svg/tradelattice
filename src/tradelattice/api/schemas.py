"""Pydantic response/request models."""
from __future__ import annotations

from typing import Any, Literal

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
    quantity: float | None = None
    unit: str | None = None
    shipment_date: str | None = None


class LandedCostOut(BaseModel):
    hs_code: str
    matched_hs_code: str
    treatment: str
    duty_rate: float
    duty: float
    total: float
    currency: str
    declared_currency: str
    value_cad: float
    fx_rate: str | None = None
    fx_on: str | None = None
    surtax_pct: str | None = None
    surtax: float = 0.0
    surtax_list_id: str | None = None
    shipment_date: str
    rate: str
    components: list[str]
    basis: Literal["ad_valorem", "specific", "compound"]
