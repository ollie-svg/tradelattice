"""CBSA duty-rate parser and calculator."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NA_MESSAGE = "rate not applicable for this treatment"
ALCOHOL = "litre of absolute ethyl alcohol"


class DutyInputError(ValueError):
    """The rate cannot be computed from the supplied inputs."""


class DutyNotApplicable(DutyInputError):
    def __init__(self) -> None:
        super().__init__(NA_MESSAGE)


@dataclass(frozen=True)
class AdValorem:
    pct: float


@dataclass(frozen=True)
class Specific:
    amount_cad: float  # dollars per unit (cents already converted)
    unit: str  # canonical: kg, tonne, litre, dozen, each, hl, or ALCOHOL
    label: str = field(default="", compare=False)  # original text, for display


@dataclass(frozen=True)
class Plus:
    a: Node
    b: Node


@dataclass(frozen=True)
class NotLessThan:
    a: Node
    floor: Node


@dataclass(frozen=True)
class Clamp:
    a: Node
    lo: Node
    hi: Node


@dataclass(frozen=True)
class NotApplicable:
    pass


Node = AdValorem | Specific | Plus | NotLessThan | Clamp | NotApplicable

_ALIASES = {
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "tonne": "tonne", "tonnes": "tonne", "t": "tonne", "mt": "tonne",
    "litre": "litre", "litres": "litre", "liter": "litre", "liters": "litre", "l": "litre",
    "dozen": "dozen", "dz": "dozen",
    "each": "each", "ea": "each", "unit": "each", "units": "each",
    "hl": "hl", "hectolitre": "hl", "hectolitres": "hl",
    ALCOHOL: ALCOHOL,
}
# canonical unit -> (family, factor to the family base unit)
_FAMILY = {
    "kg": ("mass", 1.0), "tonne": ("mass", 1000.0),
    "litre": ("volume", 1.0), "hl": ("volume", 100.0),
    "dozen": ("dozen", 1.0), "each": ("each", 1.0), ALCOHOL: (ALCOHOL, 1.0),
}
_NUM = r"\d+(?:\.\d+)?"


def normalize_unit(unit: str) -> str | None:
    return _ALIASES.get(re.sub(r"\s+", " ", unit.strip().lower()))


def _parse_term(text: str) -> Node:
    s = text.strip()
    if s.lower() == "free":
        return AdValorem(0.0)
    m = re.fullmatch(rf"({_NUM})\s*%(?:\s*/\s*kg)?", s, re.IGNORECASE)  # "6%/kg" is a CBSA typo
    if m:
        return AdValorem(float(m.group(1)))
    m = re.fullmatch(rf"(?:\$\s*(?P<d>{_NUM})|(?P<c>{_NUM})\s*¢)\s*/?\s*(?P<u>.+)", s)
    if m:
        unit = normalize_unit(m.group("u"))
        if unit is None:
            raise DutyInputError(f"unrecognised duty rate: {text.strip()!r}")
        amount = float(m.group("d")) if m.group("d") else round(float(m.group("c")) / 100, 10)
        return Specific(amount, unit, s)
    raise DutyInputError(f"unrecognised duty rate: {text.strip()!r}")


def _parse_nlt(text: str) -> Node:
    parts = re.split(r"\s+but\s+not\s+less\s+than\s+", text.strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 1:
        return _parse_term(parts[0])
    a = _parse_term(parts[0])
    bounds = re.split(r"\s+or\s+more\s+than\s+", parts[1], maxsplit=1, flags=re.IGNORECASE)
    if len(bounds) == 2:
        return Clamp(a, _parse_term(bounds[0]), _parse_term(bounds[1]))
    return NotLessThan(a, _parse_term(bounds[0]))


def parse_duty(text: str) -> Node:
    s = text.strip()
    if "n/a" in s.lower():
        return NotApplicable()
    # "plus C" binds last, so split on the final "plus".
    parts = re.split(r"\s+plus\s+", s, flags=re.IGNORECASE)
    if len(parts) == 1:
        return _parse_nlt(s)
    left = " plus ".join(parts[:-1])
    return Plus(parse_duty(left), _parse_term(parts[-1]))


def _fmt_rate(n: Specific) -> str:
    if n.label:
        return n.label
    if n.amount_cad < 1:
        return f"{n.amount_cad * 100:g}¢/{n.unit}"
    return f"${n.amount_cad:g}/{n.unit}"


def _quantity_in(node: Specific, quantity: float | None, unit: str | None) -> float:
    need = node.unit
    hint = f"{need} (or kg)" if need == "tonne" else f"{need} (or litre)" if need == "hl" else need
    if quantity is None or unit is None or not str(unit).strip():
        raise DutyInputError(f"this rate needs a quantity and unit in {hint}")
    have = normalize_unit(unit)
    if have is None or _FAMILY[have][0] != _FAMILY[need][0]:
        raise DutyInputError(f"this rate needs a quantity in {hint}, got unit {unit!r}")
    return quantity * _FAMILY[have][1] / _FAMILY[need][1]


def _eval(node: Node, value: float, qty: float | None, unit: str | None,
          comps: list[str], prefix: str = "") -> float:
    if isinstance(node, NotApplicable):
        raise DutyNotApplicable()
    if isinstance(node, AdValorem):
        d = value * node.pct / 100
        comps.append(f"{prefix}{node.pct:g}% ad valorem = {d:.2f}")
        return d
    if isinstance(node, Specific):
        q = _quantity_in(node, qty, unit)
        d = node.amount_cad * q
        shown = f"{qty:g} {unit.strip()}"
        comps.append(f"{prefix}{_fmt_rate(node)} × {shown} = {d:.2f}")
        return d
    if isinstance(node, Plus):
        return _eval(node.a, value, qty, unit, comps, prefix) + _eval(
            node.b, value, qty, unit, comps, prefix)
    if isinstance(node, NotLessThan):
        a = _eval(node.a, value, qty, unit, comps, prefix)
        return max(a, _eval(node.floor, value, qty, unit, comps, "floor "))
    if isinstance(node, Clamp):
        a = _eval(node.a, value, qty, unit, comps, prefix)
        lo = _eval(node.lo, value, qty, unit, comps, "floor ")
        hi = _eval(node.hi, value, qty, unit, comps, "cap ")
        return min(max(a, lo), hi)
    raise TypeError(node)


def evaluate(node: Node, value_cad: float, quantity: float | None = None,
             unit: str | None = None) -> tuple[float, list[str]]:
    comps: list[str] = []
    return _eval(node, value_cad, quantity, unit, comps), comps


def compute(node: Node, value_cad: float, quantity: float | None = None,
            unit: str | None = None) -> float:
    return evaluate(node, value_cad, quantity, unit)[0]


def basis(node: Node) -> str:
    if isinstance(node, AdValorem):
        return "ad_valorem"
    if isinstance(node, Specific):
        return "specific"
    return "compound"
