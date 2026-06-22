from __future__ import annotations

import html
import json
import math
import os
import re
import tempfile
from pathlib import Path

from requests import Session
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

DEFAULT_YOUTUBE_TRANSCRIPT_API_REQUEST_TIMEOUT = 5.0
YOUTUBE_TRANSCRIPT_API_REQUEST_TIMEOUT_ENV = "YOUTUBE_TOOLS_TRANSCRIPT_API_REQUEST_TIMEOUT"


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


class _TimeoutSession(Session):
    def __init__(self, timeout: float) -> None:
        super().__init__()
        self.timeout = timeout

    def request(self, method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        return super().request(method, url, **kwargs)


def _positive_timeout(value: object, name: str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise TranscriptFetchError(f"{name} must be a positive finite number") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise TranscriptFetchError(f"{name} must be a positive finite number")
    return timeout


def _youtube_transcript_api_request_timeout(timeout: float | None = None) -> float:
    if timeout is not None:
        return _positive_timeout(timeout, "transcript_api_timeout")

    raw = os.environ.get(YOUTUBE_TRANSCRIPT_API_REQUEST_TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_YOUTUBE_TRANSCRIPT_API_REQUEST_TIMEOUT
    return _positive_timeout(raw, YOUTUBE_TRANSCRIPT_API_REQUEST_TIMEOUT_ENV)


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


def _parse_subtitle_time(value: str) -> float:
    """Parse WebVTT/SRT timestamp text into seconds."""
    parts = value.strip().replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def _clean_subtitle_text(text: str) -> str:
    """Remove common WebVTT markup and normalize cue text."""
    without_tags = re.sub(r"<[^>]+>", "", text)
    return html.unescape(without_tags).strip()


def _parse_vtt(raw: str) -> list[dict[str, object]]:
    """Parse WebVTT subtitle text into snippet-like dicts."""
    result: list[dict[str, object]] = []
    lines = raw.replace("\ufeff", "").splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1
        if "-->" not in line:
            continue

        start_raw, end_part = line.split("-->", 1)
        end_raw = end_part.strip().split(maxsplit=1)[0]
        text_lines: list[str] = []
        while idx < len(lines) and lines[idx].strip():
            text_lines.append(lines[idx].strip())
            idx += 1

        text = _clean_subtitle_text(" ".join(text_lines))
        if not text:
            continue

        start = _parse_subtitle_time(start_raw)
        end = _parse_subtitle_time(end_raw)
        result.append(
            {
                "text": text,
                "start": start,
                "duration": max(0.0, end - start),
            }
        )

    return result


def _format_snippets(snippets: list[dict[str, object]]) -> str:
    if not snippets:
        raise TranscriptFetchError("Downloaded subtitle track is empty")

    lines: list[str] = []
    for snippet in snippets:
        ts = format_timestamp(float(snippet["start"]))
        text = str(snippet["text"]).replace("\n", " ")
        lines.append(f"[{ts}] {text}")

    return "\n".join(lines)


def _parse_downloaded_subtitles(raw: str, ext: str) -> list[dict[str, object]]:
    if ext == "json3":
        data = json.loads(raw)
        return _parse_json3_events(data.get("events", []))
    if ext == "vtt":
        return _parse_vtt(raw)
    raise TranscriptFetchError(f"Unsupported subtitle format downloaded via yt-dlp: {ext}")


def _select_subtitle_format(formats: list[dict]) -> dict | None:
    for ext in ("json3", "vtt"):
        matches = [fmt for fmt in formats if fmt.get("ext") == ext and (fmt.get("url") or fmt.get("data"))]
        if matches:
            return matches[-1]
    return None


def _select_from_languages(tracks: dict, candidates: list[str]) -> tuple[str, dict] | None:
    for lang in candidates:
        selected_format = _select_subtitle_format(tracks[lang])
        if selected_format is not None:
            return lang, selected_format

    return None


def _select_requested_tracks(tracks: dict, languages: tuple[str, ...]) -> tuple[str, dict] | None:
    if not tracks:
        return None

    candidates: list[str] = []
    for requested in languages:
        if requested in tracks and requested not in candidates:
            candidates.append(requested)

        prefix = f"{requested}-"
        candidates.extend(lang for lang in tracks if lang.startswith(prefix) and lang not in candidates)

    return _select_from_languages(tracks, candidates)


def _select_any_track(tracks: dict) -> tuple[str, dict] | None:
    return _select_from_languages(tracks, list(tracks))


def _select_subtitle_track(info: dict, languages: tuple[str, ...]) -> tuple[str, dict] | None:
    human = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    selected = _select_requested_tracks(human, languages)
    if selected is not None:
        return selected

    selected = _select_requested_tracks(auto, languages)
    if selected is not None:
        return selected

    selected = _select_any_track(human)
    if selected is not None:
        return selected

    return _select_any_track(auto)


def _write_subtitle_data(subtitle_path: Path, sub_info: dict) -> bool:
    data = sub_info.get("data")
    if data is None:
        return False
    with subtitle_path.open("w", encoding="utf-8", newline="") as subtitle_file:
        subtitle_file.write(str(data))
    return True


def _download_subtitle_with_ytdlp(ydl: object, info: dict, sub_info: dict, subtitle_path: Path) -> None:
    if _write_subtitle_data(subtitle_path, sub_info):
        return

    sub_copy = sub_info.copy()
    sub_copy.setdefault("http_headers", info.get("http_headers"))
    ydl.dl(str(subtitle_path), sub_copy, subtitle=True)

    if not subtitle_path.exists():
        raise TranscriptFetchError("yt-dlp did not produce a subtitle file")


def fetch_transcript_via_ytdlp(
    video_id: str,
    languages: tuple[str, ...] = ("en",),
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
    ytdlp_socket_timeout: float | None = None,
) -> str:
    """Fetch transcript via yt-dlp subtitle extraction and downloader."""
    import yt_dlp

    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    resolved_proxy = get_proxy_url(proxy)
    if resolved_proxy:
        ydl_opts["proxy"] = resolved_proxy
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = [cookies_from_browser]

    from youtube_tools_mcp.youtube.downloader import _apply_client_options, _apply_ytdlp_socket_timeout

    try:
        _apply_ytdlp_socket_timeout(ydl_opts, ytdlp_socket_timeout)
        _apply_client_options(ydl_opts, client)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise TranscriptFetchError(f"yt-dlp returned no info for video {video_id}")

            selected = _select_subtitle_track(info, languages)
            if selected is None:
                raise TranscriptFetchError("No supported subtitles available via yt-dlp")

            selected_lang, sub_info = selected
            ext = str(sub_info.get("ext") or "sub")
            safe_lang = re.sub(r"[^A-Za-z0-9_.-]+", "_", selected_lang)

            with tempfile.TemporaryDirectory(prefix="youtube-tools-mcp-subs-") as tmpdir:
                subtitle_path = Path(tmpdir) / f"{video_id}.{safe_lang}.{ext}"
                _download_subtitle_with_ytdlp(ydl, info, sub_info, subtitle_path)
                raw = subtitle_path.read_text(encoding="utf-8")

            return _format_snippets(_parse_downloaded_subtitles(raw, ext))
    except TranscriptFetchError:
        raise
    except Exception as exc:
        raise TranscriptFetchError(f"Failed to fetch subtitles via yt-dlp: {exc}") from exc


class TranscriptFetcher:
    """Fetches YouTube transcripts using youtube-transcript-api."""

    def __init__(
        self,
        proxy_url: str | None = None,
        cookies_from_browser: str | None = None,
        client: str = "web",
        transcript_api_timeout: float | None = None,
        ytdlp_socket_timeout: float | None = None,
    ) -> None:
        resolved = get_proxy_url(proxy_url)
        http_client = _TimeoutSession(_youtube_transcript_api_request_timeout(transcript_api_timeout))
        if resolved is not None:
            proxy_cfg = GenericProxyConfig(http_url=resolved, https_url=resolved)
            self._api = YouTubeTranscriptApi(proxy_config=proxy_cfg, http_client=http_client)
        else:
            self._api = YouTubeTranscriptApi(http_client=http_client)
        self._proxy_url = resolved
        self._cookies_from_browser = cookies_from_browser
        self._client = client
        self._ytdlp_socket_timeout = ytdlp_socket_timeout

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
        """Fetch via yt-dlp subtitles."""
        return fetch_transcript_via_ytdlp(
            video_id,
            languages,
            proxy=self._proxy_url,
            cookies_from_browser=self._cookies_from_browser,
            client=self._client,
            ytdlp_socket_timeout=self._ytdlp_socket_timeout,
        )

    def _fetch_via_captions_api(self, video_id: str, languages: tuple[str, ...]) -> str:
        """Fetch via YouTube Data API captions (requires OAuth)."""
        from youtube_tools_mcp.youtube.captions import fetch_transcript_via_data_api

        api_key = os.environ.get("YOUTUBE_API_KEY")
        return fetch_transcript_via_data_api(
            video_id,
            languages,
            api_key=api_key,
            proxy=self._proxy_url,
        )

    def _try_fallbacks(
        self,
        video_id: str,
        languages: tuple[str, ...],
        original_exc: Exception,
        *,
        skip_ytdlp: bool = False,
        initial_errors: list[str] | None = None,
    ) -> str:
        """Try yt-dlp then Data API captions fallback."""
        errors = list(initial_errors or [])
        if not skip_ytdlp:
            try:
                return self._fetch_via_ytdlp(video_id, languages)
            except TranscriptFetchError as exc:
                errors.append(f"yt-dlp fallback failed: {exc}")
        try:
            return self._fetch_via_captions_api(video_id, languages)
        except TranscriptFetchError as exc:
            errors.append(f"captions API fallback failed: {exc}")
        details = " | ".join(errors) if errors else "no fallback attempts were made"
        if isinstance(original_exc, CouldNotRetrieveTranscript):
            raise TranscriptFetchError(
                f"Failed to fetch transcript: {original_exc}. Fallback attempts: {details}"
            ) from original_exc
        raise TranscriptFetchError(
            f"Unexpected error fetching transcript: {original_exc}. Fallback attempts: {details}"
        ) from original_exc

    def fetch(self, video_id: str, languages: tuple[str, ...] = ("en",)) -> str:
        """Fetch transcript and format as timestamped text.

        Returns a string with lines like "[MM:SS] transcript text".
        """
        ytdlp_first_errors: list[str] = []
        if self._cookies_from_browser:
            try:
                return self._fetch_via_ytdlp(video_id, languages)
            except TranscriptFetchError as exc:
                ytdlp_first_errors.append(f"yt-dlp first attempt failed: {exc}")

        try:
            return self._fetch_yta(video_id, languages)
        except (TranscriptsDisabled, NoTranscriptFound, InvalidVideoId, VideoUnplayable) as exc:
            # Definitive errors — no point trying fallback
            raise _map_exception(exc) from exc
        except CouldNotRetrieveTranscript as exc:
            # IP blocked or other retrievable failure — try fallbacks
            return self._try_fallbacks(
                video_id,
                languages,
                exc,
                skip_ytdlp=bool(self._cookies_from_browser),
                initial_errors=ytdlp_first_errors,
            )
        except Exception as exc:
            # Unexpected error — try fallbacks
            return self._try_fallbacks(
                video_id,
                languages,
                exc,
                skip_ytdlp=bool(self._cookies_from_browser),
                initial_errors=ytdlp_first_errors,
            )
