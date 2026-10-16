from app import services
from app.database import connect
from helpers import pay, pay_full, setup_group


def test_state_survives_restart(tmp_path):
    path = str(tmp_path / "susu.db")
    first = connect(path)
    setup_group(first)
    pay(first, "Ama", 1, "50.00")
    pay(first, "Kofi", 1, "50.00")
    pay(first, "Esi", 1, "30.00")
    before = services.get_report(first)
    first.close()  # simulate the application stopping

    second = connect(path)  # simulate a restart: new connection, same file
    assert services.get_report(second) == before
    pay(second, "Esi", 1, "20.00")
    result = services.close_week(second, 1)
    assert (result.payout.member, result.payout.amount_pesewas, result.next_recipient) == ("Ama", 15000, "Kofi")
    second.close()

    third = connect(path)
    report = services.get_report(third)
    assert report.current_week == 2
    assert [(p.week, p.member) for p in report.payouts] == [(1, "Ama")]
    pay_full(third, 2)
    assert services.close_week(third, 2).payout.member == "Kofi"
    third.close()


def test_connect_is_idempotent_on_existing_database(tmp_path):
    path = str(tmp_path / "susu.db")
    connect(path).close()
    conn = connect(path)  # re-running schema creation must not fail or wipe data
    services.create_group(conn, "50.00")
    conn.close()
    assert services.get_group(connect(path)).weekly_contribution_pesewas == 5000
