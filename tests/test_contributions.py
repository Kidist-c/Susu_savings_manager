import pytest

from app import services
from app.errors import (InvalidMoney, NonPositiveAmount, Overpayment, UnknownMember, WeekAlreadyClosed,
                        WeekNotOpen)
from helpers import count, pay, setup_group


@pytest.fixture
def db(conn):
    setup_group(conn)  # Ama, Kofi, Esi at GHS 50.00
    return conn


def test_unknown_member_rejected_and_nothing_recorded(db):
    with pytest.raises(UnknownMember):
        pay(db, "Kwame", 1, "10.00")
    assert count(db, "contributions") == 0


@pytest.mark.parametrize("amount,error", [
    ("0", NonPositiveAmount), ("0.00", NonPositiveAmount), ("-10.00", NonPositiveAmount),
    ("10.123", InvalidMoney), ("ten", InvalidMoney),
])
def test_bad_amounts_rejected_and_nothing_recorded(db, amount, error):
    with pytest.raises(error):
        pay(db, "Ama", 1, amount)
    assert count(db, "contributions") == 0


def test_overpayment_rejected(db):
    with pytest.raises(Overpayment):
        pay(db, "Ama", 1, "50.01")
    assert count(db, "contributions") == 0


def test_overpayment_after_partial_uses_remaining_amount(db):
    pay(db, "Esi", 1, "30.00")
    with pytest.raises(Overpayment) as info:
        pay(db, "Esi", 1, "25.00")
    assert info.value.details["remaining"] == "20.00"
    assert pay(db, "Esi", 1, "20.00").owed_pesewas == 0
    assert count(db, "contributions") == 2


def test_partial_payment_accepted(db):
    result = pay(db, "Esi", 1, "30.00")
    assert (result.paid_pesewas, result.owed_pesewas, result.status) == (3000, 2000, "partial")


def test_full_payment_marks_paid(db):
    assert pay(db, "Ama", 1, "50.00").status == "paid"


def test_multiple_partials_complete_exactly(db):
    pay(db, "Kofi", 1, "10.00")
    pay(db, "Kofi", 1, "20.00")
    last = pay(db, "Kofi", 1, "20.00")
    assert (last.paid_pesewas, last.owed_pesewas, last.status) == (5000, 0, "paid")


def test_ten_payments_of_ten_pesewas_with_small_group(conn):
    setup_group(conn, "1.00", ("Ama",))
    for _ in range(10):
        last = pay(conn, "Ama", 1, "0.10")
    assert last.owed_pesewas == 0 and last.status == "paid"


def test_paying_when_fully_paid_is_rejected(db):
    pay(db, "Ama", 1, "50.00")
    with pytest.raises(Overpayment):
        pay(db, "Ama", 1, "50.00")
    assert count(db, "contributions") == 1


def test_member_lookup_ignores_case_and_spaces(db):
    assert pay(db, "  ama ", 1, "10.00").member == "Ama"


def test_future_week_rejected(db):
    with pytest.raises(WeekNotOpen):
        pay(db, "Ama", 2, "10.00")
    assert count(db, "contributions") == 0


def test_past_week_rejected_after_week_advances(db):
    # Advance the week directly (closing weeks is tested in test_week_closure).
    db.execute("UPDATE groups SET current_week = 2")
    with pytest.raises(WeekAlreadyClosed):
        pay(db, "Ama", 1, "10.00")
    assert count(db, "contributions") == 0


def test_contribution_without_group_fails(conn):
    from app.errors import GroupNotFound
    with pytest.raises((GroupNotFound, UnknownMember)):
        pay(conn, "Ama", 1, "10.00")
