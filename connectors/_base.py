"""Shared helpers for OpenGoods connectors."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

Envelope = dict[str, Any]

LIVE_NOT_IMPLEMENTED = (
    "{name}: live fetch is not implemented yet (offline-first, see ADR 0003). "
    "TODO: implement against {url}. Run without --live to use the bundled sample."
)


def live_not_implemented(name: str, url: str) -> NotImplementedError:
    return NotImplementedError(LIVE_NOT_IMPLEMENTED.format(name=name, url=url))


def read_csv(path: Path) -> Iterator[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            yield {k: (v or "").strip() for k, v in row.items() if k is not None}


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def to_utc_iso(d: date, end_of_day: bool = False) -> str:
    t = "23:59:59" if end_of_day else "00:00:00"
    return f"{d.isoformat()}T{t}Z"


def since_date(since: datetime | None) -> date | None:
    return since.date() if since is not None else None


def envelope(
    *, source: str, native_id: str, type_: str, observed_at: str, attributes: dict[str, Any],
    jurisdiction: str = "CA",
) -> Envelope:
    return {
        "id": f"{source}:{native_id}",
        "type": type_,
        "source": source,
        "observed_at": observed_at,
        "jurisdiction": jurisdiction,
        "attributes": attributes,
    }


def write_jsonl(records: Iterable[Envelope], out: Path) -> int:
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def run_cli(name: str, fetch: Callable[..., Iterator[Envelope]], argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(prog=f"python -m connectors.{name}")
    parser.add_argument("--out", required=True, type=Path, help="output JSONL file")
    parser.add_argument("--live", action="store_true", help="fetch live data (opt-in)")
    parser.add_argument("--since", type=datetime.fromisoformat, default=None,
                        help="ISO date/datetime; only emit records newer than this")
    args = parser.parse_args(argv)
    since = args.since
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    n = write_jsonl(fetch(since=since, live=args.live), args.out)
    print(f"{name}: wrote {n} records to {args.out}")
    return 0
