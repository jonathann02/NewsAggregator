from __future__ import annotations

from html import escape

from app.digest.email import DailyDigestEmailModel


def render_digest_email_markdown(digest: DailyDigestEmailModel) -> str:
    lines: list[str] = []
    lines.append(f"# {digest.subject}")
    lines.append("")
    lines.append(digest.greeting.strip())
    lines.append("")
    lines.append("## Your Daily AI Brief")
    lines.append(digest.introduction.strip())
    lines.append("")
    lines.append("## Today's Top Stories")
    lines.append("")

    if not digest.items:
        lines.append("No items were available for this digest window.")
    else:
        for item in digest.items:
            lines.append(f"### {item.digest_title}")
            lines.append(f"*{item.source_type.title()} | Relevance score: {item.score}/100*")
            lines.append("")
            lines.append(item.digest_summary.strip())
            lines.append("")
            lines.append(f"[Read more]({item.article_url})")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_digest_email_text(digest: DailyDigestEmailModel) -> str:
    return render_digest_email_markdown(digest)


def render_digest_email_html(digest: DailyDigestEmailModel) -> str:
    greeting = escape(digest.greeting.strip())
    intro = escape(digest.introduction.strip())

    cards_html: list[str] = []
    for item in digest.items:
        cards_html.append(
            "\n".join(
                [
                    "<article style=\"border:1px solid #e6e8eb; border-radius:10px; padding:16px; margin-bottom:12px;\">",
                    f"<h3 style=\"margin:0 0 8px 0; font-size:18px; line-height:1.3;\">{escape(item.digest_title)}</h3>",
                    f"<div style=\"margin-bottom:10px; color:#5f6368; font-size:13px;\">{escape(item.source_type.title())} | Relevance score: {item.score}/100</div>",
                    f"<p style=\"margin:0 0 12px 0; line-height:1.55; color:#202124;\">{escape(item.digest_summary)}</p>",
                    f"<a href=\"{escape(item.article_url)}\" style=\"color:#0b57d0; text-decoration:none; font-weight:600;\">Read more</a>",
                    "</article>",
                ]
            )
        )

    items_section = "\n".join(cards_html) if cards_html else "<p style=\"color:#5f6368;\">No items were available for this digest window.</p>"

    return (
        "<!doctype html>"
        "<html>"
        "<body style=\"margin:0; background:#f7f8fa; font-family:Arial,sans-serif; color:#111;\">"
        "<div style=\"max-width:720px; margin:0 auto; padding:24px 16px;\">"
        "<div style=\"background:#ffffff; border:1px solid #e6e8eb; border-radius:12px; padding:22px;\">"
        f"<h1 style=\"margin:0 0 10px 0; font-size:26px; line-height:1.25;\">{escape(digest.subject)}</h1>"
        f"<p style=\"margin:0 0 12px 0; color:#202124;\">{greeting}</p>"
        "<h2 style=\"margin:0 0 10px 0; font-size:18px;\">Your Daily AI Brief</h2>"
        f"<p style=\"margin:0 0 18px 0; line-height:1.6; color:#202124;\">{intro}</p>"
        "<h2 style=\"margin:0 0 12px 0; font-size:18px;\">Today's Top Stories</h2>"
        f"{items_section}"
        "</div>"
        "</div>"
        "</body>"
        "</html>"
    )
