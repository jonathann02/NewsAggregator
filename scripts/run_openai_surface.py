from __future__ import annotations

import argparse
import json
import sys

from app.ingest.openai import (
    DEFAULT_OPENAI_RSS_URL,
    collect_recent_openai_articles,
    serialize_openai_articles,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch OpenAI news articles from RSS and filter by a lookback window."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only return articles published in the last N hours.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Optional hard cap on number of returned articles.",
    )
    parser.add_argument(
        "--rss-url",
        default=DEFAULT_OPENAI_RSS_URL,
        help="RSS URL to parse (defaults to OpenAI news RSS).",
    )
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    articles = collect_recent_openai_articles(
        lookback_hours=args.hours,
        max_articles=args.max_articles,
        rss_url=args.rss_url,
    )

    print(f"Articles found in last {args.hours}h: {len(articles)}")
    print(json.dumps(serialize_openai_articles(articles), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

