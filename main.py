"""Application launcher for EquipTrack.

The complete Flask application lives in app.py. This module remains the
documented entry point so the project can be started with ``python main.py``.
"""

import argparse
import threading
import webbrowser

from app import app, prepare_database, verify_supabase_connection


def parse_args():
    parser = argparse.ArgumentParser(description="Run the EquipTrack application.")
    parser.add_argument(
        "--test-supabase",
        action="store_true",
        help="Verify that the configured Supabase URL and anon key are reachable.",
    )
    parser.add_argument(
        "--test-table",
        help="Optional Supabase table name to query with a limit(1) check.",
    )
    parser.add_argument(
        "--migrate-postgres",
        action="store_true",
        help="Copy the local SQLite data into the configured PostgreSQL/DATABASE_URL target.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.migrate_postgres:
        from migrate_sqlite_to_postgresql import migrate

        migrate()
        raise SystemExit(0)

    prepare_database()

    if args.test_supabase:
        verification = verify_supabase_connection(test_table=args.test_table)
        print(
            f"Supabase connection verified via {verification['rest_url']} "
            f"(HTTP {verification['rest_status']})."
        )
        if "table" in verification:
            print(
                f"Test query to table '{verification['table']}' succeeded "
                f"with {verification['sample_row_count']} sample row(s)."
            )
        raise SystemExit(0)

    browser_timer = threading.Timer(
        1.0, lambda: webbrowser.open_new("http://127.0.0.1:5000")
    )
    browser_timer.daemon = True
    browser_timer.start()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)