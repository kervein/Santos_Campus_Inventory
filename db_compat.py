"""Database backend selection and compatibility shims.

The application was originally written against sqlite3, using '?'
placeholders and sqlite3.Row-style access (both row["col"] and row[0]).
When DATABASE_URL is set (pointing at Supabase/Postgres), this module
provides a thin wrapper around psycopg2 that mimics the same interface so
the rest of the codebase does not need to be rewritten per-backend.

If DATABASE_URL is not set, the app falls back to the local SQLite file,
preserving the previous behaviour for offline development.
"""

import os
import sqlite3

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL) and psycopg2 is not None

# Exposed so callers can catch backend-appropriate exceptions without
# importing sqlite3/psycopg2 directly.
if USE_POSTGRES:
    Error = psycopg2.Error
    IntegrityError = psycopg2.IntegrityError
else:
    Error = sqlite3.Error
    IntegrityError = sqlite3.IntegrityError


def _translate(sql):
    """Convert sqlite-style '?' placeholders to psycopg2-style '%s'."""
    return sql.replace("?", "%s") if USE_POSTGRES else sql


class _Row(tuple):
    """Tuple subclass that also supports sqlite3.Row-style column access
    (row["col_name"]) in addition to positional indexing (row[0])."""

    def __new__(cls, columns, values):
        obj = super().__new__(cls, values)
        obj._columns = columns
        return obj

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                index = self._columns.index(key)
            except ValueError:
                raise KeyError(key)
            return tuple.__getitem__(self, index)
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._columns)


class _RowCursor:
    """Wraps a psycopg2 cursor to translate '?' placeholders and return
    rows that support both name-based and index-based access."""

    def __init__(self, raw_cursor):
        self._cursor = raw_cursor

    def execute(self, sql, params=None):
        self._cursor.execute(_translate(sql), params or None)
        return self

    def executemany(self, sql, seq_of_params):
        self._cursor.executemany(_translate(sql), seq_of_params)
        return self

    def _wrap(self, row):
        if row is None:
            return None
        columns = [d[0] for d in self._cursor.description]
        return _Row(columns, row)

    def fetchone(self):
        return self._wrap(self._cursor.fetchone())

    def fetchall(self):
        return [self._wrap(row) for row in self._cursor.fetchall()]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()
        return [self._wrap(row) for row in rows]

    def __iter__(self):
        for row in self._cursor:
            yield self._wrap(row)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        self._cursor.close()


class PostgresConnection:
    """Wraps a psycopg2 connection so it behaves like the sqlite3.Connection
    API surface this project relies on: an .execute() shortcut, '?'
    placeholder support, dict/index-style row access, and context-manager
    commit/rollback semantics that do not close the connection."""

    def __init__(self, raw_connection):
        self._conn = raw_connection

    def cursor(self):
        return _RowCursor(self._conn.cursor())

    def execute(self, sql, params=None):
        cursor = self.cursor()
        cursor.execute(sql, params)
        return cursor

    def executescript(self, sql):
        with self._conn.cursor() as cursor:
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False


def get_connection():
    """Return a Postgres connection (wrapped for sqlite3-style access) when
    DATABASE_URL is configured; the caller is expected to fall back to
    sqlite3.connect(...) directly otherwise."""
    if not USE_POSTGRES:
        raise RuntimeError("get_connection() called without DATABASE_URL configured.")
    raw = psycopg2.connect(DATABASE_URL)
    return PostgresConnection(raw)
