"""Exact money handling.

All amounts are whole pesewas (GHS 1.00 == 100). Text is parsed with a strict pattern and
integer arithmetic; no binary floating point is involved anywhere.
"""
import re

from app.errors import InvalidMoney

MAX_PESEWAS = 100_000_000  # GHS 1,000,000.00 sanity limit
_MONEY = re.compile(r"[0-9]+(\.[0-9]{1,2})?", re.ASCII)


def parse_ghs(text: str) -> int:
    """Convert text such as '50.00', '50' or '-5.5' to integer pesewas.

    Rejects anything that is not digits with at most two decimal places (never rounds).
    Zero and negative values are parsed, so callers can give a clearer error for them.
    """
    if not isinstance(text, str):
        raise InvalidMoney("Amount must be text such as '50.00'.", {"value": repr(text)})
    s = text.strip()
    negative = s.startswith("-")
    if negative:
        s = s[1:]
    if not _MONEY.fullmatch(s):
        raise InvalidMoney(
            f"'{text}' is not a valid amount. Use digits with at most 2 decimal places, e.g. '50.00'.",
            {"value": text},
        )
    whole, _, frac = s.partition(".")
    pesewas = int(whole) * 100 + int(frac.ljust(2, "0") or "0")
    if pesewas > MAX_PESEWAS:
        raise InvalidMoney("Amount is too large.", {"value": text})
    return -pesewas if negative else pesewas


def format_ghs(pesewas: int) -> str:
    """Convert integer pesewas to a two-decimal string, e.g. 5000 -> '50.00'."""
    sign = "-" if pesewas < 0 else ""
    pesewas = abs(pesewas)
    return f"{sign}{pesewas // 100}.{pesewas % 100:02d}"
