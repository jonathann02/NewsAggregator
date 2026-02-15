from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db import SessionLocal
from app.db.models import Article, DigestItem

RANK_MODEL = os.getenv("RANK_MODEL", "gpt-5.1")
ASSIGNMENT_EDITOR_INSTRUCTIONS_PATH = Path("app/agent/assignment_editor_instructions.txt")


class UserProfileModel(BaseModel):
    profile_name: str
    role: str
    interests: list[str]
    priorities: list[str]


class DigestCandidateModel(BaseModel):
    digest_item_id: int
    article_id: int
    article_url: str
    digest_title: str
    digest_summary: str
    source_type: str
    published_at: datetime


class RankDecisionModel(BaseModel):
    digest_item_id: int
    score: int = Field(ge=0, le=100)
    reason: str


class RankDecisionListModel(BaseModel):
    ranked_items: list[RankDecisionModel]


class RankedDigestItemModel(BaseModel):
    rank: int
    digest_item_id: int
    article_id: int
    article_url: str
    source_type: str
    digest_title: str
    digest_summary: str
    score: int = Field(ge=0, le=100)
    reason: str


class DigestRankingResultModel(BaseModel):
    profile_name: str
    model: str
    generated_at: datetime
    ranked_items: list[RankedDigestItemModel]


DEFAULT_USER_PROFILE = UserProfileModel(
    profile_name="AI Product and Engineering Lead",
    role="Leads AI product strategy and technical execution for a software company.",
    interests=[
        "new model capabilities",
        "agent workflows",
        "API/platform updates",
        "developer tooling",
        "AI safety and policy changes with product impact",
    ],
    priorities=[
        "items that change roadmap decisions",
        "items that can improve product velocity",
        "items with direct implementation relevance",
    ],
)


def run_rank_digest(
    lookback_hours: int = 24,
    max_items: int | None = 100,
    model: str = RANK_MODEL,
    user_profile: UserProfileModel = DEFAULT_USER_PROFILE,
) -> DigestRankingResultModel:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    candidates = _load_recent_digest_candidates(lookback_hours=lookback_hours, max_items=max_items)
    if not candidates:
        return DigestRankingResultModel(
            profile_name=user_profile.profile_name,
            model=model,
            generated_at=datetime.now(timezone.utc),
            ranked_items=[],
        )

    client = OpenAI(api_key=api_key)
    instructions = _load_assignment_editor_instructions()
    decisions = _rank_candidates(client=client, model=model, instructions=instructions, profile=user_profile, candidates=candidates)
    ranked = _merge_rank_decisions(candidates=candidates, decisions=decisions)

    return DigestRankingResultModel(
        profile_name=user_profile.profile_name,
        model=model,
        generated_at=datetime.now(timezone.utc),
        ranked_items=ranked,
    )


def _load_recent_digest_candidates(lookback_hours: int, max_items: int | None) -> list[DigestCandidateModel]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    stmt = (
        select(DigestItem, Article)
        .join(Article, DigestItem.article_id == Article.id)
        .where(DigestItem.created_at >= cutoff)
        .order_by(DigestItem.created_at.desc())
    )
    if max_items is not None:
        stmt = stmt.limit(max_items)

    session = SessionLocal()
    try:
        rows = session.execute(stmt).all()
        return [
            DigestCandidateModel(
                digest_item_id=digest.id,
                article_id=article.id,
                article_url=digest.article_url,
                digest_title=digest.digest_title,
                digest_summary=digest.digest_summary,
                source_type=article.source_type,
                published_at=article.published_at,
            )
            for digest, article in rows
        ]
    finally:
        session.close()


def _rank_candidates(
    *,
    client: OpenAI,
    model: str,
    instructions: str,
    profile: UserProfileModel,
    candidates: list[DigestCandidateModel],
) -> list[RankDecisionModel]:
    input_payload = _build_ranking_input(profile=profile, candidates=candidates)
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=input_payload,
        text={
            "format": {
                "type": "json_schema",
                "name": "digest_rankings",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "ranked_items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "digest_item_id": {"type": "integer"},
                                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                                    "reason": {"type": "string"},
                                },
                                "required": ["digest_item_id", "score", "reason"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["ranked_items"],
                    "additionalProperties": False,
                },
            }
        },
    )

    output_text = _extract_output_text(response)
    parsed = RankDecisionListModel.model_validate_json(output_text)
    return parsed.ranked_items


def _build_ranking_input(profile: UserProfileModel, candidates: list[DigestCandidateModel]) -> str:
    candidates_payload = [
        {
            "digest_item_id": c.digest_item_id,
            "article_id": c.article_id,
            "source_type": c.source_type,
            "digest_title": c.digest_title,
            "digest_summary": c.digest_summary,
        }
        for c in candidates
    ]
    return (
        "User profile:\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        "Digest candidates:\n"
        f"{json.dumps(candidates_payload, indent=2)}\n\n"
        "Rank these digest items for the user profile."
    )


def _merge_rank_decisions(
    *,
    candidates: list[DigestCandidateModel],
    decisions: list[RankDecisionModel],
) -> list[RankedDigestItemModel]:
    candidates_by_id = {item.digest_item_id: item for item in candidates}
    seen_ids: set[int] = set()
    merged: list[RankedDigestItemModel] = []

    for decision in sorted(decisions, key=lambda item: item.score, reverse=True):
        candidate = candidates_by_id.get(decision.digest_item_id)
        if not candidate or decision.digest_item_id in seen_ids:
            continue
        seen_ids.add(decision.digest_item_id)
        merged.append(
            RankedDigestItemModel(
                rank=len(merged) + 1,
                digest_item_id=candidate.digest_item_id,
                article_id=candidate.article_id,
                article_url=candidate.article_url,
                source_type=candidate.source_type,
                digest_title=candidate.digest_title,
                digest_summary=candidate.digest_summary,
                score=decision.score,
                reason=decision.reason.strip(),
            )
        )

    # Fill any missing candidates at the end with neutral score.
    for candidate in candidates:
        if candidate.digest_item_id in seen_ids:
            continue
        merged.append(
            RankedDigestItemModel(
                rank=len(merged) + 1,
                digest_item_id=candidate.digest_item_id,
                article_id=candidate.article_id,
                article_url=candidate.article_url,
                source_type=candidate.source_type,
                digest_title=candidate.digest_title,
                digest_summary=candidate.digest_summary,
                score=0,
                reason="Not ranked by model output.",
            )
        )

    return merged


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


def _load_assignment_editor_instructions() -> str:
    if not ASSIGNMENT_EDITOR_INSTRUCTIONS_PATH.exists():
        raise RuntimeError(f"Assignment editor instructions file missing: {ASSIGNMENT_EDITOR_INSTRUCTIONS_PATH}")
    return ASSIGNMENT_EDITOR_INSTRUCTIONS_PATH.read_text(encoding="utf-8")
