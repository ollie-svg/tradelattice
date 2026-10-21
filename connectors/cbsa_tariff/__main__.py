import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from connectors import _base
from connectors.cbsa_tariff import NAME, fetch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"python -m connectors.{NAME}")
    parser.add_argument("--out", required=True, type=Path, help="output JSONL file")
    parser.add_argument("--live", action="store_true", help="fetch live data (opt-in)")
    parser.add_argument("--since", type=datetime.fromisoformat, default=None,
                        help="ISO date/datetime; accepted for CLI parity (full snapshot, ignored)")
    parser.add_argument("--chapters", default=None,
                        help="comma-separated chapter numbers to fetch, e.g. 9,20 (live only)")
    args = parser.parse_args(argv)
    since = args.since
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    chapters = [int(c) for c in args.chapters.split(",") if c.strip()] if args.chapters else None
    n = _base.write_jsonl(fetch(since=since, live=args.live, chapters=chapters), args.out)
    print(f"{NAME}: wrote {n} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
