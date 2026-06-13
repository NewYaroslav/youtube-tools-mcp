from __future__ import annotations

import os

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from youtube_tools_mcp.utils.url import extract_video_id
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


def _default_cookies_from_browser(cookies_from_browser: str | None) -> str | None:
    if cookies_from_browser:
        return cookies_from_browser
    return os.environ.get("YOUTUBE_TOOLS_COOKIES_FROM_BROWSER") or None


def get_youtube_transcript(
    url_or_id: str,
    languages: list[str] | None = None,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """Extract transcript/subtitles from a YouTube video.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        languages: Preferred language codes in priority order. Defaults to ["ru", "en"].
        proxy: Optional proxy URL (e.g. http://user:pass@host:port).
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".

    Returns:
        Timestamped transcript text with format [MM:SS] text per line.
    """
    if languages is None:
        languages = ["ru", "en"]
    cookies_from_browser = _default_cookies_from_browser(cookies_from_browser)

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    fetcher = TranscriptFetcher(
        proxy_url=proxy,
        cookies_from_browser=cookies_from_browser,
        client=client,
    )
    try:
        return fetcher.fetch(video_id, languages=tuple(languages))
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
            "retry the same tool call with the proxy parameter, or with a different proxy if proxy was already used, "
            "or try cookies_from_browser (e.g. 'chrome', 'firefox'), or try client='android'."
        ) from exc
