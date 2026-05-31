---
description: Review a posted JIRA plan — walk the questions with the user, persist Q&A as a JIRA thread, auto-chain into /jira-impl on OK.
argument-hint: <JIRA-KEY> (e.g. FP-159)
---

Review the posted plan for JIRA ticket: **$ARGUMENTS**

This skill is the bridge between `/jira-plan` (which posts the plan + questions) and `/jira-impl` (which implements). It walks the reporter / reviewer through the Questions section, persists each turn as a JIRA comment so the audit trail lives in JIRA (not just in chat), and chains into `/jira-impl` once the user confirms with `OK`.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /jira-review --outcome started --trigger slash-command
```

This MUST run **first**, before reading the ticket or normalizing thread state. The `UserPromptSubmit` hook also records a `started` event when the user types `/jira-review` directly, but **chained invocations through the Skill tool bypass that hook** — this explicit call guarantees the start is captured regardless of how the workflow was invoked. Duplicate `started` events from hook + this call are harmless (the dashboard pairs them to the same terminal).

## Core principles
- **Does NOT move JIRA status.** Ticket stays in `In Review` throughout the conversation. Status moves are owned by `/jira-plan` (→ `In Review`) and `/jira-impl` (per team flow).
- **Doesn't guess on business intent.** If a question needs the reporter's call, ask the user. If the answer is a project convention / codebase fact, the skill *can* propose an answer but must mark it `[suggested — confirm?]` and wait for user confirmation.
- **Audit trail lives in JIRA.** Every meaningful Q&A turn is posted as a JIRA comment with the thread marker. A different intern picking up the ticket later sees the full conversation in JIRA, not just in someone's chat history.
- **Agent sign-off is required.** Every JIRA comment posted by this workflow ends with the visible audit footer below, immediately before hidden workflow markers:
  ```markdown
  ---
  **Agent sign-off:** <Claude Code | Codex | Other: NAME>
  **Workflow:** `/jira-review $ARGUMENTS`
  **Timestamp:** <ISO-8601 with timezone>
  ```
- **Same JIRA account is fine.** State discovery is by signature lines and position, not by author filtering.

## 1. Read the ticket (full state)

- Fetch the issue with all comments (chronological), status, reporter, assignee.
- Find the **latest `/jira-plan` comment** by its signature line:
  ```
  <!-- jira-plan v1 / auto-generated -->
  ```
  Note its comment ID — call this `PLAN_ID`. The thread is keyed to this ID, so older plans on the same ticket have separate threads.
- Find all comments **after** the plan with the thread marker:
  ```
  <!-- jira-review-thread plan=<PLAN_ID> -->
  ```
  This is `THREAD_SO_FAR` (may be empty on fresh start).
- Also identify comments **after** the plan **without** the thread marker, authored by the reporter or assignee. Call these `UNMARKED_REPLIES`. They may be direct JIRA replies the user typed without running the skill — handled in step 1b.

## 1b. Normalize prior thread state (handle direct JIRA replies)

This step protects against a real cross-session scenario: a different user (intern, fresh Claude) reads the plan in their browser, types answers as **plain JIRA replies** without running the skill, then later runs `/jira-review`. Their replies don't carry the thread marker — without this normalization step, the skill would silently treat the thread as empty and ask the same questions again, creating two parallel streams in the same ticket.

If `UNMARKED_REPLIES` is non-empty:

1. **Surface in chat** before doing anything else:
   ```
   Found <N> comments after the plan with no thread marker:
     • [<author> @ <timestamp>]: "<first 120 chars of comment>…"
     • [<author> @ <timestamp>]: "<first 120 chars of comment>…"

   Are these your answers to the plan's questions? (yes / no / selective)
   ```
2. **Branch on user response:**
   - **yes** → Post a single consolidated thread comment that quotes/links each unmarked reply, with the marker. From here on, treat those quoted contents as the user's authoritative answers to the matching questions. The original unmarked comments stay in JIRA (immutable), but the marker-bearing consolidated comment becomes the canonical thread record.
   - **no** → Ignore the unmarked comments entirely; treat thread as fresh (or as the marker-bearing thread state alone). Note in chat: "Ignoring those — treating thread as fresh."
   - **selective** → Walk through each unmarked comment one-by-one. For each, ask "include this one?" and consolidate only the confirmed ones.
3. **Never silently incorporate** unmarked comments. The skill MUST ask before treating any unmarked content as an answer — could be unrelated chatter, a teammate's question, a status update, etc.

If `UNMARKED_REPLIES` is empty, skip this step and proceed.

## 2. Pre-flight gate

| State | Skill behavior |
|---|---|
| **No `/jira-plan` comment exists** | Stop. Tell user: "No `/jira-plan` comment found on $ARGUMENTS. Run `/jira-plan $ARGUMENTS` first." |
| **Ticket status is `Done` / `Closed` / `Resolved` / `Cancelled`** | Stop. Tell user the ticket is closed, ask whether to reopen or drop. |
| **Ticket status is `To Do` / `Backlog`** | Stop. Tell user planning hasn't been done; run `/jira-plan` first. |
| **Ticket status is `In Progress`** | Stop. Either review is already complete or the user is at the wrong step. Tell user: "Ticket is `In Progress` — `/jira-review` only runs on `In Review`. If review is complete, run `/jira-impl $ARGUMENTS`." |
| **Status is `In Review`, thread already has `OK` + completion marker** | Stop. "Review already complete on `<date>`. Run `/jira-impl $ARGUMENTS` to implement." Do NOT auto-chain — the user re-ran the skill manually, treat that as a pause signal. |
| **Status is `In Review`, no thread yet** *(fresh start)* | Proceed to step 3. |
| **Status is `In Review`, thread in flight** | Proceed to step 3, resuming from the last turn. |

## 3. Extract questions from the plan

Parse the plan comment's **"Questions for reviewer"** section. Each item should be a checkbox-style question. Build a `QUESTIONS` list in order.

## 4. Determine current turn

Based on `THREAD_SO_FAR`:

- **Empty thread** → it's the skill's turn. Open the conversation in chat (step 5).
- **Last thread comment is from the skill (asking)** → it's the user's turn. Show the last question in chat, prompt for response (step 6).
- **Last thread comment is from the user (answering)** → it's the skill's turn. Read the answer; either follow up or wrap up (step 7).

## 5. Open the conversation (fresh thread only)

In chat:

```
Reviewing plan on $ARGUMENTS ([link to plan comment]).

The plan asks <N> questions. I'll walk through them with you and post each Q&A turn as a JIRA comment under the plan. Reply `OK` at the end to chain into /jira-impl, or `cancel` to abort.

---

Q1: <first question from plan>
```

Wait for the user's reply in chat.

## 6. Handle the user's chat reply

When the user types a reply in chat, first **classify intent** before doing anything else:

| Intent | Trigger words / pattern | Branch |
|---|---|---|
| **Direct answer** | substantive content addressing the question | step 6a |
| **Ask-back (needs AI help)** | `help`, `?`, `i don't know`, `idk`, `unsure`, `not sure`, `what do you think`, `check`, `investigate`, `look it up`, or a question to the AI | **step 6b** |
| **OK / completion** | `ok`, `looks good`, `approved`, `go`, `proceed`, `lgtm` | step 8 |
| **Cancel / abort** | `cancel`, `abort`, `stop`, `quit` | step 9 |
| **Ambiguous** (none of the above) | doesn't address the question, doesn't fit other intents | re-ask in chat, post the exchange to JIRA |

### 6a. Direct answer path

1. **Post a JIRA comment** under the plan with the marker:
   ```markdown
   **Q<n>:** <question>

   **Answer:** <user's reply, verbatim>

   ---
   **Agent sign-off:** <Claude Code | Codex | Other: NAME>
   **Workflow:** `/jira-review $ARGUMENTS`
   **Timestamp:** <ISO-8601 with timezone>

   <!-- jira-review-thread plan=<PLAN_ID> -->
   ```
2. **Decide next:**
   - More questions remain → ask the next one in chat. Post the skill's question to JIRA as its own thread comment (so the audit trail captures both sides).
   - All questions answered → ask user `Reply OK to finalize, or 'cancel' to abort.`
   - At any point, if intent shifts to ask-back / OK / cancel, branch to that step.

## 6b. Smart-draft on ask-back (the reviewer doesn't know / wants AI help)

When the user signals ask-back intent on a specific question:

1. **Investigate the codebase / project rules** before drafting:
   - Read the relevant files using Read / Grep / Glob.
   - Consult `.claude/rules/*.md` for project conventions on the area the question touches (backend / agents / frontend / KB / infra).
   - For RAG / KB questions, invoke the `rag-architect` subagent.
   - For other areas, invoke the matching specialist once FP-180 lands; until then, spawn a focused Explore subagent scoped to the relevant path.
   - **Never guess on business intent** — only draft for questions that have a grounded answer in the code, rules, or prior decisions. If a question requires *intent* (scope, priority, business decision), reply in chat: "This one needs your call — I can't ground it. What do you want?"

2. **Post a draft answer** to the JIRA thread, clearly marked as AI-suggested:
   ```markdown
   **Q<n>:** <question>

   **Draft answer (AI-suggested, please confirm):**
   <answer in 1-3 sentences>

   **Evidence:**
   - `<file>:<line>` — <what this shows>
   - `.claude/rules/<area>.md` — <relevant rule>

   Reviewer: reply `ok` to accept this as your answer, `override` followed by your own answer, or ask a follow-up question.

   ---
   **Agent sign-off:** <Claude Code | Codex | Other: NAME>
   **Workflow:** `/jira-review $ARGUMENTS`
   **Timestamp:** <ISO-8601 with timezone>

   <!-- jira-review-thread plan=<PLAN_ID> -->
   <!-- jira-review-draft question=<n> -->
   ```

3. **Wait for the user's response in chat:**
   - User replies `ok` / `accept` / `use that` → record the draft as the answer for that question. Post a confirmation thread comment: `**Q<n>:** confirmed by reviewer.` Proceed to next question.
   - User replies `override <new answer>` → use their answer; post as a regular Q&A thread comment.
   - User asks a follow-up question → respond in chat, post the back-and-forth to JIRA, loop within step 6.
   - User goes silent or exits → draft stays in JIRA marked `[draft — awaiting confirmation]`; next `/jira-review` run resumes from here.

4. **Never auto-accept the draft.** Human confirmation is required for every drafted answer. The `<!-- jira-review-draft -->` marker on a comment without a subsequent `**Q<n>:** confirmed` comment means it's still pending.

## 7. Handle a thread that was already in flight

If `THREAD_SO_FAR` shows the last message was from the user (e.g. they answered directly in JIRA, or the previous Claude session ended mid-flow):

1. Read the user's last answer from the thread.
2. Determine what state we're in:
   - Was it answering a question? → record + ask next.
   - Was it an `OK`? → wrap up (step 8).
   - Was it a back-question? → respond and resume.
3. Summarize in chat: "Resuming from JIRA thread — last reply was at `<time>`. Picking up at Q<n>."

## 8. User says `OK` — wrap up + chain

When all questions are answered (or user explicitly skips) AND user confirms `OK`:

1. **Post a completion comment** to the JIRA thread:
   ```markdown
   ## Review complete — ready for implementation

   All questions resolved by reporter. Summary:

   - **Q1:** <q> → <a>
   - **Q2:** <q> → <a>
   - ...
   - **Skipped:** Q5, Q7 (reviewer chose to defer)

   Ready for `/jira-impl $ARGUMENTS`.

   ---
   **Agent sign-off:** <Claude Code | Codex | Other: NAME>
   **Workflow:** `/jira-review $ARGUMENTS`
   **Timestamp:** <ISO-8601 with timezone>

   <!-- jira-review-thread plan=<PLAN_ID> -->
   <!-- jira-review-complete plan=<PLAN_ID> ok-at=<ISO-timestamp> -->
   ```
2. **Do NOT change JIRA status.** Ticket stays in `In Review`.
3. **Auto-chain into `/jira-impl`:**
   - Output in chat: "Review complete. Chaining into `/jira-impl $ARGUMENTS`…"
   - Hand off to the `/jira-impl` flow. `/jira-impl`'s own gate will see the `<!-- jira-review-complete -->` marker and proceed.

## 9. Cancel

If user says `cancel` / `abort` at any point:

1. **Post a cancel comment** to the JIRA thread:
   ```markdown
   Review cancelled by reviewer at `<ISO-timestamp>`. Thread remains; re-run `/jira-review $ARGUMENTS` to resume.

   ---
   **Agent sign-off:** <Claude Code | Codex | Other: NAME>
   **Workflow:** `/jira-review $ARGUMENTS`
   **Timestamp:** <ISO-8601 with timezone>

   <!-- jira-review-thread plan=<PLAN_ID> -->
   ```
2. Do NOT change JIRA status.
3. Exit cleanly.

## 10. Output in chat

Throughout the session, keep chat output tight:
- One question at a time. Don't dump all N questions.
- Mirror what was posted to JIRA with `→ posted comment <id>` for traceability.
- At the end (OK or cancel): link the completion / cancel comment.

## Guardrails

- **Never auto-OK on the user's behalf.** Only the human types `OK`. The skill can *suggest* answers (marked `[suggested — confirm?]`) but cannot mark questions resolved without the user's explicit yes.
- **Never overwrite a human-authored comment.** If a comment in the thread doesn't have the skill's marker but is clearly the reporter's answer, treat it as authoritative and just summarize.
- **Never paste raw secret values** into JIRA, chat, or commits. Redact to `[REDACTED]` and cite file:line only.
- **Never escalate scope.** If during review the user introduces a new requirement that wasn't in the plan, surface in chat: "This is new scope — recommend re-running `/jira-plan $ARGUMENTS` to update the plan before continuing review." Don't quietly add it to the answers.

## End-of-run usage recording (FP-192) — MANDATORY

You **MUST** append the terminal event before exiting (after posting the completion / cancel / no-op comment). Skipping this leaves a dangling `started` event that surfaces as "abandoned" in the dashboard.

```bash
python scripts/record_usage.py --command /jira-review --outcome <state> [--note "<friction>"]
```

States (all five are **terminal**, including `partial`): `completed` (reviewer typed `OK`, chained to `/jira-impl`) | `partial` (some questions answered, paused mid-thread) | `blocked` (pre-flight gate stopped the run — no plan, ticket closed, status mismatch) | `failed` (workflow errored) | `skipped` (cancelled). Add `--note` whenever state is not `completed`. The matching `started` event is auto-recorded by the `UserPromptSubmit` hook for user-typed invocations, but **chained invocations through the Skill tool bypass that hook** — record the `started` event manually when chained. See [`.claude/usage/schema.md`](../usage/schema.md).
