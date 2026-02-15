from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full daily pipeline (ingest, enrich, digest, and send email)."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Lookback window in hours for ingest, enrich, and ranking stages.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=100,
        help="Maximum items per stage where applicable.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Top ranked digest items to include in the outbound email.",
    )
    parser.add_argument(
        "--recipient-name",
        default=os.getenv("DIGEST_RECIPIENT_NAME", "Dave"),
        help="Recipient name used in greeting/intro text.",
    )
    parser.add_argument(
        "--digest-model",
        default=os.getenv("DIGEST_MODEL", "gpt-5.1"),
        help="OpenAI model for digest generation.",
    )
    parser.add_argument(
        "--ranking-model",
        default=os.getenv("RANK_MODEL", "gpt-5.1"),
        help="OpenAI model for ranking digest items.",
    )
    parser.add_argument(
        "--email-model",
        default=os.getenv("EMAIL_MODEL", "gpt-5.1"),
        help="OpenAI model for generating email intro text.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"[daily-pipeline] started_at={started_at}")
    print(
        "[daily-pipeline] config "
        f"hours={args.hours} max_items={args.max_items} top_n={args.top_n} recipient_name={args.recipient_name!r}"
    )

    try:
        from app.digest.email import run_build_digest_email
        from app.digest.process import run_process_digest
        from app.email.send import send_digest_email
        from app.ingest.enrich import run_enrich
        from app.ingest.pipeline import run_ingest

        print("[daily-pipeline] stage=ingest status=running")
        ingest_result = run_ingest(lookback_hours=args.hours, fetch_markdown=False)
        print(
            "[daily-pipeline] stage=ingest status=ok "
            f"inserted_articles={ingest_result['inserted']}"
        )

        print("[daily-pipeline] stage=enrich status=running")
        enrich_result = run_enrich(lookback_hours=args.hours, max_items=args.max_items)
        print(
            "[daily-pipeline] stage=enrich status=ok "
            f"updated_items={enrich_result['updated']}"
        )

        print("[daily-pipeline] stage=process_digest status=running")
        digest_result = run_process_digest(max_items=args.max_items, model=args.digest_model)
        print(
            "[daily-pipeline] stage=process_digest status=ok "
            f"processed={digest_result['processed']} created={digest_result['created']} errors={digest_result['errors']}"
        )
        if digest_result["errors"] > 0:
            raise RuntimeError(
                f"Digest processing returned {digest_result['errors']} errors. "
                "Check logs for error_details and rerun."
            )

        print("[daily-pipeline] stage=build_send_email status=running")
        digest_email = run_build_digest_email(
            lookback_hours=args.hours,
            ranking_max_items=args.max_items,
            top_n=args.top_n,
            recipient_name=args.recipient_name,
            ranking_model=args.ranking_model,
            email_model=args.email_model,
        )
        send_result = send_digest_email(digest_email)
        print(
            "[daily-pipeline] stage=build_send_email status=ok "
            f"to_email={send_result['to_email']} item_count={send_result['item_count']}"
        )

        finished_at = datetime.now(timezone.utc).isoformat()
        print(f"[daily-pipeline] status=completed finished_at={finished_at}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[daily-pipeline] status=failed error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
