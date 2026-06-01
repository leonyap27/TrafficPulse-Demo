---
description: Implement an approved JIRA plan — gate on review completion, branch, commit, test, self-review, PR.
argument-hint: <JIRA-KEY> (e.g. FP-159)
---

Implement the approved plan for JIRA ticket: **$ARGUMENTS**

Use this only AFTER `/jira-plan $ARGUMENTS` produced a plan AND `/jira-review $ARGUMENTS` captured the reporter's `OK` (or the user explicitly bypasses the review gate).

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /jira-impl --outcome started --trigger slash-command
```

This MUST run **first**, before the pre-flight gate or any branching. The `UserPromptSubmit` hook also records a `started` event when the user types `/jira-impl` directly, but **chained invocations through the Skill tool bypass that hook** — this explicit call guarantees the start is captured regardless of how the workflow was invoked. Duplicate `started` events from hook + this call are harmless (the dashboard pairs them to the same terminal).

## 1. Pre-flight gate (run before branching anything)

Read the ticket, find the latest `/jira-plan` comment by signature, and the latest review-thread state. Decide:

| State | Skill behavior |
|---|---|
| **No `/jira-plan` comment** | **STOP.** "No plan found on $ARGUMENTS. Run `/jira-plan $ARGUMENTS` first." |
| **Status `Done` / `Closed` / `Resolved` / `Cancelled`** | **STOP.** Ticket is closed. Ask user whether to reopen before proceeding. |
| **Status `In Review`, thread has `<!-- jira-review-complete plan=<id> -->` marker** | Green light — review is complete, status hasn't moved yet (by design of `/jira-review`). Proceed. **Note in chat:** "Status is `In Review`; `/jira-impl` will move it to `In Progress` once branching starts." |
| **Status `In Review`, thread has no completion marker (questions still open)** | **STOP.** "Plan has open questions awaiting review. Run `/jira-review $ARGUMENTS` first." |
| **Status `In Review`, no review thread at all** | **STOP.** "Plan posted but not reviewed. Run `/jira-review $ARGUMENTS` to walk through the questions." |
| **Status `In Progress`, review thread has `<!-- jira-review-complete -->` marker** | Green light. Happy path after `/jira-review` auto-chained. Proceed. |
| **Status `In Progress`, no review thread** | Ambiguous — review was skipped or happened off-system. **Warn in chat:** "No review thread on the plan, but status is `In Progress`. Either review happened elsewhere or it was skipped. Proceed anyway? (Y/N)" — wait for explicit yes. |
| **Status `To Do` / `Backlog`** | **STOP.** "Ticket hasn't been planned. Run `/jira-plan $ARGUMENTS` first." |

If the gate passes, transition status to `In Progress` if it isn't already (call `getTransitionsForJiraIssue` + `transitionJiraIssue`). This signals to the team board that implementation is now active.

## 2. Branch
- From `dev`. Pull latest first.
- Name: `feat/$ARGUMENTS-<short-slug>` or `fix/$ARGUMENTS-<short-slug>`.
- Never commit directly to `dev`, `main`, or any release branch.

## 2b. Auto-append to the active release tracker (FP-212)

After branching, before the first implementation commit, append a bundle line to the active release tracker so the sprint manifest stays accurate. This replaces the manual "edit the tracker by hand when work merges" step in the playbook.

The canonical algorithm (and unit tests) live in [`scripts/active_tracker.py`](../../scripts/active_tracker.py) — this section describes the same algorithm in MCP-tool-inline form. If you change one, change both.

### 2b.1 Resolve the active tracker

Run JQL via `searchJiraIssuesUsingJql`:

```
project = FP AND labels = "release-tracker" AND status not in ("READY FOR DEPLOY", DONE) ORDER BY created DESC
```

- **Zero matches** → **STOP.** Print to chat: *"No active release tracker. Run `/release-cut YES` to open one (FP-214)."* If `/release-cut` is unavailable, create the tracker manually using the [RELEASE_TRACKER_SCHEMA template](../../docs/3.0-deployment/RELEASE_TRACKER_SCHEMA.md). Record `--outcome blocked` and exit. Do not silently continue work — a missing tracker means this ticket would not appear in any release doc.
- **One match** → that's the active tracker. Capture its key (e.g. `FP-194`).
- **Multiple matches** → take the **top** (newest by `created`, per the `ORDER BY` clause). Log: *"multiple open release-trackers; using <top-key> (most recent by created)"*. This is the brief sprint-handover window where the next tracker is open while the prior is still pre-deploy; the JQL ordering resolves it deterministically.

### 2b.2 Fetch the child ticket's summary + labels

Call `getJiraIssue` with `issueIdOrKey=$ARGUMENTS` and `fields=["summary","labels"]`. One call, two outputs:

- `summary` → goes into the bundle line as-is (no quoting, no truncation).
- `labels` → drives the work-type tag (next step).

### 2b.3 Derive the work-type tag

Apply the precedence order (matches `derive_work_type` in `scripts/active_tracker.py`):

| Label on the child ticket | Tag emitted |
|---|---|
| `release-work-type:tech-debt` | `[tech-debt]` |
| `release-work-type:carry-over` | `[carry-over]` (rare — usually only set by `/release-cut`) |
| Neither label | `[sprint]` (default) |

When both `tech-debt` and `carry-over` are present, **tech-debt wins** (precedence is deterministic).

If no `release-work-type:*` label is present, log a one-line note: *"No `release-work-type:*` label on $ARGUMENTS — defaulting to `[sprint]`."* This is the documented default, not a defect, but the log surfaces misconfigured tickets.

### 2b.4 Read the tracker description and ensure the `## Bundle` section exists

Call `getJiraIssue` on the tracker key with `fields=["description"]` and `responseContentFormat: "markdown"`.

Locate the `## Bundle` heading (case-insensitive, prefix match — `## Bundle (included Jira items)` is the canonical variant per the schema, not drift). Apply the schema-drift policy (per FP-212 review Q5=C):

- **`## Bundle` section present** → proceed to 2b.5.
- **Section absent + no fuzzy-match heading** (`bundle`, `items`, `tickets`, `included`) → **auto-repair**. Insert `## Bundle\n` immediately before `## PR / commit references` (or append at end-of-description if that anchor is also missing). Log: *"Tracker <key> missing `## Bundle` section — auto-repaired and continuing."*
- **Section absent + fuzzy-match heading present** (e.g. `## Items in this release`) → **STOP.** Hard-stop with: *"Tracker <key> has `## <found-heading>` instead of `## Bundle`. Please reconcile manually."* This signals an intentional restructure; auto-repair would create a duplicate section. Record `--outcome blocked` and exit.

### 2b.5 Idempotent append

Search the `## Bundle` section body for any line containing the literal `$ARGUMENTS` token (word-boundary match — `FP-21` must not match `FP-212`).

- **Match found** → no-op, do not modify the description. Log: *"$ARGUMENTS already in tracker <key> bundle — no change."* Proceed to step 3.
- **No match** → append a new table row at the end of the section body (before the next `## ` heading):

  ```
  | [$ARGUMENTS](https://ltads.atlassian.net/browse/$ARGUMENTS) | <summary> | <work-type> | In Progress | |
  ```

  If the `## Bundle` section body has no table header yet (empty section after auto-repair), prepend the header block first:

  ```
  | Jira ID | Desc | Type | Status | Document (Y/N) |
  | --- | --- | --- | --- | --- |
  ```

  Preserve every other character in the description exactly. Markdown round-trips through the Atlassian API are lossy if unrelated content is rewritten (FP-186 hit this in a different surface) — touch only the bundle section.

### 2b.6 Persist via `editJiraIssue`

Call `editJiraIssue` on the tracker key with:

- `fields: { description: <new markdown body> }`
- `contentFormat: "markdown"`

On a 409/conflict (another `/jira-impl` updated the tracker concurrently), re-read (2b.4) and retry once with the latest description. If retry also fails, surface to the user — do not proceed to commits with a stale tracker view; that would risk a duplicate line on the next successful append.

### 2b.7 Note in chat

Add one line to the chat report:

- On append: *"Tracker <key>: appended `$ARGUMENTS [<work-type>]` to bundle."*
- On no-op: *"Tracker <key>: bundle already contains `$ARGUMENTS` (no change)."*
- On auto-repair: as above, with the additional auto-repair note.

## 3. Implement in small commits
- Each commit message starts with `$ARGUMENTS` then an imperative summary.
- One logical change per commit.
- Prefer editing existing files over adding new ones.
- Follow the approved plan's "Order of changes." If you discover the plan was wrong, **stop and surface it** — don't quietly diverge.
- **Dashboard UI/UX delegation.** If the planned changes touch dashboard surfaces (`index*.html`, `page*.html`, dashboard React components, zone pages, or any layout / interaction / data-vis / a11y concern), delegate the UI work to the [`dashboard-ui-ux`](../agents/dashboard-ui-ux.md) subagent via the `Agent` tool (`subagent_type: "dashboard-ui-ux"`). Hand it the ticket key + the relevant plan section; expect a structured hand-back (files edited, browser verification notes, things it could not verify). Fold that hand-back into the PR body's testing-evidence section verbatim. Backend / data / non-UI changes stay in this skill.
- **Subagent telemetry (MANDATORY when delegating).** The `Agent` tool does not fire `record_usage.py` on its own — the parent skill must bracket the delegation so the dashboard's usage timeline shows the subagent's activity, not just `/jira-impl`. Immediately **before** invoking the `Agent` tool:
  ```bash
  python scripts/record_usage.py --command dashboard-ui-ux --asset-type agent \
    --asset-path .claude/agents/dashboard-ui-ux.md --trigger bridge --outcome started
  ```
  Immediately **after** the `Agent` tool returns (success, partial, or refusal), record the matching terminal event with the subagent's self-reported outcome (`completed` on a clean structured hand-back; `partial` if it flagged "could not verify" items; `blocked` if it refused; `failed` on tool error). Use the same `--command dashboard-ui-ux --asset-type agent --asset-path .claude/agents/dashboard-ui-ux.md --trigger bridge` envelope. Skipping the terminal event leaves a dangling `started` that surfaces as "abandoned" in the validator.

## 4. Pre-PR smoke check (fail-fast only)

Quick local sanity check before opening the PR — *not* full testing. Full testing is owned by `/jira-test $ARGUMENTS` after the PR is open.

- Unit tests for the touched module (`pytest <path>` / `npm test -- <path>`).
- Lint + type-check on changed files (`ruff` / `mypy` / `tsc --noEmit` / `npm run lint`).
- For prompts/agents: one representative input to confirm no obvious regression.

If anything in this step fails, **fix before opening the PR.** Full evidence capture (mode classification, security checks, redacted JIRA comment) happens in `/jira-test`, not here.

## 5. Self-review before PR
- `git diff dev...HEAD` — read every hunk.
- Remove debug prints, stray comments, unused imports.
- Confirm no secrets, `.env`, keys, sensitive data staged. The `.env` block hook (`.claude/hooks/block-env-commit.sh`) will catch obvious cases, but redact-shaped strings (API keys, tokens) need a manual check.

## 6. Pre-PR sync with `dev`

Re-fetch and merge `dev` into the feature branch right before opening the PR. This catches the case where `dev` advanced during implementation (parallel PRs landing) and avoids the kind of "branch is stale" rebase friction that triggered FP-193 in the first place.

```bash
git fetch github dev
git merge github/dev
```

- Use **merge**, not rebase — matches the team's recent PR pattern (PR #28 / FP-195, PR #26 / FP-192 both merged-dev mid-branch) and avoids the force-push burden that comes with rebasing a pushed branch.
- The remote name is `github` (the project's source-of-truth GitHub remote), not `origin` (legacy CodeCommit).
- **On conflict:** stop and surface clearly to the user. Do NOT auto-resolve. Print the conflicting files and ask the user to resolve, then continue once they confirm.
- On clean merge: an extra `Merge remote-tracking branch 'github/dev' into feat/FP-XXX-…` commit is created on the feature branch — that's expected and intentional.

## 7. Open PR against `dev` — as a **draft**

Always open the PR as a **draft** (`gh pr create --draft …`). The PR stays invisible to reviewers' "needs review" queues until `/jira-test FP-XXX` runs the full test suite and lands a clean-pass recommendation, at which point it automatically flips the PR to ready-for-review (`gh pr ready`). This prevents reviewers from being pinged on broken work and keeps the PR view clean while testing is still in flight.

- Title: `$ARGUMENTS <summary>`
- Body must include:
  - JIRA link
  - Summary (the *why*)
  - Files changed (grouped, not raw list)
  - Testing evidence (commands run, screenshots, sample outputs)
  - Risk / rollback note
  - Link to the `/jira-plan` comment and the `/jira-review` completion comment
  - Agent audit footer:
    ```markdown
    ---
    **Agent sign-off:** <Claude Code | Codex | Other: NAME>
    **Workflow:** `/jira-impl $ARGUMENTS`
    **Timestamp:** <ISO-8601 with timezone>
    ```

## 8. Update JIRA + offer the test chain

- Post a comment on the ticket linking the PR. Include: PR URL, branch name (`feat/$ARGUMENTS-…`), and the `PLAN_ID` (the comment ID of the `/jira-plan` comment this implementation was based on). These three are the **handoff artefact** `/jira-test` consumes. End the comment with the same agent audit footer used in the PR body.
- **Transition the ticket to `TESTING`.** Call `getTransitionsForJiraIssue` to find the `TESTING` transition id, then `transitionJiraIssue` to move it. This signals "implementation done; testing active" and is the entry status `/jira-test` expects from the chain. The PR's draft state carries the "needs code review" signal separately — the JIRA status reflects the test lifecycle, not PR review state. End-to-end status flow: `/jira-plan` → `In Review`, `/jira-impl` → `TESTING` (here), `/jira-test` → `READY FOR DEPLOY` on clean pass.
- **Chain prompt.** Print in chat: *"PR opened. Run `/jira-test $ARGUMENTS` now? (Y / skip, default Y)"*. On Y, invoke `/jira-test $ARGUMENTS` directly. On skip, stop — user can run `/jira-test` later. A future central-agent orchestrator answers Y by default; the prompt is single-token by design.

## Guardrails
- PR base is `dev`, not `main`.
- If a pre-commit hook fails, fix the cause — never bypass with `--no-verify`.
- Never amend a published commit; create a new one.
- **Stop and ask if you discover scope beyond the approved plan.** Don't silently expand. If new scope is legitimate, the user should re-run `/jira-plan` to update the plan and re-review.
- **Never paste raw secret values** into JIRA, chat, or commits. Redact to `[REDACTED]` and cite file:line only.

## End-of-run usage recording (FP-192) — MANDATORY

You **MUST** append the terminal event before exiting (after opening the PR, posting the JIRA handoff, and offering the test chain). Skipping this leaves a dangling `started` event that surfaces as "abandoned" in the dashboard.

```bash
python scripts/record_usage.py --command /jira-impl --outcome <state> [--note "<friction>"]
```

States (all five are **terminal**, including `partial`): `completed` (branched, committed, PR opened, JIRA updated) | `partial` (some commits landed but PR not opened, or chain to `/jira-test` declined) | `blocked` (pre-flight gate stopped the run — no review completion, ticket closed) | `failed` (workflow errored mid-implementation) | `skipped` (intentional short-circuit). Add `--note` whenever state is not `completed`. The matching `started` event is auto-recorded by the `UserPromptSubmit` hook for user-typed invocations, but **chained invocations through the Skill tool bypass that hook** — record the `started` event manually when chained. See [`.claude/usage/schema.md`](../usage/schema.md).

> **Maintainer note (FP-218):** [`/dfsl`](./dfsl.md) chains this skill as its impl phase. When you change the pre-flight gate, the release-tracker bundle append (§2b), the commit/PR title format, or the JIRA handoff comment template, re-check `dfsl.md §3` and the provenance prefix rule in `dfsl.md §5`.
