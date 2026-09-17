"""One-off migration script: copies EquipTrack's local SQLite data into a
Supabase Postgres database.

Usage:
    python migrate_sqlite_to_postgresql.py

Requires DATABASE_URL to be set (in .env or the environment) pointing at the
target Postgres instance (e.g. the Supabase connection pooler string).
"""

import os
import sqlite3
import sys

import psycopg2
from psycopg2.extras import execute_values

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if load_dotenv is not None:
    load_dotenv(os.path.join(BASE_DIR, ".env"))

SQLITE_PATH = os.path.join(BASE_DIR, "hardware_inventory.db")
DATABASE_URL = os.environ.get("DATABASE_URL")

# Table definitions in dependency order (parents before children) so foreign
# keys can be satisfied as rows are inserted.
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'USER',
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL AND email != '';

CREATE TABLE IF NOT EXISTS hardware (
    item_id SERIAL PRIMARY KEY,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    borrowed_quantity INTEGER NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL,
    status TEXT NOT NULL,
    serial_number TEXT,
    condition TEXT NOT NULL DEFAULT 'Good',
    location TEXT NOT NULL DEFAULT '',
    minimum_stock INTEGER NOT NULL DEFAULT 5
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hardware_serial ON hardware(serial_number) WHERE serial_number IS NOT NULL AND serial_number != '';

CREATE TABLE IF NOT EXISTS borrow_records (
    borrow_id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES hardware(item_id),
    student_name TEXT NOT NULL,
    student_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    borrowed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    returned_at TEXT,
    due_at TEXT
);

CREATE TABLE IF NOT EXISTS password_reset_requests (
    request_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    email TEXT NOT NULL,
    requested_password_hash TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    reviewed_by TEXT
);

CREATE TABLE IF NOT EXISTS borrow_requests (
    request_id SERIAL PRIMARY KEY,
    item_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    student_id TEXT NOT NULL DEFAULT '',
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    reviewed_by TEXT
);

CREATE TABLE IF NOT EXISTS return_requests (
    request_id SERIAL PRIMARY KEY,
    borrow_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    reviewed_by TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    log_id SERIAL PRIMARY KEY,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_history (
    history_id SERIAL PRIMARY KEY,
    username TEXT,
    action TEXT,
    item_name TEXT,
    quantity INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# (table, ordered columns, primary key column) - order matches POSTGRES_SCHEMA
TABLES = [
    ("users", ["id", "username", "email", "password_hash", "role", "failed_attempts", "locked"], "id"),
    ("hardware", ["item_id", "item_name", "category", "quantity", "borrowed_quantity", "unit_price", "status", "serial_number", "condition", "location", "minimum_stock"], "item_id"),
    ("borrow_records", ["borrow_id", "item_id", "student_name", "student_id", "quantity", "borrowed_at", "returned_at", "due_at"], "borrow_id"),
    ("password_reset_requests", ["request_id", "user_id", "email", "requested_password_hash", "status", "requested_at", "reviewed_at", "reviewed_by"], "request_id"),
    ("borrow_requests", ["request_id", "item_id", "username", "student_id", "quantity", "status", "requested_at", "reviewed_at", "reviewed_by"], "request_id"),
    ("return_requests", ["request_id", "borrow_id", "username", "quantity", "status", "requested_at", "reviewed_at", "reviewed_by"], "request_id"),
    ("audit_logs", ["log_id", "username", "action", "details", "created_at"], "log_id"),
    ("audit_history", ["history_id", "username", "action", "item_name", "quantity", "created_at"], "history_id"),
]


def fetch_sqlite_rows(sqlite_conn, table, columns):
    existing_columns = {
        row["name"] for row in sqlite_conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    usable_columns = [c for c in columns if c in existing_columns]
    if not usable_columns:
        return usable_columns, []
    placeholders = ", ".join(usable_columns)
    rows = sqlite_conn.execute(f"SELECT {placeholders} FROM {table}").fetchall()
    return usable_columns, [tuple(row) for row in rows]


def migrate():
    if not DATABASE_URL:
        print("DATABASE_URL is not set. Add it to .env before running this script.")
        sys.exit(1)
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite database not found at {SQLITE_PATH}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    pg_conn.autocommit = False

    try:
        with pg_conn.cursor() as cur:
            print("Creating schema in Postgres (if not already present)...")
            cur.execute(POSTGRES_SCHEMA)
        pg_conn.commit()

        for table, columns, pk_column in TABLES:
            usable_columns, rows = fetch_sqlite_rows(sqlite_conn, table, columns)
            if not usable_columns:
                print(f"Skipping '{table}': table not found in SQLite database.")
                continue
            if not rows:
                print(f"'{table}': no rows to migrate.")
                continue

            col_list = ", ".join(usable_columns)
            with pg_conn.cursor() as cur:
                execute_values(
                    cur,
                    f"INSERT INTO {table} ({col_list}) VALUES %s ON CONFLICT ({pk_column}) DO NOTHING",
                    rows,
                )
            pg_conn.commit()
            print(f"'{table}': migrated {len(rows)} row(s).")

        # Re-sync the SERIAL sequences so future INSERTs continue after the
        # highest migrated id instead of colliding with existing rows.
        with pg_conn.cursor() as cur:
            for table, _columns, pk_column in TABLES:
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', '{pk_column}'), "
                    f"COALESCE((SELECT MAX({pk_column}) FROM {table}), 1), "
                    f"(SELECT MAX({pk_column}) FROM {table}) IS NOT NULL)"
                )
        pg_conn.commit()
        print("Sequence counters synced.")
        print("Migration complete.")
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    migrate()
