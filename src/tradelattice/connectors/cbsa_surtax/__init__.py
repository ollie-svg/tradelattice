"""Finance Canada counter-tariff (surtax) lists on US-origin goods -> SurtaxOrder records.

Each list line is a surtax under the Customs Tariff (s.53) applied in addition to the
tariff rate, as a percentage of value for duty, by country of origin. Known gap (v0.2):
remission orders and exclusions are not modelled. Assumptions: observed_at is the list's
effective_from at T00:00:00Z (the page carries no publication timestamp); no SOR number
appears on the source page; hs_prefix is the 8-digit tariff item without dots.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

from tradelattice.connectors._base import Envelope, envelope, to_utc_iso
from tradelattice.connectors.cbsa_surtax.parse import parse_finance_list_html, rows_from_json

NAME = "cbsa_surtax"
SAMPLE_DIR = Path(__file__).parent / "sample"
USER_AGENT = "TradeLattice/0.1 (+https://tradelattice.ca)"
TIMEOUT_S = 30
RETRY_DELAY_S = 0.5

LISTS: dict[str, dict[str, Any]] = {
    "finance-ca-counter-tariffs-2026-09-08": {
        "url": "https://www.canada.ca/en/department-finance/news/2026/08/"
               "list-of-products-from-the-united-states-subject-to-counter-tariffs-"
               "effective-september-8-2026.html",
        "origin_country": "US",
        "effective_from": "2026-09-08",
        "effective_to": None,
        "sample": "finance-ca-counter-tariffs-2026-09-08.json",
    },
}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
        time.sleep(RETRY_DELAY_S)
    raise RuntimeError("unreachable")  # pragma: no cover


def records_from_rows(
    rows: Iterable[dict], *, list_id: str, origin_country: str,
    effective_from: str, effective_to: str | None, source_url: str,
) -> list[Envelope]:
    observed = to_utc_iso(date.fromisoformat(effective_from))
    out: list[Envelope] = []
    for r in rows:
        prefix = re.sub(r"\D", "", r["item"])
        out.append(envelope(
            source=NAME,
            native_id=f"{list_id}:{prefix}:{origin_country}",
            type_="surtax_order",
            observed_at=observed,
            attributes={
                "hs_prefix": prefix, "origin_country": origin_country,
                "pct": str(r["rate"]), "list_id": list_id,
                "effective_from": effective_from, "effective_to": effective_to,
                "source_url": source_url,
            },
        ))
    return out


def fetch(
    since: datetime | None = None,
    live: bool = False,
    list_id: str | None = None,
    url: str | None = None,
    origin_country: str = "US",
    effective_from: str | None = None,
    effective_to: str | None = None,
) -> Iterator[Envelope]:
    """Yield SurtaxOrder envelopes. `since` is ignored (full list snapshots).

    Sample mode emits every registered list's bundled sample. Live mode fetches the
    registry URL for `list_id` (default: all registered lists), or an explicit `url`
    which requires `list_id` and `effective_from`.
    """
    if not live:
        for lid, meta in LISTS.items():
            yield from records_from_rows(
                rows_from_json(SAMPLE_DIR / meta["sample"]), list_id=lid,
                origin_country=meta["origin_country"], effective_from=meta["effective_from"],
                effective_to=meta["effective_to"], source_url=meta["url"])
        return
    if url is not None:
        if not list_id or not effective_from:
            raise ValueError("--url requires --list-id and --effective-from")
        jobs = [(list_id, url, origin_country, effective_from, effective_to)]
    else:
        ids = [list_id] if list_id else list(LISTS)
        unknown = [i for i in ids if i not in LISTS]
        if unknown:
            raise ValueError(f"unknown list id {unknown[0]!r}; known: {sorted(LISTS)}")
        jobs = [(i, LISTS[i]["url"], LISTS[i]["origin_country"],
                 LISTS[i]["effective_from"], LISTS[i]["effective_to"]) for i in ids]
    for lid, u, origin, eff_from, eff_to in jobs:
        rows = parse_finance_list_html(_get(u))
        if not rows:
            raise ValueError(f"{u}: no tariff rows parsed")
        yield from records_from_rows(rows, list_id=lid, origin_country=origin,
                                     effective_from=eff_from, effective_to=eff_to, source_url=u)


def applicable(records: Iterable[Envelope], hs_code: str, origin_country: str, on: str) -> list[dict]:
    """Surtax_order attributes in force for an HS code, origin and ISO date `on`.

    A record applies when its hs_prefix is a prefix of the digits of `hs_code`, origin
    matches, and effective_from <= on < effective_to (or effective_to is null).
    Longest prefix first; ties keep input order.
    """
    code = re.sub(r"\D", "", hs_code)
    hits = []
    for rec in records:
        if rec.get("type") != "surtax_order":
            continue
        a = rec["attributes"]
        if (code.startswith(a["hs_prefix"]) and a["origin_country"] == origin_country
                and a["effective_from"] <= on and (a["effective_to"] is None or on < a["effective_to"])):
            hits.append(a)
    return sorted(hits, key=lambda a: -len(a["hs_prefix"]))
