"""Jurisdiction registry for /landed-cost."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    currency: str
    fx_policy: str
    fx_publisher: str
    overlay_source: str
    tariff_source: str
    fee_schedule: list = field(default_factory=list)  # filled in by a later chunk


JURISDICTIONS: dict[str, Jurisdiction] = {
    "CA": Jurisdiction("CA", "CAD", "latest_on_or_before", "boc", "cbsa_surtax", "cbsa_tariff", []),
    "US": Jurisdiction("US", "USD", "quarterly_certified", "treasury", "us_overlays", "usitc_hts", []),
}


def get(code: str) -> Jurisdiction:
    """Return the registered jurisdiction; raise KeyError if unknown."""
    return JURISDICTIONS[code]
