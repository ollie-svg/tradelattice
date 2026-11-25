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
    jurisdiction: str = "CA"
    fta_qualified: bool | None = None
    mode: Literal["road", "rail", "air", "sea", "multimodal"] | None = None
    include_taxes: bool = False


class FeeLine(BaseModel):
    name: str
    authority: str
    base: str
    base_amount: float
    amount: float


class LandedCostOut(BaseModel):
    hs_code: str
    matched_hs_code: str
    treatment: str
    duty_rate: float
    duty: float
    total: float | None  # None when `missing` is non-empty: an in-scope component could not be computed
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
    jurisdiction: str = "CA"
    fta_qualified: bool | None = None
    surtax_if_fta_qualified: float | None = None
    total_if_fta_qualified: float | None = None
    fees: list[FeeLine] = []
    taxes: list[FeeLine] = []
    include_taxes: bool = False
    # Named components a complete landed cost would include and this result does not: the jurisdiction's
    # `not_modelled` set, plus anything not computed for this request (`gst` when taxes were not asked for,
    # `prohibition_check` when no prohibition records are loaded, `surtax` when no surtax orders are loaded).
    not_computed: list[str] = []
    # The subset of `not_computed` that is in scope for this jurisdiction and unavailable in this instance.
    # When non-empty, `total` and `total_if_fta_qualified` are withheld (null), never a number that silently
    # leaves the component out.
    missing: list[str] = []
