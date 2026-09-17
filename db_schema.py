"""Shared Postgres schema definition for EquipTrack.

Used by both app.py (prepare_database, when DATABASE_URL is configured)
and migrate_sqlite_to_postgresql.py, so the two stay in sync.
"""

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

-- Additive column fixes for databases created by earlier schema versions.
ALTER TABLE hardware ADD COLUMN IF NOT EXISTS minimum_stock INTEGER NOT NULL DEFAULT 5;
ALTER TABLE borrow_records ADD COLUMN IF NOT EXISTS due_at TEXT;
ALTER TABLE borrow_requests ADD COLUMN IF NOT EXISTS student_id TEXT NOT NULL DEFAULT '';
"""
