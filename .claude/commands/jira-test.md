---
description: Test an implemented JIRA ticket — generate test cases from the plan + PR diff, run them (auto where safe, guide where not), capture redacted evidence to JIRA.
argument-hint: <JIRA-KEY> (e.g. FP-159)
---

Test the implementation for JIRA ticket: **$ARGUMENTS**

This skill owns the **full testing record** for a ticket: test-case preparation, execution, redacted evidence capture, and a final ready/not-ready recommendation. It runs *after* `/jira-impl $ARGUMENTS` has opened a PR (happy path), or standalone on demand for re-testing.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /jira-test --outcome started --trigger slash-command
```

This MUST run **first**, before reading the ticket or computing the diff. The `UserPromptSubmit` hook also records a `started` event when the user types `/jira-test` directly, but **chained invocations through the Skill tool bypass that hook** — this explicit call guarantees the start is captured regardless of how the workflow was invoked. Duplicate `started` events from hook + this call are harmless (the dashboard pairs them to the same terminal).

## Core principles

- **Auto-run safe, guide unsafe.** Unit tests, lint, type-check, localhost curl → executed directly. Anything that mutates shared state, hits prod, or needs human eyes → emitted as a checklist for the user to run.
- **Redaction is mandatory.** Every tool output passes through a regex redactor; outputs that touched `gcloud` / `curl` / `env` / `secrets/` also require explicit user confirmation before posting. Per [`.claude/CLAUDE.md`](../CLAUDE.md), raw secret values never reach JIRA.
- **Evidence lives in JIRA, full output lives in the branch.** The JIRA comment shows summary + metadata. Full logs save to `.test-evidence/<JIRA-KEY>/run-N.log` (gitignored). The comment links the artefact path.
- **Status changes are proposed, never auto-flipped.** The skill computes a recommended transition and asks the user to confirm before calling `transitionJiraIssue`.
- **Re-runs append, never overwrite.** Each invocation posts a new `## Test evidence — Run N` comment. Prior runs stay in JIRA as immutable history.
- **Per-ticket + cross-tracker evidence.** Every run posts the evidence comment on the test ticket (primary record) and *also* appends a one-line link to the active release-tracker's `## Test evidence` section (secondary index — so the lead running `/release-doc YES` at sprint close has all the links in one place). See step 7b. The tracker append is best-effort: a failure there never stops the run.
- **Agent sign-off is required.** Every JIRA comment ends with the visible audit footer, immediately before hidden markers.
- **Designed to be operable by a future central agent** (no human in the loop). Every confirmation prompt is single-token (Y / N / skip), defaults are safe-for-auto, and the skill exposes an explicit unattended mode (see section "Unattended mode" at the bottom).

## 1. Read the ticket (full state)

Fetch the issue with all comments (chronological), status, reporter, assignee, linked PR (via remote links or comment body).

Find the **latest `/jira-plan` comment** by signature:
```
<!-- jira-plan v1 / auto-generated -->
```
Note its comment ID — call this `PLAN_ID`.

Find all prior test-evidence comments by marker:
```
<!-- jira-test-thread plan=<PLAN_ID> run=N -->
```
The highest `N` is the previous run. The next run is `N+1`. If none exist, this is `run=1`.

## 2. Pre-flight gate

| State | Skill behavior |
|---|---|
| **Status `Done` / `Closed` / `Resolved` / `Cancelled`** | **STOP.** "Ticket is closed. Re-testing a closed ticket? (Y/N)" — wait for explicit Y. |
| **No `/jira-plan` comment** | **WARN + PROCEED.** Print: "⚠ No `/jira-plan` comment on $ARGUMENTS. Testing against ticket description only — plan/code alignment will not be verified. Continue? (Y/N, default Y)" — the evidence comment header will carry the same warning so JIRA readers see it. |
| **No PR found** | Try `git diff dev...HEAD` on the current branch. If diff is empty: **STOP.** "No PR linked on $ARGUMENTS and current branch has no changes vs `dev`. Nothing to test." |
| **Status `To Do` / `Backlog`** | **STOP.** "Ticket hasn't been implemented yet. Run `/jira-plan` → `/jira-review` → `/jira-impl` first." |
| **Any other status with a diff** | Proceed. |

## 3. Classify scope from the diff

Compute the diff (PR diff if PR exists, else `git diff dev...HEAD`). Map changed paths to test modes:

| Path pattern | Mode triggered |
|---|---|
| `frontend-react/**` | frontend |
| `api/**`, `tools/**` | backend |
| `agents/**`, `mcp_server/**` | backend + agent |
| `data/kb/**`, anything touching retrieval/chunking | backend + rag (also recommend `/rag-review`) |
| `.claude/**`, `mcp_server/tools/*.py` | agent/tooling |
| Any auth / secret / IAM / SA / permission-related change | + security (always additive) |
| `Dockerfile`, `cloudbuild.yaml`, `deploy/**`, `*.tf` | infra |
| `docs/**` only | docs-only (lightweight check; no test execution required) |

A diff may trigger multiple modes — that's expected and normal. Report the union as the test scope.

## 4. Generate the test-case checklist

Build a table mapping every acceptance criterion (from the plan if present, else from the ticket description) to one or more test cases. Each test case has:

| Field | Notes |
|---|---|
| `ID` | `TC-001` upwards, stable within a run. |
| `Area` | frontend / backend / security / agent / infra / regression. |
| `Scenario` | One sentence — what behavior is verified. |
| `Steps / Command` | The exact command if auto-runnable; the instruction if human-verify. |
| `Expected` | Concrete observable outcome (exit code, response body shape, screenshot description). |
| `Auto vs Human` | One of `auto`, `auto-confirm`, `human-verify` (taxonomy in section 5). |
| `Evidence requirement` | Where evidence will be captured (log file, screenshot path, manual note). |

Surface the table in chat **before** running anything. Ask: "Run the auto-eligible cases now? (Y / edit / skip)". Edits = user adds/removes cases.

## 5. Execute tests by taxonomy

Apply this taxonomy (encoded as a table so future contributors can edit policy without re-deriving it):

| Bucket | What | Examples | Skill behavior |
|---|---|---|---|
| **Auto-run safe** | Local, deterministic, no side effects beyond the working tree | `pytest`, `npm test`, `npm run lint`, `tsc --noEmit`, `ruff`, `mypy`, `curl http://localhost:*` | Run directly. Capture stdout/stderr/exit-code. |
| **Auto-run with confirm** | Read-only against shared services | `gcloud … describe`, `gcloud … list`, `gcloud … get-iam-policy`, `curl https://<staging-or-uat-url>/*` | Print the command + estimated impact; require user Y before executing. |
| **Human-verify** | Mutating, prod-touching, or needs human eyes | Browser UI checks; any `gcloud deploy` / `iam set-policy` / `secrets versions add`; prod URL hits; anything under `scripts/destructive/` | Emit the command as a `[ ]` checklist item in chat + evidence comment. Do NOT execute. |

For each executed command:
1. Capture full output to `.test-evidence/$ARGUMENTS/run-N.log` (create dir if missing).
2. Compute one-line summary: command, exit code, line count, duration.
3. Run the redaction step (section 6) on any snippet you plan to include in the JIRA comment.

**Shell exit-code capture.** Use plain `$?` immediately after the command — portable across bash and zsh (FP-186 Run 1 mis-reported passing `tsc -b` and `vite build` as `FAIL` because an improvised snippet used the bash-only `${PIPESTATUS[0]}`, which returns empty on macOS zsh). Example:

```bash
npm run build
build_exit=$?
```

Only reach for `${PIPESTATUS[@]}` (bash) / `${pipestatus[@]}` (zsh) when the *intermediate* exit code of a pipeline matters — and when you do, explicitly call out the bash/zsh divergence so the snippet doesn't silently mis-report on the other shell.

## 6. Redaction

Two-pass policy:

**Pass 1 — regex redactor (always on).** Replace matches with `[REDACTED:<kind>]`:

| Kind | Pattern shape |
|---|---|
| GCP API key | `AIza[0-9A-Za-z\-_]{35}` |
| GitHub token | `gh[pousr]_[A-Za-z0-9]{36,}` |
| JWT | `eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+` |
| GCP SA JSON | any block containing `"type"\s*:\s*"service_account"` plus `"private_key"` |
| Bearer header | `[Bb]earer\s+[A-Za-z0-9_\-\.=]+` |
| `.env`-style assignment | `(?i)(api[_-]?key|secret|token|password|private[_-]?key)\s*[=:]\s*['"]?[^\s'"]+` |

**Pass 2 — confirm-before-post (default on; can be disabled in unattended mode).** If any captured snippet's source command matched `gcloud`, `curl`, `env`, or touched a file under `secrets/`, print the to-be-posted snippet in chat and ask: "Post this to JIRA? (Y / redact-more / skip)". The user can mark additional patterns for redaction; the skill re-runs Pass 1 with the user's additions.

In **unattended mode** (section "Unattended mode" below): Pass 1 only. If Pass 1 leaves any high-risk pattern un-redacted and the source command was high-risk, **refuse to post** and surface for human review.

## 7. Post the evidence comment

**WAF-safe authoring rule.** When authoring the JIRA-posted comment, refer to scanned patterns by **class name only** — e.g. "GCP API key pattern", "GitHub token pattern", "JWT pattern", "GCP service-account JSON pattern", "bearer-header pattern", "`.env`-style assignment pattern". **Never paste the regex literal into the comment text.** Cloudflare's WAF in front of JIRA inspects POST bodies for secret-shaped strings and will reject the request (FP-186 Run 1 first-post failure). The actual regexes in the section 6 catalogue stay literal — they're the scanner's source of truth and never leave this file.

Single comment per run. Heading: `## Test evidence — Run N (YYYY-MM-DD)`. Layout:

```markdown
## Test evidence — Run N (YYYY-MM-DD)

**Status:** Passed / Failed / Blocked / Partial
**Ticket:** $ARGUMENTS
**Plan reference:** [link to PLAN_ID comment]  (or "⚠ no plan found — tested against description only")
**PR:** [link to PR]  (or "no PR — tested branch <name>")
**Test mode:** frontend / backend / security / agent / infra / mixed
**Supersedes:** [link to Run N-1]  (omit if N=1)
**Full log:** `.test-evidence/$ARGUMENTS/run-N.log`

### Test cases

| ID | Area | Scenario | Steps / Command | Expected | Actual | Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-001 | … | … | … | … | … | Pass / Fail / Blocked / Not Run / N/A | log line / screenshot path |

### Summary

- **Passed:** N
- **Failed:** N — [list with one-line failure reasons]
- **Blocked:** N — [why blocked]
- **Not Run:** N — [why; usually = human-verify pending]
- **Not Applicable:** N — [why]

### Risks / follow-up

- …

### Recommendation

One of:
- **Ready** — all auto cases pass, all human-verify cases checked, no risks → propose `READY FOR DEPLOY` (or `DONE` if UAT deploy already happened).
- **Not ready** — failures or unaddressed risks → propose `TESTING`.
- **Needs reviewer decision** — ambiguous; surface in chat.

---
**Agent sign-off:** <Claude Code | Codex | Other: NAME>
**Workflow:** `/jira-test $ARGUMENTS`
**Timestamp:** <ISO-8601 with timezone>

<!-- jira-test-thread plan=<PLAN_ID> run=N -->
```

**Result vocabulary** (must be one of these — no synonyms): `Pass`, `Fail`, `Blocked`, `Not Run`, `N/A`. Maps to the AC requirement that results clearly distinguish these states.

## 7b. Upsert evidence link to active release-tracker (FP-198 + FP-212)

After step 7 posts the per-ticket evidence comment, also upsert a one-line entry on the active release-tracker's `## Test evidence` section. This consolidates a sprint's test evidence into the release tracker so the operator running `/release-doc YES` at sprint close has all the links in one place.

This step is **best-effort** (per FP-212 review Q2=B): a failure here never aborts the test run. The per-ticket comment from step 7 is the primary record; the tracker append is a convenience index. FP-213 `/jira-done` surfaces any missing-tracker case at sprint close.

The canonical algorithm (and unit tests) live in [`scripts/active_tracker.py`](../../scripts/active_tracker.py) — the `upsert_evidence_entry` + `ensure_section` helpers. This section describes the same algorithm in MCP-tool-inline form. If you change one, change both.

### 7b.1 Resolve the active tracker

Run JQL via `searchJiraIssuesUsingJql`:

```
project = FP AND labels = "release-tracker" AND status not in ("READY FOR DEPLOY", DONE) ORDER BY created DESC
```

- **No matches** → skip this entire step. Log: `no active release-tracker; skipping tracker evidence append`. Continue to step 8. (Best-effort: do NOT stop the test run. `/jira-impl` STOPs on the same condition; `/jira-test` does not.)
- **One match** → that's the active tracker. Capture its key (e.g. `FP-194`).
- **Multiple matches** → take the **top** (most recently created — the brief sprint-handover window where the next tracker is open while the prior is still pre-deploy). Log: `multiple open release-trackers; using <top-key> (most recent by created)`. Operator can verify.

Do **not** use `cat VERSION` as a tie-breaker — per `VERSIONING.md`, the file lags the in-flight tracker's manifest by one PATCH during active dev, so matching against it would point at the previous sprint's tracker, not the current one.

### 7b.2 Read the tracker description and ensure the `## Test evidence` section exists

Call `getJiraIssue` with the tracker key and `fields=["description"]`, `responseContentFormat: "markdown"`.

Locate the `## Test evidence` heading (case-insensitive, prefix match). Apply the schema-drift policy (per FP-212 review Q5=C):

- **Section present** → proceed to 7b.3.
- **Section absent + no fuzzy-match heading** (`test`, `evidence`, `qa`, `validation`) → **auto-repair**. Insert `## Test evidence\n` immediately before `## Known issues / limitations` (or append at end-of-description if that anchor is also missing). Log: `tracker <key> missing '## Test evidence' section — auto-repaired and continuing`.
- **Section absent + fuzzy-match heading present** (e.g. `## QA results`) → hard-stop this step only. Log: `tracker <key> has '## <found-heading>' instead of '## Test evidence' — please reconcile manually`. Skip the append, continue to step 8. (Per FP-212 Q5=C the fuzzy-match guard is a soft-stop for `/jira-test` — it surfaces but does not fail the test run; only `/jira-impl` hard-stops the whole flow on the same condition.)

### 7b.3 Build the new entry

Format (single-space, matches `upsert_evidence_entry` in `scripts/active_tracker.py`):

```
- $ARGUMENTS Run <N> _<result>_ — [evidence comment](<comment-url>)
```

Where:

- `$ARGUMENTS` is the test ticket key.
- `<N>` is the run number from step 7.
- `<result>` is the overall result word (`Pass` / `Fail` / `Blocked` / `Partial`).
- `<comment-url>` is the JIRA URL of the per-ticket evidence comment from step 7 (`https://ltads.atlassian.net/browse/$ARGUMENTS?focusedCommentId=<id>`).

### 7b.4 Upsert the entry (per-ticket, not per-run)

Per FP-212 review Q3=B: re-runs of `/jira-test $ARGUMENTS` **overwrite** the prior tracker line for this ticket. The tracker shows one line per FP-XXX; per-run history (Run 1, Run 2, …) lives on the per-ticket evidence comments themselves, not on the tracker.

Algorithm:

1. Search the `## Test evidence` section body for any line containing the literal `$ARGUMENTS` token (word-boundary match — `FP-21` must not match `FP-212`).
2. **Match found** → replace that line with the new entry built in 7b.3.
3. **No match** → append the new entry as a new bullet at the end of the section body (before the next `## ` heading).

Preserve every other character in the description exactly. Markdown round-trips through Atlassian are lossy if unrelated sections get rewritten — touch only the test-evidence section.

### 7b.5 Save the updated description

Call `editJiraIssue` on the tracker key with:

- `fields: { description: <new markdown body> }`
- `contentFormat: "markdown"`

If the call fails with a conflict (another process edited concurrently), re-read (7b.2) and retry once with the latest description. If retry also fails, log the failure and proceed to step 8 — do not stop the run. The per-ticket evidence comment from step 7 is the primary artefact.

### 7b.6 Note in the chat report

Add one line to the final chat report:

- On upsert (new line): `Tracker evidence: appended $ARGUMENTS entry to <tracker-key> #test-evidence`.
- On upsert (replace prior): `Tracker evidence: replaced prior $ARGUMENTS entry on <tracker-key> #test-evidence`.
- On no-tracker skip: `Tracker evidence: no active release-tracker (skipped)`.
- On schema-drift soft-stop: `Tracker evidence: tracker <key> has fuzzy-match heading instead of '## Test evidence' — skipped`.
- On auto-repair: include `tracker <key> missing '## Test evidence' — auto-repaired` alongside the upsert line.
- On retry exhaust: `Tracker evidence: edit conflict on <tracker-key> after retry — see log`.

In **unattended mode**, the JQL resolution and upsert still run; failures are logged but never stop the test run or change exit code.

## 8. Flip the draft PR + propose status transition

### 8a. Flip the draft PR to ready (clean-pass only)

If the recommendation is **Ready** (all cases `Pass`, none `Fail` / `Blocked` / `Not Run`), automatically flip the draft PR to ready-for-review **before** proposing the JIRA status transition:

```bash
gh pr ready <PR_NUMBER>
```

- Runs in **both** interactive and `--unattended` modes — no extra confirm prompt. This pairs with `/jira-impl` opening every PR as a draft: testing-passes is the implicit signal that reviewers can be pinged.
- On `Not ready` (any `Fail` / `Blocked` / `Not Run`), do **not** flip — the PR stays as draft.
- Re-runs of `/jira-test` that land another `Ready` recommendation are safe: `gh pr ready` on an already-ready PR is a no-op.
- Note the action taken in the evidence comment (`Flipped PR to ready: yes/no — <reason>`).

### 8b. Propose JIRA status transition

Compute the recommended transition from the summary:

| Run result | Recommended transition |
|---|---|
| All cases `Pass` (no `Fail` / `Blocked` / `Not Run`) | `READY FOR DEPLOY`, or `DONE` if user confirms UAT deploy already happened |
| Any `Fail` or `Blocked` | `TESTING` |
| Any `Not Run` (human-verify pending) | `TESTING` + remind user to complete the human-verify checklist |
| Mixed but recoverable | Ask user |

Print: "Recommended transition: `<status>`. Confirm? (Y / pick-different / skip)" — wait for explicit Y. On Y, call `getTransitionsForJiraIssue` + `transitionJiraIssue`. On skip, leave status untouched and note in chat.

## Unattended mode (for future central-agent orchestration)

The skill is **designed to be runnable without a human in the loop**. A central agent (orchestrator) invokes `/jira-test $ARGUMENTS --unattended` and the skill must terminate without ambiguous prompts.

Differences from interactive mode:

| Step | Interactive | Unattended |
|---|---|---|
| Pre-flight prompts (no plan, closed ticket) | Ask user | Refuse to proceed; post a JIRA comment explaining why; exit. |
| Auto-run-with-confirm bucket | Print + ask Y | Treat as auto-run-safe **only if** the command is in an explicit allow-list; otherwise treat as human-verify (= Not Run). |
| Human-verify cases | Emit as `[ ]` checklist | Emit as `[ ]` checklist marked `Not Run — human-verify required`. |
| Redaction pass 2 | Confirm-before-post | Skipped. If pass 1 leaves any high-risk pattern un-redacted from a high-risk source, refuse to post and exit non-zero. |
| Status transition | Confirm with user | Apply the recommendation directly. |

The interactive flow is the default. `--unattended` is opt-in.

## Guardrails

- **Never paste raw secret values** into JIRA, chat, or commits. If regex misses something obvious, add it to the regex catalogue in section 6 in the same PR.
- **Never auto-merge a PR.** Out of scope.
- **Never replace human QA approval** where the team flow requires it. The skill *proposes*, the human (or central agent) *decides*.
- **Don't post empty evidence.** If every case ended up `Not Run` and no cases were `Pass` / `Fail`, surface in chat instead — there's nothing useful to record.
- **One run = one comment.** Never edit a prior run's comment. Append `Supersedes:` link to the new comment instead.
- **Truncate giant outputs.** If a single command's stdout exceeds 200 lines, the JIRA snippet shows first 50 + last 50 + total count; the full log lives in `.test-evidence/`.

## End-of-run usage recording (FP-192) — MANDATORY

You **MUST** append the terminal event before exiting (after posting the redacted evidence comment and proposing the status transition). Skipping this leaves a dangling `started` event that surfaces as "abandoned" in the dashboard.

```bash
python scripts/record_usage.py --command /jira-test --outcome <state> [--note "<friction>"]
```

States (all five are **terminal**, including `partial`): `completed` (all cases ran, evidence posted, transition proposed) | `partial` (some cases `Not Run` because they require human-verify) | `blocked` (pre-flight gate stopped the run — no PR, no plan, ticket closed) | `failed` (workflow errored) | `skipped` (intentional short-circuit, e.g. unattended-mode refusal). Add `--note` whenever state is not `completed`. The matching `started` event is auto-recorded by the `UserPromptSubmit` hook for user-typed invocations, but **chained invocations through the Skill tool bypass that hook** — record the `started` event manually when chained. See [`.claude/usage/schema.md`](../usage/schema.md).

> **Maintainer note (FP-218):** [`/dfsl`](./dfsl.md) chains this skill (in `--unattended` mode) as its test phase. When you change the unattended-mode behavior, the `gh pr ready` clean-pass auto-flip, the result vocabulary, or the recommendation-to-status mapping, re-check `dfsl.md §3` and the confidence rubric in `dfsl.md §6`.
