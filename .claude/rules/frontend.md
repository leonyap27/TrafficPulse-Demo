---
description: Conventions for the React + Zustand + TypeScript frontend.
globs:
  - "frontend-react/**/*.ts"
  - "frontend-react/**/*.tsx"
---

# Frontend rules

Applies to `frontend-react/` — React 19 + Zustand 5 + TypeScript 5.9.

## Components

- Functional components only. Hooks for state. No class components.
- Reuse existing components before creating new ones. Look in `src/components/` first.
- Keep components small — one component, one responsibility. Extract sub-components when one balloons.
- Co-locate component-specific styles, hooks, and helpers with the component.

## State (Zustand)

- Single store in `src/store/index.ts`. Slice by domain inside it.
- Keep state local in components when it doesn't need to be shared. Don't push everything into the store.
- Selectors return primitives or stable references — avoid creating new objects in selectors on every render.

## Loading / error / empty / validation states

Every async data flow has four states. Render them explicitly:

- **Loading** — skeleton or spinner, not blank
- **Error** — clear message + recovery path (retry, contact, dismiss)
- **Empty** — actionable empty state, not just "no data"
- **Success** — the happy path

## API integration

- API calls live in `src/api/`. One file per domain (`generation.api.ts`, `kb.api.ts`, etc.).
- TS types in `src/types/` must match the backend Pydantic response models. When the backend contract changes, update types in the same PR.
- For streaming endpoints (e.g. `/generate/sections/stream`), the existing pattern is in `src/api/streaming.api.ts` — follow it.

## Accessibility minimums

- Every interactive element is keyboard-reachable.
- Labels on inputs (`htmlFor`); alt text on meaningful images.
- Focus states visible.
- No layout shift on load (reserve space for skeletons).

## TypeScript

- No `any` unless there's a single-line comment explaining why.
- Prefer `interface` for object shapes shared across modules; `type` for unions and aliases.
- Strict null checks: handle `undefined`/`null` explicitly.

## Verification before claiming done

UI changes need browser verification — type checks and tests don't prove the feature works:

- Start dev server, exercise the feature on the golden path.
- Try one edge case (empty, error, slow network, long content).
- Watch the console for warnings/errors.

## Don't

- Don't introduce a new design system or styling primitive without an explicit request.
- Don't silently change copy, routes, or analytics events. Call them out in the PR.
- Don't mutate Zustand state outside the store's actions — use the action methods.
