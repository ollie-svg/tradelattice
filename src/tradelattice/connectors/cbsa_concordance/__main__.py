import argparse
import sys
from collections import Counter
from pathlib import Path

from tradelattice.connectors import _base
from tradelattice.connectors.cbsa_concordance import NAME, collect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"python -m tradelattice.connectors.{NAME}")
    parser.add_argument("--out", required=True, type=Path, help="output JSONL file")
    parser.add_argument("--live", action="store_true", help="fetch live data (opt-in)")
    parser.add_argument("--year", type=int, default=None, help="tariff year (live; default current)")
    parser.add_argument("--file", default=None, help="only this workbook filename (live)")
    parser.add_argument("--from-edition", default=None, help="e.g. T2021 (required for conc-8 files)")
    parser.add_argument("--to-edition", default=None, help="e.g. T2022 (required for conc-8 files)")
    parser.add_argument("--report", action="store_true",
                        help="print counts by relation and change code to stderr")
    args = parser.parse_args(argv)
    rows = collect(live=args.live, year=args.year, file=args.file,
                   from_edition=args.from_edition, to_edition=args.to_edition)
    n = _base.write_jsonl((rec for _, rec in rows), args.out)
    print(f"{NAME}: wrote {n} records to {args.out}")
    if args.report:
        rel = Counter(rec["attributes"]["relation"] for _, rec in rows)
        chg = Counter("(blank)" if p.change == "" else "(none)" if p.change is None else p.change
                      for p, _ in rows)
        print("by relation:", dict(sorted(rel.items())), file=sys.stderr)
        print("by change code:", dict(sorted(chg.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
