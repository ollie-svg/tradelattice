"""Overlay lookups that are independent of the database."""
from __future__ import annotations

from collections.abc import Iterable

PROHIBITED_MESSAGE = (
    "goods of this origin under this tariff prefix may not be entered; no landed cost is computed"
)


def prohibited(
    records: Iterable[dict], hs: str, origin: str, on: str, jurisdiction: str
) -> dict | None:
    """Return the 409 body for the longest-prefix prohibition in force, else None.

    A `prohibition` record matches when its envelope jurisdiction equals `jurisdiction`,
    origin matches, hs_prefix is a prefix of `hs`, and effective_from <= on and
    (effective_to is null or on < effective_to).
    """
    best: dict | None = None
    for rec in records:
        if rec.get("type") != "prohibition" or rec.get("jurisdiction") != jurisdiction:
            continue
        a = rec["attributes"]
        if a["origin_country"] != origin or not hs.startswith(a["hs_prefix"]):
            continue
        if not (a["effective_from"] <= on and (a.get("effective_to") is None or on < a["effective_to"])):
            continue
        if best is None or len(a["hs_prefix"]) > len(best["hs_prefix"]):
            best = a
    if best is None:
        return None
    return {
        "prohibited": True,
        "hs_code": hs,
        "origin_country": origin,
        "jurisdiction": jurisdiction,
        "list_id": best["list_id"],
        "authority": best.get("authority"),
        "effective_from": best["effective_from"],
        "effective_to": best.get("effective_to"),
        "source_url": best.get("source_url"),
        "message": PROHIBITED_MESSAGE,
    }
