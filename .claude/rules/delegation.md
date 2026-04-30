# Agent Delegation

## Model Param — Mandatory
EVERY Agent tool call MUST include `model` param:
- haiku: search, exploration, simple lookups
- sonnet: standard implementation, verification
- opus: architecture, refactoring, complex debugging

Missing `model` param = error, not warning. Add it before submitting.

## Routing
| Task type | Agent | Model |
|-----------|-------|-------|
| Code changes | executor | opus (refactor) / sonnet (other) |
| Architecture/debugging | architect | opus |
| Code review | code-reviewer | opus |
| Security review | security-reviewer | sonnet |
| Exploration | explore | haiku |
| Planning | planner | opus |
| Verification | verifier | sonnet |
| Testing (pytest) | test-engineer | sonnet |
| Python lint/typecheck | executor | sonnet |

TaskCreate = conversation tracking only, NOT delegation.
