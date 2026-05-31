---
description: Conventions for the multi-agent orchestration layer (Drafter, Reviewer, Coherence, Formatter, Supervisor).
globs:
  - "agents/**/*.py"
---

# Agents rules

Applies to `agents/` — the multi-agent orchestration layer built on Google ADK.

Component map (use these names consistently in code and PRs):
- `supervisor.py` — orchestrator: routes work between the specialised agents (parallel vs sequential mode)
- `section_planner.py` — present but NOT wired into supervisor today (per `docs/1.0-architecture/RAG_ARCHITECTURE.md`)
- `drafter.py` — first-pass section content; calls `search_guidelines` (k=2), `search_past_papers` (k=1)
- `reviewer.py` — per-section critique; **sequential mode only**
- `coherence_reviewer.py` — cross-section coherence pass; **parallel mode only**; calls `search_guidelines` (k=3)
- `formatter.py` — final formatting / structure normalisation
- `event_collector.py`, `events.py` — observability of agent steps

## Prompts as code

- Treat agent prompts as **code**, not strings. Externalise long prompts into dedicated files / constants — don't inline a 100-line prompt in business logic.
- Prompt changes are reviewable changes. Diff the prompt; flag any change to role, constraints, or output format in the PR description.
- Never put business logic inside a prompt that belongs in code (filtering, validation, branching). Prompts describe *intent*; code enforces *correctness*.

## State between agents

- Pass state via typed structures (Pydantic / TypedDict / dataclasses) — never untyped dicts.
- One agent's output is another agent's input. Document the contract in the type, not in the prompt.

## Adding a new agent

- Mirror the shape of an existing agent (`drafter.py` is a good template).
- Add events to `event_collector.py` so the new agent's steps are visible.
- Wire it into `supervisor.py` deliberately — `section_planner.py` is a cautionary example of an unwired agent.
- Run on representative inputs and capture the full transcript (prompt → tool calls → final) before opening the PR.

## Errors

- An agent failure should propagate as a structured event, not a raw exception that crashes the orchestrator.
- Retries: bounded. Never silently retry forever — every retry should be logged with the reason.

## Don't

- Don't make agents read or write project files directly. They use tools (`tools/`) for that — preserves auditability.
- Don't change chunking + retrieval + prompt + agent in the same PR — isolate so regressions are diagnosable.
- Don't claim quality improvements without an eval. "Looks better on one example" is not evidence.
