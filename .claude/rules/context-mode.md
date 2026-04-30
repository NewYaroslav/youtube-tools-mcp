# Context-Mode Rules

## Prefer built-in tools over Bash
Use Read/Write/Edit/Glob/Grep for file operations instead of Bash commands.
These provide better UX, permission handling, and reviewability.

## Forbidden (use built-in tools instead)
1. Bash commands producing >20 lines output — use Grep/Glob with filters
2. `cat`/`head`/`tail` — use Read tool
3. `grep`/`rg`/`find` — use Grep/Glob tools
4. curl/wget in Bash — use Fetch MCP or Tavily

## Allowed Bash
git, mkdir, rm, mv, cd, uv, python, pytest, ruff, short commands (<20 lines output)
