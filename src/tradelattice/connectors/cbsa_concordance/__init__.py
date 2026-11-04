"""CBSA / Finance Canada HS concordance workbooks -> HsConcordance records.

Loads any CBSA concordance xlsx: the 8-digit HS-cycle tables (old -> new) and
the yearly 10-digit within-year table (published new -> obsolete, flipped here).
The next WCO edition is HS 2028 (in force 2028-01-01); no 2027/2028 table is
published yet. Assumptions: observed_at is `<to_edition year>-01-01T00:00:00Z`
(edition year start, not a per-line effective date); the January 10-digit
file is assumed to supersede the prior year's last edition (T<year-1> -> T<year>).
"""
from __future__ import annotations

import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

from tradelattice.connectors._base import Envelope, envelope, to_utc_iso
from tradelattice.connectors.cbsa_concordance.parse import (
    Pair,
    derive_relations,
    load_workbook_pairs,
)

NAME = "cbsa_concordance"
BASE_URL = "https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif"
SAMPLE_DIR = Path(__file__).parent / "sample"
# (file, year of the live URL, from_edition, to_edition)
SAMPLES = (
    ("conc-8-finance-2022.xlsx", 2022, "T2021", "T2022"),
    ("conc-10-finance-2026.xlsx", 2026, "T2025", "T2026"),
)
USER_AGENT = "TradeLattice/0.1 (+https://tradelattice.ca)"
TIMEOUT_S = 30
RETRY_DELAY_S = 0.5
_LINK = re.compile(r'href="([^"]*concordance/[^"]*\.xlsx)"', re.IGNORECASE)

Row = tuple[Pair, Envelope]


def file_url(year: int, filename: str) -> str:
    return f"{BASE_URL}/{year}/concordance/{filename}"


def menu_url(year: int) -> str:
    return f"{BASE_URL}/{year}/menu-eng.html"


def _get(url: str) -> bytes:
    """GET a URL; retries once on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
        time.sleep(RETRY_DELAY_S)
    raise RuntimeError("unreachable")  # pragma: no cover


def find_links(html: str, page_url: str) -> list[str]:
    seen: list[str] = []
    for href in _LINK.findall(html):
        url = urllib.parse.urljoin(page_url, href)
        if url not in seen:
            seen.append(url)
    return seen


def resolve_editions(
    filename: str, year: int, from_edition: str | None, to_edition: str | None
) -> tuple[str, str]:
    if (from_edition is None or to_edition is None) and "conc-8" in filename:
        raise ValueError(
            f"{filename} is an HS-cycle (8-digit) concordance: pass both "
            "--from-edition and --to-edition (e.g. T2021 / T2022)"
        )
    return from_edition or f"T{year - 1}", to_edition or f"T{year}"


def records_from_pairs(
    pairs: list[Pair], from_edition: str, to_edition: str, source_url: str
) -> list[Row]:
    year = int(to_edition[1:5])
    observed = to_utc_iso(date(year, 1, 1))
    rows: list[Row] = []
    for pair, rel in zip(pairs, derive_relations(pairs), strict=True):
        rows.append((pair, envelope(
            source=NAME,
            native_id=f"{to_edition}:{pair.from_code}:{pair.to_code}",
            type_="hs_concordance",
            observed_at=observed,
            attributes={
                "from_code": pair.from_code, "to_code": pair.to_code,
                "relation": rel["relation"], "from_edition": from_edition,
                "to_edition": to_edition, "inferred": False, "source_url": source_url,
            },
        )))
    return rows


def collect(
    live: bool = False,
    year: int | None = None,
    file: str | None = None,
    from_edition: str | None = None,
    to_edition: str | None = None,
) -> list[Row]:
    """Return (Pair, record) rows; the Pair keeps the Finance change code."""
    rows: list[Row] = []
    if not live:
        for name, yr, fe, te in SAMPLES:
            pairs = load_workbook_pairs(SAMPLE_DIR / name)
            rows += records_from_pairs(pairs, fe, te, file_url(yr, name))
        return rows
    yr = year or datetime.now(UTC).year
    if file is not None:
        resolve_editions(file, yr, from_edition, to_edition)  # fail before any network
    page = menu_url(yr)
    links = find_links(_get(page).decode("utf-8", "replace"), page)
    if file is not None:
        links = [u for u in links if u.rsplit("/", 1)[-1] == file]
        if not links:
            raise ValueError(f"{file}: not linked from {page}")
    if not links:
        raise ValueError(f"no concordance workbooks linked from {page}")
    eds = {u: resolve_editions(u.rsplit("/", 1)[-1], yr, from_edition, to_edition) for u in links}
    with tempfile.TemporaryDirectory() as tmp:
        for url in links:
            local = Path(tmp) / url.rsplit("/", 1)[-1]
            local.write_bytes(_get(url))
            rows += records_from_pairs(load_workbook_pairs(local), *eds[url], url)
    return rows


def fetch(
    since: datetime | None = None,
    live: bool = False,
    year: int | None = None,
    file: str | None = None,
    from_edition: str | None = None,
    to_edition: str | None = None,
) -> Iterator[Envelope]:
    """Yield HsConcordance envelopes. `since` is ignored (full snapshots).

    Sample mode reads both bundled workbooks with fixed editions and ignores the
    other flags. Live mode downloads the workbooks linked from the yearly menu.
    """
    return (rec for _, rec in collect(live, year, file, from_edition, to_edition))
