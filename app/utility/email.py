import asyncio
import logging
import smtplib
import ssl
from collections.abc import Sequence
from email.message import EmailMessage

from app.config import email_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when Google SMTP cannot deliver a message."""


async def send_email(
    receiver: str | Sequence[str],
    content: str,
    subject: str,
    *,
    html_content: str | None = None,
) -> None:
    """Send an email through the Google SMTP account in config.

    ``receiver`` is one address or a list of addresses. ``content`` is the
    plain-text body. ``html_content`` is an optional HTML alternative.
    """
    if not email_settings.is_configured:
        raise EmailSendError("SMTP is not configured")

    receivers = _normalize_receivers(receiver)
    body = content.strip()
    html = html_content.strip() if html_content else None
    if not body and not html:
        raise ValueError("email content is required")

    message = _build_message(
        receivers=receivers,
        subject=subject.strip(),
        content=body,
        html_content=html,
    )
    await asyncio.to_thread(_deliver, message, receivers)


def _normalize_receivers(receiver: str | Sequence[str]) -> list[str]:
    raw_receivers = [receiver] if isinstance(receiver, str) else list(receiver)
    receivers = [address.strip() for address in raw_receivers if address and address.strip()]
    if not receivers:
        raise ValueError("at least one receiver email is required")
    return receivers


def _build_message(
    *,
    receivers: list[str],
    subject: str,
    content: str,
    html_content: str | None,
) -> EmailMessage:
    if not subject:
        raise ValueError("email subject is required")

    message = EmailMessage()
    message["From"] = f"{email_settings.SMTP_FROM_NAME} <{email_settings.SMTP_EMAIL}>"
    message["To"] = ", ".join(receivers)
    message["Subject"] = subject
    message.set_content(content or " ")
    if html_content:
        message.add_alternative(html_content, subtype="html")
    return message


def _deliver(message: EmailMessage, receivers: list[str]) -> None:
    host = email_settings.SMTP_HOST
    port = email_settings.SMTP_PORT
    timeout = email_settings.SMTP_TIMEOUT_SECONDS
    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
                _login_and_send(server, message, receivers)
            return

        with smtplib.SMTP(host, port, timeout=timeout) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            _login_and_send(server, message, receivers)
    except (smtplib.SMTPException, OSError) as exc:
        logger.exception("failed to send email to %s", ", ".join(receivers))
        raise EmailSendError("failed to send email") from exc


def _login_and_send(
    server: smtplib.SMTP,
    message: EmailMessage,
    receivers: list[str],
) -> None:
    server.login(email_settings.SMTP_EMAIL, email_settings.SMTP_PASSWORD)
    server.send_message(message, to_addrs=receivers)
