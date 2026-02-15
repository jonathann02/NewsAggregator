from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.db.models import Article, PipelineState
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


YOUTUBE_MIN_DELAY_SECONDS = 1.5
YOUTUBE_MAX_JITTER_SECONDS = 0.5
YOUTUBE_BLOCK_COOLDOWN_HOURS = 6
YOUTUBE_BLOCK_MARKER = "youtube ip blocked"
TRANSCRIPT_UNAVAILABLE_MARKER = "transcript is not available"


def enrich_youtube_articles(session: Session, lookback_hours: int, max_items: int | None = None) -> int:
    blocked_until = _get_youtube_blocked_until(session)
    if blocked_until and blocked_until > datetime.now(timezone.utc):
        return 0

    scraper = YouTubeSurfaceScraper()
    items = _select_missing_content(session, "youtube", lookback_hours, max_items)
    items = [item for item in items if item.content_error != TRANSCRIPT_UNAVAILABLE_MARKER]
    updated = 0
    for article in items:
        try:
            if not article.video_id:
                article.video_id = scraper.extract_video_id(article.url)

            if not article.video_id:
                raise ValueError("Unable to extract video_id from URL.")

            transcript, error = scraper.get_video_transcript(article.video_id, ["en", "en-US"])
            if error:
                if _is_youtube_blocked_error(error):
                    article.content_error = YOUTUBE_BLOCK_MARKER
                    article.content_fetched_at = datetime.now(timezone.utc)
                    _set_youtube_blocked_until(session)
                    updated += 1
                    break
                article.content_error = _normalize_transcript_error(error)
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
        finally:
            _sleep_between_youtube_calls()
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


def _normalize_transcript_error(error: str) -> str:
    lower = error.lower()
    if "no transcripts were found" in lower:
        return TRANSCRIPT_UNAVAILABLE_MARKER
    if "transcriptsdisabled" in lower:
        return TRANSCRIPT_UNAVAILABLE_MARKER
    if "could not retrieve a transcript" in lower:
        return TRANSCRIPT_UNAVAILABLE_MARKER
    return error


def _is_youtube_blocked_error(error: str) -> bool:
    lower = error.lower()
    return "blocking requests from your ip" in lower or "ip has been blocked" in lower


def _sleep_between_youtube_calls() -> None:
    delay = YOUTUBE_MIN_DELAY_SECONDS + random.uniform(0, YOUTUBE_MAX_JITTER_SECONDS)
    time.sleep(delay)


def _get_youtube_blocked_until(session: Session) -> datetime | None:
    record = session.get(PipelineState, "youtube_blocked_until")
    if not record:
        return None
    try:
        return datetime.fromisoformat(record.value)
    except ValueError:
        return None


def _set_youtube_blocked_until(session: Session) -> None:
    blocked_until = datetime.now(timezone.utc) + timedelta(hours=YOUTUBE_BLOCK_COOLDOWN_HOURS)
    record = session.get(PipelineState, "youtube_blocked_until")
    if record:
        record.value = blocked_until.isoformat()
    else:
        session.add(PipelineState(key="youtube_blocked_until", value=blocked_until.isoformat()))
