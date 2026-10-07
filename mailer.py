"""Brevo SMTP email delivery for one-time passcodes (OTPs)."""

import os
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import parseaddr

BREVO_HOST = "smtp-relay.brevo.com"
# Port 2525 is used because hosts like Render block outbound SMTP on 587.
BREVO_PORT = 2525


def is_configured():
    return bool(os.environ.get("BREVO_SMTP_LOGIN") and os.environ.get("BREVO_SMTP_KEY") and os.environ.get("MAIL_FROM"))


def send_email(to_address, subject, body):
    message = EmailMessage()
    message["From"] = os.environ["MAIL_FROM"]
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    host = os.environ.get("BREVO_SMTP_HOST", BREVO_HOST)
    port = int(os.environ.get("BREVO_SMTP_PORT", BREVO_PORT))
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(os.environ["BREVO_SMTP_LOGIN"], os.environ["BREVO_SMTP_KEY"])
        server.send_message(message)


def notify_admins(admin_emails, subject, body):
    """Email every admin (plus ADMIN_NOTIFY_EMAIL, or the MAIL_FROM address when
    unset) in the background. Failures are logged and never block the request."""
    if not is_configured():
        return
    extra = os.environ.get("ADMIN_NOTIFY_EMAIL") or parseaddr(os.environ["MAIL_FROM"])[1]
    recipients = list(dict.fromkeys(a for a in [*admin_emails, extra] if a))

    def worker():
        for address in recipients:
            try:
                send_email(address, subject, body)
            except Exception as exc:  # noqa: BLE001
                print(f"[mailer] Failed to notify admin {address}: {exc}")

    threading.Thread(target=worker, daemon=True).start()


def notify_admins_password_request(admin_emails, username, user_email):
    notify_admins(
        admin_emails,
        "EquipTrack: password change request needs approval",
        f"User '{username}' ({user_email}) requested a password change.\n"
        "Sign in to EquipTrack and open Settings to approve or reject the request.",
    )


def notify_admins_borrow_request(admin_emails, username, item_name, quantity, student_id):
    notify_admins(
        admin_emails,
        "EquipTrack: new borrow request",
        f"User '{username}'"
        + (f" (student ID {student_id})" if student_id else "")
        + f" requested to borrow {quantity} unit(s) of {item_name}.\n"
        "Sign in to EquipTrack and open the dashboard to approve or reject the request.",
    )


def notify_admins_account_action(admin_emails, acting_admin, target_username, action):
    notify_admins(
        admin_emails,
        f"EquipTrack: account {action}",
        f"Admin '{acting_admin}' {action} for account '{target_username}'.\n"
        "If this was not you or someone you trust, review the audit log in EquipTrack.",
    )


def send_otp(to_address, code, minutes):
    """Send an OTP. Returns True if emailed; False if SMTP is not configured
    (the code is printed to the server console for local development)."""
    if not is_configured():
        print(f"[mailer] Brevo SMTP not configured. OTP for {to_address}: {code}")
        return False
    send_email(
        to_address,
        "Your EquipTrack verification code",
        f"Your EquipTrack verification code is {code}.\n"
        f"It expires in {minutes} minutes. If you did not request it, ignore this email.",
    )
    return True
