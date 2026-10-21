import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from connectors import _base
from connectors.cbsa_tariff import NAME, fetch
from connectors.cbsa_tariff import editions as ed

SUBCOMMANDS = {"editions", "check", "diff"}
EXIT_NEW_EDITION = 10


def _fetch_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"python -m connectors.{NAME}")
    parser.add_argument("--out", required=True, type=Path, help="output JSONL file")
    parser.add_argument("--live", action="store_true", help="fetch live data (opt-in)")
    parser.add_argument("--since", type=datetime.fromisoformat, default=None,
                        help="ISO date/datetime; accepted for CLI parity (full snapshot, ignored)")
    parser.add_argument("--chapters", default=None,
                        help="comma-separated chapter numbers to fetch, e.g. 9,20 (live only)")
    parser.add_argument("--edition", default=None,
                        help="edition name, e.g. T2026-1 (live only; default: bundled edition)")
    args = parser.parse_args(argv)
    since = args.since
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    chapters = [int(c) for c in args.chapters.split(",") if c.strip()] if args.chapters else None
    edition = None
    if args.edition:
        year = int(args.edition[1:5])
        edition = next((e for e in ed.list_editions(year) if e["name"] == args.edition), None)
        if edition is None:
            print(f"{NAME}: edition {args.edition} not found", file=sys.stderr)
            return 2
    n = _base.write_jsonl(fetch(since=since, live=args.live, edition=edition, chapters=chapters), args.out)
    print(f"{NAME}: wrote {n} records to {args.out}")
    return 0


def _check(state: Path) -> int:
    cur = ed.current_edition()
    old = None
    if state.exists():
        old = json.loads(state.read_text(encoding="utf-8")).get("name")
    record = {**cur, "checked_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if old == cur["name"]:
        print(f"unchanged {cur['name']}")
        return 0
    print(f"new {cur['name']} (was {old})")
    return EXIT_NEW_EDITION


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in SUBCOMMANDS:
        return _fetch_main(argv)
    parser = argparse.ArgumentParser(prog=f"python -m connectors.{NAME}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_ed = sub.add_parser("editions", help="list editions for a year as JSON")
    p_ed.add_argument("--year", type=int, default=datetime.now(UTC).year)
    p_ck = sub.add_parser("check", help="detect a new edition; exit 10 if new")
    p_ck.add_argument("--state", required=True, type=Path)
    p_df = sub.add_parser("diff", help="diff two JSONL snapshots")
    p_df.add_argument("old", type=Path)
    p_df.add_argument("new", type=Path)
    p_df.add_argument("--markdown", action="store_true")
    p_df.add_argument("--old-name", default="old")
    p_df.add_argument("--new-name", default="new")
    args = parser.parse_args(argv)
    if args.cmd == "editions":
        print(json.dumps(ed.list_editions(args.year), indent=2))
        return 0
    if args.cmd == "check":
        return _check(args.state)
    d = ed.diff_records(args.old, args.new)
    if args.markdown:
        print(ed.format_diff_markdown(d, args.old_name, args.new_name), end="")
    else:
        print(json.dumps(d, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
