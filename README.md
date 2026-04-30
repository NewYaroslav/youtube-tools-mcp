# youtube-tools-mcp

Python MCP server for YouTube transcripts, cleanup, frame extraction, and video/audio download.

## Overview

`youtube-tools-mcp` is a Python MCP server that helps AI agents analyze YouTube videos. It provides tools for:

- extracting YouTube transcripts / auto-subtitles with timestamps;
- cleaning noisy auto-generated subtitles;
- extracting video frames at specific timestamps or intervals;
- downloading video files in various quality presets;
- downloading audio-only files (mp3, m4a, opus, wav);
- preparing video material for summaries, notes, and research workflows.

Designed for Claude Code, VSCodium, and any MCP-compatible agent.

## Tools

| Tool | Description |
|---|---|
| `get_youtube_transcript` | Extract transcript/subtitles from a YouTube video |
| `clean_transcript` | Clean and format auto-generated transcript text |
| `extract_video_frame` | Extract a single frame at a specific timestamp |
| `extract_video_frames` | Extract multiple frames at specified timestamps |
| `extract_frames_every` | Extract frames at regular intervals |
| `download_video` | Download a YouTube video (best, 720p, 480p, 360p) |
| `download_audio` | Download audio only (mp3, m4a, opus, wav) |

## Installation

### Local development

```bash
git clone https://github.com/NewYaroslav/youtube-tools-mcp.git
cd youtube-tools-mcp
uv sync --extra dev
```

Run the server:

```bash
uv run python -m youtube_tools_mcp.server
```

Or directly:

```bash
py -X utf8 -m youtube_tools_mcp.server
```

### Via uvx (from GitHub)

```bash
claude mcp add youtube-tools --scope user -- uvx --from git+https://github.com/NewYaroslav/youtube-tools-mcp youtube-tools-mcp
```

### Claude Desktop config

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "youtube-tools": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/NewYaroslav/youtube-tools-mcp",
        "youtube-tools-mcp"
      ]
    }
  }
}
```

### VSCodium / VS Code

Add to `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "youtube-tools": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/NewYaroslav/youtube-tools-mcp",
        "youtube-tools-mcp"
      ]
    }
  },
  "enabled": ["youtube-tools"]
}
```

## System Requirements

- Python 3.12+
- **ffmpeg** — required for frame extraction and audio download. Transcript, cleanup, and video download tools work without it.

Install ffmpeg:

| Platform | Command |
|---|---|
| Windows | `winget install ffmpeg` or `choco install ffmpeg` |
| macOS | `brew install ffmpeg` |
| Linux | `sudo apt install ffmpeg` or `sudo dnf install ffmpeg` |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `YOUTUBE_API_KEY` | No | Enables YouTube Data API features (metadata, search). Core tools work without it. |

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format .
uv run pytest
```

### Local `.mcp.json` for dev testing

Create `.mcp.json` in the project root (gitignored) to run the server locally alongside other MCP tools:

```json
{
  "mcpServers": {
    "youtube-tools": {
      "command": "uv",
      "args": ["run", "python", "-m", "youtube_tools_mcp.server"]
    },
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    }
  }
}
```

## License

MIT
