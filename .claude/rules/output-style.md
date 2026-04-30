# Style & Git

## Response Rules (verified each output)
1. Language: Russian ONLY — even for technical queries. English ONLY if user writes in English.
2. Emoji: ZERO — never in text, code, or placeholders. No exceptions.
3. Summary tail: NEVER append "what I did" at end of response.
4. Explanation: max 5 sentences. Need more -> bulleted list.
5. Scope: NEVER edit files outside the stated task.
6. Comments: NEVER add comments to lines you did not change.

## Git Commits
- First line: <=50 chars, conventional prefix (fix:/feat:/refactor:/docs:/test:/chore:), imperative mood
- Body: explain WHY not WHAT
- Prefer new commit over amend
- NEVER force-push to main/master

## Python Style
- Type hints on all function signatures, `from __future__ import annotations`
- `ruff check` + `ruff format` before commits — no `# type: ignore`
- Imports: stdlib > third-party > local
- Naming: snake_case for functions/vars, PascalCase for classes
- Async: use `async def` for MCP tool handlers, `pytest-asyncio` for tests

## Notepad
Write when: choice from 2+ approaches, trade-off accepted, workaround applied.
