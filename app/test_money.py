import io
import tokenize
from pathlib import Path

import pytest

from app.errors import InvalidMoney
from app.money import format_ghs, parse_ghs


@pytest.mark.parametrize(
    "text,expected",
    [
        ("50.00", 5000), ("50", 5000), ("50.5", 5050), ("0.10", 10), ("0.01", 1),
        ("0", 0), ("0.00", 0), ("  12.34  ", 1234), ("-5.00", -500), ("-0.50", -50),
        ("1000000.00", 100_000_000),
    ],
)
def test_parse_valid(text, expected):
    assert parse_ghs(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "   ", "abc", ".5", "5.", "1,000", "1e3", "GHS 50", "50.00.1", "50.123", "--5", "+5",
     "5 0", "٣٠", "1000000.01", "NaN", "inf"],
)
def test_parse_invalid_is_rejected(text):
    with pytest.raises(InvalidMoney):
        parse_ghs(text)


def test_parse_rejects_non_text():
    for bad in (50.1, 50, None):
        with pytest.raises(InvalidMoney):
            parse_ghs(bad)


@pytest.mark.parametrize(
    "pesewas,expected",
    [(5000, "50.00"), (10, "0.10"), (0, "0.00"), (5, "0.05"), (15000, "150.00"), (-500, "-5.00")],
)
def test_format(pesewas, expected):
    assert format_ghs(pesewas) == expected


def test_ten_cents_plus_twenty_cents_is_thirty():
    total = parse_ghs("0.10") + parse_ghs("0.20")
    assert total == parse_ghs("0.30") == 30
    assert format_ghs(total) == "0.30"


def test_ten_payments_of_ten_pesewas_make_exactly_one_cedi():
    assert sum(parse_ghs("0.10") for _ in range(10)) == parse_ghs("1.00")


def test_round_trip():
    for pesewas in (0, 1, 9, 10, 99, 100, 101, 12345, 100_000_000):
        assert parse_ghs(format_ghs(pesewas)) == pesewas


def test_no_float_in_money_code():
    """Guard: the money-handling modules must never use the float type."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    for name in ("money.py", "services.py"):
        path = app_dir / name
        if not path.exists():
            continue
        tokens = tokenize.generate_tokens(io.StringIO(path.read_text()).readline)
        used = [t.string for t in tokens if t.type == tokenize.NAME and t.string == "float"]
        assert not used, f"{name} uses float"
