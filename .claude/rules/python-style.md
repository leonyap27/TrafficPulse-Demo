---
description: Generic Python conventions — PEP 8 baseline, type hints, docstrings, error handling.
globs:
  - "**/*.py"
---

# Python style

Applies to every Python file in the repo. Layered with the more specific rules (`backend.md`, `agents.md`, `mcp-service.md`, `kb.md`).

## Style baseline
- PEP 8 with these tweaks:
  - Line length: 100 chars
  - 4 spaces, no tabs
  - Double quotes for strings
  - Absolute imports preferred

## Import order
1. Standard library
2. Third-party
3. Local
One blank line between groups.

## Type hints
- Required on all function signatures
- Required on class attributes
- Required on complex data structures

```python
def create_session(user_id: str, ttl: int = 3600) -> dict[str, str]:
    ...
```

## Docstrings (Google style)
- Public functions: required
- Complex internal functions: required
- Classes: required (overview + key methods)
- Simple getters/setters/one-liners: skip

```python
def search(query: str, top_k: int = 5) -> list[dict]:
    """One-line summary.

    Args:
        query: Search query string.
        top_k: Number of results to return.

    Returns:
        List of result dicts with content, metadata, score.

    Raises:
        ValueError: If query is empty.
    """
```

## Naming
| Kind | Convention |
|---|---|
| Functions, variables | `snake_case` |
| Classes | `PascalCase` |
| Constants | `UPPER_SNAKE_CASE` |
| Private | `_leading_underscore` |

Descriptive over short: `user_session_id` beats `uid`.

## Error handling
- Catch specific exceptions, not bare `Exception`.
- Never `except: pass`.
- Log with context, then handle gracefully or re-raise.

## Logging
- Use module logger: `logger = logging.getLogger(__name__)`.
- Prefer structured logs (`extra={...}`) over f-strings in the message.
- Levels: DEBUG (diagnostic) / INFO (state changes) / WARNING (handled anomalies) / ERROR (broken functionality) / CRITICAL (system-breaking).

## Async/await
- Async for I/O (network, DB, file).
- Sync for CPU-bound.
- Never call blocking libraries (`requests`, `time.sleep`) inside `async` — use `httpx`, `asyncio.sleep`.

## Testing
- Test names describe the behavior: `test_search_returns_relevant_results`, not `test_search`.
- Specific assertions: `assert "content" in results[0]` beats `assert results`.
- Use fixtures (`conftest.py`) for shared setup.
- Integration tests should hit real dependencies when mocking would mask divergence.

## Comments
- Comment **why**, not **what**. Names tell what; comments tell motivation, constraints, or workarounds.
- No commented-out code in commits.
