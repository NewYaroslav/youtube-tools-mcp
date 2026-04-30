from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")
_WATCH_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})")
_SHORT_URL_PATTERN = re.compile(r"youtu\.be/([a-zA-Z0-9_-]{11})")
_EMBED_URL_PATTERN = re.compile(r"(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})")


def extract_video_id(url_or_id: str) -> str:
    """Extract YouTube video ID from a URL or return a bare ID as-is."""
    stripped = url_or_id.strip()

    if _VIDEO_ID_PATTERN.match(stripped):
        return stripped

    for pattern in (_WATCH_URL_PATTERN, _SHORT_URL_PATTERN, _EMBED_URL_PATTERN):
        match = pattern.search(stripped)
        if match:
            return match.group(1)

    parsed = urlparse(stripped)
    if parsed.netloc.endswith("youtu.be"):
        path_id = parsed.path.strip("/")
        if _VIDEO_ID_PATTERN.match(path_id):
            return path_id

    if "youtube.com" in parsed.netloc:
        query = parse_qs(parsed.query)
        if "v" in query:
            vid = query["v"][0]
            if _VIDEO_ID_PATTERN.match(vid):
                return vid

    raise ValueError(f"Cannot extract YouTube video ID from: {url_or_id!r}")


def normalize_url(video_id: str) -> str:
    """Construct a full YouTube watch URL from a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"
