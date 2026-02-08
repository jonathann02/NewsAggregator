from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

import feedparser
import requests
from dateutil import parser as date_parser
from pydantic import BaseModel, Field

DEFAULT_OPENAI_RSS_URL = "https://openai.com/news/rss.xml"


class OpenAINewsArticleModel(BaseModel):
    title: str
    url: str
    published_at: datetime
    summary: str | None = None
    guid: str | None = None
    categories: list[str] = Field(default_factory=list)


class OpenAINewsScraper:
    def __init__(self, rss_url: str = DEFAULT_OPENAI_RSS_URL, request_timeout_seconds: int = 15) -> None:
        self.rss_url = rss_url
        self.request_timeout_seconds = request_timeout_seconds

    def fetch_feed(self) -> feedparser.FeedParserDict:
        response = requests.get(self.rss_url, timeout=self.request_timeout_seconds)
        response.raise_for_status()
        return feedparser.parse(response.content)

    def collect_recent_articles(
        self,
        lookback_hours: int = 24,
        max_articles: int | None = None,
    ) -> list[OpenAINewsArticleModel]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        feed = self.fetch_feed()

        articles: list[OpenAINewsArticleModel] = []
        for entry in feed.entries:
            published_at = self.parse_entry_datetime(entry)
            if published_at is None or published_at < cutoff:
                continue

            category_terms = [tag.term for tag in entry.get("tags", []) if getattr(tag, "term", None)]
            article = OpenAINewsArticleModel(
                title=(entry.get("title") or "").strip(),
                url=(entry.get("link") or "").strip(),
                published_at=published_at,
                summary=(entry.get("description") or "").strip() or None,
                guid=(entry.get("id") or entry.get("guid") or "").strip() or None,
                categories=category_terms,
            )
            articles.append(article)

            if max_articles is not None and len(articles) >= max_articles:
                break

        return articles

    @staticmethod
    def parse_entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
        published = entry.get("published") or entry.get("updated")
        if not published:
            return None

        dt = date_parser.parse(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


DEFAULT_OPENAI_SCRAPER = OpenAINewsScraper()


def collect_recent_openai_articles(
    lookback_hours: int = 24,
    max_articles: int | None = None,
    rss_url: str = DEFAULT_OPENAI_RSS_URL,
    request_timeout_seconds: int = 15,
) -> list[OpenAINewsArticleModel]:
    scraper = (
        DEFAULT_OPENAI_SCRAPER
        if rss_url == DEFAULT_OPENAI_SCRAPER.rss_url
        and request_timeout_seconds == DEFAULT_OPENAI_SCRAPER.request_timeout_seconds
        else OpenAINewsScraper(rss_url=rss_url, request_timeout_seconds=request_timeout_seconds)
    )
    return scraper.collect_recent_articles(
        lookback_hours=lookback_hours,
        max_articles=max_articles,
    )


def serialize_openai_articles(articles: Sequence[OpenAINewsArticleModel]) -> list[dict]:
    return [article.model_dump(mode="json") for article in articles]
