from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from youtube_tools_mcp.tools.cleanup import clean_transcript as _clean_transcript
from youtube_tools_mcp.tools.download import (
    download_audio_file as _download_audio_file,
)
from youtube_tools_mcp.tools.download import (
    download_video_file as _download_video_file,
)
from youtube_tools_mcp.tools.frames import (
    extract_frames_every as _extract_frames_every,
)
from youtube_tools_mcp.tools.frames import (
    extract_video_frame as _extract_video_frame,
)
from youtube_tools_mcp.tools.frames import (
    extract_video_frames as _extract_video_frames,
)
from youtube_tools_mcp.tools.images import (
    analyze_image_file as _analyze_image_file,
)
from youtube_tools_mcp.tools.images import (
    read_image_file as _read_image_file,
)
from youtube_tools_mcp.tools.listing import (
    list_channel_playlists as _list_channel_playlists,
)
from youtube_tools_mcp.tools.listing import (
    list_channel_videos as _list_channel_videos,
)
from youtube_tools_mcp.tools.listing import (
    list_playlist_videos as _list_playlist_videos,
)
from youtube_tools_mcp.tools.metadata import get_youtube_video_metadata as _get_youtube_video_metadata
from youtube_tools_mcp.tools.transcript import get_youtube_transcript as _get_youtube_transcript
from youtube_tools_mcp.tools.video_context import get_youtube_video_context as _get_youtube_video_context

mcp = FastMCP(
    "youtube-tools-mcp",
    instructions=(
        "MCP server for YouTube transcript extraction, metadata, text cleanup, "
        "frame extraction, and video/audio download. "
        "If YouTube blocks a request with a bot-check, captcha, sign-in, "
        "or anti-abuse message, retry the same tool call with the proxy parameter. "
        "Example proxy format: http://user:pass@host:port. "
        "If proxy does not help, try cookies_from_browser (e.g. 'chrome', 'firefox'). "
        "You can also try client='android' or client='ios' to spoof a mobile client."
    ),
)


@mcp.tool()
def get_youtube_transcript(
    url_or_id: str,
    languages: list[str] | None = None,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """Extract transcript/subtitles from a YouTube video.

    Provide a YouTube URL or video ID and optional language preference list.
    Returns timestamped transcript text with format [MM:SS] text per line.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        languages: Preferred language codes in priority order. Defaults to ["ru", "en"].
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
    """
    return _get_youtube_transcript(url_or_id, languages, proxy, cookies_from_browser, client)


@mcp.tool()
def get_youtube_video_metadata(
    url_or_id: str,
    include_channel_description: bool = True,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """Fetch YouTube video metadata and channel information.

    Returns JSON with video title, description, channel URL,
    and channel description when available.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        include_channel_description: Try to include channel description when available.
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
    """
    return _get_youtube_video_metadata(url_or_id, include_channel_description, proxy, cookies_from_browser, client)


@mcp.tool()
def get_youtube_video_context(
    url_or_id: str,
    languages: list[str] | None = None,
    include_channel_description: bool = True,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """Fetch transcript plus video and channel metadata.

    Returns JSON with metadata and timestamped transcript text.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        languages: Preferred transcript language codes. Defaults to ["ru", "en"].
        include_channel_description: Try to include channel description when available.
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
    """
    return _get_youtube_video_context(
        url_or_id,
        languages,
        include_channel_description,
        proxy,
        cookies_from_browser,
        client,
    )


@mcp.tool()
def clean_transcript(
    text: str,
    *,
    remove_fillers: bool = True,
    fix_casing: bool = True,
    merge_lines: bool = True,
    remove_duplicates: bool = True,
) -> str:
    """Clean and format auto-generated transcript text.

    Removes filler words, fixes capitalization, merges broken subtitle lines,
    and removes duplicate lines.

    Args:
        text: Raw transcript text (with or without timestamps).
        remove_fillers: Remove filler words (hmm, um, uh, etc.).
        fix_casing: Capitalize first letter of each sentence.
        merge_lines: Merge lines broken mid-sentence.
        remove_duplicates: Remove consecutive duplicate text lines.
    """
    return _clean_transcript(
        text,
        remove_fillers=remove_fillers,
        fix_casing=fix_casing,
        merge_lines=merge_lines,
        remove_duplicates=remove_duplicates,
    )


@mcp.tool()
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
    download_first: bool = True,
) -> CallToolResult:
    """Extract a single frame from a YouTube video at a specific timestamp.

    By default saves frame as JPEG and returns the file path.
    Set return_images=True to return inline image data (for vision-capable models).
    Requires ffmpeg to be installed on the system.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamp: Timestamp in seconds (e.g., 195.0 for 3:15).
        output_dir: Directory to save frame. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. None = original size.
        jpeg_quality: JPEG quality (2=best, 31=worst). Defaults to 5.
        ffmpeg_timeout: Timeout for each ffmpeg subprocess in seconds. Defaults to 60.
        return_images: True = inline images (vision models), False = file paths.
        vision_analysis: True = return text description from configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override.
            Useful when the default provider (e.g. Aliyun) is blocked or rate-limited.
            Example: https://api.openai.com/v1
        vision_api_key: Optional vision API key override.
            Useful when the default provider is blocked or rate-limited.
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
        download_first: Download a small local video source before extracting frames.
            Slower but bypasses CDN stream restrictions when direct streaming fails.
            Defaults to True.
    """
    return _extract_video_frame(
        url_or_id=url_or_id,
        timestamp=timestamp,
        output_dir=output_dir,
        max_width=max_width,
        jpeg_quality=jpeg_quality,
        ffmpeg_timeout=ffmpeg_timeout,
        return_images=return_images,
        vision_analysis=vision_analysis,
        vision_prompt=vision_prompt,
        vision_model=vision_model,
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        proxy=proxy,
        cookies_from_browser=cookies_from_browser,
        client=client,
        download_first=download_first,
    )


@mcp.tool()
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
    download_first: bool = True,
) -> CallToolResult:
    """Extract multiple frames from a YouTube video at specified timestamps.

    By default saves frames as JPEG files and returns file paths.
    Set return_images=True to return inline image data (for vision-capable models).
    Requires ffmpeg to be installed on the system. Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        timestamps: List of timestamps in seconds.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. None = original size.
        jpeg_quality: JPEG quality (2=best, 31=worst). Defaults to 5.
        ffmpeg_timeout: Timeout for each ffmpeg subprocess in seconds. Defaults to 60.
        return_images: True = inline images (vision models), False = file paths.
        vision_analysis: True = return text descriptions from configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override.
            Useful when the default provider (e.g. Aliyun) is blocked or rate-limited.
            Example: https://api.openai.com/v1
        vision_api_key: Optional vision API key override.
            Useful when the default provider is blocked or rate-limited.
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
        download_first: Download a small local video source before extracting frames.
            Slower but bypasses CDN stream restrictions when direct streaming fails.
            Defaults to True.
    """
    return _extract_video_frames(
        url_or_id=url_or_id,
        timestamps=timestamps,
        output_dir=output_dir,
        max_width=max_width,
        jpeg_quality=jpeg_quality,
        ffmpeg_timeout=ffmpeg_timeout,
        return_images=return_images,
        vision_analysis=vision_analysis,
        vision_prompt=vision_prompt,
        vision_model=vision_model,
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        proxy=proxy,
        cookies_from_browser=cookies_from_browser,
        client=client,
        download_first=download_first,
    )


@mcp.tool()
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
    download_first: bool = True,
) -> CallToolResult:
    """Extract frames from a YouTube video at regular intervals.

    By default saves frames as JPEG files and returns file paths.
    Set return_images=True to return inline image data (for vision-capable models).
    Requires ffmpeg to be installed on the system. Maximum 30 frames per call.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        interval_sec: Interval between frames in seconds. Defaults to 30.
        max_frames: Maximum number of frames to extract. Defaults to 10, max 30.
        output_dir: Directory to save frames. Defaults to system temp/yt-frames.
        max_width: Maximum frame width in pixels. None = original size.
        jpeg_quality: JPEG quality (2=best, 31=worst). Defaults to 5.
        ffmpeg_timeout: Timeout for each ffmpeg subprocess in seconds. Defaults to 60.
        return_images: True = inline images (vision models), False = file paths.
        vision_analysis: True = return text descriptions from configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override.
            Useful when the default provider (e.g. Aliyun) is blocked or rate-limited.
            Example: https://api.openai.com/v1
        vision_api_key: Optional vision API key override.
            Useful when the default provider is blocked or rate-limited.
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
        download_first: Download a small local video source before extracting frames.
            Slower but bypasses CDN stream restrictions when direct streaming fails.
            Defaults to True.
    """
    return _extract_frames_every(
        url_or_id=url_or_id,
        interval_sec=interval_sec,
        max_frames=max_frames,
        output_dir=output_dir,
        max_width=max_width,
        jpeg_quality=jpeg_quality,
        ffmpeg_timeout=ffmpeg_timeout,
        return_images=return_images,
        vision_analysis=vision_analysis,
        vision_prompt=vision_prompt,
        vision_model=vision_model,
        vision_base_url=vision_base_url,
        vision_api_key=vision_api_key,
        proxy=proxy,
        cookies_from_browser=cookies_from_browser,
        client=client,
        download_first=download_first,
    )


@mcp.tool()
def read_image_file(
    path: str,
    vision_analysis: bool = False,
    vision_prompt: str | None = None,
    vision_model: str | None = None,
    vision_base_url: str | None = None,
    vision_api_key: str | None = None,
) -> CallToolResult:
    """Read a local image file as inline image data or text analysis.

    Use vision_analysis=True when MCP image results are visible in UI but not passed to the model.
    Supports Unicode paths, including Cyrillic filenames and directories.

    Args:
        path: Local image file path (.jpg, .jpeg, .png, .gif, .webp).
        vision_analysis: True = return text description from configured vision model.
        vision_prompt: Optional prompt for vision analysis.
        vision_model: Optional model override for vision analysis.
        vision_base_url: Optional vision API base URL override.
            Useful when the default provider (e.g. Aliyun) is blocked or rate-limited.
            Example: https://api.openai.com/v1
        vision_api_key: Optional vision API key override.
            Useful when the default provider is blocked or rate-limited.
    """
    return _read_image_file(path, vision_analysis, vision_prompt, vision_model, vision_base_url, vision_api_key)


@mcp.tool()
def analyze_image_file(
    path: str,
    prompt: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> CallToolResult:
    """Analyze a local image file with a configured vision model and return text.

    Args:
        path: Local image file path (.jpg, .jpeg, .png, .gif, .webp).
        prompt: Optional analysis prompt.
        model: Optional vision model override.
        base_url: Optional vision API base URL override.
            Useful when the default provider (e.g. Aliyun) is blocked or rate-limited.
            Example: https://api.openai.com/v1
        api_key: Optional vision API key override.
            Useful when the default provider is blocked or rate-limited.
    """
    return _analyze_image_file(path, prompt, model, base_url, api_key)


@mcp.tool()
def download_video(
    url_or_id: str,
    output_dir: str = ".",
    quality: str = "720p",
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """Download a YouTube video to a local file.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        output_dir: Directory to save the video file. Defaults to current directory.
        quality: Quality preset: "best", "720p", "480p", "360p". Defaults to "720p".
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
    """
    return _download_video_file(url_or_id, output_dir, quality, proxy, cookies_from_browser, client)


@mcp.tool()
def download_audio(
    url_or_id: str,
    output_dir: str = ".",
    audio_format: str = "mp3",
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """Download audio only from a YouTube video to a local file.

    Requires ffmpeg to be installed on the system.

    Args:
        url_or_id: YouTube video URL or 11-character video ID.
        output_dir: Directory to save the audio file. Defaults to current directory.
        audio_format: Output audio format: "mp3", "m4a", "opus", "wav". Defaults to "mp3".
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
    """
    return _download_audio_file(url_or_id, output_dir, audio_format, proxy, cookies_from_browser, client)


@mcp.tool()
def list_playlist_videos(
    playlist_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """List videos inside a YouTube playlist.

    Args:
        playlist_id_or_url: YouTube playlist URL or raw playlist ID.
        max_results: Maximum number of videos to return. Defaults to 50.
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
    """
    return _list_playlist_videos(
        playlist_id_or_url,
        max_results,
        proxy,
        cookies_from_browser,
        client,
    )


@mcp.tool()
def list_channel_videos(
    channel_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
    cookies_from_browser: str | None = None,
    client: str = "web",
) -> str:
    """List upload videos from a YouTube channel.

    Args:
        channel_id_or_url: Channel URL, handle (@name), or raw channel ID (UC...).
        max_results: Maximum number of videos to return. Defaults to 50.
        proxy: Proxy URL for YouTube requests, especially when YouTube blocks the request
            with bot-check, captcha, sign-in, or anti-abuse messages.
            Example: http://user:pass@host:port.
        cookies_from_browser: Browser to extract cookies from for YouTube auth.
            Any yt-dlp supported browser or profile syntax works, e.g.
            "chrome", "firefox", "edge", "chrome:Profile 1".
        client: yt-dlp client profile to spoof. Try "android" or "ios" when
            YouTube blocks with bot-check. Defaults to "web".
    """
    return _list_channel_videos(
        channel_id_or_url,
        max_results,
        proxy,
        cookies_from_browser,
        client,
    )


@mcp.tool()
def list_channel_playlists(
    channel_id_or_url: str,
    max_results: int = 50,
    proxy: str | None = None,
) -> str:
    """List playlists owned by a YouTube channel.

    Requires YOUTUBE_API_KEY environment variable.

    Args:
        channel_id_or_url: Channel URL, handle (@name), or raw channel ID (UC...).
        max_results: Maximum number of playlists to return (1..500). Defaults to 50.
        proxy: Proxy URL for YouTube requests.
            Example: http://user:pass@host:port.
    """
    return _list_channel_playlists(channel_id_or_url, max_results, proxy)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
