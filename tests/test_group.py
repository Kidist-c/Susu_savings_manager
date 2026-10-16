import pytest

from app import services
from app.errors import GroupAlreadyExists, GroupNotFound, InvalidMoney, NonPositiveAmount
from helpers import count


def test_create_group_stores_amount_and_starts_at_week_one(conn):
    group = services.create_group(conn, "50.00")
    assert group.weekly_contribution_pesewas == 5000
    assert group.current_week == 1
    assert services.get_group(conn) == group


def test_second_group_rejected_and_first_unchanged(conn):
    services.create_group(conn, "50.00")
    with pytest.raises(GroupAlreadyExists):
        services.create_group(conn, "10.00")
    assert services.get_group(conn).weekly_contribution_pesewas == 5000
    assert count(conn, "groups") == 1


@pytest.mark.parametrize("bad,error", [
    ("0", NonPositiveAmount), ("0.00", NonPositiveAmount), ("-5.00", NonPositiveAmount),
    ("50.123", InvalidMoney), ("abc", InvalidMoney), ("", InvalidMoney),
])
def test_group_rejects_bad_amount_and_creates_nothing(conn, bad, error):
    with pytest.raises(error):
        services.create_group(conn, bad)
    assert count(conn, "groups") == 0


def test_get_group_before_creation_raises(conn):
    with pytest.raises(GroupNotFound):
        services.get_group(conn)
