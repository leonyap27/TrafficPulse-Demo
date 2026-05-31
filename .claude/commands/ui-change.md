---
description: Walk through a frontend UI change — locate, contract, implement, verify in browser.
argument-hint: <feature or component, optional>
---

Walk through a frontend UI change: **$ARGUMENTS**

Applies when changing anything under `frontend-react/`.

For framework-level conventions, `.claude/rules/frontend.md` is already loaded when working in `frontend-react/`.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /ui-change --outcome started --trigger slash-command
```

Run this first to capture usage for direct and chained invocations.

## 1. Locate the surface
- Page/route, component tree, data hook(s) feeding it.
- Identify shared components — prefer extending an existing one over creating a sibling.

## 2. Confirm the contract
- TS types in `frontend-react/src/types/` must match backend Pydantic response shape.
- If the backend hasn't shipped the contract yet, gate the UI behind a flag or stub the hook — don't ship dead UI against a missing endpoint.
- If both move together, also run `/api-change` for the backend side.

## 3. Implement
- Reuse existing styling primitives / design tokens; don't introduce a parallel system.
- Keep state local unless it must be shared via Zustand.
- Handle loading, empty, error, and success states explicitly — none should render blank.

## 4. Verify in the browser
This is mandatory. Type-checks and unit tests don't prove the feature works.

- Start the dev server. Exercise the feature on the golden path.
- Exercise at least one edge case (empty list, error response, long content, slow network).
- Check the existing flow you most likely regressed (sibling routes, shared component consumers).
- Watch the console for warnings/errors.

## 5. Accessibility & polish
- Keyboard reachable; focus states visible.
- Labels on inputs (`htmlFor`); alt text on meaningful images.
- No layout shift on load.

## 6. Evidence for PR
- Screenshot or short clip of the new state(s).
- Note which flows you manually tested.
- Flag anything you could not test (e.g. requires staging data, integration with un-shipped backend).

## Guardrails
- If you cannot run the UI in a browser, say so — claim "implemented" only when verified.
- Do not silently change copy, routes, or analytics events; call them out in the PR.

Walk through these steps for the change above and report findings before claiming done.

## End-of-run usage recording (FP-192) — MANDATORY

```bash
python scripts/record_usage.py --command /ui-change --outcome <state> [--note "<friction>"]
```

Terminal states: `completed` | `partial` | `blocked` | `failed` | `skipped`. Add `--note` whenever the state is not `completed`.
