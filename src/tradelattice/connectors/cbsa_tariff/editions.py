"""CBSA Customs Tariff edition tracking: list editions, detect new ones, diff rate sets."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

INDEX_URL = "https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/{year}/menu-eng.html"
USER_AGENT = "TradeLattice/0.1 (+https://tradelattice.ca)"
TIMEOUT_S = 30
MAX_TABLE_ROWS = 200

# Matches e.g.: <span ...>T2026-2</span> <span class="pull-right">Effective date: 2026-09-01</span>
EDITION_RE = re.compile(
    r"(T\d{4}(?:-\d+)?)\s*</span>\s*<span[^>]*>\s*Effective date:\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def parse_editions(html_text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for name, eff in EDITION_RE.findall(html_text):
        _, _, rev = name.partition("-")
        out.append({"name": name, "revision": f"{int(rev or 0):02d}", "effective_from": eff})
    return out


def _fetch_index(year: int) -> str | None:
    req = urllib.request.Request(INDEX_URL.format(year=year), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def list_editions(year: int) -> list[dict[str, str]]:
    """Editions for `year`, newest first, as listed on the CBSA index page ([] on 404)."""
    html_text = _fetch_index(year)
    return parse_editions(html_text) if html_text else []


def current_edition(year: int | None = None) -> dict[str, str]:
    year = year or datetime.now(UTC).year
    editions = list_editions(year)
    if not editions and year == datetime.now(UTC).year:
        editions = list_editions(year - 1)
    if not editions:
        raise RuntimeError(f"no CBSA tariff editions found for {year}")
    return editions[0]


def _load(path: str | Path) -> dict[str, dict[str, Any]]:
    recs: dict[str, dict[str, Any]] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                recs[rec["id"]] = rec
    return recs


def _rate_set(rec: dict[str, Any]) -> frozenset[tuple[str, str]]:
    return frozenset((r["treatment"], r["rate"]) for r in rec["attributes"].get("rates", []))


def diff_records(old_path: str | Path, new_path: str | Path) -> dict[str, list]:
    old, new = _load(old_path), _load(new_path)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for rid in sorted(set(old) & set(new)):
        if _rate_set(old[rid]) != _rate_set(new[rid]):
            a = new[rid]["attributes"]
            changed.append({
                "id": rid,
                "hs_code": a.get("hs_code", ""),
                "description": a.get("description", ""),
                "before": old[rid]["attributes"].get("rates", []),
                "after": a.get("rates", []),
            })
    return {"added": added, "removed": removed, "changed": changed}


def _rates_by_treatment(rates: list[dict[str, str]]) -> dict[str, str]:
    return {r["treatment"]: r["rate"] for r in rates}


def format_diff_markdown(diff: dict[str, list], old_name: str, new_name: str) -> str:
    changed = diff["changed"]
    lines = [
        f"## CBSA tariff diff: {old_name} -> {new_name}",
        "",
        f"- Added: {len(diff['added'])}",
        f"- Removed: {len(diff['removed'])}",
        f"- Changed: {len(changed)}",
    ]
    rows: list[str] = []
    for item in changed:
        before, after = _rates_by_treatment(item["before"]), _rates_by_treatment(item["after"])
        for treatment in sorted(set(before) | set(after)):
            b, a = before.get(treatment), after.get(treatment)
            if b != a:
                rows.append(f"| {item['hs_code']} | {treatment} | {b or '(none)'} -> {a or '(none)'} |")
    if rows:
        lines += ["", "| hs_code | treatment | before -> after |", "| --- | --- | --- |"]
        lines += rows[:MAX_TABLE_ROWS]
        if len(rows) > MAX_TABLE_ROWS:
            lines += ["", f"{len(rows) - MAX_TABLE_ROWS} more"]
    return "\n".join(lines) + "\n"
