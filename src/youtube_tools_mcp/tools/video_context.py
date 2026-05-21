from __future__ import annotations

import json
from dataclasses import asdict

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from youtube_tools_mcp.utils.url import extract_video_id
from youtube_tools_mcp.youtube.metadata import MetadataError, fetch_video_metadata
from youtube_tools_mcp.youtube.transcript import (
    InvalidVideoIdError,
    NoTranscriptFoundError,
    TranscriptError,
    TranscriptFetcher,
    TranscriptsDisabledError,
    VideoUnavailableError,
)


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def get_youtube_video_context(
    url_or_id: str,
    languages: list[str] | None = None,
    include_channel_description: bool = True,
) -> str:
    """Fetch transcript plus video and channel metadata.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        languages: Preferred transcript language codes. Defaults to ["ru", "en"].
        include_channel_description: Try to include channel description when available.

    Returns:
        Pretty JSON with metadata and timestamped transcript text.
    """
    if languages is None:
        languages = ["ru", "en"]

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        metadata = fetch_video_metadata(
            video_id,
            include_channel_description=include_channel_description,
        )
    except MetadataError as exc:
        raise _err(f"Failed to fetch video metadata: {exc}") from exc

    fetcher = TranscriptFetcher()
    try:
        transcript = fetcher.fetch(video_id, languages=tuple(languages))
    except TranscriptsDisabledError as exc:
        raise _err(f"Transcripts are disabled for this video: {exc}") from exc
    except NoTranscriptFoundError as exc:
        raise _err(f"No transcript found for languages {languages}: {exc}") from exc
    except InvalidVideoIdError as exc:
        raise _err(f"Invalid video ID: {exc}") from exc
    except VideoUnavailableError as exc:
        raise _err(f"Video unavailable: {exc}") from exc
    except TranscriptError as exc:
        raise _err(f"Failed to fetch transcript: {exc}") from exc

    payload = {
        "metadata": asdict(metadata),
        "transcript": transcript,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
