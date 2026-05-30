from __future__ import annotations

import os

from youtube_transcript_api import (
    YouTubeTranscriptApi,
)
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnplayable,
)
from youtube_transcript_api.proxies import GenericProxyConfig

from youtube_tools_mcp.utils.proxy import get_proxy_url
from youtube_tools_mcp.utils.text import format_timestamp


class TranscriptError(Exception):
    """Base exception for transcript operations."""


class TranscriptsDisabledError(TranscriptError):
    """Transcripts are disabled for this video."""


class NoTranscriptFoundError(TranscriptError):
    """No transcript found in the requested language(s)."""


class VideoUnavailableError(TranscriptError):
    """The video is unavailable, unplayable, or age-restricted."""


class InvalidVideoIdError(TranscriptError):
    """The video ID is invalid."""


class TranscriptFetchError(TranscriptError):
    """Failed to fetch the transcript for an unexpected reason."""


def _map_exception(exc: Exception) -> TranscriptError:
    """Map youtube-transcript-api exceptions to domain exceptions."""
    if isinstance(exc, TranscriptsDisabled):
        return TranscriptsDisabledError(str(exc))
    if isinstance(exc, NoTranscriptFound):
        return NoTranscriptFoundError(str(exc))
    if isinstance(exc, InvalidVideoId):
        return InvalidVideoIdError(str(exc))
    if isinstance(exc, VideoUnplayable):
        return VideoUnavailableError(str(exc))
    return TranscriptFetchError(str(exc))


class TranscriptFetcher:
    """Fetches YouTube transcripts using youtube-transcript-api."""

    def __init__(self, proxy_url: str | None = None) -> None:
        resolved = get_proxy_url(proxy_url)
        if resolved is not None:
            proxy_cfg = GenericProxyConfig(http_url=resolved, https_url=resolved)
            self._api = YouTubeTranscriptApi(proxy_config=proxy_cfg)
        else:
            self._api = YouTubeTranscriptApi()

    def _fetch_yta(self, video_id: str, languages: tuple[str, ...]) -> str:
        """Fetch via youtube-transcript-api and format output."""
        transcript = self._api.fetch(video_id, languages=list(languages))
        lines: list[str] = []
        for snippet in transcript:
            ts = format_timestamp(snippet.start)
            text = snippet.text.replace("\n", " ")
            lines.append(f"[{ts}] {text}")
        return "\n".join(lines)

    def _fetch_via_captions_api(self, video_id: str, languages: tuple[str, ...]) -> str:
        """Fetch via YouTube Data API captions (requires OAuth)."""
        from youtube_tools_mcp.youtube.captions import fetch_transcript_via_data_api

        api_key = os.environ.get("YOUTUBE_API_KEY")
        return fetch_transcript_via_data_api(video_id, languages, api_key=api_key)

    def fetch(self, video_id: str, languages: tuple[str, ...] = ("en",)) -> str:
        """Fetch transcript and format as timestamped text.

        Returns a string with lines like "[MM:SS] transcript text".
        """
        try:
            return self._fetch_yta(video_id, languages)
        except (TranscriptsDisabled, NoTranscriptFound, InvalidVideoId, VideoUnplayable) as exc:
            # Definitive errors — no point trying fallback
            raise _map_exception(exc) from exc
        except CouldNotRetrieveTranscript as exc:
            # IP blocked or other retrievable failure — try OAuth fallback
            try:
                return self._fetch_via_captions_api(video_id, languages)
            except TranscriptFetchError:
                # Fallback also failed — return original error
                raise _map_exception(exc) from exc
        except Exception as exc:
            # Unexpected error — try fallback
            try:
                return self._fetch_via_captions_api(video_id, languages)
            except TranscriptFetchError:
                raise TranscriptFetchError(f"Unexpected error fetching transcript: {exc}") from exc
