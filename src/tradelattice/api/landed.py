"""Landed-cost reference computation: a pure function over records (ADR 0005).

`compute()` takes the request, a `RecordSet` of envelope dicts, the jurisdiction profile
and today's date, and returns a `LandedCostOut` or raises `Prohibited` / `NotComputable`.
It reads no database, makes no HTTP call and consults no clock, so a consumer such as
Mandible can call it directly, or run its own implementation in parity against it, on
identical inputs. The route in `main.py` is a thin wrapper that loads the records from the
session and maps the two exceptions to 409 and 4xx/5xx responses.

Arithmetic is unchanged from the v0.3 route handler: duty in float, then `round(.., 6)`
into Decimal for the fee cascade, half-up to the cent at the end.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from tradelattice.connectors.cbsa_surtax import applicable

from . import fees as feemod
from .duty import DutyInputError, NotApplicable, basis, evaluate, parse_duty
from .jurisdictions import Jurisdiction
from .overlays import prohibited
from .schemas import LandedCostIn, LandedCostOut

FX_PUBLISHER_LABELS = {"boc": "BoC", "treasury": "Treasury"}


@dataclass(frozen=True)
class RecordSet:
    """The records `compute()` reads, as envelope dicts (the shape `/records` returns)."""

    tariff_lines: list[dict] = field(default_factory=list)
    fx_rates: list[dict] = field(default_factory=list)
    surtax_orders: list[dict] = field(default_factory=list)
    prohibitions: list[dict] = field(default_factory=list)


class Prohibited(Exception):
    """The goods may not be entered; `payload` is the 409 body. A correct answer, not a fault."""

    def __init__(self, payload: dict) -> None:
        super().__init__(payload["message"])
        self.payload = payload


class NotComputable(Exception):
    """No landed cost can be computed from these inputs and records.

    `status` is the HTTP status the route returns; `reason` is a stable machine-readable
    code (see docs/api.md); `detail` is the human-readable message.
    """

    def __init__(self, status: int, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.reason = reason
        self.detail = detail


def normalize_hs(code: str) -> str:
    digits = code.replace(".", "").replace(" ", "")
    if not re.fullmatch(r"[0-9]{2,10}", digits):
        raise NotComputable(422, "invalid_request", "hs_code must be 2-10 digits")
    return digits


def best_tariff(tariff_lines: list[dict], hs: str) -> dict:
    """Longest-prefix tariff_line for `hs`; ties go to the latest observed_at."""
    best: dict | None = None
    for r in tariff_lines:
        if r.get("type") != "tariff_line":
            continue
        code = str(r["attributes"].get("hs_code", ""))
        if not code or not hs.startswith(code):
            continue
        if best is None:
            best = r
            continue
        bcode = str(best["attributes"]["hs_code"])
        if len(code) > len(bcode) or (
            len(code) == len(bcode) and str(r["observed_at"]) > str(best["observed_at"])
        ):
            best = r
    if best is None:
        raise NotComputable(404, "tariff_not_found", f"no tariff line matches {hs}")
    return best


def fx_for(fx_rates: list[dict], currency: str, to: str, on: str) -> tuple[str, str]:
    """(rate string, rate date) for the latest fx_rate from `currency` to `to` on or before `on`."""
    best: dict | None = None
    for r in fx_rates:
        if r.get("type") != "fx_rate":
            continue
        a = r["attributes"]
        if a.get("currency") != currency or a.get("to") != to or str(a.get("on", "9999")) > on:
            continue
        if best is None or a["on"] > best["on"]:
            best = a
    if best is None:
        raise NotComputable(
            422,
            "fx_missing",
            f"no {to} exchange rate on or before {on} for {currency}; load the boc_fx connector",
        )
    return str(best["rate"]), str(best["on"])


def _dec(x: float) -> Decimal:
    return Decimal(repr(round(x, 6)))  # strip float noise before Decimal arithmetic


def compute(
    request: LandedCostIn, records: RecordSet, jurisdiction: Jurisdiction, today: date
) -> LandedCostOut:
    """Compute a landed cost. Pure: same inputs, same output; raises Prohibited / NotComputable."""
    jcode = jurisdiction.code
    cur_out = jurisdiction.currency
    scoped_lines = [r for r in records.tariff_lines if r.get("jurisdiction") == jcode]
    if not scoped_lines:
        raise NotComputable(
            501, "jurisdiction_no_data", f"{jcode} profile has no data loaded yet; see the roadmap"
        )
    hs = normalize_hs(request.hs_code)
    origin = request.origin_country.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", origin):
        raise NotComputable(422, "invalid_request", "origin_country must be a 2-letter country code")
    if request.shipment_date is None:
        ship = today.isoformat()
    else:
        try:
            ship = date.fromisoformat(request.shipment_date).isoformat()
        except ValueError as e:
            raise NotComputable(
                422, "invalid_request", "shipment_date must be an ISO date (YYYY-MM-DD)"
            ) from e
    ban = prohibited(records.prohibitions, hs, origin, ship, jcode)
    if ban is not None:
        raise Prohibited(ban)
    line = best_tariff(scoped_lines, hs)
    treatment = request.treatment or "MFN"
    rate_str = next(
        (r["rate"] for r in line["attributes"].get("rates", []) if r.get("treatment") == treatment),
        None,
    )
    if rate_str is None:
        raise NotComputable(
            404, "rate_not_found",
            f"no rate for treatment {treatment!r} on {line['attributes']['hs_code']}",
        )
    amount = request.declared_value.amount
    cur = request.declared_value.currency.strip().upper()
    fx_rate: str | None = None
    fx_on: str | None = None
    fx_lines: list[str] = []
    if cur == cur_out:
        value = amount
    else:
        fx_rate, fx_on = fx_for(records.fx_rates, cur, cur_out, ship)
        value = amount * float(fx_rate)
        label = FX_PUBLISHER_LABELS.get(jurisdiction.fx_publisher, jurisdiction.fx_publisher)
        fx_lines.append(
            f"FX {cur}→{cur_out} at {fx_rate} ({label} {fx_on}): "
            f"{amount:,.2f} {cur} = {value:,.2f} {cur_out}"
        )
    try:
        node = parse_duty(rate_str)
        if isinstance(node, NotApplicable):
            raise DutyInputError("rate not applicable for this treatment")
        raw_duty, components = evaluate(node, value, request.quantity, request.unit)
    except DutyInputError as e:
        raise NotComputable(422, "rate_not_applicable", str(e)) from e
    surtax_pct: str | None = None
    surtax_list: str | None = None
    raw_surtax = 0.0
    sur_lines: list[str] = []
    orders = [r for r in records.surtax_orders if r.get("jurisdiction") == jcode]
    hits = applicable(orders, hs, origin, ship)
    fta = request.fta_qualified
    if fta is True:
        hits = [h for h in hits if h.get("exempt_if") != "fta_qualified"]
    if len(hits) > 1:
        # The record declares `stacking` but nothing computes it yet: refuse rather than pick
        # one (schema text; ADR 0005 corollary). Stacking arithmetic arrives with the US overlays.
        ids = ", ".join(h["list_id"] for h in hits)
        raise NotComputable(
            422, "surtax_ambiguous",
            f"{len(hits)} surtax orders apply to {hs} from {origin} on {ship} ({ids}); "
            "stacking is declared but not computed, so no single surtax can be chosen",
        )
    hit = hits[0] if hits else None
    if hit is not None and hit.get("basis", "value") != "value":
        raise NotComputable(
            422, "surtax_content_basis",
            f"surtax basis {hit['basis']!r} needs a content value; not supported yet",
        )
    raw_alt: float | None = None
    if hit:
        surtax_pct = str(hit["pct"])
        surtax_list = hit["list_id"]
        raw_surtax = value * float(surtax_pct) / 100
        sur_lines.append(
            f"surtax {float(surtax_pct):g}% of {value:,.2f} ({surtax_list}, origin {origin}) "
            f"= {raw_surtax:,.2f}"
        )
    if fta is None and hit is not None and hit.get("exempt_if") == "fta_qualified":
        # One conditional order and qualification unknown: report both outcomes, never choose.
        raw_alt = 0.0
        sur_lines.append(
            f"FTA qualification unknown: surtax {round(raw_surtax, 2):.2f} if not qualified, "
            f"{round(raw_alt, 2):.2f} if qualified"
        )
    duty = round(raw_duty, 2)
    surtax = round(raw_surtax, 2)
    value_rounded = round(value, 2)
    pct = round(duty / value * 100, 2) if value else 0.0

    def cascade(sur: float) -> tuple[list[feemod.Line], list[feemod.Line], float]:
        ctx = {"value": _dec(value), "duty": _dec(raw_duty), "surtax": _dec(sur)}
        fl, tl = feemod.run(jurisdiction.fee_schedule, ctx, ship, request.mode, request.include_taxes)
        grand = _dec(value + raw_duty + sur) + sum((x.amount for x in fl + tl), Decimal(0))
        return fl, tl, grand

    fee_lines, tax_lines, grand = cascade(raw_surtax)
    if fee_lines or tax_lines:
        total = float(grand.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    else:
        total = round(value + raw_duty + raw_surtax, 2)
    total_alt: float | None = None
    if raw_alt is not None:
        fa, ta, grand_alt = cascade(raw_alt)
        if fa or ta:
            total_alt = float(grand_alt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        else:
            total_alt = round(value + raw_duty + raw_alt, 2)
    fee_components = [feemod.describe(x) for x in fee_lines + tax_lines]
    return LandedCostOut(
        hs_code=hs,
        matched_hs_code=str(line["attributes"]["hs_code"]),
        treatment=treatment,
        duty_rate=pct,
        duty=duty,
        total=total,
        currency=cur_out,
        declared_currency=cur,
        value_cad=value_rounded,
        fx_rate=fx_rate,
        fx_on=fx_on,
        surtax_pct=surtax_pct,
        surtax=surtax,
        surtax_list_id=surtax_list,
        shipment_date=ship,
        rate=rate_str,
        components=fx_lines + components + sur_lines + fee_components,
        basis=basis(node),
        jurisdiction=jcode,
        fta_qualified=fta,
        surtax_if_fta_qualified=None if raw_alt is None else round(raw_alt, 2),
        total_if_fta_qualified=total_alt,
        fees=[feemod.to_dict(x) for x in fee_lines],
        taxes=[feemod.to_dict(x) for x in tax_lines],
        include_taxes=request.include_taxes,
    )
