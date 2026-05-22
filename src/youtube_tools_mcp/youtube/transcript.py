from __future__ import annotations

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

    def __init__(self) -> None:
        self._api = YouTubeTranscriptApi()
        self._proxy = get_proxy_url()

    def fetch(self, video_id: str, languages: tuple[str, ...] = ("en",)) -> str:
        """Fetch transcript and format as timestamped text.

        Returns a string with lines like "[MM:SS] transcript text".
        """
        try:
            kwargs: dict[str, object] = {"languages": list(languages)}
            if self._proxy is not None:
                kwargs["proxies"] = {"http": self._proxy, "https": self._proxy}
            transcript = self._api.fetch(video_id, **kwargs)
        except (TranscriptsDisabled, NoTranscriptFound, InvalidVideoId, VideoUnplayable) as exc:
            raise _map_exception(exc) from exc
        except CouldNotRetrieveTranscript as exc:
            raise _map_exception(exc) from exc
        except Exception as exc:
            raise TranscriptFetchError(f"Unexpected error fetching transcript: {exc}") from exc

        lines: list[str] = []
        for snippet in transcript:
            ts = format_timestamp(snippet.start)
            text = snippet.text.replace("\n", " ")
            lines.append(f"[{ts}] {text}")

        return "\n".join(lines)
