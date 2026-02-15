from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and send the daily ranked digest email."
    )
    parser.add_argument("--hours", type=int, default=24, help="Lookback window for digest items.")
    parser.add_argument(
        "--max-items",
        type=int,
        default=100,
        help="Maximum digest candidates before ranking and selecting top items.",
    )
    parser.add_argument("--top-n", type=int, default=10, help="Top ranked items to include in the email.")
    parser.add_argument(
        "--recipient-name",
        default="Dave",
        help="Name used in the intro paragraph.",
    )
    parser.add_argument(
        "--to-email",
        default=None,
        help="Recipient email address. Defaults to DIGEST_RECIPIENT env var.",
    )
    parser.add_argument(
        "--ranking-model",
        default="gpt-5.1",
        help="Model used by Assignment Editor ranking step.",
    )
    parser.add_argument(
        "--email-model",
        default="gpt-5.1",
        help="Model used for the email intro generation step.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and render email but do not send. Prints subject and markdown body.",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Send plain text only (skip HTML alternative).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from app.digest.email import run_build_digest_email
    from app.email.render import render_digest_email_markdown
    from app.email.send import send_digest_email

    digest_email = run_build_digest_email(
        lookback_hours=args.hours,
        ranking_max_items=args.max_items,
        top_n=args.top_n,
        recipient_name=args.recipient_name,
        ranking_model=args.ranking_model,
        email_model=args.email_model,
    )

    if args.dry_run:
        print(f"Subject: {digest_email.subject}")
        print("")
        print(render_digest_email_markdown(digest_email))
        return

    result = send_digest_email(
        digest_email,
        to_email=args.to_email,
        include_html=not args.text_only,
    )
    print(
        "Sent digest email to {to_email} with {item_count} items.".format(
            to_email=result["to_email"],
            item_count=result["item_count"],
        )
    )


if __name__ == "__main__":
    main()
