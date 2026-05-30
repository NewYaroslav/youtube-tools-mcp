from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_WATCH_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})")
_SHORT_URL_PATTERN = re.compile(r"youtu\.be/([a-zA-Z0-9_-]{11})")
_SHORTS_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})")
_EMBED_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})")

_PLAYLIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{10,}$")
_PLAYLIST_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/playlist\?list=([A-Za-z0-9_-]+)")

_CHANNEL_ID_PATTERN = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_CHANNEL_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/channel/(UC[A-Za-z0-9_-]{22})")
_HANDLE_PATTERN = re.compile(r"^@[A-Za-z0-9_.-]+$")
_HANDLE_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/@([A-Za-z0-9_.-]+)")


def extract_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from a URL or return a bare ID as-is."""
    stripped = url_or_id.strip()

    if _VIDEO_ID_PATTERN.match(stripped):
        return stripped

    for pattern in (_WATCH_URL_PATTERN, _SHORT_URL_PATTERN, _SHORTS_URL_PATTERN, _EMBED_URL_PATTERN):
        match = pattern.search(stripped)
        if match:
            return match.group(1)

    parsed = urlparse(stripped)
    if parsed.netloc.endswith("youtu.be"):
        path_id = parsed.path.strip("/")
        if _VIDEO_ID_PATTERN.match(path_id):
            return path_id

    if "youtube.com" in parsed.netloc:
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "shorts":
            vid = path_parts[1]
            if _VIDEO_ID_PATTERN.match(vid):
                return vid

        query = parse_qs(parsed.query)
        if "v" in query:
            vid = query["v"][0]
            if _VIDEO_ID_PATTERN.match(vid):
                return vid

    raise ValueError(f"Cannot extract YouTube video ID from: {url_or_id!r}")


def extract_playlist_id(url_or_id: str) -> str:
    """Extract YouTube playlist ID from a URL or return a bare ID as-is."""
    stripped = url_or_id.strip()

    match = _PLAYLIST_URL_PATTERN.search(stripped)
    if match:
        return match.group(1)

    if _PLAYLIST_ID_PATTERN.match(stripped):
        return stripped

    raise ValueError(f"Cannot extract YouTube playlist ID from: {url_or_id!r}")


def extract_channel_id(url_or_handle: str) -> str:
    """Extract YouTube channel ID (UC...) from a URL or validate a bare ID."""
    stripped = url_or_handle.strip()

    match = _CHANNEL_URL_PATTERN.search(stripped)
    if match:
        return match.group(1)

    if _CHANNEL_ID_PATTERN.match(stripped):
        return stripped

    raise ValueError(f"Cannot extract YouTube channel ID from: {url_or_handle!r}")


def resolve_channel_handle(handle: str) -> str | None:
    """Return a handle name (without @) if the input is a handle or handle URL."""
    stripped = handle.strip()

    match = _HANDLE_URL_PATTERN.search(stripped)
    if match:
        return match.group(1)

    if _HANDLE_PATTERN.match(stripped):
        return stripped.lstrip("@")

    return None


def normalize_url(video_id: str) -> str:
    """Construct a full YouTube watch URL from a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"
