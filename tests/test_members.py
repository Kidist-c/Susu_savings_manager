import pytest

from app import services
from app.errors import DuplicateMember, GroupAlreadyStarted, GroupNotFound, InvalidName
from helpers import count


@pytest.fixture
def group(conn):
    services.create_group(conn, "50.00")
    return conn


def test_members_listed_in_join_order(group):
    for name in ("Ama", "Kofi", "Esi"):
        services.add_member(group, name)
    members = services.list_members(group)
    assert [m.name for m in members] == ["Ama", "Kofi", "Esi"]
    assert [m.join_order for m in members] == [1, 2, 3]


def test_duplicate_member_rejected(group):
    services.add_member(group, "Ama")
    with pytest.raises(DuplicateMember):
        services.add_member(group, "Ama")
    assert count(group, "members") == 1


@pytest.mark.parametrize("variant", ["ama", "AMA", "  Ama  ", " aMa"])
def test_duplicate_ignores_case_and_surrounding_space(group, variant):
    services.add_member(group, "Ama")
    with pytest.raises(DuplicateMember):
        services.add_member(group, variant)
    assert count(group, "members") == 1


def test_display_name_is_trimmed_original(group):
    member = services.add_member(group, "  Kofi Mensah ")
    assert member.name == "Kofi Mensah"


@pytest.mark.parametrize("bad", ["", "   ", "x" * 101])
def test_invalid_name_rejected(group, bad):
    with pytest.raises(InvalidName):
        services.add_member(group, bad)
    assert count(group, "members") == 0


def test_adding_member_without_group_fails(conn):
    with pytest.raises(GroupNotFound):
        services.add_member(conn, "Ama")


def test_join_order_continues_after_rejected_duplicate(group):
    services.add_member(group, "Ama")
    with pytest.raises(DuplicateMember):
        services.add_member(group, "ama")
    assert services.add_member(group, "Kofi").join_order == 2


def test_add_member_after_first_contribution_rejected(group):
    services.add_member(group, "Ama")
    services.record_contribution(group, "Ama", 1, "10.00")
    with pytest.raises(GroupAlreadyStarted):
        services.add_member(group, "Yaw")
    assert count(group, "members") == 1
