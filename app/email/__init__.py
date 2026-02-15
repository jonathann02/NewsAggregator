"""Email rendering and delivery utilities."""

from app.email.render import render_digest_email_html, render_digest_email_markdown, render_digest_email_text
from app.email.send import SMTPSettings, send_digest_email

__all__ = [
    "SMTPSettings",
    "send_digest_email",
    "render_digest_email_text",
    "render_digest_email_markdown",
    "render_digest_email_html",
]
