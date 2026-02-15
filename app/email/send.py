from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import os
import smtplib

from app.digest.email import DailyDigestEmailModel
from app.email.render import render_digest_email_html, render_digest_email_text


@dataclass
class SMTPSettings:
    host: str
    port: int
    from_email: str
    use_tls: bool = True
    username: str | None = None
    password: str | None = None

    @classmethod
    def from_env(cls) -> "SMTPSettings":
        host = os.getenv("EMAIL_HOST", "").strip()
        port_raw = os.getenv("EMAIL_PORT", "587").strip() or "587"
        from_email = os.getenv("EMAIL_FROM", "").strip()
        username = os.getenv("EMAIL_USERNAME", "").strip() or None
        password = os.getenv("EMAIL_PASSWORD", "").strip() or None
        use_tls = _parse_bool(os.getenv("EMAIL_USE_TLS", "true"))

        if not host:
            raise RuntimeError("EMAIL_HOST is not set.")
        if not from_email:
            raise RuntimeError("EMAIL_FROM is not set.")

        try:
            port = int(port_raw)
        except ValueError as exc:
            raise RuntimeError("EMAIL_PORT must be an integer.") from exc

        if (username and not password) or (password and not username):
            raise RuntimeError("EMAIL_USERNAME and EMAIL_PASSWORD must be set together.")

        return cls(
            host=host,
            port=port,
            from_email=from_email,
            use_tls=use_tls,
            username=username,
            password=password,
        )


def send_digest_email(
    digest: DailyDigestEmailModel,
    *,
    to_email: str | None = None,
    settings: SMTPSettings | None = None,
    include_html: bool = True,
) -> dict[str, str | int]:
    resolved_to_email = (to_email or os.getenv("DIGEST_RECIPIENT", "")).strip()
    if not resolved_to_email:
        raise RuntimeError("DIGEST_RECIPIENT is not set. Pass --to-email or set DIGEST_RECIPIENT.")

    smtp_settings = settings or SMTPSettings.from_env()

    message = EmailMessage()
    message["Subject"] = digest.subject
    message["From"] = smtp_settings.from_email
    message["To"] = resolved_to_email

    text_body = render_digest_email_text(digest)
    message.set_content(text_body)

    if include_html:
        html_body = render_digest_email_html(digest)
        message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(smtp_settings.host, smtp_settings.port, timeout=30) as smtp:
        smtp.ehlo()
        if smtp_settings.use_tls:
            smtp.starttls()
            smtp.ehlo()
        if smtp_settings.username and smtp_settings.password:
            smtp.login(smtp_settings.username, smtp_settings.password)
        smtp.send_message(message)

    return {
        "to_email": resolved_to_email,
        "subject": digest.subject,
        "item_count": len(digest.items),
    }


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
