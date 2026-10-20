"""CanadaBuys open tender notices -> Tender records.

TODO(live): https://canadabuys.canada.ca/en/tender-opportunities (open data CSV link unconfirmed).
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from connectors._base import (
    Envelope,
    envelope,
    live_not_implemented,
    parse_date,
    read_csv,
    since_date,
    to_utc_iso,
)

NAME = "canadabuys"
LIVE_URL = "https://canadabuys.canada.ca/en/tender-opportunities"
SAMPLE = Path(__file__).parent / "sample" / "tender_notices_sample.csv"


def fetch(since: datetime | None = None, live: bool = False) -> Iterator[Envelope]:
    """Yield Tender envelopes; with `since`, only notices published on/after that date."""
    if live:
        raise live_not_implemented(NAME, LIVE_URL)
    cutoff = since_date(since)
    for row in read_csv(SAMPLE):
        published = parse_date(row["publicationDate"])
        if cutoff and published < cutoff:
            continue
        codes = [f"{p}:{row[k]}" for k, p in (("gsin", "GSIN"), ("unspsc", "UNSPSC")) if row[k]]
        attrs = {
            "title": row["title"],
            "buyer": {"name": row["contractingEntityName"], "jurisdiction": "CA",
                      "level": "federal"},
            "category_codes": codes,
            "published_at": to_utc_iso(published),
            "closes_at": (to_utc_iso(parse_date(row["tenderClosingDate"]), end_of_day=True)
                          if row["tenderClosingDate"] else None),
            "value_estimate": None,
            "url": row["noticeURL"],
            "status": row["tenderStatus"].lower(),
        }
        yield envelope(source=NAME, native_id=row["referenceNumber"], type_="tender",
                       observed_at=to_utc_iso(published), attributes=attrs)
