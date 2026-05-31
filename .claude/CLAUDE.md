# Project: Funding Paper Agent

Inherits user-global rules from `~/.claude/CLAUDE.md` (team rulebook, memory policy, generic workflows).

## Stack
- Cloud: GCP
- Frontend: React
- Agent framework: Google ADK

## JIRA
- Active epic: FP-92
- Use FP-92 child issues for development work
- Do not commit against FP-92 itself

## Branching
- Active development branch: `dev`
- PRs target: `dev`

## JIRA skill chain

Four project-local slash commands cover the ticket lifecycle. They are designed to chain and to be runnable by a future central-agent orchestrator (no human in the loop).

| Skill | Purpose | Status transition on success |
|---|---|---|
| `/jira-plan FP-XXX` | Read ticket + comments, reconcile vs code, classify ACs, post plan + questions. | `→ In Review` |
| `/jira-review FP-XXX` | Walk plan questions with reviewer, persist Q&A under the plan, chain into `/jira-impl` on `OK`. | Status-neutral |
| `/jira-impl FP-XXX` | Gate on review completion, branch from `dev`, implement in small commits, open PR, chain into `/jira-test`. | `→ In Progress` at branch; `→ TESTING` at PR open / handoff |
| `/jira-test FP-XXX` | Classify scope from PR diff, run safe tests directly + emit human-verify checklist, redact + post evidence to JIRA. | Proposes `→ READY FOR DEPLOY` / `DONE` / `TESTING` |

Test evidence artefacts (full command logs) are written to `.test-evidence/<FP-XXX>/run-N.log` and gitignored — tool-agnostic so Codex or any other agent uses the same scheme.

### Autonomous variant — `/dfsl` (FP-218)

`/dfsl FP-XXX` (Do First Sorry Later) chains all four skills above end-to-end without human gates, then exits with a PR + a DFSL disclaimer (per-phase confidence, assumptions made, items needing verification). Strict pre-flight gate (subtask state, security-touching `unclear` ACs) governs whether the run proceeds. **Terminal-only** status transitions: `In Review` on abort, `TESTING` on partial, `DONE` on full happy path. When DFSL drives a sub-skill, the sub-skill's artefacts carry a `DFSL —` heading prefix, `/dfsl > /jira-X` chain in the audit footer, and `[DFSL]` prefix on PR title + commit subjects so humans can spot autonomous work at a glance. Direct invocations of the four sub-skills are unchanged. See [.claude/commands/dfsl.md](.claude/commands/dfsl.md).

## Agent audit trail
Every agent-authored JIRA comment, PR body, or durable status update must end with a visible audit footer immediately before any hidden HTML workflow markers:

```markdown
---
**Agent sign-off:** <Claude Code | Codex | Other: NAME>
**Workflow:** <slash command or manual workflow name>
**Timestamp:** <ISO-8601 with timezone>
```

Use `Claude Code` when a Claude Code slash command/session produced the update, `Codex` when Codex produced it, and `Other: NAME` for any other tool or human-run automation. Keep existing hidden markers such as `<!-- jira-plan v1 / auto-generated -->` after the visible footer so workflow detection still works.

## Project-specific workflow
Before implementing any FP-92 child issue:
1. Read the JIRA issue.
2. Reconcile requirement against existing code.
3. Classify status: implemented / partial / missing / unclear.
4. Update JIRA with findings before coding if misaligned.

For RAG/retrieval/prompt work, also reference [@workflows/rag-feature-review.md](.claude/workflows/rag-feature-review.md).

## Local usage tracking (FP-192 + FP-196)
Local workflow telemetry only — not deployed app telemetry.

Storage is two-zone (FP-196): the recorder writes to a private live JSONL at `~/.claude-usage/<owner>/<repo>/events.jsonl` outside the worktree, and `scripts/publish_usage.py` syncs each developer's own profile into `.claude/usage/team/events-<hash>.jsonl`. The legacy `.claude/usage/events.jsonl` is gitignored.

- Record lifecycle events with `python scripts/record_usage.py`.
- Workflow runs must include both a `started` event and a terminal event (`completed` / `partial` / `blocked` / `failed` / `skipped`).
- Non-Claude-Code agents should set platform explicitly per call (for example `--platform codex`) to avoid fallback to `other`.

Before merge, run:

```bash
python scripts/validate_usage_tracking.py
```

This fails when inventory drifts, command docs are missing recorder snippets, or stale unclosed `started` events remain in the merged team + live view.
