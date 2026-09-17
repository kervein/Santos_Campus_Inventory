import hashlib
import secrets
import sqlite3
from datetime import datetime

from logger import logger
from models.schemas import UserRegisterSchema
from pydantic import ValidationError


class AuthController:
    def __init__(self, db_name="hardware_inventory.db"):
        self.db_name = db_name

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return f"{salt}${hashed.hex()}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            salt, hash_hex = stored_hash.split("$")
        except ValueError:
            return False
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return secrets.compare_digest(hashed.hex(), hash_hex)

    def register(self, username, password, email=None, role="USER"):
        try:
            validated = UserRegisterSchema(username=username, email=email, password=password)
        except ValidationError as e:
            msg = e.errors()[0]['msg']
            low = msg.lower()
            if "at least 8" in low or "at least 8 characters" in low:
                return False, "Password must be at least 8 characters."
            if "at least 3" in low:
                return False, "Username must be at least 3 characters."
            if "less than or equal to 20" in low:
                return False, "Username must be 20 characters or less."
            if "letters, numbers, and underscores" in low:
                return False, "Username must contain only letters, numbers, and underscores."
            if "uppercase" in low or "uppercase letter" in low:
                return False, "Password must include at least one uppercase letter."
            if "number" in low or "digit" in low:
                return False, "Password must include at least one number."
            if "special" in low or "special character" in low:
                return False, "Password must include at least one special character from @#$%^&*."
            if "email" in low and "valid" in low:
                return False, "Invalid email address."

            return False, msg

        role = str(role or "USER").upper()
        if role not in {"USER", "ADMIN"}:
            return False, "Role must be USER or ADMIN."
        password_hash = self._hash_password(validated.password)

        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (validated.username, validated.email, password_hash, role),
            )
            conn.commit()
            conn.close()
            logger.info(f"Account Created: '{validated.username}'")
            return True, "User registered successfully."
        except sqlite3.IntegrityError as exc:
            msg = str(exc).lower()
            if "username" in msg:
                return False, "Username already exists."
            if "email" in msg:
                return False, "Email already registered."
            return False, "Registration failed due to a database constraint."

    def login(self, username, password):
        if not username or not password:
            return False, "Username and password cannot be empty."

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash, role, failed_attempts, locked FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False, "Username is not registered."

        user_id, password_hash, role, failed_attempts, locked = row
        if locked:
            conn.close()
            return False, "Account is locked. Use Reset / Unlock Password."

        if self._verify_password(password, password_hash):
            cursor.execute("UPDATE users SET failed_attempts = 0 WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            logger.info(f"User Logged In: '{username}' logged in.")
            return True, {"username": username, "role": role}

        failed_attempts += 1
        locked = 1 if failed_attempts >= 3 else 0
        cursor.execute("UPDATE users SET failed_attempts = ?, locked = ? WHERE id = ?", (failed_attempts, locked, user_id))
        conn.commit()
        conn.close()
        if locked:
            logger.warning(f"Account locked after failed login attempts: '{username}'")
            return False, "Account is locked after three failed attempts. Use Reset / Unlock Password."
        return False, f"Invalid password. {3 - failed_attempts} attempt(s) remaining before lockout."

    def get_profile(self, username):
        with sqlite3.connect(self.db_name) as conn:
            return conn.execute("SELECT username, email, role, locked FROM users WHERE username = ?", (username,)).fetchone()

    def change_password(self, username, current_password, new_password):
        profile = self.get_profile(username)
        if not profile:
            return False, "User account not found."
        with sqlite3.connect(self.db_name) as conn:
            stored = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()[0]
        if not self._verify_password(current_password, stored):
            return False, "Current password is incorrect."
        try:
            validated = UserRegisterSchema(username=username, email=profile[1], password=new_password)
        except ValidationError:
            return False, "New password must be at least 8 characters and include uppercase, number, and special character."
        with sqlite3.connect(self.db_name) as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (self._hash_password(validated.password), username))
        logger.info(f"Password changed: '{username}'")
        return True, "Password changed successfully."

    def request_password_reset(self, email):
        new_password = "Temporary1!"
        try:
            validated = UserRegisterSchema(username="reset_user", email=email, password=new_password)
        except ValidationError:
            return False, "Enter a valid email and a strong new password."
        with sqlite3.connect(self.db_name) as conn:
            row = conn.execute("SELECT id, username FROM users WHERE email = ?", (email,)).fetchone()
            if not row:
                return False, "No account is registered with that email."
            conn.execute(
                "INSERT INTO password_reset_requests (user_id, email, requested_password_hash) VALUES (?, ?, ?)",
                (row[0], email, ""),
            )
        logger.info(f"Password reset requested: '{row[1]}'")
        return True, "Password reset request submitted for admin approval."

    def get_reset_requests(self, status=None):
        query = """SELECT r.request_id, u.username, r.email, r.status, r.requested_at,
                   r.reviewed_at, r.reviewed_by
                   FROM password_reset_requests r JOIN users u ON u.id = r.user_id"""
        params = ()
        if status:
            query += " WHERE r.status = ?"
            params = (status.upper(),)
        query += " ORDER BY r.request_id DESC"
        with sqlite3.connect(self.db_name) as conn:
            return conn.execute(query, params).fetchall()

    def review_reset_request(self, request_id, admin_username, approve, new_password=None):
        with sqlite3.connect(self.db_name) as conn:
            row = conn.execute(
                "SELECT user_id, requested_password_hash, status FROM password_reset_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if not row or row[2] != "PENDING":
                return False, "Pending reset request not found."
            status = "APPROVED" if approve else "REJECTED"
            if approve:
                if not new_password:
                    return False, "The admin must provide a new password."
                conn.execute(
                    "UPDATE users SET password_hash = ?, failed_attempts = 0, locked = 0 WHERE id = ?",
                    (self._hash_password(new_password), row[0]),
                )
            conn.execute(
                "UPDATE password_reset_requests SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE request_id = ?",
                (status, datetime.now().isoformat(timespec="seconds"), admin_username, request_id),
            )
        logger.info(f"Password reset request {request_id} {status.lower()} by '{admin_username}'")
        return True, f"Password reset request {status.lower()}."

    register_user = register
    login_user = login
