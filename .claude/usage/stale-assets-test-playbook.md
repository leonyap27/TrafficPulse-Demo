# FP-199 Stale / Unused Asset Test Playbook

Tracks: FP-192, FP-195, FP-199

Use this playbook to test every local workflow asset one by one, teach a new
joiner how the FP-192 dashboard works, and collect before/after screenshots for
knowledge sharing.

The goal is not to decide automatically whether an asset is good. The goal is to
prove that:

- every inventoried asset can be explained and exercised;
- the dashboard correctly moves an asset out of "Stale / unused assets" when a
  matching event exists;
- Claude/Codex behavior is visibly different when the asset is used versus when
  the same requirement is handled without it;
- synthetic test data is removed after the walkthrough.

## Scope

In scope:

- local workflow assets from `.claude/commands/`, `.claude/rules/`,
  `.claude/hooks/`, `.claude/agents/`, `.claude/CLAUDE.md`,
  `.claude/ONBOARDING.md`, and `AGENTS.md`;
- local live/team usage events used by the FP-192 dashboard;
- screenshots from the local dashboard;
- examples comparing "without skill" and "with skill" outputs.

Out of scope:

- deployed application telemetry;
- production observability;
- scoring assets with AI;
- publishing synthetic events as real team evidence.

## Testing Modes

Run both modes when doing a complete knowledge-sharing session.

| Mode | What it proves | Data used | Cleanup required |
|---|---|---|---|
| Coverage test | The dashboard stale table responds correctly for every asset. | Synthetic usage events with a test run id in `note`. | Yes. Remove synthetic live/team events. |
| Behavior test | Claude/Codex output is better, safer, or more structured when the asset is used. | Real chat output, usually screenshots or pasted snippets. | Usually no, except recorder events. |

## Before You Start

Work from the repo root.

```bash
git status --short
python3 scripts/validate_usage_tracking.py
```

If `git status` already shows unrelated changes, do not revert them. Note them in
the evidence summary and keep the test artifacts separate.

Create a run id and evidence directory:

```bash
RUN_ID="FP-199-$(date +%Y%m%d-%H%M%S)"
EVIDENCE_DIR=".test-evidence/FP-199/$RUN_ID"
mkdir -p "$EVIDENCE_DIR"
```

Resolve and back up the private live event file:

```bash
LIVE_PATH="$(python3 -c 'import sys; sys.path.insert(0, "scripts"); import record_usage; print(record_usage.live_events_path())')"
echo "$LIVE_PATH" > "$EVIDENCE_DIR/live-path.txt"

if [ -f "$LIVE_PATH" ]; then
  cp "$LIVE_PATH" "$EVIDENCE_DIR/live-events.before.jsonl"
else
  touch "$EVIDENCE_DIR/live-events.before.jsonl"
fi
```

Capture the current inventory and recommendations:

```bash
python3 scripts/seed_inventory.py --output "$EVIDENCE_DIR/inventory.before.json"
python3 scripts/generate_recommendations.py --output "$EVIDENCE_DIR/recommendations.before.md"
python3 scripts/validate_usage_tracking.py > "$EVIDENCE_DIR/validation.before.txt" 2>&1
```

Start the dashboard:

```bash
python3 scripts/open_dashboard.py --no-open --port 8765
```

Open:

```text
http://localhost:8765/.claude/usage/viewer/index.html
```

Take screenshot `01-dashboard-before.png`.

For consistent screenshots:

- clear all filters first;
- capture the KPI row and the "Stale / unused assets" table;
- if the stale table is long, also capture a second screenshot scrolled to the
  asset being tested;
- record the stale count shown in the KPI row.

Important dashboard detail: the stale table is based on the currently filtered
event set. Clear filters for the canonical team-wide view. Use filters only when
you intentionally want to explain platform-specific or asset-type-specific
behavior.

## Synthetic Coverage Test

Use this mode to test assets one by one without mutating Jira, code, production,
or release state.

For each asset:

1. Capture a before screenshot with the asset visible in the stale table.
2. Append a synthetic `started` event and a synthetic terminal event.
3. Refresh the dashboard.
4. Capture an after screenshot showing the asset no longer appears as stale.
5. Record the observed stale count change.
6. Continue to the next asset. Do not clean up between assets unless you want
   every asset to start from the same baseline.

Template:

```bash
python3 scripts/record_usage.py \
  --command "<asset name>" \
  --asset-path "<asset path>" \
  --asset-type "<asset type>" \
  --trigger "<trigger>" \
  --platform codex \
  --outcome started \
  --note "$RUN_ID synthetic coverage start for <asset name>"

python3 scripts/record_usage.py \
  --command "<asset name>" \
  --asset-path "<asset path>" \
  --asset-type "<asset type>" \
  --trigger "<trigger>" \
  --platform codex \
  --outcome completed \
  --candidate-action keep \
  --note "$RUN_ID synthetic coverage close for <asset name>"
```

Use these trigger defaults:

| Asset type | Trigger |
|---|---|
| command | `manual` for synthetic tests, `slash-command` for real slash-command runs |
| rule | `direct` |
| hook | `hook` |
| agent | `direct` |
| bridge | `bridge` |

## Asset Checklist

Test all rows. The "skill run" column is the behavior test; the synthetic
coverage test still uses the event template above.

| ID | Asset | Type | Path | Coverage trigger | Without skill baseline | With skill / asset run |
|---|---|---|---|---|---|---|
| A01 | `rag-architect` | agent | `.claude/agents/rag-architect.md` | direct | Ask: "Review this RAG change" without loading the agent file. | Ask Claude/Codex to use `rag-architect` for the same change. Expected: seven repo-specific review sections and RAG facts from the agent file. |
| A02 | `CLAUDE.md` | bridge | `.claude/CLAUDE.md` | bridge | Ask for project rules without reading project memory. | Ask the agent to read `.claude/CLAUDE.md` first. Expected: local usage tracking, Jira chain, audit footer, and branch target rules appear. |
| A03 | `ONBOARDING.md` | bridge | `.claude/ONBOARDING.md` | bridge | Ask: "How should a new joiner start?" without opening onboarding. | Ask the agent to read `.claude/ONBOARDING.md`. Expected: setup sequence and project-specific onboarding references. |
| A04 | `AGENTS.md` | bridge | `AGENTS.md` | bridge | Ask Codex to work in the repo without the bridge context. | Ask Codex to follow `AGENTS.md`. Expected: Codex records FP-192 usage events and follows Claude project context. |
| A05 | `/api-change` | command | `.claude/commands/api-change.md` | manual | Ask: "Review adding a backend endpoint" with no command. | Run `/api-change <endpoint or change>`. Expected: contract, compatibility, frontend callers, security, validation, PR evidence. |
| A06 | `/jira-impl` | command | `.claude/commands/jira-impl.md` | manual | Ask: "Implement FP-XXX" directly. | Run `/jira-impl FP-XXX` only on an approved ticket. Expected: review gate, branch, commit, PR, chain to testing. |
| A07 | `/jira-plan` | command | `.claude/commands/jira-plan.md` | manual | Ask: "Plan FP-XXX" casually. | Run `/jira-plan FP-XXX`. Expected: reads Jira, reconciles code, classifies ACs, posts plan with audit footer. |
| A08 | `/jira-review` | command | `.claude/commands/jira-review.md` | manual | Ask: "Review the plan" without workflow markers. | Run `/jira-review FP-XXX`. Expected: walks plan questions, persists Q&A, chains to impl after `OK`. |
| A09 | `/jira-test` | command | `.claude/commands/jira-test.md` | manual | Ask: "Test this ticket" without the skill. | Run `/jira-test FP-XXX`. Expected: test cases, safe auto-run policy, evidence log, screenshot checklist, Jira evidence. |
| A10 | `/mcp-tool-review` | command | `.claude/commands/mcp-tool-review.md` | manual | Ask: "Review this MCP tool" generically. | Run `/mcp-tool-review <tool/change>`. Expected: tool description, args, return shape, error, versioning, injection review. |
| A11 | `/rag-review` | command | `.claude/commands/rag-review.md` | manual | Ask for a generic RAG review. | Run `/rag-review <change>`. Expected: KB integrity, retrieval sanity, prompt diff, eval, attribution, logging/cost. |
| A12 | `/release-doc` | command | `.claude/commands/release-doc.md` | manual | Ask: "Write release docs" without tracker workflow. | Run `/release-doc <tracker-key>`. Expected: release tracker lookup, deterministic renderer, docs path, Jira update. |
| A13 | `/ui-change` | command | `.claude/commands/ui-change.md` | manual | Ask: "Change this UI" without workflow. | Run `/ui-change <feature/component>`. Expected: surface lookup, contract check, browser verification, accessibility, screenshots. |
| A14 | `block-env-commit` | hook | `.claude/hooks/block-env-commit.sh` | hook | Ask: "Can I stage `.env`?" The answer is advisory only. | Simulate the hook with a `git add .env` payload. Expected: exit 2 and block message. |
| A15 | `record-slash-usage` | hook | `.claude/hooks/record-slash-usage.py` | hook | Type a slash-like request in a non-hook context; no automatic `started` event appears. | Simulate the hook with a prompt payload. Expected: a `started` event for the slash command. |
| A16 | `release-doc-prompt` | hook | `.claude/hooks/release-doc-prompt.py` | hook | Start a session with no hook; no pending-release nudge. | Simulate `SessionStart` with a temp deploy-ledger pending file. Expected: `additionalContext` recommends `/release-doc`. |
| A17 | `agents` | rule | `.claude/rules/agents.md` | direct | Ask for agent-layer advice without loading the rule. | Load the rule before reviewing `agents/**/*.py`. Expected: orchestration-specific conventions. |
| A18 | `backend` | rule | `.claude/rules/backend.md` | direct | Ask for backend advice generically. | Load the rule before reviewing `api/**/*.py` or `tools/**/*.py`. Expected: FastAPI/shared-helper conventions. |
| A19 | `frontend` | rule | `.claude/rules/frontend.md` | direct | Ask for React advice generically. | Load the rule before reviewing `frontend-react/**/*.tsx`. Expected: project frontend conventions and browser verification. |
| A20 | `kb` | rule | `.claude/rules/kb.md` | direct | Ask for KB advice generically. | Load the rule before reviewing `data/kb/**` or `tools/knowledge_base.py`. Expected: manifest, chunking, retrieval conventions. |
| A21 | `mcp-service` | rule | `.claude/rules/mcp-service.md` | direct | Ask for MCP advice generically. | Load the rule before reviewing `mcp_server/**/*.py`. Expected: FastMCP tool surface conventions. |
| A22 | `python-style` | rule | `.claude/rules/python-style.md` | direct | Ask for Python style generically. | Load the rule before editing/reviewing Python. Expected: local Python conventions, type/docstring/error-handling expectations. |
| A23 | `/dfsl` | command | `.claude/commands/dfsl.md` | manual | Ask: "Run the whole JIRA chain autonomously on FP-XXX" without the skill. | Run `/dfsl FP-XXX` on a clean-AC sandbox ticket. Expected: pre-flight gate (subtask + security-touching `unclear` checks), plan comment with signature, branch from `dev`, draft PR with disclaimer (per-phase confidence Low/Med/High, assumptions, items needing verification), terminal-only status landing (`In Review` / `TESTING` / `DONE`). Provenance: `DFSL —` heading prefix, `[DFSL]` PR title + commit subjects, `/dfsl > /jira-X` chain in footer. |

## Behavior Test Output Template

For each asset, save a short before/after comparison:

```markdown
### <asset id> - <asset name>

Requirement tested:
<one sentence>

Without skill / asset:
<paste 5-12 lines or summarize the output>

With skill / asset:
<paste 5-12 lines or summarize the output>

Observed difference:
- Structure:
- Repo-specific rules:
- Safety / audit behavior:
- Missing or confusing parts:

Screenshots:
- Before stale screenshot: `<path>`
- After usage screenshot: `<path>`
- Output screenshot or transcript: `<path>`

Decision:
keep | improve | demote | retire | generalize
```

Suggested evidence paths:

```text
.test-evidence/FP-199/<RUN_ID>/A01-before.png
.test-evidence/FP-199/<RUN_ID>/A01-after.png
.test-evidence/FP-199/<RUN_ID>/A01-output.md
```

`.test-evidence/` is gitignored. Post a short summary to Jira and keep the full
screenshots/logs locally unless the team explicitly wants to attach them.

## Hook Behavior Examples

Use real hook simulations for the hook assets after the synthetic coverage test.

The end-to-end verification pattern for hooks that write usage events is:

| Step | What to check |
|---|---|
| **[1] Fire** | Run the subprocess command. Check exit code and stderr/stdout. |
| **[2] Dashboard** | Refresh the dashboard. Confirm the new event is visible. |
| **[2b] Cleanup** | Remove the test event. Refresh and confirm it is gone. |

A14 and A16 do not write usage events — they block a command or emit context
only. Their verification is exit-code and output only (no dashboard step).

### A14 block-env-commit

**[1] Fire:**

```bash
printf '{"tool_input":{"command":"git add .env"}}\n' | python3 .claude/hooks/block-env-commit.sh
echo $?
```

Expected: exit code `2`, stderr contains `.env` block message. No usage event
is written — no dashboard or cleanup step needed.

Screenshot: `A14-output.png` — terminal showing exit 2 + block message.

### A15 record-slash-usage

This hook writes a `started` event to the live file. Back up the live file
first because the hook does not add the run id note to its auto-created event.

**Back up:**

```bash
cp "$LIVE_PATH" "$EVIDENCE_DIR/live-events.before-a15.jsonl"
```

**[1] Fire:**

```bash
printf '{"prompt":"/jira-plan FP-199 hook smoke"}\n' \
  | CLAUDE_PROJECT_DIR="$PWD" USAGE_PLATFORM=claude-code python3 .claude/hooks/record-slash-usage.py
```

Expected: exit code `0`, no output to stdout.

**[2] Verify dashboard update:**

Refresh the dashboard (`http://localhost:8765/.claude/usage/viewer/index.html`).
The events list should show a new `started` record for `/jira-plan` with
`platform=claude-code`. If `/jira-plan` was in the stale table, it should now
be absent.

Screenshot: `A15-after.png` — events list showing the new hook-generated entry.

**[2b] Cleanup:**

The event has no run-id in its note, so restore from the backup taken above:

```bash
cp "$EVIDENCE_DIR/live-events.before-a15.jsonl" "$LIVE_PATH"
```

Refresh the dashboard and confirm the event is gone.

Screenshot: `A15-cleanup.png` — dashboard returned to pre-test state.

### A16 release-doc-prompt

This hook outputs `additionalContext` to stdout. It does not write usage events
— no dashboard or cleanup step needed. Use a temp project directory so the repo
is not modified.

**[1] Fire:**

```bash
TMP_PROJECT="$(mktemp -d)"
mkdir -p "$TMP_PROJECT/.claude/usage/deploy-ledger/pending"
cat > "$TMP_PROJECT/.claude/usage/deploy-ledger/pending/demo.json" <<'JSON'
{"version":"0.0.0-test","target":"uat","timestamp":"2026-05-26T00:00:00+08:00"}
JSON

printf '{}\n' | CLAUDE_PROJECT_DIR="$TMP_PROJECT" python3 .claude/hooks/release-doc-prompt.py
```

Expected: JSON output with `hookSpecificOutput.additionalContext` mentioning one
pending deploy and `/release-doc`. Exit code `0`.

Screenshot: `A16-output.png` — terminal showing the JSON context output.

**Cleanup:**

```bash
rm -rf "$TMP_PROJECT"
```

## End-of-Run Dashboard Checks

After all synthetic coverage events are recorded:

```bash
python3 scripts/generate_recommendations.py --output "$EVIDENCE_DIR/recommendations.after-synthetic.md"
python3 scripts/validate_usage_tracking.py > "$EVIDENCE_DIR/validation.after-synthetic.txt" 2>&1
```

Refresh the dashboard and capture:

- `98-dashboard-after-all-assets.png` - KPI row and stale table;
- `99-dashboard-platform-codex.png` - platform filter set to `codex`;
- one screenshot per asset, or at minimum per asset type, showing the before and
  after state.

Expected:

- each tested asset has at least one matching event in the current unfiltered
  dashboard view;
- the stale table no longer lists tested assets;
- no abandoned starts were created by the synthetic coverage test;
- validation has no new errors from the test run.

## Cleanup

Synthetic events must not remain as real evidence.

Preferred cleanup is to remove only events whose note contains the run id. This
preserves any legitimate events recorded after the backup.

```bash
python3 -c 'import sys
from pathlib import Path
run_id, path = sys.argv[1], Path(sys.argv[2])
if not path.exists():
    raise SystemExit(0)
kept = []
for line in path.read_text(encoding="utf-8").splitlines():
    if run_id not in line:
        kept.append(line)
path.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
' "$RUN_ID" "$LIVE_PATH"
```

If you also published during the test, clean your own team profile the same way.
First find it:

```bash
TEAM_PATH="$(python3 -c 'import sys; sys.path.insert(0, "scripts"); import publish_usage; print(publish_usage.team_file_for(publish_usage.detect_developer_email()))')"
echo "$TEAM_PATH"
```

Then filter it:

```bash
python3 -c 'import sys
from pathlib import Path
run_id, path = sys.argv[1], Path(sys.argv[2])
if not path.exists():
    raise SystemExit(0)
kept = []
for line in path.read_text(encoding="utf-8").splitlines():
    if run_id not in line:
        kept.append(line)
path.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
' "$RUN_ID" "$TEAM_PATH"
```

Run the final checks:

```bash
python3 scripts/generate_recommendations.py --output "$EVIDENCE_DIR/recommendations.after-cleanup.md"
python3 scripts/validate_usage_tracking.py > "$EVIDENCE_DIR/validation.after-cleanup.txt" 2>&1
git status --short
```

Refresh the dashboard and capture `100-dashboard-after-cleanup.png`.

Expected:

- stale count returns to the pre-test value, except for any legitimate usage
  events that happened during the session;
- no synthetic `RUN_ID` lines remain in the live file or team file;
- `git status` has no unexpected usage-event changes from the test;
- any pre-existing unrelated changes are still present and untouched.

## Jira Summary Template

Post a concise summary to FP-199 or FP-192:

```markdown
## Stale / unused asset test evidence - <RUN_ID>

Scope:
- Tested all 22 inventoried local workflow assets.
- Ran synthetic dashboard coverage for each asset.
- Ran with-skill vs without-skill behavior comparisons.
- Captured before/after dashboard screenshots.
- Removed synthetic events after the run.

Results:
- Dashboard stale behavior: pass / fail / partial
- Validation gate: pass / fail
- Cleanup verification: pass / fail

Key observations:
- <asset>: keep/improve/demote/retire/generalize - <why>
- ...

Evidence:
- Local evidence directory: `.test-evidence/FP-199/<RUN_ID>/`
- Before dashboard screenshot: `<path>`
- After all assets screenshot: `<path>`
- After cleanup screenshot: `<path>`

---
**Agent sign-off:** <Claude Code | Codex | Other: NAME>
**Workflow:** FP-199 stale/unused asset test playbook
**Timestamp:** <ISO-8601 with timezone>
```

## Reviewer Notes

Use human judgement for the final candidate action:

| Signal | Suggested action |
|---|---|
| Asset produced clearly better, safer, more repo-specific output. | `keep` |
| Asset is useful but instructions were confusing or incomplete. | `improve` |
| Asset has little use now but might be useful after onboarding. | `demote` |
| Asset is obsolete, duplicate, or points to retired workflow. | `retire` |
| Asset is useful beyond this repo and should become shared guidance. | `generalize` |

Do not decide from event counts alone. FP-192 is a local decision-support tool,
not an automated asset-ranking system.
