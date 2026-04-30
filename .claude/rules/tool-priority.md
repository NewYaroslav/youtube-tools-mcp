# Tool Priority Chain

## Web Search (non-Anthropic provider override)
Native WebSearch does NOT work with non-Anthropic providers (Fireworks, OpenRouter, etc.).
Use MCP search tools instead. Priority:
1. Tavily MCP (`mcp__tavily__tavily_search`) — requires API key
2. Fetch MCP (`mcp__fetch__fetch_markdown`) — for known URLs only
NEVER use built-in WebSearch tool — it will fail with non-Anthropic providers.

## General Ordering (use first match)
1. Context7 — SDK/API docs before web search
2. Read/Write/Edit/Glob/Grep — file operations
3. LSP (pyright) — symbols, definitions, diagnostics
4. GitHub plugin — repo ops, issues, PRs
5. Tavily — web search
6. Fetch MCP — URL content (fallback: tavily-extract)
7. Serena — code analysis, symbol search

## Error Recovery
- MCP server fail: retry once, then fallback to next in chain
- LSP disconnected: Grep/Glob fallback immediately
- Agent error: retry with clearer prompt once, escalate after 2nd failure
- WebSearch tool call fails: use Tavily MCP instead
