---
description: Walk through a backend API change — contract, compatibility, security, frontend callers.
argument-hint: <endpoint or change description, optional>
---

Walk through a backend API change: **$ARGUMENTS**

Applies when adding, modifying, or removing an HTTP endpoint or backend contract under `api/`.

For language-level conventions, you have `.claude/rules/python-style.md` and `.claude/rules/backend.md` already loaded when working in `api/`.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /api-change --outcome started --trigger slash-command
```

Run this first to capture usage for direct and chained invocations.

## 1. Locate the contract
- Route/handler in `api/` (and router registration).
- Request/response Pydantic models.
- Every frontend caller in `frontend-react/src/api/` and consuming components.

## 2. Decide compatibility
- **Additive** (new optional field / new endpoint): safe.
- **Breaking** (renamed field, removed endpoint, changed status code, changed auth): list every caller and confirm migration path before changing anything.
- Prefer additive + deprecation over breaking when feasible.

## 3. Update in this order
1. Pydantic models / schemas
2. Handler logic
3. Tests (unit + integration; do not mock things that would mask integration bugs)
4. Frontend callers and TS types in `frontend-react/src/types/`
5. OpenAPI / hand-written docs if applicable

## 4. Validate
- Run the API locally; hit the endpoint with a real request (curl / HTTP client / FastAPI's `/docs`).
- Confirm error paths return the documented shape, not stack traces.
- Check logs: no secrets, no PII leaks, structured fields preserved.

## 5. Security pass
- AuthN/AuthZ on the route is explicit.
- Input validation at the boundary (not deep in business logic).
- No SQL/command injection, no SSRF, no unbounded input sizes.
- Sensitive fields not echoed back in responses or logs.

## 6. Document in PR
- Before/after request + response shape.
- List of frontend files updated.
- Migration note if breaking.

## Guardrails
- Trust internal callers; validate only at system boundaries.
- Do not add backward-compat shims for callers you control — just update them.
- If the change touches auth or data access, flag it explicitly in the PR risk note.

Walk through these steps for the change above and report findings before making code changes.

## End-of-run usage recording (FP-192) — MANDATORY

```bash
python scripts/record_usage.py --command /api-change --outcome <state> [--note "<friction>"]
```

Terminal states: `completed` | `partial` | `blocked` | `failed` | `skipped`. Add `--note` whenever the state is not `completed`.
