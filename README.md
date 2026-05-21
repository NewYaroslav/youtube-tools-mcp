# youtube-tools-mcp

Python MCP server for YouTube transcripts, cleanup, frame extraction, and video/audio download.

## Overview

`youtube-tools-mcp` is a Python MCP server that helps AI agents analyze YouTube videos. It provides tools for:

- extracting YouTube transcripts / auto-subtitles with timestamps;
- cleaning noisy auto-generated subtitles;
- extracting video frames at specific timestamps or intervals;
- returning frames either as saved file paths or inline image data;
- reading local image files as MCP image content for vision-capable models;
- downloading video files in various quality presets;
- downloading audio-only files (mp3, m4a, opus, wav);
- preparing video material for summaries, notes, and research workflows.

Designed for Claude Code, VSCodium, and any MCP-compatible agent.

## Tools

| Tool | Description |
|---|---|
| `get_youtube_transcript` | Extract transcript/subtitles from a YouTube video |
| `get_youtube_video_metadata` | Fetch video title, description, channel URL, and channel description when available |
| `get_youtube_video_context` | Fetch video metadata plus transcript in one JSON response |
| `clean_transcript` | Clean and format auto-generated transcript text |
| `extract_video_frame` | Extract a single frame at a specific timestamp |
| `extract_video_frames` | Extract multiple frames at specified timestamps |
| `extract_frames_every` | Extract frames at regular intervals |
| `read_image_file` | Read a local image path and return inline image data or vision analysis |
| `analyze_image_file` | Analyze a local image with a configured vision model |
| `download_video` | Download a YouTube video (best, 720p, 480p, 360p) |
| `download_audio` | Download audio only (mp3, m4a, opus, wav) |

## Metadata and context

`get_youtube_video_metadata` returns JSON with:

- `title`
- `description`
- `channel_title`
- `channel_url`
- `channel_description` (when available)
- `duration` (in seconds)
- `upload_date`

Without `YOUTUBE_API_KEY`, metadata is fetched via `yt-dlp`. With `YOUTUBE_API_KEY`, richer channel descriptions are fetched via YouTube Data API, and the response includes a `warnings` field if the API falls back to `yt-dlp`.

`get_youtube_video_context` returns a single JSON object with:

- `metadata` (same fields as above)
- `transcript` (timestamped transcript text)
- `metadata_error` (only if metadata failed but transcript succeeded)

This means `get_youtube_video_context` is partially resilient: a transcript is still returned even if metadata could not be fetched.

## Frame and image modes

Frame extraction tools support three return modes:

- `return_images=false` (default): save JPEG frames to disk and return file paths as text. Use this with text-only or non-vision models.
- `return_images=true`: return inline MCP `ImageContent` for vision-capable models.
- `vision_analysis=true`: send extracted frames to a configured OpenAI-compatible vision model and return text descriptions.

Frame parameters:

| Parameter | Default | Description |
|---|---|---|
| `output_dir` | system temp directory | Directory for saved frames when `return_images=false` |
| `max_width` | `null` | Optional maximum frame width. `null` keeps original width |
| `jpeg_quality` | `5` | ffmpeg JPEG quality, where `2` is best and `31` is worst |
| `vision_prompt` | default image description prompt | Optional prompt for `vision_analysis=true` |
| `vision_model` | configured env model | Optional model override for `vision_analysis=true` |

`read_image_file(path)` reads an existing local `.jpg`, `.jpeg`, `.png`, `.gif`, or `.webp` file and returns it as inline MCP image content. Set `vision_analysis=true`, or call `analyze_image_file(path)`, to return a text description instead. Unicode paths are supported, including Cyrillic filenames and directories.

`vision_analysis=true` cannot be combined with `return_images=true`.

For non-vision models, use saved paths or `vision_analysis=true` instead of reading image files directly.

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

### Configuring API keys for MCP clients

Core tools work without API keys. Add environment variables only for the features you want to enable:

- `YOUTUBE_API_KEY` enables YouTube Data API features such as metadata and search.
- Vision analysis requires `YOUTUBE_TOOLS_VISION_BASE_URL`, `YOUTUBE_TOOLS_VISION_API_KEY`, and `YOUTUBE_TOOLS_VISION_MODEL`.

For Claude Desktop, VS Code, VSCodium, and other JSON-based MCP clients, add an `env` block to the `youtube-tools` server entry:

```json
{
  "mcpServers": {
    "youtube-tools": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/NewYaroslav/youtube-tools-mcp",
        "youtube-tools-mcp"
      ],
      "env": {
        "YOUTUBE_API_KEY": "your-youtube-api-key",
        "YOUTUBE_TOOLS_VISION_BASE_URL": "https://api.openai.com/v1",
        "YOUTUBE_TOOLS_VISION_API_KEY": "your-vision-api-key",
        "YOUTUBE_TOOLS_VISION_MODEL": "gpt-4o-mini",
        "YOUTUBE_TOOLS_VISION_MAX_TOKENS": "1024"
      }
    }
  }
}
```

Remove variables for features you do not use. Do not commit real API keys or tokens; use user-level MCP config or placeholders for shared config files.

With Claude CLI, pass environment variables before `--`, then pass the server name, command, and arguments:

```bash
claude mcp add --scope user \
  -e YOUTUBE_API_KEY=your-youtube-api-key \
  -e YOUTUBE_TOOLS_VISION_BASE_URL=http://127.0.0.1:8000/v1 \
  -e YOUTUBE_TOOLS_VISION_API_KEY=your-vision-api-key \
  -e YOUTUBE_TOOLS_VISION_MODEL=your-vision-model \
  -e YOUTUBE_TOOLS_VISION_MAX_TOKENS=1024 \
  -- youtube-tools uvx --from git+https://github.com/NewYaroslav/youtube-tools-mcp youtube-tools-mcp
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

Environment variables can be set in the process environment or in a local `.env` file in the project root. `.env` is gitignored.

When installed via `uvx` from an MCP client, the server may run outside your project checkout. In that case, set variables in the MCP client's `env` block or in the parent process environment.

| Variable | Required | Description |
|---|---|---|
| `YOUTUBE_API_KEY` | No | Enables YouTube Data API features (metadata, search). Core tools work without it. |
| `YOUTUBE_TOOLS_VISION_BASE_URL` | For vision analysis | OpenAI-compatible base URL. Falls back to `OPENAI_BASE_URL`, then `ANTHROPIC_BASE_URL` + `/v1`. |
| `YOUTUBE_TOOLS_VISION_API_KEY` | For vision analysis | API token. Falls back to `OPENAI_API_KEY`. |
| `YOUTUBE_TOOLS_VISION_MODEL` | For vision analysis | Vision-capable model. Falls back to `OPENAI_VISION_MODEL`, `ANTHROPIC_TOOL_USE_MODEL`, then `ANTHROPIC_MODEL`. |
| `YOUTUBE_TOOLS_VISION_MAX_TOKENS` | No | Vision completion token budget. Defaults to `1024`; values are clamped from `64` to `4096`. |
| `YOUTUBE_TOOLS_VISION_TIMEOUT` | No | Vision request timeout in seconds. Defaults to `60`. |

### If you installed the MCP server without tokens

Update the existing `youtube-tools` MCP server entry, add the needed `env` variables, and fully restart the MCP client.

For Claude Desktop, VS Code, and VSCodium, edit the existing JSON config entry. For Claude CLI, remove and re-add the server with the needed environment, or edit the generated MCP config if your client supports it.

After updating tokens:

1. Fully restart the MCP client.
2. Confirm the `youtube-tools` server reconnects.
3. Retry the tool that requires the token.

## Development

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format .
uv run pytest
```

### Local `.mcp.json` for dev testing

Create `.mcp.json` in the project root (gitignored) to run the server locally alongside other MCP tools:

For local development, you can also put these values in a project-root `.env` file. Use the `env` block when you want the MCP client configuration to be self-contained.

```json
{
  "mcpServers": {
    "youtube-tools": {
      "command": "uv",
      "args": ["run", "python", "-m", "youtube_tools_mcp.server"],
      "env": {
        "YOUTUBE_API_KEY": "your-youtube-api-key",
        "YOUTUBE_TOOLS_VISION_BASE_URL": "https://api.openai.com/v1",
        "YOUTUBE_TOOLS_VISION_API_KEY": "your-vision-api-key",
        "YOUTUBE_TOOLS_VISION_MODEL": "gpt-4o-mini",
        "YOUTUBE_TOOLS_VISION_MAX_TOKENS": "1024"
      }
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
