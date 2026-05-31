---
description: Conventions for the FastAPI backend and shared tools/ helpers.
globs:
  - "api/**/*.py"
  - "tools/**/*.py"
---

# Backend rules

Applies to `api/` (FastAPI routes, streaming generation) and `tools/` (helpers consumed by agents and the API).

For language-level rules (type hints, docstrings, imports) see `.claude/rules/python-style.md`.
For multi-agent orchestration code in `agents/` see `.claude/rules/agents.md`.
For the MCP-facing layer in `mcp_server/` see `.claude/rules/mcp-service.md`.

## Routes (api/)

- RESTful paths: `POST /api/session`, `GET /api/session/{id}`. Not `/create-session`.
- Every route has a Pydantic request model and a Pydantic response model.
- Use `response_model=` on the route — don't rely on duck-typed dicts.
- Error responses use a consistent shape via shared error model + `HTTPException`. Never let raw exceptions leak as 500s with stack traces.
- Streaming responses (e.g. section generation) emit structured events the frontend can parse — see `api/streaming_generation.py` for the existing pattern.

## Validation

- Validate at the boundary using Pydantic validators on the request model. Don't validate deep in business logic.
- Bound user-supplied content (max lengths) before it reaches any LLM call.

## Tools (tools/)

- Tools are pure helpers callable from both `api/` and `agents/`. Keep side effects minimal and explicit.
- Type the public boundary fully. Internal helpers can be looser.
- If a tool talks to an external service (GCS, KB, document extractor), make the I/O easy to swap for tests.

## Logging

- One module logger per file: `logger = logging.getLogger(__name__)`.
- Prefer structured (`extra={...}`) over f-string in the log message.
- Never log secrets, full API keys, or full user-uploaded content.

## Don't

- Don't add backwards-compatibility shims for callers you control — just update them.
- Don't introduce a parallel "v3" path for an endpoint when you can change the existing route + update callers in the same PR.
- Don't mock external services inside production code paths to "make tests easier" — that belongs in test fixtures.
