from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, init_db
from app.ingest.anthropic import AnthropicScraper
from app.ingest.openai import OpenAINewsScraper
from app.ingest.youtube import YouTubeSurfaceScraper
from app.models import Article, YoutubeChannel


def run_ingest(
    lookback_hours: int = 24,
    fetch_markdown: bool = False,
) -> dict:
    init_db()
    session = SessionLocal()
    try:
        inserted = 0

        inserted += ingest_youtube(session, lookback_hours)
        inserted += ingest_openai(session, lookback_hours, fetch_markdown=fetch_markdown)
        inserted += ingest_anthropic(session, lookback_hours, fetch_markdown=fetch_markdown)

        session.commit()
        return {"inserted": inserted}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ingest_youtube(session: Session, lookback_hours: int) -> int:
    channels = session.scalars(select(YoutubeChannel).where(YoutubeChannel.active.is_(True))).all()
    if not channels:
        return 0

    scraper = YouTubeSurfaceScraper()
    results = scraper.collect_latest_videos(
        channel_inputs=[channel.channel_input for channel in channels],
        lookback_hours=lookback_hours,
        include_transcripts=True,
    )

    inserted = 0
    for result in results:
        for video in result.videos:
            inserted += upsert_article(
                session,
                source_type="youtube",
                source=video.channel_id,
                title=video.title,
                url=video.url,
                published_at=video.published_at,
                summary=None,
                raw_content=video.transcript.text if video.transcript else None,
            )
    return inserted


def ingest_openai(session: Session, lookback_hours: int, fetch_markdown: bool) -> int:
    scraper = OpenAINewsScraper()
    articles = scraper.collect_recent_articles(lookback_hours=lookback_hours)
    inserted = 0

    for article in articles:
        raw_content = None
        if fetch_markdown:
            raw_content = scraper.fetch_article_markdown(article.url)

        inserted += upsert_article(
            session,
            source_type="openai",
            source="openai_news",
            title=article.title,
            url=article.url,
            published_at=article.published_at,
            summary=article.summary,
            raw_content=raw_content,
        )
    return inserted


def ingest_anthropic(session: Session, lookback_hours: int, fetch_markdown: bool) -> int:
    scraper = AnthropicScraper()
    articles = scraper.collect_recent_articles(lookback_hours=lookback_hours)
    inserted = 0

    for article in articles:
        raw_content = None
        if fetch_markdown:
            raw_content = scraper.fetch_article_markdown(article.url)

        inserted += upsert_article(
            session,
            source_type="anthropic",
            source=article.feed_url or "anthropic",
            title=article.title,
            url=article.url,
            published_at=article.published_at,
            summary=article.summary,
            raw_content=raw_content,
        )
    return inserted


def upsert_article(
    session: Session,
    *,
    source_type: str,
    source: str,
    title: str,
    url: str,
    published_at,
    summary: str | None,
    raw_content: str | None,
) -> int:
    existing = session.scalar(select(Article).where(Article.url == url))
    if existing:
        return 0

    session.add(
        Article(
            source_type=source_type,
            source=source,
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
            raw_content=raw_content,
        )
    )
    return 1
