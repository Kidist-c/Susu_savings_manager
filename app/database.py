"""SQLite connection, schema and transaction helpers (no business rules)."""
import os
import sqlite3
from contextlib import contextmanager

DEFAULT_DB_PATH = "susu.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    weekly_contribution_pesewas INTEGER NOT NULL CHECK (weekly_contribution_pesewas > 0),
    current_week INTEGER NOT NULL CHECK (current_week >= 1)
);
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_key TEXT NOT NULL UNIQUE,
    join_order INTEGER NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id INTEGER NOT NULL REFERENCES members(id),
    week INTEGER NOT NULL CHECK (week >= 1),
    amount_pesewas INTEGER NOT NULL CHECK (amount_pesewas > 0),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contrib_member_week ON contributions(member_id, week);
CREATE TABLE IF NOT EXISTS payouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week INTEGER NOT NULL UNIQUE,
    member_id INTEGER NOT NULL REFERENCES members(id),
    amount_pesewas INTEGER NOT NULL CHECK (amount_pesewas > 0),
    paid_at TEXT NOT NULL
);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open a connection (path, else $SUSU_DB_PATH, else ./susu.db) and make sure tables exist.

    The connection is in autocommit mode; transactions are explicit via transaction().
    check_same_thread=False is safe because each HTTP request opens its own connection.
    """
    path = path or os.environ.get("SUSU_DB_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Write transaction: takes the write lock up front; commits on success, rolls back on any error."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


@contextmanager
def read_transaction(conn: sqlite3.Connection):
    """Read-only snapshot so a multi-query read sees one consistent state."""
    conn.execute("BEGIN")
    try:
        yield conn
    finally:
        conn.execute("COMMIT")
