import pytest

from app import services
from app.errors import GroupNotFound
from helpers import pay, pay_full, setup_group


def test_report_reflects_mid_week_state(conn):
    setup_group(conn)
    pay(conn, "Ama", 1, "50.00")
    pay(conn, "Kofi", 1, "12.50")
    report = services.get_report(conn)
    assert report.current_week == 1
    assert [(m.name, m.paid_pesewas, m.owed_pesewas, m.status) for m in report.members] == [
        ("Ama", 5000, 0, "paid"), ("Kofi", 1250, 3750, "partial"), ("Esi", 0, 5000, "unpaid"),
    ]
    assert report.total_outstanding_pesewas == 8750
    assert report.pot_pesewas == 15000
    assert report.next_recipient == "Ama"
    assert report.payouts == ()


def test_fresh_group_report_everyone_unpaid(conn):
    setup_group(conn)
    report = services.get_report(conn)
    assert {m.status for m in report.members} == {"unpaid"}
    assert report.total_outstanding_pesewas == 15000


def test_payout_history_ordered_with_amounts(conn):
    setup_group(conn)
    for week in (1, 2, 3):
        pay_full(conn, week)
        services.close_week(conn, week)
    report = services.get_report(conn)
    assert [(p.week, p.member, p.amount_pesewas) for p in report.payouts] == [
        (1, "Ama", 15000), (2, "Kofi", 15000), (3, "Esi", 15000),
    ]
    assert report.current_week == 4
    assert report.next_recipient == "Ama"


def test_report_shows_only_current_week_balances(conn):
    setup_group(conn)
    pay_full(conn, 1)
    services.close_week(conn, 1)
    report = services.get_report(conn)
    assert report.total_outstanding_pesewas == 15000  # week 1 payments do not count toward week 2
    assert {m.paid_pesewas for m in report.members} == {0}


def test_report_is_read_only(conn):
    setup_group(conn)
    pay(conn, "Ama", 1, "10.00")
    assert services.get_report(conn) == services.get_report(conn)


def test_failed_close_leaves_report_identical(conn):
    setup_group(conn)
    pay(conn, "Ama", 1, "50.00")
    pay(conn, "Esi", 1, "30.00")
    before = services.get_report(conn)
    with pytest.raises(Exception):
        services.close_week(conn, 1)
    assert services.get_report(conn) == before


def test_report_without_group_raises(conn):
    with pytest.raises(GroupNotFound):
        services.get_report(conn)


def test_report_with_group_but_no_members(conn):
    services.create_group(conn, "50.00")
    report = services.get_report(conn)
    assert report.members == () and report.next_recipient is None and report.pot_pesewas == 0
import pytest

from app import services
from app.errors import GroupNotFound
from helpers import pay, pay_full, setup_group


def test_report_reflects_mid_week_state(conn):
    setup_group(conn)
    pay(conn, "Ama", 1, "50.00")
    pay(conn, "Kofi", 1, "12.50")
    report = services.get_report(conn)
    assert report.current_week == 1
    assert [(m.name, m.paid_pesewas, m.owed_pesewas, m.status) for m in report.members] == [
        ("Ama", 5000, 0, "paid"), ("Kofi", 1250, 3750, "partial"), ("Esi", 0, 5000, "unpaid"),
    ]
    assert report.total_outstanding_pesewas == 8750
    assert report.pot_pesewas == 15000
    assert report.next_recipient == "Ama"
    assert report.payouts == ()


def test_fresh_group_report_everyone_unpaid(conn):
    setup_group(conn)
    report = services.get_report(conn)
    assert {m.status for m in report.members} == {"unpaid"}
    assert report.total_outstanding_pesewas == 15000


def test_payout_history_ordered_with_amounts(conn):
    setup_group(conn)
    for week in (1, 2, 3):
        pay_full(conn, week)
        services.close_week(conn, week)
    report = services.get_report(conn)
    assert [(p.week, p.member, p.amount_pesewas) for p in report.payouts] == [
        (1, "Ama", 15000), (2, "Kofi", 15000), (3, "Esi", 15000),
    ]
    assert report.current_week == 4
    assert report.next_recipient == "Ama"


def test_report_shows_only_current_week_balances(conn):
    setup_group(conn)
    pay_full(conn, 1)
    services.close_week(conn, 1)
    report = services.get_report(conn)
    assert report.total_outstanding_pesewas == 15000  # week 1 payments do not count toward week 2
    assert {m.paid_pesewas for m in report.members} == {0}


def test_report_is_read_only(conn):
    setup_group(conn)
    pay(conn, "Ama", 1, "10.00")
    assert services.get_report(conn) == services.get_report(conn)


def test_failed_close_leaves_report_identical(conn):
    setup_group(conn)
    pay(conn, "Ama", 1, "50.00")
    pay(conn, "Esi", 1, "30.00")
    before = services.get_report(conn)
    with pytest.raises(Exception):
        services.close_week(conn, 1)
    assert services.get_report(conn) == before


def test_report_without_group_raises(conn):
    with pytest.raises(GroupNotFound):
        services.get_report(conn)


def test_report_with_group_but_no_members(conn):
    services.create_group(conn, "50.00")
    report = services.get_report(conn)
    assert report.members == () and report.next_recipient is None and report.pot_pesewas == 0
