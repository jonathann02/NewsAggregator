from __future__ import annotations

import argparse

from app.ingest.pipeline import run_ingest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the ingestion pipeline for YouTube, OpenAI, and Anthropic."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only ingest content published in the last N hours.",
    )
    parser.add_argument(
        "--fetch-markdown",
        action="store_true",
        help="Use Docling to fetch full markdown content for OpenAI and Anthropic articles.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_ingest(
        lookback_hours=args.hours,
        fetch_markdown=args.fetch_markdown,
    )
    print(f"Inserted articles: {result['inserted']}")


if __name__ == "__main__":
    main()

