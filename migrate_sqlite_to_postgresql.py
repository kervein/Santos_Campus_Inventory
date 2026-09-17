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

from db_schema import POSTGRES_SCHEMA  # noqa: E402  (kept in sync with app.py)

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
