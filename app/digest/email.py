from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os

from openai import BadRequestError, OpenAI
from pydantic import BaseModel, Field

from app.digest.rank import (
    DEFAULT_USER_PROFILE,
    RANK_MODEL,
    RankedDigestItemModel,
    UserProfileModel,
    run_rank_digest,
)

EMAIL_MODEL = os.getenv("EMAIL_MODEL", "gpt-5.1")
DEFAULT_RECIPIENT_NAME = "Dave"
EMAIL_EDITOR_INSTRUCTIONS_PATH = Path("app/agent/email_editor_instructions.txt")


class EmailIntroModel(BaseModel):
    subject: str
    greeting: str
    introduction: str


class DigestEmailItemModel(BaseModel):
    rank: int
    digest_item_id: int
    article_id: int
    article_url: str
    source_type: str
    digest_title: str
    digest_summary: str
    score: int = Field(ge=0, le=100)
    reason: str


class DailyDigestEmailModel(BaseModel):
    recipient_name: str
    profile_name: str
    digest_date: str
    ranking_model: str
    email_model: str
    subject: str
    greeting: str
    introduction: str
    items: list[DigestEmailItemModel]


def run_build_digest_email(
    lookback_hours: int = 24,
    ranking_max_items: int | None = 100,
    top_n: int = 10,
    recipient_name: str = DEFAULT_RECIPIENT_NAME,
    ranking_model: str = RANK_MODEL,
    email_model: str = EMAIL_MODEL,
    user_profile: UserProfileModel = DEFAULT_USER_PROFILE,
) -> DailyDigestEmailModel:
    ranking = run_rank_digest(
        lookback_hours=lookback_hours,
        max_items=ranking_max_items,
        model=ranking_model,
        user_profile=user_profile,
    )

    selected_items = ranking.ranked_items[: max(top_n, 0)]
    digest_date = datetime.now(timezone.utc).date().isoformat()

    if selected_items:
        email_intro = _generate_email_intro(
            model=email_model,
            recipient_name=recipient_name,
            digest_date=digest_date,
            profile_name=user_profile.profile_name,
            ranked_items=selected_items,
        )
    else:
        email_intro = EmailIntroModel(
            subject=f"AI Digest - {digest_date}",
            greeting=f"Hey {recipient_name},",
            introduction=(
                f"Here is your daily AI news digest for {digest_date}. "
                "No ranked items were found in the selected window."
            ),
        )

    return DailyDigestEmailModel(
        recipient_name=recipient_name,
        profile_name=user_profile.profile_name,
        digest_date=digest_date,
        ranking_model=ranking_model,
        email_model=email_model,
        subject=email_intro.subject.strip(),
        greeting=email_intro.greeting.strip(),
        introduction=email_intro.introduction.strip(),
        items=[DigestEmailItemModel.model_validate(item.model_dump()) for item in selected_items],
    )


def _generate_email_intro(
    *,
    model: str,
    recipient_name: str,
    digest_date: str,
    profile_name: str,
    ranked_items: list[RankedDigestItemModel],
) -> EmailIntroModel:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    instructions = _load_email_editor_instructions()
    payload = _build_intro_input(
        recipient_name=recipient_name,
        digest_date=digest_date,
        profile_name=profile_name,
        ranked_items=ranked_items,
    )

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=payload,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "digest_email_intro",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "greeting": {"type": "string"},
                            "introduction": {"type": "string"},
                        },
                        "required": ["subject", "greeting", "introduction"],
                        "additionalProperties": False,
                    },
                }
            },
        )
    except BadRequestError as exc:
        if "model_not_found" in str(exc):
            raise RuntimeError(
                f"Model '{model}' was not found. Use --email-model with an available model (for example: gpt-5.1)."
            ) from exc
        raise

    output_text = _extract_output_text(response)
    parsed = EmailIntroModel.model_validate_json(output_text)
    return parsed


def _build_intro_input(
    *,
    recipient_name: str,
    digest_date: str,
    profile_name: str,
    ranked_items: list[RankedDigestItemModel],
) -> str:
    top_lines = [
        {
            "rank": item.rank,
            "source_type": item.source_type,
            "title": item.digest_title,
            "score": item.score,
        }
        for item in ranked_items
    ]

    return (
        "Generate an opening for a daily AI digest email.\n\n"
        f"Recipient: {recipient_name}\n"
        f"Digest date: {digest_date}\n"
        f"User profile: {profile_name}\n"
        "Top ranked items:\n"
        f"{json.dumps(top_lines, indent=2)}\n"
        "\nReturn a concise greeting line and a short introduction paragraph.\n"
    )


def _extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)
    if not chunks:
        raise ValueError("No text output returned from Responses API.")
    return "".join(chunks)


def _load_email_editor_instructions() -> str:
    if not EMAIL_EDITOR_INSTRUCTIONS_PATH.exists():
        raise RuntimeError(f"Email editor instructions file missing: {EMAIL_EDITOR_INSTRUCTIONS_PATH}")
    return EMAIL_EDITOR_INSTRUCTIONS_PATH.read_text(encoding="utf-8")
