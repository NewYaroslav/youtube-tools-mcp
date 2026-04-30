# youtube-tools-mcp — Agent Context

## Project Overview
Python MCP server for YouTube transcripts, cleanup, frame extraction, and video/audio download.
Exposes tools via stdio transport using the `mcp` Python SDK (FastMCP).

## Architecture

```
youtube-tools-mcp/
  src/youtube_tools_mcp/
    __init__.py
    server.py              # MCP server entrypoint, tool registration (FastMCP)
    tools/
      __init__.py
      transcript.py        # get_youtube_transcript tool logic
      cleanup.py           # clean_transcript tool logic
      frames.py            # extract_video_frame, extract_video_frames, extract_frames_every
      download.py          # download_video_file, download_audio_file
    youtube/
      __init__.py
      transcript.py        # TranscriptFetcher (youtube-transcript-api wrapper)
      downloader.py        # get_stream_url, get_video_duration, extract_frame, extract_frames_batch, download_video, download_audio
      client.py            # YouTube Data API client (optional YOUTUBE_API_KEY) — not yet implemented
    utils/
      __init__.py
      text.py              # text cleaning/normalization helpers
      url.py               # YouTube URL parsing, video ID extraction
  tests/
    conftest.py
    utils/test_url.py
    utils/test_text.py
    youtube/test_transcript.py
    youtube/test_downloader.py
    tools/test_transcript.py
    tools/test_cleanup.py
    tools/test_frames.py
  pyproject.toml
```

## Key Dependencies
- `mcp>=1.12.0,<2.0.0` — Python MCP SDK (FastMCP, stdio transport, tool decorators)
- `youtube-transcript-api>=1.0.0` — fetch transcripts without API key
- `yt-dlp>=2024.1.0` — download video/audio, extract frames
- `google-api-python-client` — YouTube Data API (optional, requires YOUTUBE_API_KEY)

## MCP Tools

### get_youtube_transcript(url_or_id, languages=["ru","en"])
Input: video URL or ID, optional language code list
Output: transcript text with timestamps [MM:SS] per line
Uses: youtube-transcript-api (no key required)

### clean_transcript(text, *, remove_fillers=True, fix_casing=True, merge_lines=True, remove_duplicates=True)
Input: raw text, optional cleanup flags
Output: cleaned/normalized text
Uses: internal text utils (no external API)

### extract_video_frame(url_or_id, timestamp)
Input: video URL or ID, timestamp in seconds
Output: CallToolResult with base64 JPEG image
Uses: yt-dlp + ffmpeg (no key required)

### extract_video_frames(url_or_id, timestamps)
Input: video URL or ID, list of timestamps in seconds
Output: CallToolResult with multiple base64 JPEG images
Uses: yt-dlp + ffmpeg, max 30 frames per call

### extract_frames_every(url_or_id, interval_sec=30, max_frames=10)
Input: video URL or ID, interval in seconds, max frame count
Output: CallToolResult with base64 JPEG images at regular intervals
Uses: yt-dlp + ffmpeg, max 30 frames per call

### download_video(url_or_id, output_dir=".", quality="720p")
Input: video URL or ID, output directory, quality preset ("best", "720p", "480p", "360p")
Output: absolute path to downloaded MP4 file
Uses: yt-dlp (no ffmpeg required)

### download_audio(url_or_id, output_dir=".", audio_format="mp3")
Input: video URL or ID, output directory, audio format ("mp3", "m4a", "opus", "wav")
Output: absolute path to downloaded audio file
Uses: yt-dlp + ffmpeg (required for audio extraction/conversion)

## Environment Variables
- `YOUTUBE_API_KEY` — optional, enables YouTube Data API features (not yet implemented)
- Read via `os.environ.get("YOUTUBE_API_KEY")` with None fallback
- Never hardcode, never log, never include in error messages

## Development Commands
- `uv run python -m youtube_tools_mcp.server` — run the MCP server
- `uv run ruff check .` — lint
- `uv run ruff format .` — format
- `uv run pytest` — run tests (117 tests)
- `uv add <package>` — add dependency

## Testing Strategy
- Unit tests for each tool with mocked YouTube responses (117 tests)
- All external calls (youtube-transcript-api, yt-dlp, ffmpeg) are mocked
- No network calls in test suite
- `pytest-asyncio` for async MCP handler tests

## Error Handling
- YouTube API errors -> graceful degradation, never crash the MCP server
- Missing YOUTUBE_API_KEY -> skip Data API features, transcript-only mode
- Invalid video URL/ID -> McpError with descriptive message
- ffmpeg not found -> McpError with installation instructions
- Network failures -> error in tool result, server stays alive

## Commit Conventions
See `agents/commit-conventions.md` for full rules.
Format: `type(scope): short summary` with descriptive body.
