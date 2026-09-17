import hashlib
import hmac
import csv
import io
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for, send_file

from models.database import init_hardware_db
from controller.hardware_controller import HardwareController


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "hardware_inventory.db")
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "web", "templates"), static_folder=os.path.join(BASE_DIR, "web"), static_url_path="/static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "development-secret-change-me")
app.config["DATABASE"] = DATABASE


def db():
    connection = sqlite3.connect(
        app.config["DATABASE"], timeout=10, isolation_level=None
    )
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.row_factory = sqlite3.Row
    return connection


def prepare_database():
    init_hardware_db(app.config["DATABASE"])
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS borrow_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL, username TEXT NOT NULL,
                student_id TEXT NOT NULL, quantity INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT, reviewed_by TEXT
            );
            CREATE TABLE IF NOT EXISTS return_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                borrow_id INTEGER NOT NULL, username TEXT NOT NULL,
                quantity INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT, reviewed_by TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL, action TEXT NOT NULL,
                details TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        hardware_columns = {row["name"] for row in connection.execute("PRAGMA table_info(hardware)").fetchall()}
        if "minimum_stock" not in hardware_columns:
            connection.execute("ALTER TABLE hardware ADD COLUMN minimum_stock INTEGER NOT NULL DEFAULT 5")
        borrow_columns = {row["name"] for row in connection.execute("PRAGMA table_info(borrow_records)").fetchall()}
        if "due_at" not in borrow_columns:
            connection.execute("ALTER TABLE borrow_records ADD COLUMN due_at TEXT")
        borrow_request_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(borrow_requests)").fetchall()
        }
        if "student_id" not in borrow_request_columns:
            connection.execute(
                "ALTER TABLE borrow_requests ADD COLUMN student_id TEXT NOT NULL DEFAULT ''"
            )


def password_hash(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, stored):
    if stored.startswith("$2"):
        return bcrypt.checkpw(password.encode(), stored.encode())
    try:
        salt, digest = stored.split("$")
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
        return hmac.compare_digest(calculated, digest)
    except (ValueError, TypeError):
        return False


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "ADMIN":
            return redirect(url_for("catalog"))
        return view(*args, **kwargs)
    return wrapped


def audit(username, action, details, connection=None):
    owns_connection = connection is None
    connection = connection or db()
    connection.execute("INSERT INTO audit_logs (username, action, details) VALUES (?, ?, ?)", (username, action, details))
    if owns_connection:
        connection.commit()
        connection.close()


@app.before_request
def ensure_db():
    if not getattr(app, "_database_ready", False):
        prepare_database()
        app._database_ready = True


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with db() as connection:
            user = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if not user:
                flash("Username is not registered.", "error")
            elif user["locked"] or user["failed_attempts"] >= 3:
                if not user["locked"]:
                    connection.execute("UPDATE users SET locked = 1 WHERE id = ?", (user["id"],))
                flash("Account is locked. Use Reset / Unlock Password.", "error")
            elif verify_password(password, user["password_hash"]):
                connection.execute("UPDATE users SET failed_attempts = 0 WHERE id = ?", (user["id"],))
                session.update(username=user["username"], role=user["role"])
                audit(username, "LOGIN", "Successful login", connection)
                return redirect(url_for("dashboard"))
            else:
                attempts = user["failed_attempts"] + 1
                locked = 1 if attempts >= 3 else 0
                connection.execute("UPDATE users SET failed_attempts = ?, locked = ? WHERE id = ?", (attempts, locked, user["id"]))
                flash("Account is locked after three failed attempts." if locked else f"Invalid password. {3 - attempts} attempt(s) remaining.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "USER").upper()
        if len(username) < 3 or len(username) > 20 or not username.replace("_", "").isalnum():
            flash("Username must be 3-20 characters using only letters, numbers, and underscores.", "error")
        elif len(password) < 8 or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password) or not any(c in "@#$%^&*" for c in password):
            flash("Password must be at least 8 characters and include uppercase, number, and special character.", "error")
        elif "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            flash("Enter a valid email address.", "error")
        elif role not in {"USER", "ADMIN"}:
            flash("Invalid role.", "error")
        else:
            try:
                with db() as connection:
                    connection.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)", (username, email, password_hash(password), role))
                flash("Registration successful. You can now sign in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Username or email is already registered.", "error")
    return render_template("register.html")


@app.route("/reset", methods=["GET", "POST"])
def reset():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        with db() as connection:
            user = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                connection.execute(
                    "INSERT INTO password_reset_requests (user_id, email, requested_password_hash) VALUES (?, ?, '')",
                    (user["id"], email),
                )
                flash("Password change request submitted. An administrator will provide your new password.", "success")
                return redirect(url_for("login"))
        flash("No account is registered with that email.", "error")
    return render_template("reset.html")


@app.route("/dashboard")
@admin_required
def dashboard():
    with db() as connection:
        items = connection.execute("SELECT * FROM hardware ORDER BY item_id").fetchall()
        borrowed = connection.execute("SELECT b.*, h.item_name FROM borrow_records b JOIN hardware h ON h.item_id=b.item_id WHERE b.returned_at IS NULL AND b.quantity > 0 ORDER BY b.borrowed_at DESC").fetchall()
        my_requests = connection.execute("SELECT r.*, h.item_name FROM borrow_requests r JOIN hardware h ON h.item_id=r.item_id WHERE r.username=? ORDER BY r.requested_at DESC", (session["username"],)).fetchall()
        pending_borrows = connection.execute("SELECT r.*, h.item_name FROM borrow_requests r JOIN hardware h ON h.item_id=r.item_id WHERE r.status='PENDING' ORDER BY r.requested_at").fetchall() if session["role"] == "ADMIN" else []
        pending_returns = connection.execute("SELECT r.*, h.item_name, b.student_id FROM return_requests r JOIN borrow_records b ON b.borrow_id=r.borrow_id JOIN hardware h ON h.item_id=b.item_id WHERE r.status='PENDING' ORDER BY r.requested_at").fetchall() if session["role"] == "ADMIN" else []
        history = connection.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 40").fetchall() if session["role"] == "ADMIN" else []
        edit_item_id = request.args.get("edit", type=int)
        edit_item = connection.execute("SELECT * FROM hardware WHERE item_id = ?", (edit_item_id,)).fetchone() if edit_item_id else None
        category_stats = connection.execute(
            "SELECT category, SUM(quantity + borrowed_quantity) AS stock, SUM(borrowed_quantity) AS borrowed FROM hardware GROUP BY category ORDER BY stock DESC"
        ).fetchall()
    total_stocks = sum(i["quantity"] + i["borrowed_quantity"] for i in items)
    total_available = sum(i["quantity"] for i in items)
    total_borrowed = sum(i["borrowed_quantity"] for i in items)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=29)
    first_month = end_date.replace(day=1)
    for _ in range(5):
        first_month = (first_month - timedelta(days=1)).replace(day=1)
    month_keys = []
    month_cursor = first_month
    for _ in range(6):
        month_keys.append(month_cursor.strftime("%Y-%m"))
        month_cursor = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    with db() as connection:
        report_items = connection.execute("SELECT * FROM hardware ORDER BY item_name").fetchall()
        category_options = connection.execute("SELECT DISTINCT category FROM hardware ORDER BY category").fetchall()
        report_categories = connection.execute(
            "SELECT category, COUNT(*) AS item_types, SUM(quantity) AS stock, SUM(borrowed_quantity) AS borrowed, SUM(quantity * unit_price) AS value FROM hardware GROUP BY category ORDER BY stock DESC"
        ).fetchall()
        report_borrowed = connection.execute("SELECT COALESCE(SUM(quantity), 0) AS count FROM borrow_records WHERE date(borrowed_at) BETWEEN ? AND ?", (start_date.isoformat(), end_date.isoformat())).fetchone()["count"]
        report_returned = connection.execute("SELECT COALESCE(SUM(quantity), 0) AS count FROM borrow_records WHERE returned_at IS NOT NULL AND date(returned_at) BETWEEN ? AND ?", (start_date.isoformat(), end_date.isoformat())).fetchone()["count"]
        report_pending = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM borrow_requests WHERE status = 'PENDING')
                + (SELECT COUNT(*) FROM return_requests WHERE status = 'PENDING') AS count
            """
        ).fetchone()["count"]
        report_overdue = connection.execute("SELECT COUNT(*) AS count FROM borrow_records WHERE returned_at IS NULL AND due_at IS NOT NULL AND datetime(due_at) < CURRENT_TIMESTAMP").fetchone()["count"]
        trend_rows = connection.execute("SELECT date(borrowed_at) AS activity_date, SUM(quantity) AS borrowed FROM borrow_records WHERE date(borrowed_at) BETWEEN ? AND ? GROUP BY date(borrowed_at)", (start_date.isoformat(), end_date.isoformat())).fetchall()
        activity_map = {row["activity_date"]: row["borrowed"] for row in trend_rows}
        report_activity = [{"label": (start_date + timedelta(days=i)).strftime("%b %#d"), "borrowed": activity_map.get((start_date + timedelta(days=i)).isoformat(), 0)} for i in range(30)]
        monthly_rows = connection.execute(
            """
            SELECT strftime('%Y-%m', borrowed_at) AS activity_month,
                   COALESCE(SUM(quantity), 0) AS borrowed
            FROM borrow_records
            WHERE date(borrowed_at) BETWEEN ? AND ?
            GROUP BY strftime('%Y-%m', borrowed_at)
            """,
            (first_month.isoformat(), end_date.isoformat()),
        ).fetchall()
        monthly_map = {row["activity_month"]: row["borrowed"] for row in monthly_rows}
        monthly_activity = []
        month_cursor = first_month
        for month_key in month_keys:
            monthly_activity.append(
                {
                    "label": month_cursor.strftime("%b"),
                    "borrowed": monthly_map.get(month_key, 0),
                }
            )
            month_cursor = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        report_activity_log = connection.execute("SELECT action, details, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 10").fetchall()
    monthly_max = max((point["borrowed"] for point in monthly_activity), default=0)
    monthly_mid = monthly_max / 2
    low_stock_items = [item for item in report_items if 0 < item["quantity"] <= 5]
    return render_template(
        "dashboard.html",
        items=items,
        borrowed=borrowed,
        my_requests=my_requests,
        pending_borrows=pending_borrows,
        pending_returns=pending_returns,
        history=history,
        total_stocks=total_stocks,
        total_available=total_available,
        total_borrowed=total_borrowed,
        category_stats=category_stats,
        role=session["role"],
        edit_item=edit_item,
        report_items=report_items,
        category_options=category_options,
        report_categories=report_categories,
        report_borrowed=report_borrowed,
        report_returned=report_returned,
        report_pending=report_pending,
        report_overdue=report_overdue,
        report_activity=report_activity,
        monthly_activity=monthly_activity,
        monthly_max=monthly_max,
        monthly_mid=monthly_mid,
        report_activity_log=report_activity_log,
        report_low_stock_items=low_stock_items,
        report_start_date=start_date.isoformat(),
        report_end_date=end_date.isoformat(),
        report_query="",
    )


def page_data():
    with db() as connection:
        items = connection.execute("SELECT * FROM hardware ORDER BY item_id").fetchall()
        borrowed = connection.execute("SELECT b.*, h.item_name FROM borrow_records b JOIN hardware h ON h.item_id=b.item_id WHERE b.returned_at IS NULL AND b.quantity > 0 ORDER BY b.borrowed_at DESC").fetchall()
        pending_borrows = connection.execute("SELECT r.*, h.item_name FROM borrow_requests r JOIN hardware h ON h.item_id=r.item_id WHERE r.status='PENDING' ORDER BY r.requested_at").fetchall()
        pending_returns = connection.execute("SELECT r.*, h.item_name, b.student_id FROM return_requests r JOIN borrow_records b ON b.borrow_id=r.borrow_id JOIN hardware h ON h.item_id=b.item_id WHERE r.status='PENDING' ORDER BY r.requested_at").fetchall()
        history = connection.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"items": items, "borrowed": borrowed, "pending_borrows": pending_borrows, "pending_returns": pending_returns, "history": history, "role": session["role"]}


@app.get("/catalog")
@login_required
def catalog():
    data = page_data()
    if session["role"] != "ADMIN":
        with db() as connection:
            data["user_request_history"] = connection.execute(
                """
                SELECT r.*, h.item_name
                FROM borrow_requests r
                JOIN hardware h ON h.item_id = r.item_id
                WHERE r.username = ? AND r.status != 'PENDING'
                ORDER BY COALESCE(r.reviewed_at, r.requested_at) DESC
                LIMIT 20
                """,
                (session["username"],),
            ).fetchall()
            data["user_active_borrowed"] = connection.execute(
                """
                SELECT b.*, h.item_name,
                       rr.status AS return_status
                FROM borrow_records b
                JOIN hardware h ON h.item_id = b.item_id
                LEFT JOIN return_requests rr
                    ON rr.borrow_id = b.borrow_id AND rr.status = 'PENDING'
                WHERE b.student_name = ? AND b.returned_at IS NULL AND b.quantity > 0
                ORDER BY b.borrowed_at DESC
                """,
                (session["username"],),
            ).fetchall()
    else:
        data["user_request_history"] = []
        data["user_active_borrowed"] = []
    edit_item_id = request.args.get("edit", type=int)
    if edit_item_id and session["role"] == "ADMIN":
        with db() as connection:
            data["edit_item"] = connection.execute(
                "SELECT * FROM hardware WHERE item_id = ?", (edit_item_id,)
            ).fetchone()
    else:
        data["edit_item"] = None
    if session["role"] != "ADMIN":
        data["items"] = [item for item in data["items"] if item["quantity"] > 0]
    return render_template("catalog.html", **data)


@app.get("/my-borrowing")
@login_required
def my_borrowing():
    if session["role"] == "ADMIN":
        return redirect(url_for("dashboard"))
    with db() as connection:
        request_history = connection.execute(
            """
            SELECT r.*, h.item_name
            FROM borrow_requests r
            JOIN hardware h ON h.item_id = r.item_id
            WHERE r.username = ? AND r.status != 'PENDING'
            ORDER BY COALESCE(r.reviewed_at, r.requested_at) DESC
            LIMIT 20
            """,
            (session["username"],),
        ).fetchall()
        active_borrowed = connection.execute(
            """
            SELECT b.*, h.item_name, rr.status AS return_status
            FROM borrow_records b
            JOIN hardware h ON h.item_id = b.item_id
            LEFT JOIN return_requests rr
                ON rr.borrow_id = b.borrow_id AND rr.status = 'PENDING'
            WHERE b.student_name = ? AND b.returned_at IS NULL AND b.quantity > 0
            ORDER BY b.borrowed_at DESC
            """,
            (session["username"],),
        ).fetchall()
    return render_template(
        "my_borrowing.html",
        role=session["role"],
        user_request_history=request_history,
        user_active_borrowed=active_borrowed,
    )


@app.get("/borrowed")
@admin_required
def borrowed_page():
    return render_template("borrowed.html", **page_data())


@app.get("/approvals")
@admin_required
def approvals():
    return render_template("approvals.html", **page_data())


@app.get("/history")
@admin_required
def history_page():
    return render_template("history.html", **page_data())


@app.get("/reports")
@admin_required
def reports():
    date_range = request.args.get("date_range", "month")
    category_filter = request.args.get("category", "ALL")
    status_filter = request.args.get("status", "ALL")
    trend_period = request.args.get("trend_period", "30", type=int)
    if date_range not in {"today", "week", "month", "custom"}:
        date_range = "month"
    if trend_period not in {7, 30, 180, 365}:
        trend_period = 30
    custom_start = request.args.get("start_date", "")
    custom_end = request.args.get("end_date", "")
    if date_range == "custom":
        try:
            start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
        except ValueError:
            start_date = datetime.now().date() - timedelta(days=29)
            end_date = datetime.now().date()
            date_range = "month"
    else:
        end_date = datetime.now().date()
        range_days = {"today": 0, "week": 6, "month": 29}[date_range]
        start_date = end_date - timedelta(days=range_days)
    start_text, end_text = start_date.isoformat(), end_date.isoformat()
    with db() as connection:
        category_options = connection.execute("SELECT DISTINCT category FROM hardware ORDER BY category").fetchall()
        inventory_where, inventory_params = [], []
        if category_filter != "ALL":
            inventory_where.append("category = ?")
            inventory_params.append(category_filter)
        if status_filter != "ALL":
            inventory_where.append("status = ?")
            inventory_params.append(status_filter)
        inventory_clause = f" WHERE {' AND '.join(inventory_where)}" if inventory_where else ""
        items = connection.execute(f"SELECT * FROM hardware{inventory_clause} ORDER BY item_name", inventory_params).fetchall()
        categories = connection.execute(
            f"""
            SELECT category, COUNT(*) AS item_types, COALESCE(SUM(quantity), 0) AS stock,
                   COALESCE(SUM(borrowed_quantity), 0) AS borrowed,
                   COALESCE(SUM(quantity * unit_price), 0) AS value
            FROM hardware{inventory_clause} GROUP BY category ORDER BY stock DESC
            """,
            inventory_params,
        ).fetchall()
        period_params = (start_text, end_text)
        borrowed_in_range = connection.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS count FROM borrow_records WHERE date(borrowed_at) BETWEEN ? AND ?",
            period_params,
        ).fetchone()["count"]
        returned_in_range = connection.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS count FROM borrow_records WHERE returned_at IS NOT NULL AND date(returned_at) BETWEEN ? AND ?",
            period_params,
        ).fetchone()["count"]
        trend_start = end_date - timedelta(days=trend_period - 1)
        trend_rows = connection.execute(
            """
            SELECT date(borrowed_at) AS activity_date, COALESCE(SUM(quantity), 0) AS borrowed
            FROM borrow_records WHERE date(borrowed_at) BETWEEN ? AND ?
            GROUP BY date(borrowed_at) ORDER BY activity_date
            """,
            (trend_start.isoformat(), end_text),
        ).fetchall()
        trend_map = {row["activity_date"]: row["borrowed"] for row in trend_rows}
        trend = [
            {"label": (trend_start + timedelta(days=index)).strftime("%b %-d" if os.name != "nt" else "%b %#d"), "borrowed": trend_map.get((trend_start + timedelta(days=index)).isoformat(), 0)}
            for index in range(trend_period)
        ]
        pending_requests = connection.execute("SELECT COUNT(*) AS count FROM borrow_requests WHERE status='PENDING'").fetchone()["count"]
        overdue = connection.execute(
            "SELECT COUNT(*) AS count FROM borrow_records WHERE returned_at IS NULL AND due_at IS NOT NULL AND datetime(due_at) < CURRENT_TIMESTAMP"
        ).fetchone()["count"]
        recent_activity = connection.execute(
            "SELECT action, details, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    total_quantity = sum(item["quantity"] for item in items)
    total_borrowed = sum(item["borrowed_quantity"] for item in items)
    total_value = sum(item["quantity"] * item["unit_price"] for item in items)
    low_stock_items = [item for item in items if 0 < item["quantity"] <= 5]
    out_of_stock = sum(1 for item in items if item["quantity"] <= 0)
    query = request.args.to_dict()
    query.pop("format", None)
    return render_template(
        "reports.html",
        items=items,
        role=session["role"],
        categories=categories,
        category_options=category_options,
        recent_activity=recent_activity,
        total_quantity=total_quantity,
        total_borrowed=total_borrowed,
        total_value=total_value,
        low_stock=len(low_stock_items),
        out_of_stock=out_of_stock,
        low_stock_items=low_stock_items,
        pending_requests=pending_requests,
        returned_in_range=returned_in_range,
        borrowed_in_range=borrowed_in_range,
        overdue=overdue,
        trend=trend,
        date_range=date_range,
        category_filter=category_filter,
        status_filter=status_filter,
        trend_period=trend_period,
        start_date=start_text,
        end_date=end_text,
        trend_start=trend_start.isoformat(),
        report_query="&".join(f"{key}={value}" for key, value in query.items()),
    )


@app.get("/admin/reports/export")
@admin_required
def export_report():
    category_filter = request.args.get("category", "ALL")
    status_filter = request.args.get("status", "ALL")
    date_range = request.args.get("date_range", "month")
    end_date = datetime.now().date()
    if date_range == "today":
        start_date = end_date
    elif date_range == "week":
        start_date = end_date - timedelta(days=6)
    elif date_range == "custom":
        try:
            start_date = datetime.strptime(request.args.get("start_date", ""), "%Y-%m-%d").date()
            end_date = datetime.strptime(request.args.get("end_date", ""), "%Y-%m-%d").date()
        except ValueError:
            start_date = end_date - timedelta(days=29)
    else:
        start_date = end_date - timedelta(days=29)
    conditions, params = [], []
    if category_filter != "ALL":
        conditions.append("category = ?")
        params.append(category_filter)
    if status_filter != "ALL":
        conditions.append("status = ?")
        params.append(status_filter)
    clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    with db() as connection:
        rows = connection.execute(
            f"SELECT item_id, item_name, category, quantity, borrowed_quantity, unit_price, status, condition FROM hardware{clause} ORDER BY item_name",
            params,
        ).fetchall()
        borrowing_summary = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN date(borrowed_at) BETWEEN ? AND ? THEN quantity ELSE 0 END), 0) AS borrowed,
                COALESCE(SUM(CASE WHEN returned_at IS NOT NULL AND date(returned_at) BETWEEN ? AND ? THEN quantity ELSE 0 END), 0) AS returned
            FROM borrow_records
            """,
            (start_date.isoformat(), end_date.isoformat(), start_date.isoformat(), end_date.isoformat()),
        ).fetchone()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["ID", "Item", "Category", "Available", "Borrowed", "Unit Price", "Status", "Condition"])
    writer.writerows(rows)
    writer.writerow([])
    writer.writerow(["Report filters", f"Category: {category_filter}", f"Status: {status_filter}", f"Dates: {start_date.isoformat()} to {end_date.isoformat()}"])
    writer.writerow(["Borrowing summary", f"Borrowed in range: {borrowing_summary['borrowed']}", f"Returned in range: {borrowing_summary['returned']}"])
    audit(session["username"], "REPORT_EXPORT", f"Exported {len(rows)} filtered report record(s) to CSV")
    return send_file(io.BytesIO(output.getvalue().encode("utf-8-sig")), mimetype="text/csv", as_attachment=True, download_name="equiptrack_report.csv")


@app.get("/settings")
@login_required
def settings():
    locked_users = []
    reset_requests = []
    profile = None
    if session["role"] == "ADMIN":
        with db() as connection:
            locked_users = connection.execute(
                """
                SELECT username, email, failed_attempts
                FROM users
                WHERE locked = 1 OR failed_attempts >= 3
                ORDER BY username
                """
            ).fetchall()
            reset_requests = connection.execute(
                """
                SELECT r.request_id, u.username, r.email, r.requested_at
                FROM password_reset_requests r
                JOIN users u ON u.id = r.user_id
                WHERE r.status = 'PENDING'
                ORDER BY r.requested_at DESC
                """
            ).fetchall()
    else:
        with db() as connection:
            profile = connection.execute(
                "SELECT email FROM users WHERE username = ?", (session["username"],)
            ).fetchone()
    return render_template(
        "settings.html",
        role=session["role"],
        locked_users=locked_users,
        reset_requests=reset_requests,
        profile=profile,
    )


@app.post("/account/password-request")
@login_required
def account_password_request():
    requested_password = request.form.get("requested_password", "")
    if (
        len(requested_password) < 8
        or not any(character.isupper() for character in requested_password)
        or not any(character.isdigit() for character in requested_password)
        or not any(character in "@#$%^&*" for character in requested_password)
    ):
        flash(
            "Password must be at least 8 characters and include uppercase, number, and special character.",
            "error",
        )
        return redirect(url_for("settings"))

    with db() as connection:
        user = connection.execute(
            "SELECT id, email FROM users WHERE username = ?",
            (session["username"],),
        ).fetchone()
        if not user:
            flash("User account was not found.", "error")
            return redirect(url_for("settings"))
        connection.execute(
            "INSERT INTO password_reset_requests (user_id, email, requested_password_hash) VALUES (?, ?, ?)",
            (user["id"], user["email"], password_hash(requested_password)),
        )
    flash("Password change request submitted. An administrator must approve it before it takes effect.", "success")
    return redirect(url_for("settings"))


@app.post("/account/change-password")
@login_required
def account_change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if new_password != confirm_password:
        flash("The new password and confirmation do not match.", "error")
        return redirect(url_for("settings"))
    if (
        len(new_password) < 8
        or not any(character.isupper() for character in new_password)
        or not any(character.isdigit() for character in new_password)
        or not any(character in "@#$%^&*" for character in new_password)
    ):
        flash(
            "Password must be at least 8 characters and include uppercase, number, and special character.",
            "error",
        )
        return redirect(url_for("settings"))

    with db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (session["username"],),
        ).fetchone()
        if not user or not verify_password(current_password, user["password_hash"]):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("settings"))
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash(new_password), user["id"]),
        )
    audit(session["username"], "PASSWORD_CHANGED", "Changed account password")
    flash("Your password was changed successfully.", "success")
    return redirect(url_for("settings"))


@app.post("/admin/account-reset")
@admin_required
def admin_account_reset():
    username = request.form.get("username", "").strip()
    new_password = request.form.get("password", "")
    if (
        len(new_password) < 8
        or not any(character.isupper() for character in new_password)
        or not any(character.isdigit() for character in new_password)
        or not any(character in "@#$%^&*" for character in new_password)
    ):
        flash(
            "Password must be at least 8 characters and include uppercase, number, and special character.",
            "error",
        )
        return redirect(url_for("settings"))
    with db() as connection:
        user = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            flash("User account was not found.", "error")
            return redirect(url_for("settings"))
        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, failed_attempts = 0, locked = 0
            WHERE id = ?
            """,
            (password_hash(new_password), user["id"]),
        )
        connection.execute(
            """
            UPDATE password_reset_requests
            SET status = 'APPROVED', reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?
            WHERE user_id = ? AND status = 'PENDING'
            """,
            (session["username"], user["id"]),
        )
    audit(
        session["username"],
        "ADMIN_ACCOUNT_RESET",
        f"Reset password and unlocked account '{username}'",
    )
    flash(f"Account '{username}' was unlocked and its password was reset.", "success")
    return redirect(url_for("settings"))


@app.post("/admin/password-request/<int:request_id>/<action>")
@admin_required
def review_password_request(request_id, action):
    if action not in {"approve", "reject"}:
        flash("Invalid password request action.", "error")
        return redirect(url_for("settings"))

    with db() as connection:
        password_request = connection.execute(
            """
            SELECT r.user_id, u.username, r.requested_password_hash
            FROM password_reset_requests r
            JOIN users u ON u.id = r.user_id
            WHERE r.request_id = ? AND r.status = 'PENDING'
            """,
            (request_id,),
        ).fetchone()
        if not password_request:
            flash("Pending password request was not found.", "error")
            return redirect(url_for("settings"))

        if action == "reject":
            connection.execute(
                """
                UPDATE password_reset_requests
                SET status = 'REJECTED', reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?
                WHERE request_id = ?
                """,
                (session["username"], request_id),
            )
            flash(f"Password change request for '{password_request['username']}' was rejected.", "success")
            return redirect(url_for("settings"))

        if not password_request["requested_password_hash"]:
            flash("This request does not contain a requested password and cannot be approved.", "error")
            return redirect(url_for("settings"))

        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, failed_attempts = 0, locked = 0
            WHERE id = ?
            """,
            (password_request["requested_password_hash"], password_request["user_id"]),
        )
        connection.execute(
            """
            UPDATE password_reset_requests
            SET status = 'APPROVED', reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?
            WHERE request_id = ?
            """,
            (session["username"], request_id),
        )
    audit(
        session["username"],
        "PASSWORD_CHANGE_REQUEST_APPROVED",
        f"Provided a new password for '{password_request['username']}'",
    )
    flash(f"Password change request for '{password_request['username']}' was approved.", "success")
    return redirect(url_for("settings"))


@app.post("/admin/equipment/save")
@admin_required
def save_equipment():
    controller = HardwareController(app.config["DATABASE"])
    item_id = request.form.get("item_id", type=int)
    values = {
        "name": request.form.get("name", ""),
        "category": request.form.get("category", ""),
        "quantity": request.form.get("quantity", ""),
        "price": request.form.get("price", ""),
        "serial_number": request.form.get("serial_number", ""),
        "condition": request.form.get("condition", "Good"),
    }
    if item_id:
        success, message = controller.update_item(item_id, **values)
        action = "EQUIPMENT_UPDATED"
    else:
        success, message = controller.add_item(**values)
        action = "EQUIPMENT_ADDED"
    if success:
        audit(session["username"], action, message)
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("catalog"))


@app.post("/admin/equipment/<int:item_id>/delete")
@admin_required
def delete_equipment(item_id):
    success, message = HardwareController(app.config["DATABASE"]).delete_item(item_id)
    if success:
        audit(session["username"], "EQUIPMENT_DELETED", message)
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("dashboard", _anchor="catalog"))


@app.get("/admin/equipment/export")
@admin_required
def export_equipment():
    with db() as connection:
        rows = connection.execute(
            """
            SELECT item_id, item_name, category, quantity, borrowed_quantity,
                   unit_price, status, serial_number, condition
            FROM hardware
            ORDER BY item_id
            """
        ).fetchall()

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "Name",
            "Category",
            "Available Quantity",
            "Borrowed Quantity",
            "Unit Price",
            "Status",
            "Serial Number",
            "Condition",
        ]
    )
    writer.writerows(rows)
    audit(session["username"], "EQUIPMENT_EXPORT", f"Exported {len(rows)} equipment record(s) to CSV")
    csv_file = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    return send_file(
        csv_file,
        mimetype="text/csv",
        as_attachment=True,
        download_name="hardware_inventory.csv",
    )


@app.post("/borrow")
@login_required
def borrow():
    item_id = request.form.get("item_id", type=int)
    item_name = request.form.get("item_name", "").strip()
    quantity = request.form.get("quantity", type=int)
    if not item_id and item_name:
        with db() as connection:
            match = connection.execute("SELECT item_id FROM hardware WHERE lower(item_name) = lower(?)", (item_name,)).fetchone()
        item_id = match["item_id"] if match else None
    if not item_id or not quantity or quantity < 1:
        flash("Choose an equipment item and enter a valid borrow quantity.", "error")
    else:
        with db() as connection:
            item = connection.execute("SELECT item_name, quantity FROM hardware WHERE item_id=?", (item_id,)).fetchone()
            if not item:
                flash("Equipment was not found.", "error")
            elif quantity > item["quantity"]:
                flash(f"Only {item['quantity']} unit(s) are available.", "error")
            else:
                connection.execute("INSERT INTO borrow_requests (item_id, username, student_id, quantity) VALUES (?, ?, ?, ?)", (item_id, session["username"], request.form.get("student_id", "").strip(), quantity))
                audit(session["username"], "BORROW_REQUEST", f"Requested {quantity} unit(s) of {item['item_name']}", connection)
                flash("Borrow request submitted. Stock remains unchanged until approval.", "success")
    return redirect(url_for("dashboard"))


@app.post("/return-request")
@login_required
def return_request():
    borrow_id, quantity = request.form.get("borrow_id", type=int), request.form.get("quantity", type=int)
    with db() as connection:
        owner_clause = "AND b.student_name = ?" if session["role"] != "ADMIN" else ""
        owner_params = (session["username"],) if session["role"] != "ADMIN" else ()
        record = connection.execute(
            f"SELECT b.*, h.item_name FROM borrow_records b JOIN hardware h ON h.item_id=b.item_id WHERE b.borrow_id=? AND b.returned_at IS NULL {owner_clause}",
            (borrow_id, *owner_params),
        ).fetchone()
        if not record or not quantity or quantity < 1 or quantity > record["quantity"]:
            flash("Invalid return quantity.", "error")
        else:
            connection.execute("INSERT INTO return_requests (borrow_id, username, quantity) VALUES (?, ?, ?)", (borrow_id, session["username"], quantity))
            audit(session["username"], "RETURN_REQUEST", f"Requested return of {quantity} unit(s) of {record['item_name']}", connection)
            flash("Return request submitted. Stock will be restored after admin approval.", "success")
    return redirect(url_for("dashboard"))


@app.post("/admin/borrow/<int:request_id>/<action>")
@admin_required
def review_borrow(request_id, action):
    if action not in {"approve", "reject"}:
        return redirect(url_for("dashboard"))
    with db() as connection:
        request_row = connection.execute("SELECT r.*, h.item_name, h.quantity AS available_quantity FROM borrow_requests r JOIN hardware h ON h.item_id=r.item_id WHERE r.request_id=? AND r.status='PENDING'", (request_id,)).fetchone()
        if not request_row:
            flash("Pending borrow request not found.", "error")
        elif action == "approve" and request_row["quantity"] > request_row["available_quantity"]:
            flash("Not enough stock remains for this request.", "error")
        else:
            status = "APPROVED" if action == "approve" else "REJECTED"
            if action == "approve":
                connection.execute("UPDATE hardware SET quantity=quantity-?, borrowed_quantity=borrowed_quantity+?, status=CASE WHEN quantity-?<=0 THEN 'Out of Stock' WHEN quantity-?<=5 THEN 'Low Stock' ELSE 'In Stock' END WHERE item_id=?", (request_row["quantity"], request_row["quantity"], request_row["quantity"], request_row["quantity"], request_row["item_id"]))
                connection.execute("INSERT INTO borrow_records (item_id, student_name, student_id, quantity, due_at) VALUES (?, ?, ?, ?, datetime('now', '+14 days'))", (request_row["item_id"], request_row["username"], request_row["student_id"], request_row["quantity"]))
            connection.execute("UPDATE borrow_requests SET status=?, reviewed_at=CURRENT_TIMESTAMP, reviewed_by=? WHERE request_id=?", (status, session["username"], request_id))
            audit(session["username"], f"BORROW_{status}", f"{request_row['quantity']} unit(s) of {request_row['item_name']}", connection)
            flash(f"Borrow request {status.lower()}.", "success")
    return redirect(url_for("dashboard"))


@app.post("/admin/return/<int:request_id>/<action>")
@admin_required
def review_return(request_id, action):
    with db() as connection:
        row = connection.execute("SELECT r.*, b.item_id, b.quantity AS borrowed, h.item_name FROM return_requests r JOIN borrow_records b ON b.borrow_id=r.borrow_id JOIN hardware h ON h.item_id=b.item_id WHERE r.request_id=? AND r.status='PENDING'", (request_id,)).fetchone()
        if not row:
            flash("Pending return request not found.", "error")
        else:
            status = "APPROVED" if action == "approve" else "REJECTED"
            if status == "APPROVED":
                connection.execute("UPDATE hardware SET quantity=quantity+?, borrowed_quantity=borrowed_quantity-? WHERE item_id=?", (row["quantity"], row["quantity"], row["item_id"]))
                if row["quantity"] == row["borrowed"]:
                    connection.execute("UPDATE borrow_records SET quantity=0, returned_at=CURRENT_TIMESTAMP WHERE borrow_id=?", (row["borrow_id"],))
                else:
                    connection.execute("UPDATE borrow_records SET quantity=quantity-? WHERE borrow_id=?", (row["quantity"], row["borrow_id"]))
            connection.execute("UPDATE return_requests SET status=?, reviewed_at=CURRENT_TIMESTAMP, reviewed_by=? WHERE request_id=?", (status, session["username"], request_id))
            audit(session["username"], f"RETURN_{status}", f"{row['quantity']} unit(s) of {row['item_name']}", connection)
            flash(f"Return request {status.lower()}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    username = session.pop("username", None)
    session.pop("role", None)
    if username:
        audit(username, "LOGOUT", "User logged out")
    return redirect(url_for("login"))


prepare_database()
