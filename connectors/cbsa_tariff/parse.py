"""Parse CBSA Customs Tariff HTML chapter pages (standard library only)."""
from __future__ import annotations

import re
from html.parser import HTMLParser

_ITEM_RE = re.compile(r"^\d{4}(\.\d{2}){0,2}$")
_SS_RE = re.compile(r"^\d{1,2}$")


def _clean(text: str) -> str:
    """Collapse whitespace within lines, keep newlines (from <br>/<p>) as line breaks."""
    text = text.replace("\xa0", " ")
    lines = (re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in text.split("\n"))
    return "\n".join(ln for ln in lines if ln)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._cell_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            if self._cell is None:
                self._cell = []
            self._cell_depth += 1
        elif tag in ("br", "p", "li", "div") and self._cell is not None:
            self._cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None:
            self._cell_depth -= 1
            if self._cell_depth <= 0:
                if self._row is not None:
                    self._row.append(_clean("".join(self._cell)))
                self._cell, self._cell_depth = None, 0
        elif tag in ("p", "li", "div") and self._cell is not None:
            self._cell.append("\n")
        elif tag == "tr" and self._row is not None:
            if self._cell is not None:  # unterminated cell
                self._row.append(_clean("".join(self._cell)))
                self._cell, self._cell_depth = None, 0
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_chapter_html(html_text: str) -> list[dict]:
    """Return one dict per priced tariff row (heading rows without an MFN rate are skipped)."""
    parser = _TableParser()
    parser.feed(html_text)
    parser.close()
    out: list[dict] = []
    for cells in parser.rows:
        if len(cells) < 6:
            continue
        item, ss, desc, uom, mfn, pref = (c.strip() for c in cells[:6])
        if not _ITEM_RE.match(item) or not mfn:
            continue
        if ss and not _SS_RE.match(ss):
            continue
        out.append({
            "tariff_item": item,
            "ss": ss,
            "description": " ".join(desc.split()),
            "uom": uom,
            "mfn_rate": " ".join(mfn.split()),
            "preferential": pref,
        })
    return out


def parse_preferential(raw: str) -> list[dict]:
    """Expand "CCCT, LDCT: Free; UST: 2%" into [{"treatment","rate"}, ...]."""
    out: list[dict] = []
    codes = ""  # treatment codes waiting for a rate (line wrapped before/after the colon)
    has_colon = False
    for group in re.split(r"[;\n]", raw or ""):
        group = group.strip()
        if not group:
            continue
        head, colon, rate = group.partition(":")
        if colon:
            codes = f"{codes} {head}".strip()
            has_colon = True
            rate = rate.strip()
        elif has_colon:  # the rate wrapped onto its own line
            rate = group
        else:  # more codes wrapped onto the next line
            codes = f"{codes} {group}".strip()
            continue
        if not rate:
            continue
        rate = " ".join(rate.split())
        for code in codes.split(","):
            if code.strip():
                out.append({"treatment": code.strip(), "rate": rate})
        codes, has_colon = "", False
    return out
