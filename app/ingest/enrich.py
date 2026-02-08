from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.db.models import Article
from app.ingest.anthropic import AnthropicScraper
from app.ingest.openai import OpenAINewsScraper
from app.ingest.youtube import YouTubeSurfaceScraper


def run_enrich(lookback_hours: int = 24, max_items: int | None = None) -> dict:
    init_db()
    session = SessionLocal()
    try:
        updated = 0
        updated += enrich_openai_articles(session, lookback_hours, max_items=max_items)
        updated += enrich_anthropic_articles(session, lookback_hours, max_items=max_items)
        updated += enrich_youtube_articles(session, lookback_hours, max_items=max_items)
        session.commit()
        return {"updated": updated}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def enrich_openai_articles(session: Session, lookback_hours: int, max_items: int | None = None) -> int:
    scraper = OpenAINewsScraper()
    items = _select_missing_content(session, "openai", lookback_hours, max_items)
    return _enrich_markdown(session, items, scraper.fetch_article_markdown, content_type="markdown")


def enrich_anthropic_articles(session: Session, lookback_hours: int, max_items: int | None = None) -> int:
    scraper = AnthropicScraper()
    items = _select_missing_content(session, "anthropic", lookback_hours, max_items)
    return _enrich_markdown(session, items, scraper.fetch_article_markdown, content_type="markdown")


def enrich_youtube_articles(session: Session, lookback_hours: int, max_items: int | None = None) -> int:
    scraper = YouTubeSurfaceScraper()
    items = _select_missing_content(session, "youtube", lookback_hours, max_items)
    updated = 0
    for article in items:
        try:
            if not article.video_id:
                article.video_id = scraper.extract_video_id(article.url)

            if not article.video_id:
                raise ValueError("Unable to extract video_id from URL.")

            transcript, error = scraper.get_video_transcript(article.video_id, ["en", "en-US"])
            if error:
                article.content_error = error
            else:
                article.raw_content = transcript.text if transcript else None
                article.content_type = "transcript"
                article.content_error = None

            article.content_fetched_at = datetime.now(timezone.utc)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            article.content_error = str(exc)
            article.content_fetched_at = datetime.now(timezone.utc)
            updated += 1
    return updated


def _select_missing_content(
    session: Session,
    source_type: str,
    lookback_hours: int,
    max_items: int | None,
) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    stmt = (
        select(Article)
        .where(Article.source_type == source_type)
        .where(Article.raw_content.is_(None))
        .where(Article.published_at >= cutoff)
        .order_by(Article.published_at.desc())
    )
    if max_items:
        stmt = stmt.limit(max_items)
    return list(session.scalars(stmt))


def _enrich_markdown(
    session: Session,
    items: list[Article],
    fetch_fn,
    *,
    content_type: str,
) -> int:
    updated = 0
    for article in items:
        try:
            article.raw_content = fetch_fn(article.url)
            article.content_type = content_type
            article.content_error = None
            article.content_fetched_at = datetime.now(timezone.utc)
            updated += 1
        except Exception as exc:  # noqa: BLE001
            article.content_error = str(exc)
            article.content_fetched_at = datetime.now(timezone.utc)
            updated += 1
    return updated
