from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable, Sequence
from urllib.parse import parse_qs, quote, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

YOUTUBE_FEED_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id="
YOUTUBE_URL = "https://www.youtube.com"
CHANNEL_ID_PATTERN = re.compile(r"^UC[a-zA-Z0-9_-]{22}$")
CHANNEL_ID_IN_HTML_PATTERN = re.compile(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"')
EXTERNAL_ID_IN_HTML_PATTERN = re.compile(r'"externalId":"(UC[a-zA-Z0-9_-]{22})"')
BROWSE_ID_IN_HTML_PATTERN = re.compile(r'"browseId":"(UC[a-zA-Z0-9_-]{22})"')
VIDEO_ID_IN_URL_PATTERN = re.compile(r"(?:v=|/videos/|/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})")
YOUTUBE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
# Helps bypass the consent interstitial that breaks channel ID extraction.
YOUTUBE_COOKIES = {"CONSENT": "YES+", "SOCS": "CAI"}


@dataclass(slots=True)
class VideoItem:
    channel_input: str
    channel_id: str
    video_id: str
    title: str
    url: str
    published_at: datetime
    transcript: str | None
    transcript_error: str | None


@dataclass(slots=True)
class ChannelResult:
    channel_input: str
    channel_id: str | None
    videos: list[VideoItem]
    error: str | None


def load_channel_inputs(path: str) -> list[str]:
    channels: list[str] = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            channels.append(cleaned)
    return channels


def collect_latest_videos(
    channel_inputs: Sequence[str],
    lookback_hours: int = 24,
    include_transcripts: bool = True,
    transcript_languages: Sequence[str] | None = None,
    max_videos_per_channel: int | None = None,
    request_timeout_seconds: int = 15,
) -> list[ChannelResult]:
    results: list[ChannelResult] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    languages = list(transcript_languages or ("en", "en-US"))

    for channel_input in channel_inputs:
        try:
            channel_id = resolve_channel_id(channel_input, timeout_seconds=request_timeout_seconds)
            videos = fetch_recent_videos_from_channel_id(
                channel_input=channel_input,
                channel_id=channel_id,
                cutoff_utc=cutoff,
                include_transcripts=include_transcripts,
                transcript_languages=languages,
                max_videos=max_videos_per_channel,
            )
            results.append(ChannelResult(channel_input=channel_input, channel_id=channel_id, videos=videos, error=None))
        except Exception as exc:  # noqa: BLE001
            results.append(
                ChannelResult(
                    channel_input=channel_input,
                    channel_id=None,
                    videos=[],
                    error=str(exc),
                )
            )

    return results


def fetch_recent_videos_from_channel_id(
    channel_input: str,
    channel_id: str,
    cutoff_utc: datetime,
    include_transcripts: bool,
    transcript_languages: Sequence[str],
    max_videos: int | None = None,
) -> list[VideoItem]:
    feed_url = f"{YOUTUBE_FEED_BASE}{channel_id}"
    feed = feedparser.parse(feed_url)
    videos: list[VideoItem] = []

    for entry in feed.entries:
        published_at = parse_entry_datetime(entry)
        if published_at is None or published_at < cutoff_utc:
            continue

        video_url = entry.get("link", "")
        video_id = entry.get("yt_videoid") or extract_video_id(video_url)
        if not video_id:
            continue

        transcript = None
        transcript_error = None
        if include_transcripts:
            transcript, transcript_error = get_video_transcript(video_id, transcript_languages)

        videos.append(
            VideoItem(
                channel_input=channel_input,
                channel_id=channel_id,
                video_id=video_id,
                title=entry.get("title", "").strip(),
                url=video_url,
                published_at=published_at,
                transcript=transcript,
                transcript_error=transcript_error,
            )
        )

        if max_videos is not None and len(videos) >= max_videos:
            break

    return videos


def resolve_channel_id(channel_input: str, timeout_seconds: int = 15) -> str:
    normalized = channel_input.strip()
    if not normalized:
        raise ValueError("Channel input is empty.")

    direct = try_extract_channel_id_from_text(normalized)
    if direct:
        return direct

    candidate_url = to_channel_url(normalized)
    html = get_youtube_html(candidate_url, timeout_seconds)

    from_meta = extract_channel_id_from_html(html)
    if from_meta:
        return from_meta

    videos_url = candidate_url.rstrip("/") + "/videos"
    videos_html = get_youtube_html(videos_url, timeout_seconds)
    from_videos_page = extract_channel_id_from_html(videos_html)
    if from_videos_page:
        return from_videos_page

    from_oembed = extract_channel_id_from_oembed(candidate_url, timeout_seconds)
    if from_oembed:
        return from_oembed

    raise ValueError(
        f"Could not resolve channel ID from input '{channel_input}'. "
        "Use a channel ID (UC...), channel URL, or @handle URL."
    )


def to_channel_url(channel_input: str) -> str:
    parsed = urlparse(channel_input)
    if parsed.scheme and parsed.netloc:
        return channel_input
    if channel_input.startswith("@"):
        return f"{YOUTUBE_URL}/{channel_input}"
    if channel_input.startswith("youtube.com/"):
        return f"https://{channel_input}"
    raise ValueError(
        f"Unsupported channel input '{channel_input}'. "
        "Expected channel ID, URL, or @handle."
    )


def try_extract_channel_id_from_text(text: str) -> str | None:
    if CHANNEL_ID_PATTERN.fullmatch(text):
        return text

    parsed = urlparse(text)
    path = parsed.path.strip("/")
    if path.startswith("channel/"):
        candidate = path.split("/", maxsplit=1)[1]
        if CHANNEL_ID_PATTERN.fullmatch(candidate):
            return candidate
    return None


def extract_channel_id_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"itemprop": "channelId"})
    if meta and meta.get("content") and CHANNEL_ID_PATTERN.fullmatch(meta["content"]):
        return meta["content"]

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        extracted = try_extract_channel_id_from_text(canonical["href"])
        if extracted:
            return extracted

    match = CHANNEL_ID_IN_HTML_PATTERN.search(html)
    if match:
        return match.group(1)

    match = EXTERNAL_ID_IN_HTML_PATTERN.search(html)
    if match:
        return match.group(1)

    match = BROWSE_ID_IN_HTML_PATTERN.search(html)
    if match:
        return match.group(1)
    return None


def extract_channel_id_from_oembed(channel_url: str, timeout_seconds: int) -> str | None:
    endpoint = f"https://www.youtube.com/oembed?url={quote(channel_url, safe='')}&format=json"
    response = requests.get(
        endpoint,
        timeout=timeout_seconds,
        headers=YOUTUBE_HEADERS,
        cookies=YOUTUBE_COOKIES,
    )
    if response.status_code != 200:
        return None

    payload = response.json()
    author_url = payload.get("author_url")
    if not author_url:
        return None

    return try_extract_channel_id_from_text(author_url)


def get_youtube_html(url: str, timeout_seconds: int) -> str:
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers=YOUTUBE_HEADERS,
        cookies=YOUTUBE_COOKIES,
    )
    response.raise_for_status()
    return response.text


def parse_entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    published = entry.get("published") or entry.get("updated")
    if not published:
        return None
    dt = date_parser.parse(published)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def extract_video_id(video_url: str) -> str | None:
    if not video_url:
        return None
    parsed = urlparse(video_url)
    query = parse_qs(parsed.query)
    if "v" in query and query["v"]:
        return query["v"][0]

    match = VIDEO_ID_IN_URL_PATTERN.search(video_url)
    if match:
        return match.group(1)
    return None


def get_video_transcript(video_id: str, transcript_languages: Iterable[str]) -> tuple[str | None, str | None]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        languages = list(transcript_languages)

        # Compatibility across youtube-transcript-api versions:
        # older versions expose get_transcript(...), newer versions use instance.fetch(...).
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            chunks = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            text = " ".join(part.get("text", "").strip() for part in chunks if part.get("text")).strip()
            return text or None, None

        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(video_id, languages=languages)
            text_parts = [snippet.text.strip() for snippet in fetched if getattr(snippet, "text", "").strip()]
            text = " ".join(text_parts).strip()
            return text or None, None
        except Exception as preferred_error:  # noqa: BLE001
            # Fallback: if preferred languages are missing, use the first available transcript.
            transcript_list = api.list(video_id)
            transcripts = list(transcript_list)
            transcripts.sort(key=lambda transcript: transcript.is_generated)

            for transcript in transcripts:
                try:
                    fetched = transcript.fetch()
                    text_parts = [snippet.text.strip() for snippet in fetched if getattr(snippet, "text", "").strip()]
                    text = " ".join(text_parts).strip()
                    if text:
                        return text, None
                except Exception:  # noqa: BLE001
                    continue

            return None, str(preferred_error)
    except ModuleNotFoundError:
        return None, "Missing dependency: youtube-transcript-api"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def serialize_results(results: Sequence[ChannelResult]) -> list[dict]:
    payload: list[dict] = []
    for result in results:
        item = {
            "channel_input": result.channel_input,
            "channel_id": result.channel_id,
            "error": result.error,
            "videos": [],
        }
        for video in result.videos:
            video_dict = asdict(video)
            video_dict["published_at"] = video.published_at.isoformat()
            item["videos"].append(video_dict)
        payload.append(item)
    return payload
