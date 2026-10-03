"""Brevo SMTP email delivery for one-time passcodes (OTPs)."""

import os
import smtplib
import ssl
from email.message import EmailMessage

BREVO_HOST = "smtp-relay.brevo.com"
BREVO_PORT = 587


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
