from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, CallToolResult, ErrorData, ImageContent, TextContent

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


def _image_content(path: Path) -> ImageContent:
    data = base64.b64encode(path.read_bytes()).decode()
    return ImageContent(type="image", data=data, mimeType="image/jpeg")


def _cleanup_dir(path: Path) -> None:
    if path.exists():
        for f in path.iterdir():
            f.unlink(missing_ok=True)


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
    lines = [f"Extracted {len(paths)} frames from video {video_id}"]
    lines.append(f"Output directory: {output_dir}")
    lines.append("")
    lines.append("Frames (use Read tool or open in viewer):")
    for p, ts in zip(paths, timestamps, strict=True):
        lines.append(f"  [{_format_timestamp(ts)}] {p}")
    lines.append("")
    lines.append(
        "IMPORTANT: Do NOT use Read on all frames at once — "
        "images will fill the context window and freeze the session. "
        "Instead: copy frames to your project assets folder, "
        "insert markdown image links like ![desc](path), "
        "and add captions based on transcript timestamps. "
        "If you must view a specific frame, Read only ONE at a time."
    )
    return TextContent(type="text", text="\n".join(lines))


def extract_video_frame(url_or_id: str, timestamp: float, max_width: int = 1280) -> CallToolResult:
    """Extract a single frame from a YouTube video at a specific timestamp.

    Gets a direct stream URL via yt-dlp, then uses ffmpeg to seek and extract.
    Uses progressive mp4 format so ffmpeg can seek without downloading.
    Frame is downscaled to max_width to keep context usage low.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamp: Timestamp in seconds (e.g., 195.0 for 3:15).
        max_width: Maximum frame width in pixels. Defaults to 1280.

    Returns:
        MCP result containing a JPEG image of the frame.
    """
    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    try:
        stream_url, _ = get_stream_url(video_id)
    except DownloadError as exc:
        raise _err(f"Failed to get stream URL: {exc}") from exc

    tmp_dir = Path(tempfile.mkdtemp(prefix="yt_frame_"))
    try:
        out_path = tmp_dir / "frame.jpg"
        extract_frame(stream_url, timestamp, out_path, max_width=max_width)
        return CallToolResult(content=[_image_content(out_path)])
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(f"Frame extraction failed: {exc}") from exc
    finally:
        _cleanup_dir(tmp_dir)


def extract_video_frames(
    url_or_id: str,
    timestamps: list[float],
    output_dir: str | None = None,
    max_width: int = 1280,
) -> CallToolResult:
    """Extract multiple frames from a YouTube video at specified timestamps.

    Saves frames as JPEG files to output_dir and returns file paths.
    Frames are downscaled to max_width to keep file size small.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamps: List of timestamps in seconds.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. Defaults to 1280.

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
    max_width: int = 1280,
) -> CallToolResult:
    """Extract frames from a YouTube video at regular intervals.

    Saves frames as JPEG files to output_dir and returns file paths.
    Frames are downscaled to max_width to keep file size small.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        interval_sec: Interval between frames in seconds. Defaults to 30.
        max_frames: Maximum number of frames to extract. Defaults to 10, max 30.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. Defaults to 1280.

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
