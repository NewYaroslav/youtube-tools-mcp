<!-- USER RULES -->
<!-- Rules are loaded from ~/.claude/rules/ via auto-inclusion. -->
<!-- Priority: rules/ files > this file > managed defaults -->

<!-- OMC:START -->
<!-- OMC:VERSION:4.11.5 -->

# oh-my-claudecode (OMC) — Multi-Agent Orchestration

## Operating Rules
- Delegate specialized work to agents. Work directly ONLY for: trivial ops, single commands, edits to ~/.claude/** or .omc/**
- Evidence > assumptions: verify outcomes before claiming completion
- Lightest path that preserves quality
- Official docs before implementing with SDKs/frameworks

## Skills & Triggers
Invoke via `/oh-my-claudecode:<name>`. Auto-detect keywords:
- "autopilot"->autopilot | "ralph"->ralph | "ulw"->ultrawork | "ralplan"->ralplan
- "deep interview"->deep-interview | "deslop"/"anti-slop"->ai-slop-cleaner
- "ccg"->ccg | "cancelomc"->cancel
- Team orchestration: explicit via `/team`
- Agent catalog and full registry: `omc-reference` skill

## Execution Protocol
- Broad requests: explore first, then plan. 2+ independent tasks in parallel.
- Authoring and review: SEPARATE passes. NEVER self-approve in same context.
- Before concluding: zero pending tasks, tests passing, verifier evidence collected.
- Background: `run_in_background` for builds/tests.

## Verification
- small->haiku | standard->sonnet | large/security->opus
- Fails? Keep iterating.

## Hooks & Cancellation
- `<system-reminder>` tags from hooks. Patterns: `hook success: Success`, `[MAGIC KEYWORD: ...]`, `The boulder never stops`
- `/oh-my-claudecode:cancel` ends modes. Cancel when done+verified or blocked.

## State Paths
`.omc/state/`, `.omc/notepad.md`, `.omc/plans/`, `.omc/research/`, `.omc/logs/`

## Setup
Say "setup omc" or `/oh-my-claudecode:omc-setup`

## WebSearch Override
Native WebSearch does NOT work with non-Anthropic providers.
Use MCP search tools instead: Tavily MCP > Fetch MCP.
See `.claude/rules/tool-priority.md` for full priority chain.

---

# youtube-tools-mcp — Project Rules

## What
Python MCP server exposing YouTube tools: transcript extraction, text cleanup, frame extraction.

## Tech Stack
- Runtime: Python 3.12+
- Package manager: `uv` (uv init, uv add, uv run, uvx)
- MCP SDK: `mcp` Python package (stdio transport)
- YouTube: `youtube-transcript-api` (no key), `yt-dlp` (no key)
- YouTube Data API: optional, requires `YOUTUBE_API_KEY` env var (metadata, search)
- Lint/format: `ruff`
- Testing: `pytest`
- Type checking: built-in (type hints required on all signatures)

## MCP Tools (server exposes)
- `get_transcript` — extract transcript/subtitles from a YouTube video
- `cleanup_text` — clean and format transcript text
- `extract_frames` — pull individual frames from a YouTube video

## YouTube API Key
Core tools work without `YOUTUBE_API_KEY`. If set, additional tools become available (video metadata, search).
Never hardcode the key — always read from `os.environ["YOUTUBE_API_KEY"]` with graceful fallback.

## Python Conventions
- Type hints on all function signatures, `from __future__ import annotations`
- `ruff check` + `ruff format` before commits
- `pytest` for tests, `pytest-asyncio` for async MCP handlers
- Imports: stdlib > third-party > local
- snake_case for functions/vars, PascalCase for classes
- No `# type: ignore` — fix the type instead
