from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from openai import OpenAI
from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.db.models import Article, DigestItem

DIGEST_MODEL = "gpt-5.1-instant"
DEFAULT_MAX_INPUT_CHARS = 12000
AGENT_INSTRUCTIONS_PATH = Path("app/agent/digest_instructions.txt")


def run_process_digest(max_items: int | None = None, model: str = DIGEST_MODEL) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    init_db()
    client = OpenAI(api_key=api_key)
    instructions = _load_agent_instructions()

    session = SessionLocal()
    try:
        articles = _select_articles_missing_digest(session, max_items=max_items)
        created = 0
        skipped = 0
        errors = 0

        for article in articles:
            try:
                digest = _summarize_article(
                    client=client,
                    model=model,
                    instructions=instructions,
                    article=article,
                )
                session.add(
                    DigestItem(
                        article_id=article.id,
                        article_url=article.url,
                        digest_title=digest["digest_title"],
                        digest_summary=digest["digest_summary"],
                        model=model,
                    )
                )
                created += 1
            except Exception:
                errors += 1

        session.commit()
        return {
            "processed": len(articles),
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _select_articles_missing_digest(session, max_items: int | None = None) -> list[Article]:
    stmt = (
        select(Article)
        .where(~Article.id.in_(select(DigestItem.article_id)))
        .order_by(Article.published_at.desc())
    )
    if max_items is not None:
        stmt = stmt.limit(max_items)
    return list(session.scalars(stmt))


def _summarize_article(client: OpenAI, model: str, instructions: str, article: Article) -> dict[str, str]:
    content = _build_article_input(article)
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=content,
        text={
            "format": {
                "type": "json_schema",
                "name": "digest_item",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "digest_title": {"type": "string"},
                        "digest_summary": {"type": "string"},
                    },
                    "required": ["digest_title", "digest_summary"],
                    "additionalProperties": False,
                },
            }
        },
    )

    output_text = _extract_output_text(response)
    parsed = json.loads(output_text)
    title = str(parsed["digest_title"]).strip()
    summary = str(parsed["digest_summary"]).strip()
    if not title or not summary:
        raise ValueError("Digest output missing required fields.")
    return {"digest_title": title, "digest_summary": summary}


def _extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)
    if not chunks:
        raise ValueError("No text output returned from Responses API.")
    return "".join(chunks)


def _build_article_input(article: Article) -> str:
    raw_content = (article.raw_content or "").strip()
    if len(raw_content) > DEFAULT_MAX_INPUT_CHARS:
        raw_content = raw_content[:DEFAULT_MAX_INPUT_CHARS]

    return (
        "Summarize this article into a digest item.\n\n"
        f"Source type: {article.source_type}\n"
        f"Source: {article.source}\n"
        f"Published at: {article.published_at.isoformat() if article.published_at else ''}\n"
        f"Article title: {article.title}\n"
        f"Article URL: {article.url}\n"
        f"Existing summary: {article.summary or ''}\n"
        "Article content:\n"
        f"{raw_content}\n"
    )


def _load_agent_instructions() -> str:
    if not AGENT_INSTRUCTIONS_PATH.exists():
        raise RuntimeError(f"Agent instructions file missing: {AGENT_INSTRUCTIONS_PATH}")
    return AGENT_INSTRUCTIONS_PATH.read_text(encoding="utf-8")
