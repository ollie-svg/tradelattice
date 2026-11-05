import argparse
import sys
from collections import Counter
from pathlib import Path

from tradelattice.connectors import _base
from tradelattice.connectors.cbsa_surtax import NAME, fetch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"python -m tradelattice.connectors.{NAME}")
    parser.add_argument("--out", required=True, type=Path, help="output JSONL file")
    parser.add_argument("--live", action="store_true", help="fetch live data (opt-in)")
    parser.add_argument("--list-id", default=None, help="registered list id (live) or id for --url")
    parser.add_argument("--url", default=None, help="explicit Finance list page (live)")
    parser.add_argument("--origin-country", default="US", help="with --url (default US)")
    parser.add_argument("--effective-from", default=None, help="YYYY-MM-DD, required with --url")
    parser.add_argument("--effective-to", default=None, help="YYYY-MM-DD, with --url")
    parser.add_argument("--report", action="store_true",
                        help="print counts by pct and HS chapter to stderr")
    args = parser.parse_args(argv)
    recs = list(fetch(live=args.live, list_id=args.list_id, url=args.url,
                      origin_country=args.origin_country,
                      effective_from=args.effective_from, effective_to=args.effective_to))
    n = _base.write_jsonl(recs, args.out)
    print(f"{NAME}: wrote {n} records to {args.out}")
    if args.report:
        pct = Counter(r["attributes"]["pct"] for r in recs)
        ch = Counter(r["attributes"]["hs_prefix"][:2] for r in recs)
        print("by pct:", dict(sorted(pct.items(), key=lambda kv: -int(kv[0]))), file=sys.stderr)
        print("by chapter:", dict(sorted(ch.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
