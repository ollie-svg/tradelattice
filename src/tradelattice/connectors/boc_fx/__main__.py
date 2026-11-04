import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from tradelattice.connectors import _base
from tradelattice.connectors.boc_fx import NAME, fetch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"python -m tradelattice.connectors.{NAME}")
    parser.add_argument("--out", required=True, type=Path, help="output JSONL file")
    parser.add_argument("--live", action="store_true", help="fetch live data (opt-in)")
    parser.add_argument("--since", type=datetime.fromisoformat, default=None,
                        help="ISO date; live window start (same as --start)")
    parser.add_argument("--start", type=date.fromisoformat, default=None, help="YYYY-MM-DD window start")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="YYYY-MM-DD window end")
    parser.add_argument("--currencies", default=None, help="comma-separated, e.g. USD,EUR")
    args = parser.parse_args(argv)
    since = args.since
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    cur = [c.strip() for c in args.currencies.split(",") if c.strip()] if args.currencies else None
    n = _base.write_jsonl(
        fetch(since=since, live=args.live, start=args.start, end=args.end, currencies=cur), args.out)
    print(f"{NAME}: wrote {n} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
