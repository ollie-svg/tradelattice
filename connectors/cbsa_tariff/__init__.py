"""CBSA Customs Tariff schedule -> TariffLine records.

Live mode parses the HTML chapter pages published at
https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/<year>/html/<revision>/chNN-eng.html
"""
from __future__ import annotations

import logging
import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from connectors._base import (
    Envelope,
    digits_only,
    envelope,
    parse_date,
    read_csv,
    to_utc_iso,
)
from connectors.cbsa_tariff.parse import parse_chapter_html, parse_preferential

log = logging.getLogger(__name__)

NAME = "cbsa_tariff"
LIVE_URL = "https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/"
SAMPLE = Path(__file__).parent / "sample" / "customs_tariff_sample.csv"
EFFECTIVE_FROM = "2026-01-01"
# Revision 02 = T2026-2. Assumption: the base edition (T2026) uses revision "00".
EDITION = {"name": "T2026-2", "revision": "02", "effective_from": "2026-09-01"}
USER_AGENT = "TradeLattice/0.1 (+https://tradelattice.ca)"
CHAPTER_URL = (
    "https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/{year}/html/{revision}/ch{nn:02d}-eng.html"
)
REQUEST_DELAY_S = 0.5
TIMEOUT_S = 30


def parse_rates(mfn: str, preferential: str) -> list[dict[str, str]]:
    """Build the spec `rates[]` array: MFN first, then `TREATMENT:rate;...` entries."""
    rates = [{"treatment": "MFN", "rate": mfn}] if mfn else []
    for part in filter(None, (p.strip() for p in preferential.split(";"))):
        treatment, _, rate = part.partition(":")
        if treatment.strip() and rate.strip():
            rates.append({"treatment": treatment.strip(), "rate": rate.strip()})
    return rates


def chapter_url(edition: dict[str, str], chapter: int) -> str:
    """URL of a chapter page *as published under this edition's own revision*.

    Only a fallback: an edition's index page points each chapter at whichever
    revision last changed it (T2026-1 changed one chapter; its other 98 links go
    to revision 00). Use `chapter_urls()` for the real map.
    """
    return CHAPTER_URL.format(year=edition["name"][1:5], revision=edition["revision"], nn=chapter)


def index_url(edition: dict[str, str]) -> str:
    year = edition["name"][1:5]
    rev = int(edition["revision"])
    suffix = f"-{rev}" if rev else ""
    return f"https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/{year}/html/tblmod{suffix}-eng.html"


_CHAPTER_LINK = re.compile(r'href="(/trade-commerce/tariff-tarif/\d{4}/html/\d{2}/ch(\d{2})-eng\.html)"')


def chapter_urls(edition: dict[str, str], index_html: str | None = None) -> dict[int, str]:
    """Map chapter number -> absolute chapter URL by reading the edition's index page."""
    if index_html is None:
        index_html = _get(index_url(edition))
        if index_html is None:
            raise RuntimeError(f"edition index not found: {index_url(edition)}")
    urls: dict[int, str] = {}
    for path, nn in _CHAPTER_LINK.findall(index_html):
        urls.setdefault(int(nn), "https://www.cbsa-asfc.gc.ca" + path)
    return urls


def _get(url: str) -> str | None:
    """GET a chapter page. Returns None on 404; retries once on any other failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if attempt == 2:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
        time.sleep(REQUEST_DELAY_S)
    return None  # pragma: no cover


def records_from_html(html_text: str, *, effective_from: str, observed_at: str) -> Iterator[Envelope]:
    """Map parsed chapter rows to TariffLine envelopes (one per tariff_item + ss)."""
    for row in parse_chapter_html(html_text):
        item, ss = row["tariff_item"], row["ss"]
        attrs = {
            "hs_code": digits_only(item) + ss,
            "description": row["description"],
            "rates": [{"treatment": "MFN", "rate": row["mfn_rate"]}, *parse_preferential(row["preferential"])],
            "effective_from": effective_from,
            "effective_to": None,
        }
        native_id = f"{item}.{ss}" if ss else item
        yield envelope(source=NAME, native_id=native_id, type_="tariff_line",
                       observed_at=observed_at, attributes=attrs)


def fetch(
    since: datetime | None = None,
    live: bool = False,
    edition: dict[str, str] | None = None,
    chapters: Iterable[int] | None = None,
) -> Iterator[Envelope]:
    """Yield TariffLine envelopes. `since` is ignored: the schedule is a full snapshot."""
    if live:
        ed = edition or EDITION
        nums = sorted(set(chapters)) if chapters is not None else list(range(1, 100))
        for n in nums:
            if not 1 <= n <= 99:
                raise ValueError(f"chapter out of range 1..99: {n}")
        urls = chapter_urls(ed)
        first = True
        for n in nums:
            if not first:
                time.sleep(REQUEST_DELAY_S)
            first = False
            url = urls.get(n) or chapter_url(ed, n)
            html_text = _get(url)
            if html_text is None:
                log.warning("cbsa_tariff: chapter %02d not found (404), skipping: %s", n, url)
                continue
            observed = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            yield from records_from_html(html_text, effective_from=ed["effective_from"],
                                         observed_at=observed)
        return
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
