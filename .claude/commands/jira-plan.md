---
description: Plan implementation for a JIRA ticket — validate status, read comments, reconcile vs code, classify, post plan to JIRA (or skip when nothing changed).
argument-hint: <JIRA-KEY> (e.g. FP-159)
---

Plan implementation for JIRA ticket: **$ARGUMENTS**

Follow this workflow. The plan is posted to JIRA automatically when appropriate — do NOT wait for approval before posting. Do NOT write code until I approve the plan in chat.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /jira-plan --outcome started --trigger slash-command
```

This MUST run **first**, before any JIRA reads or branching. The `UserPromptSubmit` hook also records a `started` event when the user types `/jira-plan` directly, but **chained invocations through the Skill tool bypass that hook** — this explicit call guarantees the start is captured regardless of how the workflow was invoked. Duplicate `started` events from hook + this call are harmless (the dashboard pairs them to the same terminal).

## 1. Read the JIRA issue (full state, not just description)
- Pull title, description, current **workflow status**, assignee, reporter, labels, acceptance criteria, **all comments in chronological order**, linked issues, attachments.
- Note designs, contracts, examples.

## 2. Pre-flight gate (run before anything else)

### 2a. Status check
Branch on the ticket's workflow status:

- **Done / Closed / Resolved / Cancelled** → **STOP**. Do not post anything to JIRA. Return to chat:
  - Current status + who closed it + when
  - Last 3 comments summarised
  - Any linked PR / merge commit
  - Ask whether to reopen, plan a follow-up ticket, or drop.
- **In Review / Awaiting QA / Ready for QA** → **STOP**. Do not post. Warn in chat that an active review is in progress and ask before continuing.
- **In Progress** → continue, but flag in the plan that work has already started (cite the assignee if set, and any in-flight branch/PR if linked).
- **To Do / Backlog / Open / Selected for Development / Reopened** → continue, normal flow.

### 2b. Comment delta
Read every comment. Build a **delta vs the original description**:
- Scope added or removed in comments
- Decisions that override the description
- Testing notes ("staff B tested X, found Y")
- Whether a prior plan comment exists (see 2c)

If the delta materially changes the AC, the plan must reflect the *current* scope, not the original description.

### 2c. Prior-plan detection
Look for a previous plan comment on this ticket. Auto-generated plans carry this signature line at the bottom:

```
<!-- jira-plan v1 / auto-generated -->
```

- **No prior plan** → proceed to step 3.
- **Prior auto-generated plan exists** (signature present):
  - Re-run steps 3 + classification.
  - If the new classification + affected files + risks are **materially the same** as the prior plan → **do not post**. Return to chat: "Prior plan from <date> still holds — <link to prior comment>." Done.
  - If anything material has changed → post a **revision** comment titled `Plan — revision N (YYYY-MM-DD)`. Include a "**What changed vs prior plan**" section at the top, then the full updated plan. Link the prior comment.
- **Prior plan looks human-written** (no signature line, but it's clearly a plan from a person) → **STOP**. Surface the prior comment in chat and ask whether to supersede it. Do not auto-post over a human's plan.

## 3. Reconcile against existing code
- Search the repo for related modules, endpoints, components, agents, prompts.
- Identify exact file/function/line seams the change will touch.

## 3b. Confirm component label (release doc area)

Check whether the ticket has a `component:*` label. This label determines the **Area** column in the sprint business release doc and bucket grouping in the technical doc — it must be set before `/jira-done` runs.

| Label on ticket | Area in release docs |
|---|---|
| `component:frontend` | Frontend |
| `component:backend` or `component:api` | Backend |
| `component:agents` or `component:rag` | Agents+RAG |
| `component:infra` | Infra |
| `component:security` | Security |
| `component:docs` | Docs |
| *(none)* | Other |

- **Label present and matches the affected code** → no action.
- **Label missing** → determine the correct label from the affected files (Step 3), then call `editJiraIssue` on `$ARGUMENTS` to add the label. Note in chat: *"Added `component:<area>` label to FP-XXX — no label was set."*
- **Label mismatched with the affected code** → call `editJiraIssue` to replace the incorrect label with the correct one. Note in chat: *"Updated label from `component:<old>` → `component:<new>` on FP-XXX."*

This applies to re-runs too: older tickets planned before this step existed will have their label set automatically on the next `/jira-plan` run.

## 4. Classify each acceptance criterion
For each AC:
- `implemented` — already exists, nothing to do (cite file:line evidence)
- `partial` — exists but missing behavior listed in AC (cite file:line + what's missing)
- `missing` — not in code
- `unclear` — requirement ambiguous or contradicts current behavior

## 5. Post the plan to JIRA (when 2a + 2c allow it)
Post a JIRA comment with these sections in order:

1. **Acceptance criteria classification** — list/table, one row per AC, classification + file/function evidence
2. **Affected files** — grouped, not raw list
3. **Order of changes** — numbered, smallest viable steps
4. **Risks / unclear points**
5. **Test approach** — unit, integration, manual UI/API check as applicable
6. **Questions for reviewer** — *required section*. Open questions, scope ambiguities, decisions the reporter must make before implementation. Tag the reporter (and assignee if different).

   **Format each question with two parts:**
   - **The question itself** — checkbox + bold label + concrete options or what to confirm.
   - **An `If unsure:` hint** — what the reviewer can ask the skill to do if they don't know the answer (e.g. "reply `help` and I'll check the project's SA naming conventions and propose an answer").

   Example:
   ````
   - [ ] **POC SA name** — confirm `funding-paper-agent-poc@…`?
     *If unsure:* reply `help` and the skill will check the project's SA naming conventions and propose an answer for you to confirm.

   - [ ] **API key rotation scope** — keep inside FP-163 or split to a follow-up?
     *If unsure:* reply `help` and the skill will look at recent rotation work and recommend a scope.
   ````

   Every question must have an `If unsure:` hint. No bare yes/no questions without an escape hatch — the reviewer should never be forced to guess.

7. **Effort estimate** — *required section*. One-line estimate as an hour range, plus a one-line rationale citing the drivers. Format:

   ```
   **Effort estimate:** `<range>` — <rationale citing missing-AC count, affected-file count, cross-skill blast radius, unclear ACs>
   ```

   Use this heuristic table to pick the range (it's a floor, not a ceiling — bump up if you hit unfamiliar code, missing test infra, or security-sensitive surface):

   | Estimate | Rough indicators |
   |---|---|
   | `<1h` | 1 file, 1 `missing` AC, no cross-skill impact, no `unclear` ACs |
   | `1–2h` | 1–2 files, 1–2 `missing` ACs, single skill area |
   | `2–4h` | 2–3 files, 2–4 `missing` ACs, possibly some `partial` cleanup |
   | `4–8h` | 3+ files, multiple skill areas, or 1+ `unclear` AC needing follow-up |
   | `1–2d` | Cross-cutting changes (e.g. backend + frontend + agent), or `unclear` ACs that may expand scope |
   | `>2d` | Anything bigger — flag in chat that the ticket should probably be split |

   Examples: `**Effort estimate:** \`2–4h\` — 3 affected files (jira-impl.md, jira-test.md, jira-plan.md), 4 missing ACs across one skill area (.claude/commands/), no unclear ACs that expand scope.`

   Also append to the effort estimate section of the plan comment a one-line scheduling note (see 7b below for the computed values):
   ```
   **Scheduling:** Story points: `<N>` · Start: `<YYYY-MM-DD>` (Mon) · Due: `<YYYY-MM-DD>` (Fri of last week)
   ```

7b. **Ticket field updates** — *required, runs immediately after step 7 (computing the effort estimate)*. Call `editJiraIssue` on `$ARGUMENTS` to set story points, start date, and due date. Do this in the same step as posting the plan comment — compute → include scheduling note in comment → call `editJiraIssue`.

   **Story points** (`customfield_10016`)

   Take the upper bound of the effort range in hours and compute `story_points = ceil(hours / 2)`:

   | Effort estimate | Hours (upper bound) | Story points |
   |---|---|---|
   | `<1h` | 1 | 1 |
   | `1–2h` | 2 | 1 |
   | `2–4h` | 4 | 2 |
   | `4–8h` | 8 | 4 |
   | `1–2d` | 16 | 8 |
   | `>2d` | use the ticket's explicit hour estimate if stated; otherwise use 40 | 20 |

   **Start and due dates** (`customfield_10015`, `duedate`)

   Step 1 — determine the anchor Monday:
   - Today is Mon–Fri → Monday of the **current** calendar week
   - Today is Sat–Sun → Monday of the **upcoming** calendar week

   Step 2 — compute total workdays: `total_days = ceil(story_points / 4)` (4 story points = 1 workday = 8 work hours).

   Step 3 — pick start and due:

   | total_days | Start date | Due date |
   |---|---|---|
   | ≤ 5 (fits in 1 week) | Anchor Monday | Anchor Friday (anchor Mon + 4 calendar days) |
   | > 5 (multi-week) | Anchor Monday | Friday of the last week (anchor Mon + `(ceil(total_days / 5) × 7) - 3` calendar days) |

   Multi-week example — 44 story points (11 workdays across 3 calendar weeks): start = anchor Mon, due = Friday of week 3 = anchor Mon + 18 calendar days (3 weeks × 7 days − 3 days to get to Friday).

   **Fields to set:**
   ```
   customfield_10016 = <story_points>   (integer)
   customfield_10015 = "<YYYY-MM-DD>"   (start date — ISO-8601)
   duedate           = "<YYYY-MM-DD>"   (due date — ISO-8601)
   ```

8. **How to respond** — *required footer*, exact text below. This tells the reader (especially fresh interns whose Claude session has no context) how to reply without needing to know markers or status workflow:

   ````
   ---
   **How to respond:** Open Claude Code in this repo and run `/jira-review $ARGUMENTS`. The skill will extract the questions above, ask you in chat one at a time, post your answers as a JIRA thread under this plan, and when you reply `OK` it will chain into `/jira-impl $ARGUMENTS`. You do not need to flip JIRA status or remember any marker — the skill handles both.

   **If you don't know an answer:** reply `help`, `?`, or "I don't know" — the skill will investigate the codebase / project rules and propose a draft answer for you to confirm or override. The skill never guesses on business intent without your sign-off.

   **If you reply directly in JIRA (not via the skill):** the skill can still pick up your replies on the next `/jira-review` run. It will ask you to confirm before consolidating them into the canonical thread.
   ````

9. **Agent audit footer** — required for every posted plan/revision. Put it after "How to respond" and immediately before the hidden signature marker:

   ```markdown
   ---
   **Agent sign-off:** <Claude Code | Codex | Other: NAME>
   **Workflow:** `/jira-plan $ARGUMENTS`
   **Timestamp:** <ISO-8601 with timezone>
   ```

End the comment with the hidden signature line so future runs can detect it:

```
<!-- jira-plan v1 / auto-generated -->
```

For revisions, the title is `Plan — revision N (YYYY-MM-DD)` and a "What changed vs prior plan" block comes before section 1.

## 6. Transition the ticket to `In Review` (only when the comment was posted)

If — and only if — step 5 actually posted a new comment (i.e. not silent-skip, not stopped at the gate, not blocked by a human prior plan), transition the JIRA status:

- Call `getTransitionsForJiraIssue` to find the available transitions from the current status.
- If a transition to `In Review` exists from the current status, call `transitionJiraIssue` to move it.
- If no such transition exists from the current status (or the ticket is already past `In Review`), do **not** force it — note this in chat instead.

**Do not transition** when:
- The plan was silent-skipped (no material change vs prior auto-generated plan).
- The pre-flight gate stopped the run (Done/Closed, In Review, prior human plan).
- The comment post failed for any reason.

The transition turns the workflow into: `In Progress` → `/jira-plan` posts comment → ticket moves to `In Review` (awaiting human approval of the plan before `/jira-impl`).

## 7. Output a short plan in chat
Mirror the JIRA comment, plus:
- Direct link to the posted/updated JIRA comment (or note that posting was skipped and why)
- Confirmation of whether the status transitioned to `In Review` (or why it was skipped)
- The **effort estimate** (same hour range + rationale that landed in the JIRA comment) — so the user can react to scope without re-opening JIRA
- Any blockers / questions for the human

## Guardrails
- Do not use `FP-92` (the epic) for code commits — use the child key.
- Stop and ask if AC contradicts current behavior in a non-trivial way.
- Stack is GCP + React + Google ADK — ignore any older references to Streamlit / Strands / Azure.
- **Never paste raw secret values into JIRA, chat, or commits.** If a secret-shaped string appears in evidence (API keys, tokens, passwords, private URLs), redact to `[REDACTED]` and cite the file:line only.
- Posting the plan to JIRA does not require my approval. **Writing code does** — do not start `/jira-impl` until I say go.

## End-of-run usage recording (FP-192) — MANDATORY

You **MUST** append the terminal event to the local usage log before exiting. Skipping this leaves a dangling `started` event that surfaces as "abandoned" in the dashboard and corrupts every "is this workflow useful?" report.

```bash
python scripts/record_usage.py --command /jira-plan --outcome <state> [--note "<friction>"]
```

States (all five are **terminal**, including `partial`): `completed` (plan posted or silent-skipped cleanly) | `partial` (posted, but open follow-ups) | `blocked` (pre-flight gate stopped the run) | `failed` (workflow errored) | `skipped` (intentional short-circuit). Add `--note` whenever the state is not `completed`. The matching `started` event is auto-recorded by `.claude/hooks/record-slash-usage.py` via the `UserPromptSubmit` hook in `.claude/settings.json`, but **chained invocations through the Skill tool bypass that hook** — so when this workflow is chained from another, record the `started` event manually too. See [`.claude/usage/schema.md`](../usage/schema.md).

> **Maintainer note (FP-218):** [`/dfsl`](./dfsl.md) chains this skill as its plan phase. When you change the AC-classification rules, the plan comment template, or the status transitions here, re-check `dfsl.md §3` to confirm the chain still composes.
