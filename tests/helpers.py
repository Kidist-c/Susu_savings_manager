"""Small helpers that keep tests short and readable."""
from app import services

NAMES = ("Ama", "Kofi", "Esi")


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]