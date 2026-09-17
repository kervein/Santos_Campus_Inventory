import sqlite3

from logger import logger


def init_hardware_db(db_name="hardware_inventory.db"):
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'USER',
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS hardware (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                borrowed_quantity INTEGER NOT NULL DEFAULT 0,
                unit_price REAL NOT NULL,
                status TEXT NOT NULL,
                serial_number TEXT,
                condition TEXT NOT NULL DEFAULT 'Good',
                location TEXT NOT NULL DEFAULT ''
            )
            """
        )

        # Ensure email column exists (migrate older DBs) and create a unique index
        cursor.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cursor.fetchall()]
        if "email" not in cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
            except sqlite3.Error:
                # Some SQLite builds may not allow certain ALTER operations; ignore and continue
                pass
        if "role" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'USER'")
        if "failed_attempts" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0")
        if "locked" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN locked INTEGER NOT NULL DEFAULT 0")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")

        cursor.execute("PRAGMA table_info(hardware)")
        hardware_cols = [r[1] for r in cursor.fetchall()]
        for col_name, col_sql in {
            "serial_number": "ALTER TABLE hardware ADD COLUMN serial_number TEXT",
            "condition": "ALTER TABLE hardware ADD COLUMN condition TEXT NOT NULL DEFAULT 'Good'",
            "location": "ALTER TABLE hardware ADD COLUMN location TEXT NOT NULL DEFAULT ''",
            "borrowed_quantity": "ALTER TABLE hardware ADD COLUMN borrowed_quantity INTEGER NOT NULL DEFAULT 0",
        }.items():
            if col_name not in hardware_cols:
                try:
                    cursor.execute(col_sql)
                except sqlite3.Error:
                    pass
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_hardware_serial ON hardware(serial_number) WHERE serial_number IS NOT NULL AND serial_number != ''")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS borrow_records (
                borrow_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                student_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                borrowed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                returned_at TEXT,
                FOREIGN KEY (item_id) REFERENCES hardware(item_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                requested_password_hash TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'PENDING',
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT,
                reviewed_by TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        conn.commit()
        conn.close()
        logger.info("Hardware inventory database initialized successfully.")
    except sqlite3.Error as exc:
        logger.error(f"Error initializing hardware database: {exc}")
