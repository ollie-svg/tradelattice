"""Cascading fee and tax rules for /landed-cost.

Money and rates are decimal strings, computed with Decimal and rounded once at the end
(half-up to 2 dp). Rules evaluate in list order; a rule's base may be a context value or
the sum of fee amounts evaluated before it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

Base = Literal["value", "duty", "surtax", "duty_paid_value", "fees_so_far"]

BASE_LABELS = {
    "value": "value",
    "duty": "duty",
    "surtax": "surtax",
    "duty_paid_value": "duty-paid value",
    "fees_so_far": "fees so far",
}

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class FeeRule:
    name: str
    authority: str
    kind: Literal["pct", "flat"]
    rate_pct: str | None
    amount: str | None
    base: Base
    min: str | None
    max: str | None
    applies_when: dict | None
    effective_from: str
    effective_to: str | None
    category: Literal["fee", "tax"]
    source_url: str | None


@dataclass(frozen=True)
class Line:
    rule: FeeRule
    base_amount: Decimal
    amount: Decimal  # unrounded, after clamping
    clamp: Literal["min", "max"] | None


def _q(d: Decimal) -> float:
    return float(d.quantize(_CENT, rounding=ROUND_HALF_UP))


def _applies(rule: FeeRule, on: str, mode: str | None) -> bool:
    if on < rule.effective_from:
        return False
    if rule.effective_to is not None and on >= rule.effective_to:
        return False
    if rule.applies_when:
        for key, want in rule.applies_when.items():
            if key == "mode":
                if mode != want:
                    return False
            else:
                return False  # unknown condition: do not apply
    return True


def run(
    rules: list[FeeRule],
    ctx: dict[str, Decimal],
    on: str,
    mode: str | None,
    include_taxes: bool,
) -> tuple[list[Line], list[Line]]:
    """Evaluate rules in order; return unrounded (fee lines, tax lines)."""
    # Accept floats/ints/strings as well as Decimals; go through str() so
    # float noise (0.1 + 0.2) does not leak into money arithmetic.
    value, duty, surtax = (
        v if isinstance(v, Decimal) else Decimal(str(round(float(v), 6)))
        for v in (ctx["value"], ctx["duty"], ctx["surtax"])
    )
    bases = {
        "value": value,
        "duty": duty,
        "surtax": surtax,
        "duty_paid_value": value + duty + surtax,
    }
    fees: list[Line] = []
    taxes: list[Line] = []
    fees_so_far = Decimal(0)
    for rule in rules:
        if rule.category == "tax" and not include_taxes:
            continue
        if not _applies(rule, on, mode):
            continue
        base_amount = fees_so_far if rule.base == "fees_so_far" else bases[rule.base]
        if rule.kind == "pct":
            amount = base_amount * Decimal(rule.rate_pct or "0") / 100
        else:
            amount = Decimal(rule.amount or "0")
        clamp = None
        if rule.min is not None and amount < Decimal(rule.min):
            amount, clamp = Decimal(rule.min), "min"
        elif rule.max is not None and amount > Decimal(rule.max):
            amount, clamp = Decimal(rule.max), "max"
        line = Line(rule, base_amount, amount, clamp)
        if rule.category == "tax":
            taxes.append(line)
        else:
            fees.append(line)
            fees_so_far += amount
    return fees, taxes


def to_dict(line: Line) -> dict[str, Any]:
    return {
        "name": line.rule.name,
        "authority": line.rule.authority,
        "base": line.rule.base,
        "base_amount": _q(line.base_amount),
        "amount": _q(line.amount),
    }


def evaluate(
    rules: list[FeeRule],
    ctx: dict[str, Decimal],
    on: str,
    mode: str | None,
    include_taxes: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fees, taxes = run(rules, ctx, on, mode, include_taxes)
    return [to_dict(x) for x in fees], [to_dict(x) for x in taxes]


def describe(line: Line) -> str:
    r = line.rule
    base = f"{line.base_amount.quantize(_CENT, rounding=ROUND_HALF_UP):,.2f}"
    amt = f"{line.amount.quantize(_CENT, rounding=ROUND_HALF_UP):,.2f}"
    if r.kind == "pct":
        text = f"{r.name} {r.rate_pct}% of {BASE_LABELS[r.base]} {base} = {amt}"
    else:
        text = f"{r.name} flat {amt}"
    if line.clamp == "max":
        text += f" (clamped to max {r.max})"
    elif line.clamp == "min":
        text += f" (clamped to min {r.min})"
    elif r.min is not None or r.max is not None:
        parts = [f"min {r.min}" if r.min is not None else None,
                 f"max {r.max}" if r.max is not None else None]
        text += f" ({', '.join(p for p in parts if p)})"
    return text
