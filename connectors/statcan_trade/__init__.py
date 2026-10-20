"""Statistics Canada CIMT imports by HS6 -> PriceObservation records (unit value = value/qty).

TODO(live): https://www150.statcan.gc.ca/ (Canadian International Merchandise Trade tables).
"""
from __future__ import annotations

import calendar
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

from connectors._base import (
    Envelope,
    digits_only,
    envelope,
    live_not_implemented,
    read_csv,
    since_date,
    to_utc_iso,
)

NAME = "statcan_trade"
LIVE_URL = "https://www150.statcan.gc.ca/"
SOURCE_URL = "https://www150.statcan.gc.ca/n1/en/type/data"
SAMPLE = Path(__file__).parent / "sample" / "cimt_imports_sample.csv"
CURRENCY = "CAD"


def fetch(since: datetime | None = None, live: bool = False) -> Iterator[Envelope]:
    """Yield PriceObservation envelopes; rows with zero quantity are skipped.

    With `since`, only reference months ending on/after that date are emitted.
    """
    if live:
        raise live_not_implemented(NAME, LIVE_URL)
    cutoff = since_date(since)
    for row in read_csv(SAMPLE):
        quantity = float(row["QUANTITY"] or 0)
        if quantity <= 0:
            continue
        year, month = (int(p) for p in row["REF_DATE"].split("-")[:2])
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        if cutoff and month_end < cutoff:
            continue
        hs = digits_only(row["HS_CODE"])
        attrs = {
            "subject": {"type": "product", "hs_code": hs, "description": row["DESCRIPTION"]},
            "price": {"amount": round(float(row["VALUE"]) / quantity, 4), "currency": CURRENCY,
                      "per_unit": row["UOM"]},
            "observed_at": to_utc_iso(month_end),
            "location": {"country": "CA"},
            "source_url": SOURCE_URL,
        }
        yield envelope(source=NAME, native_id=f"{row['REF_DATE']}-CA-{hs}",
                       type_="price_observation", observed_at=to_utc_iso(month_end),
                       attributes=attrs)
