from __future__ import annotations

import argparse

from app.digest.process import DIGEST_MODEL, run_process_digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process article digest items from DB using OpenAI Responses API."
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Optional cap for number of articles to process.",
    )
    parser.add_argument(
        "--model",
        default=DIGEST_MODEL,
        help="OpenAI model for digest generation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_process_digest(max_items=args.max_items, model=args.model)
    print(
        "Processed: {processed}, Created: {created}, Errors: {errors}".format(
            processed=result["processed"],
            created=result["created"],
            errors=result["errors"],
        )
    )
    if result["errors"]:
        print("First errors:")
        for item in result["error_details"][:5]:
            print(f"- article_id={item['article_id']} error={item['error']}")


if __name__ == "__main__":
    main()
