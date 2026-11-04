"""Parse CBSA / Finance Canada concordance workbooks into (from, to) code pairs."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import openpyxl


@dataclass(frozen=True)
class Pair:
    from_code: str  # old / obsolete code
    to_code: str  # new code
    change: str | None = None  # Finance "Change" column (SC, WC, ...); not emitted in records


def _digits(value: object, width: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0", text):  # numeric cell read back as float
        text = text[:-2]
    d = re.sub(r"\D", "", text)
    return d.zfill(width) if d else ""


def _header(row: tuple) -> list[str]:
    return [str(c).strip() if c is not None else "" for c in row]


def _parse_8digit(rows: list[tuple], start: int) -> list[Pair]:
    pairs: list[Pair] = []
    for row in rows[start + 1:]:
        old, new = _digits(row[0], 8), _digits(row[1], 8)
        if not old or not new:
            continue
        change = row[2] if len(row) > 2 else None
        pairs.append(Pair(old, new, None if change is None else str(change).strip()))
    return pairs


def _parse_10digit(rows: list[tuple], start: int, head: list[str]) -> list[Pair]:
    new_i = next(i for i, h in enumerate(head) if h.lower().startswith("new hs10"))
    old_i = next(i for i, h in enumerate(head) if h.lower().startswith("obsolete hs10"))
    pairs: list[Pair] = []
    for row in rows[start + 1:]:
        new, old = _digits(row[new_i], 10), _digits(row[old_i], 10)
        if not old or not new:
            continue
        pairs.append(Pair(old, new, None))
    return pairs


def load_workbook_pairs(path: str | Path) -> list[Pair]:
    """Auto-detect the layout and return (old, new) pairs.

    8-digit Finance layout: the sheet whose header starts with 'Current TI'
    (columns Current TI, <year> Tariff Item, Change), already old -> new.
    10-digit layout: header cells starting 'New HS10' / 'Obsolete HS10'; the
    file lists new -> obsolete, so columns are swapped to (old, new).
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
            for i, row in enumerate(rows[:15]):
                head = _header(row)
                first = head[0].lower() if head else ""
                if first.startswith("current ti") and any("tariff item" in h.lower() for h in head):
                    return _parse_8digit(rows, i)
                if any(h.lower().startswith(("new hs10", "obsolete hs10")) for h in head):
                    return _parse_10digit(rows, i, head)
    finally:
        wb.close()
    raise ValueError(f"{path}: no recognised concordance layout (8-digit 'Current TI' or 10-digit 'New HS10')")


def derive_relations(pairs: list[Pair]) -> list[dict]:
    """One dict per pair: from_code, to_code, change, relation.

    same: from == to and 1:1. The HS-cycle table lists only codes involved in a
    change, so an X->X row normally appears only when X is a source or target of
    a split/merge: its scope changed though its number did not, so it is classed
    split/merged (needs review), never `same`. renumbered: from != to and 1:1.
    split: the source has more than one target (wins over merged when the target
    also has several sources). merged: the target has several sources and the
    source has exactly one target. `removed` is never produced: every row in
    these workbooks carries both codes.
    """
    targets = Counter(p.from_code for p in pairs)
    sources = Counter(p.to_code for p in pairs)
    out: list[dict] = []
    for p in pairs:
        if targets[p.from_code] > 1:
            rel = "split"
        elif sources[p.to_code] > 1:
            rel = "merged"
        elif p.from_code == p.to_code:
            rel = "same"
        else:
            rel = "renumbered"
        out.append({"from_code": p.from_code, "to_code": p.to_code,
                    "change": p.change, "relation": rel})
    return out
