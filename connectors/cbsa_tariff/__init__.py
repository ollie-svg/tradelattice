"""CBSA Customs Tariff schedule -> TariffLine records.

TODO(live): the schedule is published at
https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/ ; the exact CSV/XLSX URL is unconfirmed.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from connectors._base import (
    Envelope,
    digits_only,
    envelope,
    live_not_implemented,
    parse_date,
    read_csv,
    to_utc_iso,
)

NAME = "cbsa_tariff"
LIVE_URL = "https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/"
SAMPLE = Path(__file__).parent / "sample" / "customs_tariff_sample.csv"
EFFECTIVE_FROM = "2026-01-01"


def parse_rates(mfn: str, preferential: str) -> list[dict[str, str]]:
    """Build the spec `rates[]` array: MFN first, then `TREATMENT:rate;...` entries."""
    rates = [{"treatment": "MFN", "rate": mfn}] if mfn else []
    for part in filter(None, (p.strip() for p in preferential.split(";"))):
        treatment, _, rate = part.partition(":")
        if treatment.strip() and rate.strip():
            rates.append({"treatment": treatment.strip(), "rate": rate.strip()})
    return rates


def fetch(since: datetime | None = None, live: bool = False) -> Iterator[Envelope]:
    """Yield TariffLine envelopes. `since` is ignored: the schedule is a full snapshot."""
    if live:
        raise live_not_implemented(NAME, LIVE_URL)
    observed = to_utc_iso(parse_date(EFFECTIVE_FROM))
    for row in read_csv(SAMPLE):
        item = row["tariff_item"]
        attrs = {
            "hs_code": digits_only(item),
            "description": row["description"],
            "rates": parse_rates(row["mfn_rate"], row["preferential_tariffs"]),
            "effective_from": EFFECTIVE_FROM,
            "effective_to": None,
        }
        yield envelope(source=NAME, native_id=item, type_="tariff_line",
                       observed_at=observed, attributes=attrs)
