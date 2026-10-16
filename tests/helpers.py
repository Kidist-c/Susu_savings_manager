"""Small helpers that keep tests short and readable."""
from app import services

NAMES = ("Ama", "Kofi", "Esi")


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

def setup_group(conn, amount="50.00", names=NAMES):
    """Create a group and add members in the given joining order."""
    services.create_group(conn, amount)
    for name in names:
        services.add_member(conn, name)


def pay(conn, name, week, amount):
    return services.record_contribution(conn, name, week, amount)


def pay_full(conn, week, amount="50.00", names=None):
    """Everyone pays the full amount for the given week."""
    for name in names or [m.name for m in services.list_members(conn)]:
        pay(conn, name, week, amount)
