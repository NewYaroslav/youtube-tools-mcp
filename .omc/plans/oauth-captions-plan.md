# Plan: OAuth + YouTube Data API captions fallback

## Problem
youtube-transcript-api fails without proxy (IP blocked). yt-dlp also blocked. Need alternative transcript source.

## Solution
YouTube Data API `captions.download` requires OAuth. Add OAuth device flow + captions fallback.

## Files to create/modify

### New files
1. `src/youtube_tools_mcp/youtube/oauth.py` — Google OAuth 2.0 device code flow
   - `run_device_flow(client_id, client_secret)` — interactive CLI auth
   - `get_access_token()` — load stored creds, auto-refresh
   - Token storage: `~/.config/youtube-tools-mcp/oauth.json`
2. `src/youtube_tools_mcp/youtube/captions.py` — Data API captions integration
   - `list_caption_tracks(video_id, api_key)` — captions.list
   - `download_caption(caption_id, access_token)` — captions.download (tfmt=srt)
   - `fetch_transcript_via_data_api(video_id, languages, api_key)` — high-level
   - `_parse_srt(raw)` — SRT -> list of {"text": ..., "start": ..., "duration": ...}

### Modified files
3. `src/youtube_tools_mcp/youtube/transcript.py` — add OAuth fallback
   - `TranscriptFetcher.fetch()` — after youtube-transcript-api fails, try captions via Data API
4. `src/youtube_tools_mcp/tools/transcript.py` — no structural changes needed
5. `pyproject.toml` — add `youtube-tools-mcp-oauth` console script
6. `src/youtube_tools_mcp/youtube/__init__.py` — export new modules if needed

## Env vars
- `YOUTUBE_API_KEY` — already used, for captions.list
- `YOUTUBE_OAUTH_CLIENT_ID` — new, for OAuth
- `YOUTUBE_OAUTH_CLIENT_SECRET` — new, for OAuth

## Flow
1. User runs `YOUTUBE_OAUTH_CLIENT_ID=... YOUTUBE_OAUTH_CLIENT_SECRET=... youtube-tools-mcp-oauth`
2. Opens URL, enters code
3. Refresh token saved to `~/.config/youtube-tools-mcp/oauth.json`
4. MCP server reads token, auto-refreshes access token
5. On transcript request: youtube-transcript-api -> if fails -> captions.list + captions.download -> parse SRT -> format

## Scope
`https://www.googleapis.com/auth/youtube.force-ssl` (required for captions.download)

## Testing
- Unit tests for SRT parser
- Unit tests for OAuth token refresh logic (mocked HTTP)
- Integration: test captions module with mocked API responses
