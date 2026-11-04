"""Bank of Canada daily exchange rates -> FxRate records (Valet API).

Live mode is the default-useful path: it queries a date window (never `recent=N`,
which returns stale data) of the FX_RATES_DAILY group.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from tradelattice.connectors._base import Envelope, envelope, to_utc_iso

NAME = "boc_fx"
LIVE_URL = "https://www.bankofcanada.ca/valet/observations/group/FX_RATES_DAILY/json"
SAMPLE = Path(__file__).parent / "sample" / "fx_rates_daily_sample.json"
USER_AGENT = "TradeLattice/0.1 (+https://tradelattice.ca)"
DEFAULT_WINDOW_DAYS = 10
TIMEOUT_S = 30
RETRY_DELAY_S = 0.5
_SERIES = re.compile(r"^FX([A-Z]{3})CAD$")


def _get(url: str) -> str:
    """GET a URL; retries once on any failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 2:
                raise
        time.sleep(RETRY_DELAY_S)
    raise RuntimeError("unreachable")  # pragma: no cover


def window_url(start: date, end: date) -> str:
    q = urllib.parse.urlencode({"start_date": start.isoformat(), "end_date": end.isoformat()})
    return f"{LIVE_URL}?{q}"


def records_from_payload(
    payload: dict, currencies: Iterable[str] | None = None
) -> Iterator[Envelope]:
    """One fx_rate envelope per (date, currency); skips series missing on a day."""
    wanted = {c.upper() for c in currencies} if currencies is not None else None
    for obs in payload.get("observations", []):
        day = obs["d"]
        for key, val in obs.items():
            m = _SERIES.match(key)
            if not m or not isinstance(val, dict) or not val.get("v"):
                continue
            cur = m.group(1)
            if wanted is not None and cur not in wanted:
                continue
            yield envelope(
                source=NAME, native_id=f"{day}:{cur}", type_="fx_rate",
                observed_at=to_utc_iso(date.fromisoformat(day)),
                attributes={"currency": cur, "to": "CAD", "rate": str(val["v"]),
                            "on": day, "publisher": "boc"},
            )


def fetch(
    since: datetime | None = None,
    live: bool = False,
    start: date | None = None,
    end: date | None = None,
    currencies: Iterable[str] | None = None,
) -> Iterator[Envelope]:
    """Yield FxRate envelopes.

    Live window: `start`/`since` .. `end`; default is the last 10 calendar days
    ending today (UTC). `since` sets `start` when `start` is not given.
    Sample mode ignores the window flags and reads the bundled response.
    """
    if live:
        end_d = end or datetime.now(UTC).date()
        start_d = start or (since.date() if since is not None else end_d - timedelta(days=DEFAULT_WINDOW_DAYS))
        if start_d > end_d:
            raise ValueError(f"start {start_d} is after end {end_d}")
        payload = json.loads(_get(window_url(start_d, end_d)))
    else:
        payload = json.loads(SAMPLE.read_text(encoding="utf-8"))
    yield from records_from_payload(payload, currencies)
