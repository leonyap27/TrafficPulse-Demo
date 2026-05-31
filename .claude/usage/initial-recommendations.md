# Local Workflow Asset — Initial Recommendation List

Generated: `2026-05-24T22:16:21+08:00`  
Inventory entries: **20**  
Events recorded so far: **0**  
Days since first recorded event: **0**  
Probation window: **14 days**

This is the FP-192 baseline. The recommendations below are conservative defaults — after real usage data accumulates, re-run `scripts/generate_recommendations.py` (or override directly in the dashboard) to refresh actions. Every asset starts on `keep` so the team has a chance to use it; assets with no event after the probation window flip to `demote` for review.

## Summary by asset type

| Type | Count | With ≥1 event | Stale |
|---|---:|---:|---:|
| agent | 1 | 0 | 1 |
| bridge | 3 | 0 | 3 |
| command | 8 | 0 | 8 |
| hook | 2 | 0 | 2 |
| rule | 6 | 0 | 6 |

## agent

| Asset | Path | Events | Recommendation | Rationale |
|---|---|---:|---|---|
| `rag-architect` | `.claude/agents/rag-architect.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |

## bridge

| Asset | Path | Events | Recommendation | Rationale |
|---|---|---:|---|---|
| `CLAUDE.md` | `.claude/CLAUDE.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `ONBOARDING.md` | `.claude/ONBOARDING.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `AGENTS.md` | `AGENTS.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |

## command

| Asset | Path | Events | Recommendation | Rationale |
|---|---|---:|---|---|
| `/api-change` | `.claude/commands/api-change.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `/jira-impl` | `.claude/commands/jira-impl.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `/jira-plan` | `.claude/commands/jira-plan.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `/jira-review` | `.claude/commands/jira-review.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `/jira-test` | `.claude/commands/jira-test.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `/mcp-tool-review` | `.claude/commands/mcp-tool-review.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `/rag-review` | `.claude/commands/rag-review.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `/ui-change` | `.claude/commands/ui-change.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |

## hook

| Asset | Path | Events | Recommendation | Rationale |
|---|---|---:|---|---|
| `block-env-commit` | `.claude/hooks/block-env-commit.sh` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `record-slash-usage` | `.claude/hooks/record-slash-usage.py` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |

## rule

| Asset | Path | Events | Recommendation | Rationale |
|---|---|---:|---|---|
| `agents` | `.claude/rules/agents.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `backend` | `.claude/rules/backend.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `frontend` | `.claude/rules/frontend.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `kb` | `.claude/rules/kb.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `mcp-service` | `.claude/rules/mcp-service.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |
| `python-style` | `.claude/rules/python-style.md` | 0 | `keep` | no events yet, but tracker started <14d ago — probation |

---

Re-generate with: `python scripts/generate_recommendations.py`. Live dashboard: open `.claude/usage/viewer/index.html` from the filesystem.
