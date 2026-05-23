from __future__ import annotations

import json
from dataclasses import asdict

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from youtube_tools_mcp.utils.url import extract_video_id
from youtube_tools_mcp.youtube.metadata import (
    MetadataError,
    YouTubeVideoMetadata,
    fetch_video_metadata,
)
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
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
) -> str:
    """Fetch transcript plus video and channel metadata.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        languages: Preferred transcript language codes. Defaults to ["ru", "en"].
        include_channel_description: Try to include channel description when available.
        proxy: Optional proxy URL (e.g. http://user:pass@host:port).

    Returns:
        Pretty JSON with metadata and timestamped transcript text.
        If metadata fails but transcript succeeds, metadata will be null
        and a metadata_error field will be present instead.
    """
    if languages is None:
        languages = ["ru", "en"]

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    metadata: YouTubeVideoMetadata | None = None
    metadata_error: str | None = None
    try:
        metadata = fetch_video_metadata(
            video_id,
            include_channel_description=include_channel_description,
            proxy=proxy,
            cookies_from_browser=cookies_from_browser,
        )
    except MetadataError as exc:
        metadata_error = (
            f"Failed to fetch video metadata: {exc}. "
            "If YouTube returned a bot-check, captcha, sign-in, or anti-abuse message, "
            "retry the same tool call with the proxy parameter, or with a different proxy if proxy was already used, "
            "or try cookies_from_browser (e.g. 'chrome', 'firefox')."
        )

    fetcher = TranscriptFetcher(proxy_url=proxy)
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
        raise _err(
            f"Failed to fetch transcript: {exc}. "
            "If YouTube returned a bot-check, captcha, sign-in, or anti-abuse message, "
            "retry the same tool call with the proxy parameter, or with a different proxy if proxy was already used."
        ) from exc

    payload: dict[str, object] = {
        "metadata": asdict(metadata) if metadata is not None else None,
        "transcript": transcript,
    }
    if metadata_error is not None:
        payload["metadata_error"] = metadata_error
    if metadata is not None and metadata.warnings:
        payload["metadata_warnings"] = metadata.warnings

    return json.dumps(payload, ensure_ascii=False, indent=2)
