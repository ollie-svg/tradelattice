"""Validate TradeLattice record files against the v0.3 JSON Schemas.

Usage: python -m tradelattice.spec.validate src/tradelattice/spec/examples/*.json
Each file may contain a single record or an array of records.
Exit status is non-zero if any record is invalid or unreadable.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR = Path(__file__).parent / "schemas"

_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)

FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time", raises=ValueError)
def _is_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if not _RFC3339.match(value):
        raise ValueError("not an RFC 3339 date-time")
    datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    return True


@FORMAT_CHECKER.checks("date", raises=ValueError)
def _is_date(value: object) -> bool:
    if isinstance(value, str):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("not a date")
        date.fromisoformat(value)
    return True


@FORMAT_CHECKER.checks("uri", raises=ValueError)
def _is_uri(value: object) -> bool:
    if isinstance(value, str):
        parts = urlparse(value)
        if not parts.scheme or not (parts.netloc or parts.path) or " " in value:
            raise ValueError("not a URI")
    return True


@lru_cache(maxsize=1)
def _load() -> tuple[Registry, dict[str, dict]]:
    schemas: dict[str, dict] = {}
    registry = Registry()
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas[path.name.removesuffix(".schema.json")] = schema
        registry = registry.with_resource(
            schema["$id"], Resource.from_contents(schema, default_specification=DRAFT202012)
        )
    return registry, schemas


def validator_for_type(record_type: str) -> Draft202012Validator:
    registry, schemas = _load()
    if record_type not in schemas or record_type == "envelope":
        raise KeyError(f"unknown record type: {record_type!r}")
    return Draft202012Validator(
        schemas[record_type], registry=registry, format_checker=FORMAT_CHECKER
    )


def semantic_checks(record: dict) -> list[str]:
    """Checks JSON Schema cannot express. Applied to prohibition and surtax_order records."""
    if record.get("type") not in ("prohibition", "surtax_order"):
        return []
    attrs = record.get("attributes")
    if not isinstance(attrs, dict):
        return []
    start, end = attrs.get("effective_from"), attrs.get("effective_to")
    if isinstance(start, str) and isinstance(end, str):
        try:
            if date.fromisoformat(end) < date.fromisoformat(start):
                return [
                    (
                        f"attributes/effective_to: {end} is before effective_from {start}; "
                        "effective_to, when set, must not be before effective_from"
                    )
                ]
        except ValueError:
            return []  # malformed dates are reported by the schema format check
    return []


def validate_record(record: dict) -> list[str]:
    """Return a list of error messages (empty if valid)."""
    if not isinstance(record, dict):
        return ["record is not a JSON object"]
    registry, schemas = _load()
    rtype = record.get("type")
    try:
        validator = validator_for_type(rtype) if isinstance(rtype, str) else None
    except KeyError:
        validator = None
    if validator is None:
        validator = Draft202012Validator(
            schemas["envelope"], registry=registry, format_checker=FORMAT_CHECKER
        )
    errors = [
        f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(record), key=lambda e: list(map(str, e.absolute_path)))
    ]
    return errors + semantic_checks(record)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: python -m tradelattice.spec.validate FILE [FILE...]", file=sys.stderr)
        return 2
    failed = False
    for name in args:
        try:
            text = Path(name).read_text(encoding="utf-8")
            if name.endswith(".jsonl"):
                data = [json.loads(line) for line in text.splitlines() if line.strip()]
            else:
                data = json.loads(text)
        except (OSError, ValueError) as exc:
            print(f"FAIL {name}: {exc}")
            failed = True
            continue
        records = data if isinstance(data, list) else [data]
        errors = [f"[{i}] {m}" for i, r in enumerate(records) for m in validate_record(r)]
        if errors:
            failed = True
            print(f"FAIL {name}")
            for m in errors:
                print(f"  {m}")
        else:
            print(f"OK   {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
