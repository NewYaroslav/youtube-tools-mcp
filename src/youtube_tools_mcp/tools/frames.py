from __future__ import annotations

import base64
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, CallToolResult, ErrorData, ImageContent, TextContent

from youtube_tools_mcp.utils.url import extract_video_id
from youtube_tools_mcp.vision import VisionAPIError, VisionConfigError, analyze_image_path
from youtube_tools_mcp.youtube.downloader import (
    DownloadError,
    FFmpegNotFoundError,
    download_frame_source,
    extract_frame,
    extract_frames_batch,
    get_media_duration,
    get_stream_url,
)

_MAX_FRAMES = 30
_DEFAULT_OUTPUT_DIR = Path(tempfile.gettempdir()) / "yt-frames"
_FrameSourceKind = Literal["direct", "downloaded"]
_FrameSourceMode = Literal["auto", "always", "never"]


@dataclass(frozen=True)
class _VideoSource:
    value: str
    kind: _FrameSourceKind
    duration: float | None = None
    temp_dir: Path | None = None


def _err(msg: str) -> McpError:
    return McpError(ErrorData(code=INTERNAL_ERROR, message=msg))


def _image_content(path: Path) -> ImageContent:
    data = base64.b64encode(path.read_bytes()).decode()
    return ImageContent(type="image", data=data, mimeType="image/jpeg")


def _format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _analysis_result_text(analyses: list[str], timestamps: list[float], video_id: str) -> TextContent:
    lines = [f"Analyzed {len(analyses)} frame(s) from video {video_id}"]
    for text, ts in zip(analyses, timestamps, strict=True):
        lines.append("")
        lines.append(f"[{_format_timestamp(ts)}]")
        lines.append(text)
    return TextContent(type="text", text="\n".join(lines))


def _frames_result_text(
    paths: list[Path],
    timestamps: list[float],
    video_id: str,
    output_dir: Path,
    output_dir_note: str | None = None,
) -> TextContent:
    lines = [f"Extracted {len(paths)} frame(s) from video {video_id}"]
    lines.append(f"Output directory: {output_dir}")
    if output_dir_note is not None:
        lines.append(output_dir_note)
    lines.append("")
    lines.append("Frame files:")
    for p, ts in zip(paths, timestamps, strict=True):
        lines.append(f"  [{_format_timestamp(ts)}] {p}")
    lines.append("")
    lines.append(
        "Note: If your model does not support vision, do NOT Read frame files. "
        "Embed as links with captions from transcript context instead. "
        "If your model supports vision, you may Read individual frames to inspect them."
    )
    return TextContent(type="text", text="\n".join(lines))


def _get_save_dir(output_dir: str | None, video_id: str) -> Path:
    save_dir = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR / video_id
    save_dir = save_dir.expanduser().resolve(strict=False)
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir


def _output_dir_note(output_dir: str | None) -> str | None:
    if output_dir is None:
        return None
    path = Path(output_dir).expanduser()
    if path.is_absolute():
        return None
    cwd = Path.cwd().resolve(strict=False)
    return f"Relative output_dir was resolved against MCP server working directory: {cwd}"


def _analyze_frames(
    paths: list[Path],
    vision_prompt: str | None,
    vision_model: str | None,
    vision_base_url: str | None = None,
    vision_api_key: str | None = None,
) -> list[str]:
    try:
        return [
            analyze_image_path(path, "image/jpeg", vision_prompt, vision_model, vision_base_url, vision_api_key)
            for path in paths
        ]
    except (VisionConfigError, VisionAPIError) as exc:
        raise _err(str(exc)) from exc


def _download_error_hint() -> str:
    return (
        "If YouTube returned a bot-check, captcha, sign-in, or anti-abuse message, "
        "retry the same tool call with the proxy parameter, "
        "or with a different proxy if proxy was already used, "
        "or try cookies_from_browser (e.g. 'chrome', 'firefox'), or try client='android'."
    )


def _frame_failure_message(exc: DownloadError) -> str:
    return f"Frame extraction failed: {exc}. {_download_error_hint()}"


def _normalize_source_mode(download_first: bool | str) -> _FrameSourceMode:
    if isinstance(download_first, bool):
        return "always" if download_first else "never"
    if isinstance(download_first, str):
        value = download_first.strip().lower()
        if value == "auto":
            return "auto"
        if value == "always":
            return "always"
        if value == "never":
            return "never"
        if value in {"true", "yes", "1"}:
            return "always"
        if value in {"false", "no", "0"}:
            return "never"
    raise _err("download_first must be 'auto', 'always', 'never', true, or false")


def _resolve_direct_video_source(
    video_id: str,
    proxy: str | None,
    cookies_from_browser: str | None,
    client: str,
) -> _VideoSource:
    try:
        stream_url, duration = get_stream_url(
            video_id,
            proxy=proxy,
            cookies_from_browser=cookies_from_browser,
            client=client,
        )
        return _VideoSource(stream_url, "direct", duration=duration)
    except DownloadError as exc:
        raise DownloadError(f"Failed to get stream URL: {exc}") from exc


def _resolve_downloaded_video_source(
    video_id: str,
    proxy: str | None,
    cookies_from_browser: str | None,
    client: str,
) -> _VideoSource:
    temp_dir = Path(tempfile.mkdtemp(prefix="yt_video_"))
    try:
        video_path = download_frame_source(
            video_id,
            temp_dir,
            proxy=proxy,
            cookies_from_browser=cookies_from_browser,
            client=client,
        )
        return _VideoSource(str(video_path), "downloaded", temp_dir=temp_dir)
    except DownloadError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise DownloadError(f"Failed to download frame source: {exc}") from exc


def _run_source_operation[T](source: _VideoSource, operation: Callable[[_VideoSource], T]) -> T:
    try:
        return operation(source)
    finally:
        if source.temp_dir is not None:
            shutil.rmtree(source.temp_dir, ignore_errors=True)


def _run_with_video_source[T](
    video_id: str,
    source_mode: _FrameSourceMode,
    proxy: str | None,
    cookies_from_browser: str | None,
    client: str,
    operation: Callable[[_VideoSource], T],
) -> T:
    if source_mode == "always":
        return _run_source_operation(
            _resolve_downloaded_video_source(video_id, proxy, cookies_from_browser, client),
            operation,
        )
    if source_mode == "never":
        return _run_source_operation(
            _resolve_direct_video_source(video_id, proxy, cookies_from_browser, client),
            operation,
        )

    try:
        return _run_source_operation(
            _resolve_direct_video_source(video_id, proxy, cookies_from_browser, client),
            operation,
        )
    except FFmpegNotFoundError:
        raise
    except DownloadError as direct_exc:
        try:
            return _run_source_operation(
                _resolve_downloaded_video_source(video_id, proxy, cookies_from_browser, client),
                operation,
            )
        except FFmpegNotFoundError:
            raise
        except DownloadError as fallback_exc:
            raise DownloadError(
                f"direct stream failed: {direct_exc}; local fallback failed: {fallback_exc}"
            ) from fallback_exc


def extract_video_frame(
    url_or_id: str,
    timestamp: float,
    output_dir: str | None = None,
    max_width: int | None = None,
    jpeg_quality: int = 5,
    ffmpeg_timeout: float = 60.0,
    return_images: bool = False,
    vision_analysis: bool = False,
    vision_prompt: str | None = None,
    vision_model: str | None = None,
    vision_base_url: str | None = None,
    vision_api_key: str | None = None,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
    download_first: bool | str = "auto",
) -> CallToolResult:
    """Extract a single frame from a YouTube video at a specific timestamp.

    By default saves frame as JPEG file and returns the file path.
    Set return_images=True to get inline base64 image data instead
    (for vision-capable models like Claude or GPT-4o).

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamp: Timestamp in seconds (e.g., 195.0 for 3:15).
        output_dir: Directory to save frame. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. None = original size.
        jpeg_quality: JPEG quality (2=best, 31=worst). Defaults to 5.
        return_images: True = return inline images (vision models), False = file paths.
        vision_analysis: True = return text description from configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override.
        vision_api_key: Optional vision API key override.
        proxy: Optional proxy URL (e.g. http://user:pass@host:port).
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Examples: "chrome", "firefox", "edge", "safari".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
        download_first: "auto" (default) tries direct stream extraction first and
            falls back to a local low-resolution source on stream failure. True or
            "always" downloads first. False or "never" uses direct stream only.

    Returns:
        MCP result with either TextContent (file path) or ImageContent (inline).
    """
    if ffmpeg_timeout <= 0:
        raise _err("ffmpeg_timeout must be positive")
    if vision_analysis and return_images:
        raise _err("vision_analysis cannot be combined with return_images")

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    source_mode = _normalize_source_mode(download_first)

    def _with_source(source: _VideoSource) -> CallToolResult:
        video_source = source.value
        if vision_analysis:
            tmp_dir = Path(tempfile.mkdtemp(prefix="yt_frame_analysis_"))
            try:
                out_path = tmp_dir / "frame.jpg"
                extract_frame(
                    video_source,
                    timestamp,
                    out_path,
                    max_width=max_width,
                    quality=jpeg_quality,
                    ffmpeg_timeout=ffmpeg_timeout,
                    proxy=proxy,
                )
                analyses = _analyze_frames([out_path], vision_prompt, vision_model, vision_base_url, vision_api_key)
                return CallToolResult(content=[_analysis_result_text(analyses, [timestamp], video_id)])
            finally:
                _cleanup_dir(tmp_dir)

        if return_images:
            tmp_dir = Path(tempfile.mkdtemp(prefix="yt_frame_"))
            try:
                out_path = tmp_dir / "frame.jpg"
                extract_frame(
                    video_source,
                    timestamp,
                    out_path,
                    max_width=max_width,
                    quality=jpeg_quality,
                    ffmpeg_timeout=ffmpeg_timeout,
                    proxy=proxy,
                )
                return CallToolResult(content=[_image_content(out_path)])
            finally:
                _cleanup_dir(tmp_dir)
        else:
            save_dir = _get_save_dir(output_dir, video_id)
            out_path = save_dir / f"frame_{timestamp:.0f}.jpg"
            extract_frame(
                video_source,
                timestamp,
                out_path,
                max_width=max_width,
                quality=jpeg_quality,
                ffmpeg_timeout=ffmpeg_timeout,
                proxy=proxy,
            )
            return CallToolResult(
                content=[
                    _frames_result_text(
                        [out_path],
                        [timestamp],
                        video_id,
                        save_dir,
                        _output_dir_note(output_dir),
                    )
                ]
            )

    try:
        return _run_with_video_source(video_id, source_mode, proxy, cookies_from_browser, client, _with_source)
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(_frame_failure_message(exc)) from exc


def extract_video_frames(
    url_or_id: str,
    timestamps: list[float],
    output_dir: str | None = None,
    max_width: int | None = None,
    jpeg_quality: int = 5,
    ffmpeg_timeout: float = 60.0,
    return_images: bool = False,
    vision_analysis: bool = False,
    vision_prompt: str | None = None,
    vision_model: str | None = None,
    vision_base_url: str | None = None,
    vision_api_key: str | None = None,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
    download_first: bool | str = "auto",
) -> CallToolResult:
    """Extract multiple frames from a YouTube video at specified timestamps.

    By default saves frames as JPEG files and returns file paths.
    Set return_images=True to get inline base64 image data instead
    (for vision-capable models). Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamps: List of timestamps in seconds.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. None = original size.
        jpeg_quality: JPEG quality (2=best, 31=worst). Defaults to 5.
        return_images: True = return inline images (vision models), False = file paths.
        vision_analysis: True = return text descriptions from configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override.
        vision_api_key: Optional vision API key override.
        proxy: Optional proxy URL (e.g. http://user:pass@host:port).
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Examples: "chrome", "firefox", "edge", "safari".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
        download_first: "auto" (default) tries direct stream extraction first and
            falls back to a local low-resolution source on stream failure. True or
            "always" downloads first. False or "never" uses direct stream only.

    Returns:
        MCP result with either TextContent (file paths) or ImageContent list (inline).
    """
    if len(timestamps) > _MAX_FRAMES:
        raise _err(f"Too many timestamps ({len(timestamps)}), maximum is {_MAX_FRAMES}")
    if ffmpeg_timeout <= 0:
        raise _err("ffmpeg_timeout must be positive")
    if vision_analysis and return_images:
        raise _err("vision_analysis cannot be combined with return_images")

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    source_mode = _normalize_source_mode(download_first)

    def _with_source(source: _VideoSource) -> CallToolResult:
        video_source = source.value
        if vision_analysis:
            tmp_dir = Path(tempfile.mkdtemp(prefix="yt_frames_analysis_"))
            try:
                paths = extract_frames_batch(
                    video_source,
                    timestamps,
                    tmp_dir,
                    max_width=max_width,
                    quality=jpeg_quality,
                    ffmpeg_timeout=ffmpeg_timeout,
                    proxy=proxy,
                )
                return CallToolResult(
                    content=[
                        _analysis_result_text(
                            _analyze_frames(paths, vision_prompt, vision_model, vision_base_url, vision_api_key),
                            timestamps,
                            video_id,
                        )
                    ]
                )
            finally:
                _cleanup_dir(tmp_dir)

        if return_images:
            tmp_dir = Path(tempfile.mkdtemp(prefix="yt_frames_"))
            try:
                paths = extract_frames_batch(
                    video_source,
                    timestamps,
                    tmp_dir,
                    max_width=max_width,
                    quality=jpeg_quality,
                    ffmpeg_timeout=ffmpeg_timeout,
                    proxy=proxy,
                )
                return CallToolResult(content=[_image_content(p) for p in paths])
            finally:
                _cleanup_dir(tmp_dir)
        else:
            save_dir = _get_save_dir(output_dir, video_id)
            paths = extract_frames_batch(
                video_source,
                timestamps,
                save_dir,
                max_width=max_width,
                quality=jpeg_quality,
                ffmpeg_timeout=ffmpeg_timeout,
                proxy=proxy,
            )
            return CallToolResult(
                content=[
                    _frames_result_text(
                        paths,
                        timestamps,
                        video_id,
                        save_dir,
                        _output_dir_note(output_dir),
                    )
                ]
            )

    try:
        return _run_with_video_source(video_id, source_mode, proxy, cookies_from_browser, client, _with_source)
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(_frame_failure_message(exc)) from exc


def extract_frames_every(
    url_or_id: str,
    interval_sec: float = 30.0,
    max_frames: int = 10,
    output_dir: str | None = None,
    max_width: int | None = None,
    jpeg_quality: int = 5,
    ffmpeg_timeout: float = 60.0,
    return_images: bool = False,
    vision_analysis: bool = False,
    vision_prompt: str | None = None,
    vision_model: str | None = None,
    vision_base_url: str | None = None,
    vision_api_key: str | None = None,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
    download_first: bool | str = "auto",
) -> CallToolResult:
    """Extract frames from a YouTube video at regular intervals.

    By default saves frames as JPEG files and returns file paths.
    Set return_images=True to get inline base64 image data instead
    (for vision-capable models). Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        interval_sec: Interval between frames in seconds. Defaults to 30.
        max_frames: Maximum number of frames to extract. Defaults to 10, max 30.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. None = original size.
        jpeg_quality: JPEG quality (2=best, 31=worst). Defaults to 5.
        return_images: True = return inline images (vision models), False = file paths.
        vision_analysis: True = return text descriptions from configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override.
        vision_api_key: Optional vision API key override.
        proxy: Optional proxy URL (e.g. http://user:pass@host:port).
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Examples: "chrome", "firefox", "edge", "safari".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
        download_first: "auto" (default) tries direct stream extraction first and
            falls back to a local low-resolution source on stream failure. True or
            "always" downloads first. False or "never" uses direct stream only.

    Returns:
        MCP result with either TextContent (file paths) or ImageContent list (inline).
    """
    if max_frames > _MAX_FRAMES:
        raise _err(f"max_frames ({max_frames}) exceeds limit ({_MAX_FRAMES})")
    if interval_sec <= 0:
        raise _err("interval_sec must be positive")
    if ffmpeg_timeout <= 0:
        raise _err("ffmpeg_timeout must be positive")
    if vision_analysis and return_images:
        raise _err("vision_analysis cannot be combined with return_images")

    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as exc:
        raise _err(str(exc)) from exc

    source_mode = _normalize_source_mode(download_first)

    def _with_source(source: _VideoSource) -> CallToolResult:
        video_source = source.value
        try:
            if source.kind == "downloaded":
                duration = get_media_duration(video_source, ffmpeg_timeout=ffmpeg_timeout)
            else:
                if source.duration is None:
                    raise DownloadError("direct stream duration is unavailable")
                duration = source.duration
        except DownloadError as exc:
            raise DownloadError(f"Failed to get video info: {exc}") from exc

        count = min(int(duration / interval_sec), max_frames)
        if count == 0:
            raise _err(f"Video duration ({duration:.1f}s) is shorter than interval ({interval_sec}s)")

        timestamps = [i * interval_sec for i in range(count)]

        if vision_analysis:
            tmp_dir = Path(tempfile.mkdtemp(prefix="yt_interval_analysis_"))
            try:
                paths = extract_frames_batch(
                    video_source,
                    timestamps,
                    tmp_dir,
                    max_width=max_width,
                    quality=jpeg_quality,
                    ffmpeg_timeout=ffmpeg_timeout,
                    proxy=proxy,
                )
                return CallToolResult(
                    content=[
                        _analysis_result_text(
                            _analyze_frames(paths, vision_prompt, vision_model, vision_base_url, vision_api_key),
                            timestamps,
                            video_id,
                        )
                    ]
                )
            finally:
                _cleanup_dir(tmp_dir)

        if return_images:
            tmp_dir = Path(tempfile.mkdtemp(prefix="yt_interval_"))
            try:
                paths = extract_frames_batch(
                    video_source,
                    timestamps,
                    tmp_dir,
                    max_width=max_width,
                    quality=jpeg_quality,
                    ffmpeg_timeout=ffmpeg_timeout,
                    proxy=proxy,
                )
                return CallToolResult(content=[_image_content(p) for p in paths])
            finally:
                _cleanup_dir(tmp_dir)
        else:
            save_dir = _get_save_dir(output_dir, video_id)
            paths = extract_frames_batch(
                video_source,
                timestamps,
                save_dir,
                max_width=max_width,
                quality=jpeg_quality,
                ffmpeg_timeout=ffmpeg_timeout,
                proxy=proxy,
            )
            return CallToolResult(
                content=[
                    _frames_result_text(
                        paths,
                        timestamps,
                        video_id,
                        save_dir,
                        _output_dir_note(output_dir),
                    )
                ]
            )

    try:
        return _run_with_video_source(video_id, source_mode, proxy, cookies_from_browser, client, _with_source)
    except FFmpegNotFoundError as exc:
        raise _err(str(exc)) from exc
    except DownloadError as exc:
        raise _err(_frame_failure_message(exc)) from exc
