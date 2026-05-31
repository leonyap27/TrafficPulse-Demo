---
description: Do First Sorry Later — run plan → impl → test → done autonomously on a JIRA ticket, no human gates, exit with a disclaimer of assumptions + per-phase confidence.
argument-hint: <JIRA-KEY> (e.g. FP-159) — strictly one argument, no flags
---

Run the full DFSL (Do First Sorry Later) pipeline on JIRA ticket: **$ARGUMENTS**.

DFSL chains `/jira-plan` → `/jira-impl` → `/jira-test` → `/jira-done` end-to-end without human gates. It exits with a PR + a structured DFSL disclaimer that names every assumption made, every item needing human verification, and a per-phase confidence rating (Low / Medium / High).

**v1 is strictly one-arg.** `/dfsl FP-XXX`, nothing else. Reject any extra tokens with a one-line error and exit.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /dfsl --outcome started --trigger slash-command
```

This MUST run **first**, before pre-flight checks or any sub-skill invocation. Each sub-skill DFSL invokes will record its own `started` and terminal events on top of this one — that's expected and how the dashboard reconstructs the chain. See [`.claude/usage/schema.md`](../usage/schema.md).

## 1. Pre-flight gate (run before any sub-skill)

DFSL is autonomous — once past this gate, no further human consent is sought until the run terminates. The gate is therefore stricter than `/jira-impl`'s gate.

Read `$ARGUMENTS` via `getJiraIssue`. Pull `status`, `subtasks` (via the `issuelinks`/`subtasks` field), `labels`, comments, and acceptance criteria. Run every check below; if any fails, **abort the run** before the plan phase, post a structured abort comment, leave status untouched, and record `--outcome blocked`.

| Check | Pass condition | On fail |
|---|---|---|
| **Subtask state (AC8)** | Every subtask of `$ARGUMENTS` is `Done` (or no subtasks exist) | Post `## DFSL aborted — subtasks not Done` comment listing each subtask + status. Recommend two paths: (1) finish subtasks then re-run `/dfsl $ARGUMENTS`, or (2) run `/dfsl FP-YYY` per subtask. |
| **Parent status** | Not `Done` / `Closed` / `Resolved` / `Cancelled` (nothing to do). Not already at `TESTING` / `READY FOR DEPLOY` (work already underway). | Post `## DFSL aborted — ticket in <status>` explaining why DFSL won't touch in-flight or closed work. |
| **At least one clear AC** | Required — DFSL needs some signal to act on. If 100% of ACs are `unclear`, abort. | Post `## DFSL aborted — all ACs are unclear` listing the ACs and asking a human to disambiguate. |
| **Security-touching `unclear` ACs (Q4 abort)** | None. Any single `unclear` AC touching auth / IAM / secrets / security → hard-abort, regardless of how many other ACs are clear. | Post `## DFSL aborted — security-touching unclear AC` naming the specific AC and why autonomous decisions on auth/IAM/secrets are out of scope. |

The pre-flight abort comment ends with the standard agent audit footer + the `<!-- dfsl-aborted -->` marker so re-runs detect the prior abort.

## 2. The Decide phase (DFSL's autonomous replacement for `/jira-review`)

For every `unclear` AC that survived the pre-flight gate, DFSL makes a best-effort call **before** invoking `/jira-impl`. Each decision is recorded as a structured assumption that ends up in the DFSL disclaimer (§7).

Decision policy:

- **Grounded in code / project rules** → pick the answer that best matches existing patterns. Cite the file:line or `.claude/rules/<area>.md` rule that informed the choice.
- **Grounded in prior tickets** → search recent merged work in the same surface; mirror it. Cite the prior FP-key.
- **Pure business intent** (scope, priority, naming) → pick the most conservative reading (additive over breaking; opt-in over default-on; small scope over expanded scope). Log the rationale.

The Decide phase produces a `DECISIONS` list of `{ac_index, ac_text, decision, evidence, rationale}` records. This list is consumed by `/jira-impl`'s implementation and surfaces verbatim in the disclaimer.

## 3. Sub-skill chain (Q5: reference + deltas)

DFSL does NOT re-implement plan / impl / test / done. It invokes the existing skills in order. The skill files are the single source of truth; this file only specifies the **deltas** that apply when DFSL is the caller.

| Step | Sub-skill | DFSL delta |
|---|---|---|
| 3.1 | [`/jira-plan $ARGUMENTS`](./jira-plan.md) | Run the full plan flow. The plan comment IS posted (AC2-decision Q2(a)) so downstream skills find the `<!-- jira-plan v1 -->` signature. Apply the provenance prefix (§5). After posting, do NOT wait for a human review thread — proceed directly. |
| 3.2 | (Decide phase, §2) | DFSL-only. No sub-skill equivalent. |
| 3.3 | [`/jira-impl $ARGUMENTS`](./jira-impl.md) | Run the full impl flow including the release-tracker bundle append (§2b). Apply the provenance prefix to commits and PR title (§5). Open the PR as `--draft` per `/jira-impl §7` (Q3 confirmed). |
| 3.4 | [`/jira-test $ARGUMENTS`](./jira-test.md) | Run `--unattended` mode. Auto-eligible cases execute; human-verify cases are recorded as `Not Run — human-verify required` and surface in the disclaimer. The skill's own `gh pr ready` clean-pass auto-flip applies. |
| 3.5 | [`/jira-done $ARGUMENTS`](./jira-done.md) | Only invoke if `/jira-test` returned a clean-pass recommendation. Otherwise skip — terminal status lands at `TESTING`, not `DONE`. |

When a sub-skill stops at its own pre-flight gate or returns an error, DFSL captures the reason, sets the run outcome accordingly (see §6), and proceeds to the disclaimer + JIRA summary phases without forcing the next sub-skill.

## 4. Terminal JIRA status

DFSL is **terminal-only** — no intermediate transitions are made by DFSL itself. The sub-skills' own status transitions still fire (e.g. `/jira-plan` moves `To Do → In Review`; `/jira-impl` moves to `In Progress`; `/jira-test` proposes `READY FOR DEPLOY`). What DFSL guarantees is the **final landing state**:

| Run outcome | Final JIRA status | How it gets there |
|---|---|---|
| Pre-flight gate fired (§1) | Unchanged (left where it was) | DFSL never invoked any sub-skill, never transitioned anything |
| `/jira-plan` or `/jira-impl` errored / blocked | Wherever the failing sub-skill left it | The failing sub-skill's own recovery state applies |
| `/jira-test` produced any `Fail` / `Blocked` / `Not Run` | `TESTING` | `/jira-impl` already moved it; `/jira-test`'s recommendation is `TESTING`; DFSL skips `/jira-done` |
| `/jira-test` clean-pass + `/jira-done` produced release docs | `DONE` | `/jira-test`'s clean-pass recommendation + `/jira-done` chain → DFSL accepts the proposed `DONE` transition without further prompt |

## 5. Provenance marking (AC9)

When DFSL drives a sub-skill, every visible artefact that sub-skill produces must carry a `DFSL` marker. The marker tells a human glancing at the ticket, PR queue, or `git log` that the work came from the autonomous pipeline and that the disclaimer matters.

Sub-skills do NOT change their default templates. DFSL applies the prefix/chain at the point of invocation:

| Surface | Direct invocation (unchanged) | DFSL-driven invocation |
|---|---|---|
| JIRA comment heading | `## Plan — /jira-plan (date)` | `## DFSL — Plan (date)` |
| Agent footer `Workflow:` field | `**Workflow:** /jira-plan FP-XXX` | `**Workflow:** /dfsl > /jira-plan` |
| PR title | `FP-XXX <summary>` | `[DFSL] FP-XXX <summary>` |
| Commit subject | `FP-XXX <imperative>` | `[DFSL] FP-XXX <imperative>` |

Mechanically: when DFSL invokes a sub-skill, pass an environment hint (e.g. `DFSL_PARENT=1`) and have the sub-skill's prompt acknowledge it by prefixing headings, switching the footer to chain form, and prefixing commit subjects + PR title. Until each sub-skill is updated to honour the hint, DFSL post-processes the artefacts it can observe (PR title via `gh pr edit`, commit subjects via amending its own commits before push, JIRA comment via re-posting before the audit footer).

## 6. The DFSL Disclaimer

The disclaimer is the canonical end-of-run artefact. It appears in two places: appended to the PR body (last section), and reproduced inside the consolidated JIRA summary comment (§7).

```markdown
## ⚠️ DFSL Disclaimer — review before merging

**Overall confidence:** <Low | Medium | High>

| Phase | Confidence | Drivers |
|---|---|---|
| Plan | <Low/Med/High> | <one-line reason citing AC counts + unclear handling> |
| Impl | <Low/Med/High> | <one-line reason citing unfamiliar code, conflict frequency, skipped commits> |
| Test | <Low/Med/High> | <one-line reason citing case Pass/Fail/Not Run counts> |

### Assumptions made
- AC #<n> was `unclear`; assumed <decision> because <rationale> (evidence: `<file:line>` or `<rule path>` or `<prior FP-key>`).
- ...

### Items needing human verification
- [ ] <case scored `Not Run` because it required browser eyes / shared infra / human judgement>
- [ ] <edge case skipped because of <reason>>

### Known gaps
- <AC scored `missing` that was deliberately left unimplemented — name it and explain why>

### Run outcome
- Sub-skills run: <list of skills that fired>
- Sub-skills skipped: <list + reason>
- Final JIRA status: <In Review | TESTING | DONE>

---
**Agent sign-off:** Claude Code
**Workflow:** `/dfsl $ARGUMENTS`
**Timestamp:** <ISO-8601 with timezone>
```

**Confidence scoring rubric** (per phase):

| Phase | High | Medium | Low |
|---|---|---|---|
| **Plan** | All ACs cleanly classified; no `unclear`; no security-touching surface | ≤1 `unclear` AC; familiar surface | ≥2 `unclear` ACs OR security-adjacent (but not enough to abort) |
| **Impl** | Touched only well-known files; no merge conflicts; all commits clean | Touched unfamiliar code or had one conflict resolved | Multiple conflicts, partial implementation, or scope diverged from plan |
| **Test** | All cases `Pass`; full `/jira-test` ran in `--unattended` mode without refusal | ≤1 `Not Run`; everything else `Pass` | Any `Fail` or `Blocked`, or `--unattended` refused to post evidence |

**Overall confidence roll-up:** Low if any phase is Low. Medium if no Low but ≥1 Medium. High only if all three are High. The roll-up is mechanical; never override it for rhetorical effect.

## 7. End-of-run JIRA summary comment

After all sub-skills have terminated, post a single consolidated comment to `$ARGUMENTS`. This is in addition to the per-skill comments the sub-skills already posted.

```markdown
## DFSL — Run summary (YYYY-MM-DD)

**Outcome:** <Completed | Partial | Aborted>
**Final status:** <In Review | TESTING | DONE>
**PR:** <url or "no PR — aborted at pre-flight">
**Sub-skills:** ✓ `/jira-plan` · ✓ `/jira-impl` · ✓ `/jira-test` · ✓ `/jira-done`  *(✗ for skipped, with reason)*

<-- inline the full DFSL Disclaimer from §6 here -->

---
**Agent sign-off:** Claude Code
**Workflow:** `/dfsl $ARGUMENTS`
**Timestamp:** <ISO-8601 with timezone>

<!-- dfsl-summary run=<N> -->
```

## Guardrails

- **Never push directly to `dev` or `main`.** DFSL's branch is the only target. The PR is the human gate.
- **Never bypass pre-commit hooks** (`--no-verify` is banned). If a hook fails, DFSL records the failure as a `partial` outcome and surfaces it in the disclaimer.
- **Never skip the PR.** Even on a stuck implementation, open the PR with whatever landed and add a `blocked` section to the disclaimer — let a human pick it up.
- **Pre-granted operations only.** DFSL must not invoke any command that would prompt for permission. The pre-granted set: JIRA read/comment/transition/edit, `git` (feature branches), `gh pr create / ready / edit`, `pytest`, `npm test`, `gcloud auth/config list`. Anything outside that → treat as human-verify and surface in the disclaimer; never request consent mid-run.
- **Never paste raw secret values** into JIRA, chat, commits, or the disclaimer. Redact to `[REDACTED]` and cite `file:line` only.
- **Strictly one-arg.** If invoked with anything other than a single JIRA key, exit immediately with a one-line error. No flags in v1.

## End-of-run usage recording (FP-192) — MANDATORY

You **MUST** append the terminal event before exiting (after the disclaimer + JIRA summary comment have landed, or after a pre-flight abort).

```bash
python scripts/record_usage.py --command /dfsl --outcome <state> [--note "<friction>"]
```

States (all five are **terminal**):
- `completed` — `/jira-test` clean-pass and `/jira-done` produced release docs (final status `DONE`)
- `partial` — PR opened but tests had `Fail` / `Blocked` / `Not Run` (final status `TESTING`)
- `blocked` — pre-flight gate fired, sub-skill blocked, or pre-granted-permissions guardrail tripped (final status unchanged)
- `failed` — DFSL itself errored (e.g. unexpected git conflict it could not resolve)
- `skipped` — DFSL intentionally short-circuited (e.g. detected a prior `<!-- dfsl-aborted -->` marker from a recent run)

Add `--note` whenever state is not `completed`. The matching `started` event is auto-recorded by the `UserPromptSubmit` hook for user-typed invocations, but **chained invocations through the Skill tool bypass that hook** — record the `started` event manually when chained.
