from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

import feedparser
import requests
from dateutil import parser as date_parser
from pydantic import BaseModel, Field
from docling.document_converter import DocumentConverter

DEFAULT_ANTHROPIC_FEEDS = [
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
]


class AnthropicArticleModel(BaseModel):
    title: str
    url: str
    published_at: datetime
    summary: str | None = None
    guid: str | None = None
    categories: list[str] = Field(default_factory=list)
    feed_url: str | None = None


class AnthropicScraper:
    def __init__(
        self,
        feed_urls: Sequence[str] = DEFAULT_ANTHROPIC_FEEDS,
        request_timeout_seconds: int = 15,
    ) -> None:
        self.feed_urls = list(feed_urls)
        self.request_timeout_seconds = request_timeout_seconds

    def fetch_feed(self, feed_url: str) -> feedparser.FeedParserDict:
        response = requests.get(feed_url, timeout=self.request_timeout_seconds)
        response.raise_for_status()
        return feedparser.parse(response.content)

    def collect_recent_articles(
        self,
        lookback_hours: int = 24,
        max_articles_per_feed: int | None = None,
    ) -> list[AnthropicArticleModel]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        articles: list[AnthropicArticleModel] = []

        for feed_url in self.feed_urls:
            feed = self.fetch_feed(feed_url)
            per_feed_count = 0

            for entry in feed.entries:
                published_at = self.parse_entry_datetime(entry)
                if published_at is None or published_at < cutoff:
                    continue

                category_terms = [tag.term for tag in entry.get("tags", []) if getattr(tag, "term", None)]
                article = AnthropicArticleModel(
                    title=(entry.get("title") or "").strip(),
                    url=(entry.get("link") or "").strip(),
                    published_at=published_at,
                    summary=(entry.get("description") or "").strip() or None,
                    guid=(entry.get("id") or entry.get("guid") or "").strip() or None,
                    categories=category_terms,
                    feed_url=feed_url,
                )
                articles.append(article)
                per_feed_count += 1

                if max_articles_per_feed is not None and per_feed_count >= max_articles_per_feed:
                    break

        return articles

    def fetch_article_markdown(self, url: str) -> str:
        converter = DocumentConverter()
        result = converter.convert(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        return result.document.export_to_markdown()

    @staticmethod
    def parse_entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
        published = entry.get("published") or entry.get("updated")
        if not published:
            return None

        dt = date_parser.parse(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


DEFAULT_ANTHROPIC_SCRAPER = AnthropicScraper()


def collect_recent_anthropic_articles(
    lookback_hours: int = 24,
    max_articles_per_feed: int | None = None,
    feed_urls: Sequence[str] = DEFAULT_ANTHROPIC_FEEDS,
    request_timeout_seconds: int = 15,
) -> list[AnthropicArticleModel]:
    scraper = (
        DEFAULT_ANTHROPIC_SCRAPER
        if list(feed_urls) == DEFAULT_ANTHROPIC_SCRAPER.feed_urls
        and request_timeout_seconds == DEFAULT_ANTHROPIC_SCRAPER.request_timeout_seconds
        else AnthropicScraper(feed_urls=feed_urls, request_timeout_seconds=request_timeout_seconds)
    )
    return scraper.collect_recent_articles(
        lookback_hours=lookback_hours,
        max_articles_per_feed=max_articles_per_feed,
    )


def serialize_anthropic_articles(articles: Sequence[AnthropicArticleModel]) -> list[dict]:
    return [article.model_dump(mode="json") for article in articles]
