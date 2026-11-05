"""Jurisdiction registry for /landed-cost."""
from __future__ import annotations

from dataclasses import dataclass, field

from .fees import FeeRule


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    currency: str
    fx_policy: str
    fx_publisher: str
    overlay_source: str
    tariff_source: str
    fee_schedule: list[FeeRule] = field(default_factory=list)


CA_FEES: list[FeeRule] = [
    FeeRule("GST", "ETA s.212", "pct", "5", None, "duty_paid_value", None, None, None,
            "1991-01-01", None, "tax", "https://laws-lois.justice.gc.ca/eng/acts/E-15/"),
]
"""CA schedule. Only federal GST is modelled. PST/HST depend on the importer's province and
registration (tenant facts, not properties of the goods), so they are deliberately absent."""

_MPF_AUTH = "19 CFR 24.23 / FR 2026-15530"
US_FEES: list[FeeRule] = [
    FeeRule("MPF", _MPF_AUTH, "pct", "0.3464", None, "value", "33.58", "651.50", None,
            "2025-10-01", "2026-10-01", "fee", None),  # FY2026
    FeeRule("MPF", _MPF_AUTH, "pct", "0.3464", None, "value", "34.58", "670.86", None,
            "2026-10-01", None, "fee", None),  # FY2027
    FeeRule("HMF", "26 USC 4461", "pct", "0.125", None, "value", None, None, {"mode": "sea"},
            "1987-04-01", None, "fee", None),
]

JURISDICTIONS: dict[str, Jurisdiction] = {
    "CA": Jurisdiction("CA", "CAD", "latest_on_or_before", "boc", "cbsa_surtax", "cbsa_tariff", CA_FEES),
    "US": Jurisdiction("US", "USD", "quarterly_certified", "treasury", "us_overlays", "usitc_hts", US_FEES),
}


def get(code: str) -> Jurisdiction:
    """Return the registered jurisdiction; raise KeyError if unknown."""
    return JURISDICTIONS[code]
