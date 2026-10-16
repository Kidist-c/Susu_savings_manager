"""All business rules. No FastAPI/Pydantic imports: every function takes a sqlite3 connection."""
import sqlite3
from datetime import datetime, timezone

from app.database import read_transaction, transaction
from app.errors import (ConcurrentModification, DuplicateMember, GroupAlreadyExists, GroupAlreadyStarted,
                        GroupNotFound, InvalidName, NoMembers, NonPositiveAmount, Overpayment, UnknownMember,
                        WeekAlreadyClosed, WeekIncomplete, WeekNotOpen)
from app.models import (CloseResult, ContributionResult, Group, Member, MemberStatus, Payout,
                        WeekReport)
from app.money import format_ghs, parse_ghs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_positive(text: str) -> int:
    amount = parse_ghs(text)
    if amount <= 0:
        raise NonPositiveAmount("Amount must be greater than zero.", {"value": text})
    return amount


def _require_group(conn: sqlite3.Connection) -> Group:
    row = conn.execute("SELECT weekly_contribution_pesewas, current_week FROM groups WHERE id = 1").fetchone()
    if row is None:
        raise GroupNotFound()
    return Group(row["weekly_contribution_pesewas"], row["current_week"])


def create_group(conn: sqlite3.Connection, weekly_text: str) -> Group:
    """Create the single group with its fixed weekly contribution; it starts at week 1."""
    amount = _parse_positive(weekly_text)
    with transaction(conn):
        if conn.execute("SELECT 1 FROM groups").fetchone():
            raise GroupAlreadyExists()
        conn.execute(
            "INSERT INTO groups (id, weekly_contribution_pesewas, current_week) VALUES (1, ?, 1)", (amount,)
        )
    return Group(amount, 1)


def get_group(conn: sqlite3.Connection) -> Group:
    return _require_group(conn)


MAX_NAME_LENGTH = 100


def _name_key(name: str) -> str:
    return name.strip().casefold()


def add_member(conn: sqlite3.Connection, raw_name: str) -> Member:
    """Add a member at the end of the joining order. Only allowed before the group starts."""
    if not isinstance(raw_name, str):
        raise InvalidName("Name must be text.")
    name = raw_name.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise InvalidName(f"Name must be 1 to {MAX_NAME_LENGTH} characters after trimming.")
    key = _name_key(name)
    with transaction(conn):
        group = _require_group(conn)
        started = group.current_week > 1 or conn.execute("SELECT 1 FROM contributions LIMIT 1").fetchone()
        if started:
            raise GroupAlreadyStarted()
        if conn.execute("SELECT 1 FROM members WHERE name_key = ?", (key,)).fetchone():
            raise DuplicateMember(name)
        order = conn.execute("SELECT COALESCE(MAX(join_order), 0) + 1 FROM members").fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO members (name, name_key, join_order) VALUES (?, ?, ?)", (name, key, order)
        )
    return Member(cursor.lastrowid, name, order)


def list_members(conn: sqlite3.Connection) -> list[Member]:
    rows = conn.execute("SELECT id, name, join_order FROM members ORDER BY join_order").fetchall()
    return [Member(r["id"], r["name"], r["join_order"]) for r in rows]


def _status(fixed: int, owed: int) -> str:
    if owed == 0:
        return "paid"
    return "unpaid" if owed == fixed else "partial"


def _paid_this_week(conn: sqlite3.Connection, member_id: int, week: int) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(amount_pesewas), 0) FROM contributions WHERE member_id = ? AND week = ?",
        (member_id, week),
    ).fetchone()[0]


def record_contribution(conn: sqlite3.Connection, member_name: str, week: int, amount_text: str) -> ContributionResult:
    """Record a full or partial payment for the CURRENT week.

    Validation order (fixed, so the same bad request always gives the same error):
    money format, positive, group exists, member exists, week is current, not more than remaining.
    """
    amount = _parse_positive(amount_text)
    with transaction(conn):
        group = _require_group(conn)
        key = _name_key(member_name) if isinstance(member_name, str) else ""
        row = conn.execute("SELECT id, name FROM members WHERE name_key = ?", (key,)).fetchone()
        if row is None:
            raise UnknownMember(str(member_name))
        if week < group.current_week:
            raise WeekAlreadyClosed(week, group.current_week)
        if week > group.current_week:
            raise WeekNotOpen(week, group.current_week)
        paid = _paid_this_week(conn, row["id"], week)
        owed = group.weekly_contribution_pesewas - paid
        if amount > owed:
            raise Overpayment(row["name"], format_ghs(owed), format_ghs(amount))
        conn.execute(
            "INSERT INTO contributions (member_id, week, amount_pesewas, created_at) VALUES (?, ?, ?, ?)",
            (row["id"], week, amount, _now()),
        )
    paid += amount
    owed -= amount
    return ContributionResult(row["name"], week, paid, owed, _status(group.weekly_contribution_pesewas, owed))


def _member_statuses(conn: sqlite3.Connection, group: Group, week: int) -> list[MemberStatus]:
    """Every member in joining order with what they paid for `week` and what they still owe."""
    rows = conn.execute(
        """
        SELECT m.id, m.name, m.join_order, COALESCE(SUM(c.amount_pesewas), 0) AS paid
        FROM members m
        LEFT JOIN contributions c ON c.member_id = m.id AND c.week = ?
        GROUP BY m.id
        ORDER BY m.join_order
        """,
        (week,),
    ).fetchall()
    fixed = group.weekly_contribution_pesewas
    return [
        MemberStatus(r["id"], r["name"], r["join_order"], r["paid"], fixed - r["paid"], _status(fixed, fixed - r["paid"]))
        for r in rows
    ]


def recipient_index(week: int, member_count: int) -> int:
    """Zero-based position in joining order of the member paid in `week` (wraps after the last member)."""
    return (week - 1) % member_count


def close_week(conn: sqlite3.Connection, week_number: int) -> CloseResult:
    """Try to close `week_number`, which must be the current week.

    If anyone still owes money nothing is written and WeekIncomplete lists who and how much.
    Otherwise the payout is recorded and the week advances in ONE transaction: both or neither.
    """
    with transaction(conn):
        group = _require_group(conn)
        if week_number < group.current_week:
            raise WeekAlreadyClosed(week_number, group.current_week)
        if week_number > group.current_week:
            raise WeekNotOpen(week_number, group.current_week)
        statuses = _member_statuses(conn, group, week_number)
        if not statuses:
            raise NoMembers()
        outstanding = [{"member": s.name, "owed": format_ghs(s.owed_pesewas)} for s in statuses if s.owed_pesewas > 0]
        if outstanding:
            raise WeekIncomplete(week_number, outstanding)  # nothing has been written

        count = len(statuses)
        recipient = statuses[recipient_index(week_number, count)]
        pot = group.weekly_contribution_pesewas * count
        conn.execute(
            "INSERT INTO payouts (week, member_id, amount_pesewas, paid_at) VALUES (?, ?, ?, ?)",
            (week_number, recipient.member_id, pot, _now()),
        )
        advanced = conn.execute(
            "UPDATE groups SET current_week = ? WHERE id = 1 AND current_week = ?", (week_number + 1, week_number)
        )
        if advanced.rowcount != 1:
            raise ConcurrentModification()
        next_recipient = statuses[recipient_index(week_number + 1, count)].name
    return CloseResult(Payout(week_number, recipient.name, pot), week_number + 1, next_recipient)


def get_report(conn: sqlite3.Connection) -> WeekReport:
    """Read-only snapshot: current week, each member's status, outstanding total and payout history."""
    with read_transaction(conn):
        group = _require_group(conn)
        statuses = _member_statuses(conn, group, group.current_week)
        payout_rows = conn.execute(
            """
            SELECT p.week, m.name, p.amount_pesewas
            FROM payouts p JOIN members m ON m.id = p.member_id
            ORDER BY p.week
            """
        ).fetchall()
    count = len(statuses)
    return WeekReport(
        current_week=group.current_week,
        weekly_contribution_pesewas=group.weekly_contribution_pesewas,
        pot_pesewas=group.weekly_contribution_pesewas * count,
        next_recipient=statuses[recipient_index(group.current_week, count)].name if count else None,
        members=tuple(statuses),
        total_outstanding_pesewas=sum(s.owed_pesewas for s in statuses),
        payouts=tuple(Payout(r["week"], r["name"], r["amount_pesewas"]) for r in payout_rows),
    )
