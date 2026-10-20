"""CLI: python -m api.cli load FILE.jsonl"""
from __future__ import annotations

import argparse
import json
import sys

from .db import SessionLocal, init_db
from .store import upsert_records

BATCH = 500


def load(path: str) -> tuple[int, int]:
    from spec.validate import validate_record

    init_db()
    loaded = invalid = 0
    batch: list[dict] = []

    def flush(session) -> None:
        nonlocal loaded
        if batch:
            loaded += upsert_records(session, batch)
            session.commit()
            batch.clear()

    with SessionLocal() as session, open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError as exc:
                print(f"line {lineno}: invalid JSON: {exc}", file=sys.stderr)
                invalid += 1
                continue
            errors = validate_record(rec)
            if errors:
                print(f"line {lineno}: {'; '.join(errors)}", file=sys.stderr)
                invalid += 1
                continue
            batch.append(rec)
            if len(batch) >= BATCH:
                flush(session)
        flush(session)
    return loaded, invalid


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m api.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("load", help="upsert records from a JSONL file")
    lp.add_argument("file")
    args = p.parse_args(argv)
    loaded, invalid = load(args.file)
    print(f"loaded={loaded} invalid={invalid}")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
