from __future__ import annotations

from html import escape

from app.digest.email import DailyDigestEmailModel


def render_digest_email_markdown(digest: DailyDigestEmailModel) -> str:
    lines: list[str] = []
    lines.append(f"# {digest.subject}")
    lines.append("")
    lines.append("## Greeting")
    lines.append(digest.greeting.strip())
    lines.append("")
    lines.append("## Overview")
    lines.append(digest.introduction.strip())
    lines.append("")
    lines.append(f"## Top {len(digest.items)} Ranked Articles")
    lines.append("")

    if not digest.items:
        lines.append("No items were available for this digest window.")
    else:
        for item in digest.items:
            lines.append(f"### {item.rank}. {item.digest_title}")
            lines.append(f"- Source: `{item.source_type}`")
            lines.append(f"- Score: `{item.score}`")
            lines.append(f"- Link: {item.article_url}")
            lines.append("")
            lines.append(item.digest_summary.strip())
            lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_digest_email_text(digest: DailyDigestEmailModel) -> str:
    return render_digest_email_markdown(digest)


def render_digest_email_html(digest: DailyDigestEmailModel) -> str:
    greeting = escape(digest.greeting.strip())
    intro = escape(digest.introduction.strip())

    item_html = []
    for item in digest.items:
        item_html.append(
            "\n".join(
                [
                    "<li style=\"margin-bottom:16px;\">",
                    f"<h4 style=\"margin:0;\">{item.rank}. {escape(item.digest_title)}</h4>",
                    f"<div style=\"margin-top:6px; color:#555;\">Source: {escape(item.source_type)} | Score: {item.score}</div>",
                    f"<div style=\"margin-top:6px; line-height:1.5;\">{escape(item.digest_summary)}</div>",
                    f"<div style=\"margin-top:6px;\"><a href=\"{escape(item.article_url)}\">Read original source</a></div>",
                    "</li>",
                ]
            )
        )

    items_section = "\n".join(item_html) if item_html else "<p>No items were available for this digest window.</p>"

    return (
        "<!doctype html>"
        "<html>"
        "<body style=\"font-family:Arial,sans-serif; color:#111;\">"
        f"<h2 style=\"margin-bottom:8px;\">{escape(digest.subject)}</h2>"
        "<h3 style=\"margin-bottom:8px;\">Greeting</h3>"
        f"<p>{greeting}</p>"
        "<h3 style=\"margin-bottom:8px;\">Overview</h3>"
        f"<p>{intro}</p>"
        f"<h3 style=\"margin-bottom:12px;\">Top {len(digest.items)} Ranked Articles</h3>"
        f"<ol style=\"padding-left:20px;\">{items_section}</ol>"
        "</body>"
        "</html>"
    )
