from __future__ import annotations

import tempfile
from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, CallToolResult, ErrorData, TextContent

from youtube_tools_mcp.utils.url import extract_video_id
from youtube_tools_mcp.youtube.downloader import (
    DownloadError,
    FFmpegNotFoundError,
    extract_frame,
    extract_frames_batch,
    get_stream_url,
)

_MAX_FRAMES = 30
_DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "yt-frames"


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def _format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _frames_result_text(
    paths: list[Path],
    timestamps: list[float],
    video_id: str,
    output_dir: Path,
) -> TextContent:
    lines = ["STOP: Do NOT Read these frame files."]
    lines.append("Reading multiple images fills the context window and freezes the session.")
    lines.append(
        "Copy frames to your project assets folder, embed as links, and write captions from transcript context."
    )
    lines.append("If you must inspect one specific frame, Read ONLY that single file.")
    lines.append("")
    lines.append(f"Extracted {len(paths)} frame(s) from video {video_id}")
    lines.append(f"Output directory: {output_dir}")
    lines.append("")
    lines.append("Frame files:")
    for p, ts in zip(paths, timestamps, strict=True):
        lines.append(f"  [{_format_timestamp(ts)}] {p}")
    return TextContent(type="text", text="\n".join(lines))


def extract_video_frame(
    url_or_id: str,
    timestamp: float,
    output_dir: str | None = None,
    max_width: int = 640,
) -> CallToolResult:
    """Extract a single frame from a YouTube video at a specific timestamp.

    Saves frame as a JPEG file and returns the file path (not inline image).
    Requires ffmpeg to be installed on the system.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamp: Timestamp in seconds (e.g., 195.0 for 3:15).
        output_dir: Directory to save frame. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. Defaults to 640.

    Returns:
        MCP result with file path and timestamp for the extracted frame.
    """
    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        stream_url, _ = get_stream_url(video_id)
    except DownloadError as exc:
        raise _err(f"Failed to get stream URL: {exc}") from exc

    save_dir = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR / video_id
    save_dir.mkdir(parents=True, exist_ok=True)
    try:
        out_path = save_dir / f"frame_{timestamp:.0f}.jpg"
        extract_frame(stream_url, timestamp, out_path, max_width=max_width)
        return CallToolResult(content=[_frames_result_text([out_path], [timestamp], video_id, save_dir)])
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(f"Frame extraction failed: {exc}") from exc


def extract_video_frames(
    url_or_id: str,
    timestamps: list[float],
    output_dir: str | None = None,
    max_width: int = 640,
) -> CallToolResult:
    """Extract multiple frames from a YouTube video at specified timestamps.

    Saves frames as JPEG files and returns file paths (not inline images).
    Requires ffmpeg to be installed on the system. Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamps: List of timestamps in seconds.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. Defaults to 640.

    Returns:
        MCP result with file paths and timestamps for each extracted frame.
    """
    if len(timestamps) > _MAX_FRAMES:
        raise _err(f"Too many timestamps ({len(timestamps)}), maximum is {_MAX_FRAMES}")

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        stream_url, _ = get_stream_url(video_id)
    except DownloadError as exc:
        raise _err(f"Failed to get stream URL: {exc}") from exc

    save_dir = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR / video_id
    save_dir.mkdir(parents=True, exist_ok=True)
    try:
        paths = extract_frames_batch(stream_url, timestamps, save_dir, max_width=max_width)
        return CallToolResult(content=[_frames_result_text(paths, timestamps, video_id, save_dir)])
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(f"Frame extraction failed: {exc}") from exc


def extract_frames_every(
    url_or_id: str,
    interval_sec: float = 30.0,
    max_frames: int = 10,
    output_dir: str | None = None,
    max_width: int = 640,
) -> CallToolResult:
    """Extract frames from a YouTube video at regular intervals.

    Saves frames as JPEG files and returns file paths (not inline images).
    Requires ffmpeg to be installed on the system. Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        interval_sec: Interval between frames in seconds. Defaults to 30.
        max_frames: Maximum number of frames to extract. Defaults to 10, max 30.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. Defaults to 640.

    Returns:
        MCP result with file paths and timestamps for each extracted frame.
    """
    if max_frames > _MAX_FRAMES:
        raise _err(f"max_frames ({max_frames}) exceeds limit ({_MAX_FRAMES})")
    if interval_sec <= 0:
        raise _err("interval_sec must be positive")

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        stream_url, duration = get_stream_url(video_id)
    except DownloadError as exc:
        raise _err(f"Failed to get video info: {exc}") from exc

    count = min(int(duration / interval_sec), max_frames)
    if count == 0:
        raise _err(f"Video duration ({duration:.1f}s) is shorter than interval ({interval_sec}s)")

    timestamps = [i * interval_sec for i in range(count)]

    save_dir = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR / video_id
    save_dir.mkdir(parents=True, exist_ok=True)
    try:
        paths = extract_frames_batch(stream_url, timestamps, save_dir, max_width=max_width)
        return CallToolResult(content=[_frames_result_text(paths, timestamps, video_id, save_dir)])
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(f"Frame extraction failed: {exc}") from exc
