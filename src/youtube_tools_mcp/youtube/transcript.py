from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

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


def _parse_json3_events(events: list[dict]) -> list[dict[str, object]]:
    """Parse YouTube json3 automatic caption events into snippet-like dicts."""
    result: list[dict[str, object]] = []
    for event in events:
        segs = event.get("segs")
        if not segs:
            continue
        text = "".join(seg.get("utf8", "") for seg in segs)
        text = text.strip()
        if not text or text == "\n":
            continue
        start_ms = event.get("tStartMs", 0)
        duration_ms = event.get("dDurationMs", 0)
        result.append(
            {
                "text": text,
                "start": start_ms / 1000.0,
                "duration": duration_ms / 1000.0,
            }
        )
    return result


def fetch_transcript_via_ytdlp(
    video_id: str,
    languages: tuple[str, ...] = ("en",),
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """Fetch transcript via yt-dlp automatic caption extraction."""
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    if proxy:
        ydl_opts["proxy"] = proxy
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = [cookies_from_browser]

    from youtube_tools_mcp.youtube.downloader import _apply_client_options

    _apply_client_options(ydl_opts, client)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    auto_caps = info.get("automatic_captions") or {}

    selected_url: str | None = None
    for lang in languages:
        if lang in auto_caps:
            for fmt in auto_caps[lang]:
                if fmt.get("ext") == "json3":
                    selected_url = fmt.get("url")
                    break
            if selected_url:
                break

    if not selected_url:
        for _lang, fmts in auto_caps.items():
            for fmt in fmts:
                if fmt.get("ext") == "json3":
                    selected_url = fmt.get("url")
                    break
            if selected_url:
                break

    if not selected_url:
        raise TranscriptFetchError("No automatic captions available via yt-dlp")

    req = urllib.request.Request(selected_url)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TranscriptFetchError(f"Failed to download subtitles: HTTP {exc.code}: {body}") from exc
    except Exception as exc:
        raise TranscriptFetchError(f"Failed to download subtitles: {exc}") from exc

    events = data.get("events", [])
    snippets = _parse_json3_events(events)

    if not snippets:
        raise TranscriptFetchError("Downloaded subtitle track is empty")

    lines: list[str] = []
    for snippet in snippets:
        ts = format_timestamp(float(snippet["start"]))
        text = str(snippet["text"]).replace("\n", " ")
        lines.append(f"[{ts}] {text}")

    return "\n".join(lines)


class TranscriptFetcher:
    """Fetches YouTube transcripts using youtube-transcript-api."""

    def __init__(
        self,
        proxy_url: str | None = None,
        cookies_from_browser: str | None = None,
        client: str = "web",
    ) -> None:
        resolved = get_proxy_url(proxy_url)
        if resolved is not None:
            proxy_cfg = GenericProxyConfig(http_url=resolved, https_url=resolved)
            self._api = YouTubeTranscriptApi(proxy_config=proxy_cfg)
        else:
            self._api = YouTubeTranscriptApi()
        self._proxy_url = resolved
        self._cookies_from_browser = cookies_from_browser
        self._client = client

    def _fetch_yta(self, video_id: str, languages: tuple[str, ...]) -> str:
        """Fetch via youtube-transcript-api and format output."""
        transcript = self._api.fetch(video_id, languages=list(languages))
        lines: list[str] = []
        for snippet in transcript:
            ts = format_timestamp(snippet.start)
            text = snippet.text.replace("\n", " ")
            lines.append(f"[{ts}] {text}")
        return "\n".join(lines)

    def _fetch_via_ytdlp(self, video_id: str, languages: tuple[str, ...]) -> str:
        """Fetch via yt-dlp automatic captions."""
        return fetch_transcript_via_ytdlp(
            video_id,
            languages,
            proxy=self._proxy_url,
            cookies_from_browser=self._cookies_from_browser,
            client=self._client,
        )

    def _fetch_via_captions_api(self, video_id: str, languages: tuple[str, ...]) -> str:
        """Fetch via YouTube Data API captions (requires OAuth)."""
        from youtube_tools_mcp.youtube.captions import fetch_transcript_via_data_api

        api_key = os.environ.get("YOUTUBE_API_KEY")
        return fetch_transcript_via_data_api(video_id, languages, api_key=api_key)

    def _try_fallbacks(self, video_id: str, languages: tuple[str, ...], original_exc: Exception) -> str:
        """Try yt-dlp then Data API captions fallback."""
        if self._cookies_from_browser:
            try:
                return self._fetch_via_ytdlp(video_id, languages)
            except TranscriptFetchError:
                pass
        try:
            return self._fetch_via_captions_api(video_id, languages)
        except TranscriptFetchError:
            if isinstance(original_exc, CouldNotRetrieveTranscript):
                raise _map_exception(original_exc) from original_exc
            raise TranscriptFetchError(f"Unexpected error fetching transcript: {original_exc}") from original_exc

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
            # IP blocked or other retrievable failure — try fallbacks
            return self._try_fallbacks(video_id, languages, exc)
        except Exception as exc:
            # Unexpected error — try fallbacks
            return self._try_fallbacks(video_id, languages, exc)
