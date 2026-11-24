"""Golden landed-cost cases, shipped as package data (ADR 0005).

A consumer that runs its own implementation in parity reads the same file and applies the
same comparison rule, both from here:

    from tradelattice.golden import cases, check
    for case in cases():
        status, body = my_implementation(case)
        check(case["expect"]["body"], body)  # raises AssertionError on the first mismatch

Each case is self-contained: `records` is a RecordSet as four lists of envelope dicts,
`request` the landed-cost body, `jurisdiction` the registered code, `today` the date passed
as `today`, and `expect` the status plus a subset of the body. See README.md beside this file.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from importlib import resources

#: Fields compared within TOLERANCE; everything else is compared exactly.
MONEY_FIELDS = frozenset({
    "duty", "surtax", "surtax_if_fta_qualified", "total", "total_if_fta_qualified",
    "value_cad", "amount", "base_amount",
})
TOLERANCE = 0.01


def _lines() -> Iterator[str]:
    text = resources.files(__package__).joinpath("landed_cost.jsonl").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip():
            yield line


def cases() -> list[dict]:
    """Every golden case, in file order. Returns fresh dicts on each call."""
    return [json.loads(line) for line in _lines()]


def check(expected, actual, path: str = "") -> None:
    """Assert `actual` matches `expected`: money fields within TOLERANCE, the rest exactly.

    `expected` may be a subset: dict keys absent from `expected` are not checked; lists must
    match in length and element by element. Raises AssertionError naming the first mismatch.
    """
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path or '<root>'}: expected an object"
        for k, v in expected.items():
            assert k in actual, f"{path}.{k} missing"
            check(v, actual[k], f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), \
            f"{path}: expected {len(expected)} items"
        for i, (e, a) in enumerate(zip(expected, actual, strict=True)):
            check(e, a, f"{path}[{i}]")
    elif (path.rsplit(".", 1)[-1] in MONEY_FIELDS and expected is not None
          and isinstance(expected, int | float) and not isinstance(expected, bool)):
        assert actual is not None and abs(actual - expected) <= TOLERANCE, \
            f"{path}: {actual} != {expected} (tolerance {TOLERANCE})"
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"
