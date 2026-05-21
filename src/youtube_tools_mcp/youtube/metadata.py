from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from youtube_tools_mcp.utils.url import normalize_url


class MetadataError(Exception):
    """Base exception for YouTube metadata operations."""


class MetadataFetchError(MetadataError):
    """Failed to fetch YouTube metadata."""


_DURATION_PATTERN = re.compile(
    r"^P"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$",
)


@dataclass(slots=True)
class YouTubeVideoMetadata:
    """Metadata describing a YouTube video and its channel."""

    video_id: str
    video_url: str
    title: str | None = None
    description: str | None = None
    channel_id: str | None = None
    channel_title: str | None = None
    channel_url: str | None = None
    channel_description: str | None = None
    duration: float | None = None
    upload_date: str | None = None
    source: str = "yt-dlp"
    warnings: list[str] = field(default_factory=list)


def _clean_string(value: object) -> str | None:
    """Return non-empty string value or None."""
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    return stripped or None


def _normalize_upload_date(value: object) -> str | None:
    """Normalize yt-dlp upload date from YYYYMMDD to YYYY-MM-DD."""
    if not isinstance(value, str):
        return None

    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"

    return _clean_string(value)


def _parse_iso8601_duration(value: object) -> float | None:
    """Parse YouTube ISO-8601 duration to seconds."""
    if not isinstance(value, str):
        return None

    match = _DURATION_PATTERN.match(value)
    if match is None:
        return None

    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    if days == 0 and hours == 0 and minutes == 0 and seconds == 0:
        return None

    return float(days * 86400 + hours * 3600 + minutes * 60 + seconds)


def _extract_metadata_from_ytdlp_info(
    video_id: str,
    info: dict[str, object],
) -> YouTubeVideoMetadata:
    """Convert yt-dlp info dict to metadata DTO."""
    channel_id = _clean_string(info.get("channel_id"))
    channel_url = _clean_string(info.get("channel_url"))

    if channel_url is None and channel_id is not None:
        channel_url = f"https://www.youtube.com/channel/{channel_id}"

    duration_raw = info.get("duration")
    duration = float(duration_raw) if isinstance(duration_raw, (int, float)) else None

    return YouTubeVideoMetadata(
        video_id=video_id,
        video_url=normalize_url(video_id),
        title=_clean_string(info.get("title")),
        description=_clean_string(info.get("description")),
        channel_id=channel_id,
        channel_title=_clean_string(info.get("channel")) or _clean_string(info.get("uploader")),
        channel_url=channel_url,
        channel_description=_clean_string(info.get("channel_description")),
        duration=duration,
        upload_date=_normalize_upload_date(info.get("upload_date")),
        source="yt-dlp",
    )


def fetch_video_metadata_ytdlp(video_id: str) -> YouTubeVideoMetadata:
    """Fetch video metadata via yt-dlp without downloading the video."""
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(normalize_url(video_id), download=False)
    except Exception as exc:
        raise MetadataFetchError(f"yt-dlp failed to fetch metadata for video {video_id}: {exc}") from exc

    if not isinstance(info, dict):
        raise MetadataFetchError(f"yt-dlp returned no metadata for video {video_id}")

    return _extract_metadata_from_ytdlp_info(video_id, info)


def _youtube_api_get(path: str, params: dict[str, str]) -> dict[str, object]:
    """Call YouTube Data API v3 and return parsed JSON."""
    query = urlencode(params)
    request = Request(f"https://www.googleapis.com/youtube/v3/{path}?{query}")

    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        raise MetadataFetchError(f"YouTube Data API HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise MetadataFetchError(f"YouTube Data API request failed: {exc.reason}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetadataFetchError("YouTube Data API returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise MetadataFetchError("YouTube Data API returned unexpected JSON")

    return data


def _first_item(data: dict[str, object]) -> dict[str, object] | None:
    """Return first item from YouTube API response."""
    items = data.get("items")
    if not isinstance(items, list) or not items:
        return None

    item = items[0]
    return item if isinstance(item, dict) else None


def fetch_video_metadata_api(
    video_id: str,
    api_key: str,
    include_channel_description: bool = True,
) -> YouTubeVideoMetadata:
    """Fetch video and channel metadata via YouTube Data API v3."""
    video_data = _youtube_api_get(
        "videos",
        {
            "part": "snippet,contentDetails",
            "id": video_id,
            "key": api_key,
        },
    )

    video_item = _first_item(video_data)
    if video_item is None:
        raise MetadataFetchError(f"YouTube Data API returned no video for ID {video_id}")

    snippet = video_item.get("snippet")
    if not isinstance(snippet, dict):
        raise MetadataFetchError("YouTube Data API video response has no snippet")

    channel_id = _clean_string(snippet.get("channelId"))

    content_details = video_item.get("contentDetails")
    duration: float | None = None
    if isinstance(content_details, dict):
        duration = _parse_iso8601_duration(content_details.get("duration"))

    metadata = YouTubeVideoMetadata(
        video_id=video_id,
        video_url=normalize_url(video_id),
        title=_clean_string(snippet.get("title")),
        description=_clean_string(snippet.get("description")),
        channel_id=channel_id,
        channel_title=_clean_string(snippet.get("channelTitle")),
        channel_url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
        duration=duration,
        upload_date=_clean_string(snippet.get("publishedAt")),
        source="youtube-data-api",
    )

    if include_channel_description and channel_id is not None:
        try:
            channel_data = _youtube_api_get(
                "channels",
                {
                    "part": "snippet",
                    "id": channel_id,
                    "key": api_key,
                },
            )
        except MetadataError as exc:
            metadata.warnings.append(f"youtube-data-api channel metadata failed: {exc}")
            return metadata

        channel_item = _first_item(channel_data)
        if channel_item is not None:
            channel_snippet = channel_item.get("snippet")
            if isinstance(channel_snippet, dict):
                metadata.channel_description = _clean_string(channel_snippet.get("description"))

                custom_url = _clean_string(channel_snippet.get("customUrl"))
                if custom_url:
                    metadata.channel_url = f"https://www.youtube.com/{custom_url}"

    return metadata


def fetch_video_metadata(
    video_id: str,
    include_channel_description: bool = True,
) -> YouTubeVideoMetadata:
    """Fetch video metadata.

    Uses YouTube Data API when YOUTUBE_API_KEY is configured, because it can
    return channel description. Falls back to yt-dlp, which works without API key.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if api_key:
        try:
            return fetch_video_metadata_api(video_id, api_key, include_channel_description)
        except MetadataError as exc:
            metadata = fetch_video_metadata_ytdlp(video_id)
            metadata.warnings.append(f"youtube-data-api failed: {exc}")
            return metadata

    return fetch_video_metadata_ytdlp(video_id)


def metadata_to_json(metadata: YouTubeVideoMetadata) -> str:
    """Serialize video metadata as stable pretty JSON."""
    return json.dumps(asdict(metadata), ensure_ascii=False, indent=2)
