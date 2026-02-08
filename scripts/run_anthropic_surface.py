from __future__ import annotations

import argparse
import json
import sys

from app.ingest.anthropic import (
    DEFAULT_ANTHROPIC_FEEDS,
    AnthropicScraper,
    collect_recent_anthropic_articles,
    serialize_anthropic_articles,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch Anthropic articles from multiple RSS feeds and filter by a lookback window."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only return articles published in the last N hours.",
    )
    parser.add_argument(
        "--max-per-feed",
        type=int,
        default=None,
        help="Optional hard cap on number of returned articles per feed.",
    )
    parser.add_argument(
        "--feed-urls",
        nargs="*",
        default=DEFAULT_ANTHROPIC_FEEDS,
        help="Override feed URLs (space-separated).",
    )
    parser.add_argument(
        "--markdown-url",
        default=None,
        help="Optional URL to fetch and export as markdown via Docling.",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.markdown_url:
        scraper = AnthropicScraper(feed_urls=args.feed_urls)
        markdown = scraper.fetch_article_markdown(args.markdown_url)
        print(markdown)
        return

    articles = collect_recent_anthropic_articles(
        lookback_hours=args.hours,
        max_articles_per_feed=args.max_per_feed,
        feed_urls=args.feed_urls,
    )

    print(f"Articles found in last {args.hours}h: {len(articles)}")
    print(json.dumps(serialize_anthropic_articles(articles), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
