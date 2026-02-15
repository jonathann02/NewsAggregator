from __future__ import annotations

import argparse
import json

from app.digest.rank import RANK_MODEL, run_rank_digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank digest items from the last N hours against a user profile."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only rank digest items created in the last N hours.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=100,
        help="Maximum number of digest items to rank.",
    )
    parser.add_argument(
        "--model",
        default=RANK_MODEL,
        help="OpenAI model used for ranking.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_rank_digest(
        lookback_hours=args.hours,
        max_items=args.max_items,
        model=args.model,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
