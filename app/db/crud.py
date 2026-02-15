from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Article, DigestItem, YoutubeChannel


def create_youtube_channel(session: Session, channel_input: str, active: bool = True) -> YoutubeChannel:
    existing = session.scalar(select(YoutubeChannel).where(YoutubeChannel.channel_input == channel_input))
    if existing:
        return existing

    channel = YoutubeChannel(channel_input=channel_input, active=active)
    session.add(channel)
    session.flush()
    return channel


def list_youtube_channels(session: Session, active_only: bool = False) -> list[YoutubeChannel]:
    stmt = select(YoutubeChannel)
    if active_only:
        stmt = stmt.where(YoutubeChannel.active.is_(True))
    return list(session.scalars(stmt))


def set_youtube_channel_active(session: Session, channel_input: str, active: bool) -> YoutubeChannel | None:
    channel = session.scalar(select(YoutubeChannel).where(YoutubeChannel.channel_input == channel_input))
    if not channel:
        return None
    channel.active = active
    session.flush()
    return channel


def delete_youtube_channel(session: Session, channel_input: str) -> int:
    result = session.execute(delete(YoutubeChannel).where(YoutubeChannel.channel_input == channel_input))
    return result.rowcount or 0


def create_article(
    session: Session,
    *,
    source_type: str,
    source: str,
    title: str,
    url: str,
    video_id: str | None = None,
    published_at,
    summary: str | None = None,
    raw_content: str | None = None,
) -> Article:
    existing = session.scalar(select(Article).where(Article.url == url))
    if not existing and source_type == "youtube" and video_id:
        existing = session.scalar(
            select(Article).where(Article.source_type == "youtube", Article.video_id == video_id)
        )
    if existing:
        return existing

    article = Article(
        source_type=source_type,
        source=source,
        title=title,
        url=url,
        video_id=video_id,
        published_at=published_at,
        summary=summary,
        raw_content=raw_content,
    )
    session.add(article)
    session.flush()
    return article


def get_article_by_url(session: Session, url: str) -> Article | None:
    return session.scalar(select(Article).where(Article.url == url))


def list_articles(session: Session, source_type: str | None = None, limit: int = 50) -> list[Article]:
    stmt = select(Article)
    if source_type:
        stmt = stmt.where(Article.source_type == source_type)
    stmt = stmt.order_by(Article.published_at.desc()).limit(limit)
    return list(session.scalars(stmt))


def delete_article(session: Session, url: str) -> int:
    result = session.execute(delete(Article).where(Article.url == url))
    return result.rowcount or 0


def create_digest_item(
    session: Session,
    *,
    article_id: int,
    article_url: str,
    digest_title: str,
    digest_summary: str,
    model: str,
) -> DigestItem:
    existing = session.scalar(select(DigestItem).where(DigestItem.article_id == article_id))
    if existing:
        return existing

    item = DigestItem(
        article_id=article_id,
        article_url=article_url,
        digest_title=digest_title,
        digest_summary=digest_summary,
        model=model,
    )
    session.add(item)
    session.flush()
    return item


def list_digest_items(session: Session, limit: int = 100) -> list[DigestItem]:
    stmt = select(DigestItem).order_by(DigestItem.created_at.desc()).limit(limit)
    return list(session.scalars(stmt))
