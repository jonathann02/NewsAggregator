from __future__ import annotations

import argparse

from app.ingest.enrich import run_enrich


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill missing markdown/transcripts into articles."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only enrich content for items published in the last N hours.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Optional cap for total items per source.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_enrich(lookback_hours=args.hours, max_items=args.max_items)
    print(f"Updated items: {result['updated']}")


if __name__ == "__main__":
    main()
