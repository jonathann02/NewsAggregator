from __future__ import annotations

import argparse
import json

from app.digest.email import EMAIL_MODEL, run_build_digest_email
from app.digest.rank import RANK_MODEL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a ranked digest email payload from recent digest items."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only include digest items created in the last N hours.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=100,
        help="Maximum number of digest items to rank before selecting top items.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top ranked items to include in the email payload.",
    )
    parser.add_argument(
        "--recipient-name",
        default="Dave",
        help="Name used in the email introduction.",
    )
    parser.add_argument(
        "--ranking-model",
        default=RANK_MODEL,
        help="OpenAI model used by the Assignment Editor ranking step.",
    )
    parser.add_argument(
        "--email-model",
        default=EMAIL_MODEL,
        help="OpenAI model used for email intro generation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_build_digest_email(
        lookback_hours=args.hours,
        ranking_max_items=args.max_items,
        top_n=args.top_n,
        recipient_name=args.recipient_name,
        ranking_model=args.ranking_model,
        email_model=args.email_model,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
