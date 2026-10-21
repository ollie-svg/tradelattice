import pytest

from api.duty import (
    AdValorem,
    Clamp,
    DutyInputError,
    NotApplicable,
    NotLessThan,
    Plus,
    Specific,
    compute,
    parse_duty,
)


def c(text, value=1000, qty=None, unit=None):
    return compute(parse_duty(text), value, qty, unit)


def test_free():
    assert parse_duty("Free") == AdValorem(0)
    assert c("Free") == 0


def test_ad_valorem():
    assert c("6.5%") == pytest.approx(65.0)  # 1000 * 6.5%


def test_typo_percent_per_kg():
    assert parse_duty("6%/kg") == AdValorem(6.0)


@pytest.mark.parametrize(
    "text,qty,unit,expected",
    [
        ("12¢/kg", 100, "kg", 12.0),  # 0.12 * 100
        ("$1.20/kg", 10, "kilogram", 12.0),  # 1.20 * 10
        ("$5/tonne", 3, "t", 15.0),  # 5 * 3
        ("25¢/litre", 40, "L", 10.0),  # 0.25 * 40
        ("30¢/dozen", 10, "dz", 3.0),  # 0.30 * 10
        ("8¢each", 50, "ea", 4.0),  # 0.08 * 50
        ("$2/dozen", 5, "dozen", 10.0),  # 2 * 5
        ("$34.50/hl", 2, "hectolitre", 69.0),  # 34.50 * 2
        ("$2/litre of absolute ethyl alcohol", 3, "litre of absolute ethyl alcohol", 6.0),  # 2 * 3
    ],
)
def test_specific_forms(text, qty, unit, expected):
    assert c(text, qty=qty, unit=unit) == pytest.approx(expected)


def test_cents_converted_and_ast():
    assert parse_duty("4.74¢/kg") == Specific(0.0474, "kg")


def test_tonne_with_kg_quantity():
    # $50/tonne, 2500 kg = 2.5 tonne -> 125
    assert c("$50/tonne", qty=2500, unit="kg") == pytest.approx(125.0)


def test_hl_with_litres():
    # $34.50/hl, 50 l = 0.5 hl -> 17.25
    assert c("$34.50/hl", qty=50, unit="litre") == pytest.approx(17.25)


def test_plus():
    assert isinstance(parse_duty("12¢/kg plus 5%"), Plus)
    # 0.12*100 = 12; 5% of 1000 = 50 -> 62
    assert c("12¢/kg plus 5%", qty=100, unit="kg") == pytest.approx(62.0)
    # $10/tonne with 500 kg = 5; 2% = 20 -> 25
    assert c("$10/tonne plus 2%", qty=500, unit="kg") == pytest.approx(25.0)


def test_not_less_than_ad_valorem_wins():
    assert isinstance(parse_duty("241% but not less than $34.50/hl"), NotLessThan)
    # 241% of 1000 = 2410; 0.5 hl * 34.50 = 17.25 -> 2410
    assert c("241% but not less than $34.50/hl", qty=50, unit="litre") == pytest.approx(2410.0)


def test_not_less_than_floor_wins():
    # 1% of 1000 = 10; floor 0.10*200 = 20 -> 20
    assert c("1% but not less than 10¢/kg", qty=200, unit="kg") == pytest.approx(20.0)


def test_specific_not_less_than_percent():
    # 1¢/kg * 100 = 1; 5% of 1000 = 50 -> 50
    assert c("1¢/kg but not less than 5%", qty=100, unit="kg") == pytest.approx(50.0)


def test_clamp():
    text = "5% but not less than 4.74¢/kg or more than 9.48¢/kg"
    assert isinstance(parse_duty(text), Clamp)
    # 5% = 50; floor 0.0474*2000 = 94.80; cap 0.0948*2000 = 189.60 -> 94.80
    assert c(text, qty=2000, unit="kg") == pytest.approx(94.80)
    # value 5000: 5% = 250 > cap 189.60 -> 189.60
    assert c(text, value=5000, qty=2000, unit="kg") == pytest.approx(189.60)
    # value 3000: 5% = 150, within [94.80, 189.60] -> 150
    assert c(text, value=3000, qty=2000, unit="kg") == pytest.approx(150.0)


def test_not_less_than_plus_binds_right_to_left():
    text = "3¢/kg but not less than 2% plus 4%"
    node = parse_duty(text)
    assert isinstance(node, Plus) and isinstance(node.a, NotLessThan)
    # 0.03*100 = 3; 2% of 1000 = 20 -> max 20; plus 4% = 40 -> 60
    assert c(text, qty=100, unit="kg") == pytest.approx(60.0)


def test_missing_quantity():
    with pytest.raises(DutyInputError, match="kg"):
        c("12¢/kg")
    with pytest.raises(DutyInputError, match="litre"):
        c("5% but not less than 10¢/litre")


def test_unit_mismatch():
    with pytest.raises(DutyInputError, match="kg"):
        c("12¢/kg", qty=5, unit="litre")


def test_ad_valorem_needs_no_quantity():
    assert c("5%") == pytest.approx(50.0)


@pytest.mark.parametrize("text", ["N/A", "Free, CPUKT N/A"])
def test_not_applicable(text):
    node = parse_duty(text)
    assert node == NotApplicable()
    with pytest.raises(DutyInputError, match="not applicable"):
        compute(node, 1000, None, None)


def test_garbage():
    with pytest.raises(DutyInputError):
        parse_duty("lots of money")
