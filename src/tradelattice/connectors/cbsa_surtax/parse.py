"""Parse Finance Canada counter-tariff lists (HTML table or bundled JSON)."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

_ITEM = re.compile(r"\d{4}\.\d{2}\.\d{2}")
_INT = re.compile(r"\d+")


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _clean(item: str, heading: str, desc: str, rate: str) -> dict | None:
    item, rate = item.strip(), rate.strip()
    if not _ITEM.fullmatch(item) or not _INT.fullmatch(rate):
        return None
    return {"item": item, "heading": heading.strip(), "desc": desc.strip(), "rate": int(rate)}


def parse_finance_list_html(html_text: str) -> list[dict]:
    """Rows of (Tariff item | HS heading | description | rate); malformed rows are skipped."""
    p = _TableParser()
    p.feed(html_text)
    out: list[dict] = []
    for cells in p.rows:
        if len(cells) != 4:
            continue
        row = _clean(*cells)
        if row is not None:
            out.append(row)
    return out


def rows_from_json(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[dict] = []
    for d in data:
        rate = d.get("rate")
        if isinstance(rate, bool) or not isinstance(rate, int):
            continue
        row = _clean(str(d.get("item", "")), str(d.get("heading", "")),
                     str(d.get("desc", "")), str(rate))
        if row is not None:
            out.append(row)
    return out
