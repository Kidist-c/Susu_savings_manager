import sqlite3

import pytest

from app import services
from app.errors import NoMembers, WeekAlreadyClosed, WeekIncomplete, WeekNotOpen
from helpers import count, pay, pay_full, setup_group


def required_example(conn):
    """The challenge example: Ama 50.00, Kofi 50.00, Esi 30.00 in week 1."""
    setup_group(conn)
    pay(conn, "Ama", 1, "50.00")
    pay(conn, "Kofi", 1, "50.00")
    pay(conn, "Esi", 1, "30.00")


def test_blocked_close_reports_esi_owes_20(conn):
    required_example(conn)
    with pytest.raises(WeekIncomplete) as info:
        services.close_week(conn, 1)
    assert info.value.details["outstanding"] == [{"member": "Esi", "owed": "20.00"}]


def test_failed_close_changes_nothing(conn):
    required_example(conn)
    before = (services.get_group(conn), count(conn, "payouts"), count(conn, "contributions"))
    with pytest.raises(WeekIncomplete):
        services.close_week(conn, 1)
    after = (services.get_group(conn), count(conn, "payouts"), count(conn, "contributions"))
    assert after == before
    assert services.get_group(conn).current_week == 1
    assert count(conn, "payouts") == 0


def test_blocked_close_lists_every_member_who_owes(conn):
    setup_group(conn)
    pay(conn, "Ama", 1, "50.00")
    pay(conn, "Kofi", 1, "0.10")
    with pytest.raises(WeekIncomplete) as info:
        services.close_week(conn, 1)
    assert info.value.details["outstanding"] == [
        {"member": "Kofi", "owed": "49.90"}, {"member": "Esi", "owed": "50.00"},
    ]


def test_close_after_all_paid_pays_ama_150_and_advances(conn):
    required_example(conn)
    with pytest.raises(WeekIncomplete):
        services.close_week(conn, 1)
    pay(conn, "Esi", 1, "20.00")
    result = services.close_week(conn, 1)
    assert (result.payout.week, result.payout.member, result.payout.amount_pesewas) == (1, "Ama", 15000)
    assert result.current_week == 2
    assert result.next_recipient == "Kofi"
    assert services.get_group(conn).current_week == 2
    assert count(conn, "payouts") == 1


def test_pot_scales_with_member_count(conn):
    setup_group(conn, "25.50", ("A", "B", "C", "D"))
    pay_full(conn, 1, "25.50")
    assert services.close_week(conn, 1).payout.amount_pesewas == 10200


def test_recipient_must_also_pay(conn):
    setup_group(conn)
    pay_full(conn, 1, names=["Kofi", "Esi"])  # Ama, the week-1 recipient, has not paid
    with pytest.raises(WeekIncomplete) as info:
        services.close_week(conn, 1)
    assert info.value.details["outstanding"] == [{"member": "Ama", "owed": "50.00"}]


def test_rotation_follows_join_order_and_wraps(conn):
    setup_group(conn)
    recipients = []
    for week in range(1, 8):
        pay_full(conn, week)
        recipients.append(services.close_week(conn, week).payout.member)
    assert recipients == ["Ama", "Kofi", "Esi", "Ama", "Kofi", "Esi", "Ama"]
    assert services.get_group(conn).current_week == 8


def test_join_order_not_alphabetical(conn):
    setup_group(conn, names=("Zed", "Amy"))
    pay_full(conn, 1)
    assert services.close_week(conn, 1).payout.member == "Zed"


def test_double_close_creates_one_payout(conn):
    setup_group(conn)
    pay_full(conn, 1)
    services.close_week(conn, 1)
    with pytest.raises(WeekAlreadyClosed):
        services.close_week(conn, 1)
    assert count(conn, "payouts") == 1
    assert services.get_group(conn).current_week == 2


def test_close_future_week_rejected(conn):
    setup_group(conn)
    pay_full(conn, 1)
    with pytest.raises(WeekNotOpen):
        services.close_week(conn, 2)
    assert count(conn, "payouts") == 0
    assert services.get_group(conn).current_week == 1


def test_close_with_no_members_rejected(conn):
    services.create_group(conn, "50.00")
    with pytest.raises(NoMembers):
        services.close_week(conn, 1)
    assert count(conn, "payouts") == 0


def test_single_member_group_gets_own_contribution_back(conn):
    setup_group(conn, "10.00", ("Solo",))
    pay(conn, "Solo", 1, "10.00")
    result = services.close_week(conn, 1)
    assert (result.payout.member, result.payout.amount_pesewas, result.next_recipient) == ("Solo", 1000, "Solo")


def test_week_two_needs_fresh_payments(conn):
    setup_group(conn)
    pay_full(conn, 1)
    services.close_week(conn, 1)
    with pytest.raises(WeekIncomplete) as info:
        services.close_week(conn, 2)
    assert len(info.value.details["outstanding"]) == 3


def test_close_is_atomic_when_week_update_fails(conn):
    """If advancing the week fails after the payout INSERT, the payout must be rolled back too."""
    setup_group(conn)
    pay_full(conn, 1)
    conn.execute(
        "CREATE TRIGGER block_week_update BEFORE UPDATE ON groups BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
    )
    with pytest.raises(sqlite3.Error):
        services.close_week(conn, 1)
    assert count(conn, "payouts") == 0
    assert services.get_group(conn).current_week == 1
    conn.execute("DROP TRIGGER block_week_update")
    assert services.close_week(conn, 1).payout.member == "Ama"  # the group is still usable afterwards


def test_payout_week_is_unique_in_database(conn):
    setup_group(conn)
    pay_full(conn, 1)
    services.close_week(conn, 1)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO payouts (week, member_id, amount_pesewas, paid_at) VALUES (1, 1, 100, 'x')")
