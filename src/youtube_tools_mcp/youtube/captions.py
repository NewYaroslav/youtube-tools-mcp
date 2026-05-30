from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from youtube_tools_mcp.utils.proxy import get_proxy_url
from youtube_tools_mcp.youtube.oauth import get_access_token
from youtube_tools_mcp.youtube.transcript import TranscriptFetchError

_API_BASE = "https://www.googleapis.com/youtube/v3"
_CAPTIONS_DOWNLOAD_URL = "https://www.googleapis.com/youtube/v3/captions"


class CaptionError(Exception):
    """Error fetching captions via Data API."""


class CaptionDownloadError(CaptionError):
    """Failed to download caption track."""


class CaptionListError(CaptionError):
    """Failed to list caption tracks."""


def _api_get(
    endpoint: str,
    params: dict[str, str],
    access_token: str | None = None,
    proxy: str | None = None,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{_API_BASE}/{endpoint}?{query}"
    req = urllib.request.Request(url)  # noqa: S310

    if access_token:
        req.add_header("Authorization", f"Bearer {access_token}")

    proxy_url = get_proxy_url(proxy)
    opener = (
        urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
        if proxy_url
        else None
    )

    try:
        if opener is not None:
            with opener.open(req, timeout=20) as response:
                raw = response.read().decode("utf-8")
        else:
            with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CaptionListError(f"YouTube Data API HTTP error {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise CaptionListError(f"YouTube Data API request failed: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CaptionListError("Invalid JSON from YouTube Data API") from exc


def list_caption_tracks(
    video_id: str,
    api_key: str | None = None,
    access_token: str | None = None,
    proxy: str | None = None,
) -> list[dict[str, Any]]:
    """List available caption tracks for a video."""
    params: dict[str, str] = {"part": "snippet", "videoId": video_id}

    if api_key:
        params["key"] = api_key

    data = _api_get("captions", params, access_token=access_token, proxy=proxy)

    items = data.get("items")
    if not isinstance(items, list):
        return []

    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        snippet = item.get("snippet")
        if not isinstance(snippet, dict):
            continue
        result.append(
            {
                "id": item.get("id"),
                "language": snippet.get("language"),
                "name": snippet.get("name"),
                "is_auto_generated": snippet.get("trackKind") == "asr",
            }
        )

    return result


def download_caption_track(
    caption_id: str,
    access_token: str,
    proxy: str | None = None,
) -> str:
    """Download a caption track as SRT."""
    params = {"tfmt": "srt"}
    query = urllib.parse.urlencode(params)
    url = f"{_CAPTIONS_DOWNLOAD_URL}/{urllib.parse.quote(caption_id)}?{query}"
    req = urllib.request.Request(url)  # noqa: S310
    req.add_header("Authorization", f"Bearer {access_token}")

    proxy_url = get_proxy_url(proxy)
    opener = (
        urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
        if proxy_url
        else None
    )

    try:
        if opener is not None:
            with opener.open(req, timeout=20) as response:
                return response.read().decode("utf-8")
        else:
            with urllib.request.urlopen(req, timeout=20) as response:  # noqa: S310
                return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise CaptionDownloadError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise CaptionDownloadError(f"Download failed: {exc.reason}") from exc


_SRT_RE = re.compile(
    r"\d+\s*\n"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n"
    r"(.*?)"
    r"(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def _parse_srt(raw: str) -> list[dict[str, Any]]:
    """Parse SRT text into snippet-like dicts."""
    result: list[dict[str, Any]] = []
    for match in _SRT_RE.finditer(raw):
        h1, m1, s1, ms1, h2, m2, s2, ms2 = match.group(1, 2, 3, 4, 5, 6, 7, 8)
        text = match.group(9).strip().replace("\n", " ")

        start = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000
        end = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000

        result.append(
            {
                "text": text,
                "start": start,
                "duration": max(0.0, end - start),
            }
        )

    return result


def fetch_transcript_via_data_api(
    video_id: str,
    languages: tuple[str, ...] = ("en",),
    api_key: str | None = None,
    proxy: str | None = None,
) -> str:
    """Fetch transcript via YouTube Data API captions.download."""
    access_token = get_access_token()
    if not access_token:
        raise TranscriptFetchError(
            "OAuth token not available. Run `youtube-tools-mcp-oauth` to authorize."
        )

    tracks = list_caption_tracks(video_id, api_key=api_key, access_token=access_token, proxy=proxy)

    if not tracks:
        raise TranscriptFetchError("No caption tracks found for this video")

    selected_track: dict[str, Any] | None = None

    # First pass: exact language match
    for lang in languages:
        for track in tracks:
            track_lang = track.get("language", "")
            if track_lang.lower() == lang.lower():
                selected_track = track
                break
        if selected_track:
            break

    # Second pass: language prefix match (e.g., "ru" matches "ru-RU")
    if not selected_track:
        for lang in languages:
            for track in tracks:
                track_lang = track.get("language", "")
                if track_lang.lower().startswith(lang.lower()):
                    selected_track = track
                    break
            if selected_track:
                break

    # Third pass: any auto-generated track, then first available
    if not selected_track:
        for track in tracks:
            if track.get("is_auto_generated"):
                selected_track = track
                break
        if not selected_track:
            selected_track = tracks[0]

    caption_id = selected_track.get("id")
    if not caption_id:
        raise TranscriptFetchError("Selected caption track has no ID")

    srt_text = download_caption_track(caption_id, access_token, proxy=proxy)
    snippets = _parse_srt(srt_text)

    if not snippets:
        raise TranscriptFetchError("Downloaded caption track is empty")

    from youtube_tools_mcp.utils.text import format_timestamp

    lines: list[str] = []
    for snippet in snippets:
        ts = format_timestamp(snippet["start"])
        text = snippet["text"].replace("\n", " ")
        lines.append(f"[{ts}] {text}")

    return "\n".join(lines)
