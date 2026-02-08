from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ingest.youtube import collect_latest_videos, load_channel_inputs, serialize_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch latest videos from YouTube channels via RSS and optionally include transcripts."
    )
    parser.add_argument(
        "--channels",
        nargs="*",
        default=[],
        help="Channel IDs (UC...), channel URLs, or @handles.",
    )
    parser.add_argument(
        "--channels-file",
        default="app/ingest/channels.txt",
        help="Text file with one channel input per line.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only return videos published in the last N hours.",
    )
    parser.add_argument(
        "--max-per-channel",
        type=int,
        default=None,
        help="Optional hard cap per channel.",
    )
    parser.add_argument(
        "--skip-transcripts",
        action="store_true",
        help="Skip transcript calls for faster testing.",
    )
    parser.add_argument(
        "--languages",
        nargs="*",
        default=["en", "en-US"],
        help="Preferred transcript languages in order.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    channels = list(args.channels)

    channel_file = Path(args.channels_file)
    if channel_file.exists():
        channels.extend(load_channel_inputs(str(channel_file)))

    channels = [channel.strip() for channel in channels if channel.strip()]
    if not channels:
        raise SystemExit(
            "No channels provided. Use --channels or create app/ingest/channels.txt with one channel per line."
        )

    results = collect_latest_videos(
        channel_inputs=channels,
        lookback_hours=args.hours,
        include_transcripts=not args.skip_transcripts,
        transcript_languages=args.languages,
        max_videos_per_channel=args.max_per_channel,
    )

    total_videos = sum(len(result.videos) for result in results)
    print(f"Channels checked: {len(results)}")
    print(f"Videos found in last {args.hours}h: {total_videos}")
    print(json.dumps(serialize_results(results), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

