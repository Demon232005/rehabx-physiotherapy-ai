"""Outbound email service (SMTP).

Uses the standard library so no extra dependency is required. When SMTP
is not configured (no ``SMTP_HOST``) sending is a graceful no-op that
logs a warning — this keeps local development frictionless while
production only needs environment variables.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import get_settings

logger = logging.getLogger("rehabx.email")

PASSWORD_RESET_SUBJECT = "RehabX AI — password reset request"


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True when handed to an SMTP server.

    Never raises: delivery problems are logged and reported as False so
    callers can decide whether to surface an error to the user.
    """
    settings = get_settings()
    if not settings.smtp_host:
        logger.warning("SMTP not configured (SMTP_HOST empty); skipping email to %s", to)
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.app_name, settings.smtp_from))
    msg["To"] = to

    try:
        if settings.smtp_port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with server:
            server.ehlo()
            if settings.smtp_use_tls and settings.smtp_port != 465:
                server.starttls()
                server.ehlo()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_from, [to], msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_password_reset_email(to: str, reset_token: str) -> bool:
    """Email the password-reset link for ``to``."""
    settings = get_settings()
    reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={reset_token}"
    body = (
        "Hello,\n\n"
        "We received a request to reset your RehabX AI password.\n\n"
        f"Open the link below to choose a new password:\n{reset_url}\n\n"
        "The link expires shortly. If you did not request this, you can "
        "ignore this email and your password will remain unchanged.\n\n"
        "- The RehabX AI team"
    )
    return send_email(to, PASSWORD_RESET_SUBJECT, body)
