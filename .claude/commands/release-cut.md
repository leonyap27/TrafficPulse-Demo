---
description: Close the current sprint release, bump VERSION, and open the next tracker with carry-overs. Two modes — PREVIEW (default, read-only, ephemeral) shows the bundle decision table; YES mode performs the actual cut on a chore branch. FP-214.
argument-hint: [<semver>] [YES]
---

Close the sprint release for: **$ARGUMENTS**

## Command shapes

| Invocation | Mode | Effect |
|---|---|---|
| `/release-cut` | **PREVIEW** | Read-only decision table. No writes. |
| `/release-cut 0.5.0` | **PREVIEW** | PREVIEW with explicit next-version shown. |
| `/release-cut YES` | **CUT** | Performs the cut with default patch bump. |
| `/release-cut 0.5.0 YES` | **CUT** | Performs the cut with explicit version. |

**PREVIEW is the default.** Re-run any time — it is ephemeral and writes nothing.

**YES is required** to perform any writes (JIRA, VERSION file, git commit).

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /release-cut --outcome started --trigger slash-command
```

Run this first. Chained invocations bypass the `UserPromptSubmit` hook; this
call guarantees the event is captured regardless.

## 1. Parse arguments

Parse `$ARGUMENTS`:

- Semver-shaped positional arg matching `^\d+\.\d+\.\d+$` → `explicit_version`.
- `YES` (case-sensitive) anywhere in args → `cut_mode = True`. Default: `False`.

## 2. Resolve active tracker

Run JQL via `searchJiraIssuesUsingJql`:

```
project = FP AND labels = "release-tracker" AND status not in ("READY FOR DEPLOY", DONE) ORDER BY created DESC
```

- **Zero matches** → **STOP.** Print:
  ```
  No active release tracker. Create one manually using the
  RELEASE_TRACKER_SCHEMA.md template, or open one from a prior cut.
  ```
  Record `--outcome blocked` and exit.
- **One match** → `TRACKER_KEY` (e.g. `FP-194`). Capture `description`.
- **Multiple matches** → take the **top** (newest by `created`). Log:
  _"Multiple open release-trackers; using `<top-key>` (most recent by created)."_

## 3. Read current version

```bash
VERSION=$(cat VERSION)
```

Validate it is a MAJOR.MINOR.PATCH string. If malformed, **STOP** with:
```
VERSION file contains "<content>" which is not a valid semver. Fix it before cutting.
```

## 4. Compute next version

```python
from scripts.release_cut import resolve_next_version
next_version = resolve_next_version(current_version, explicit_version_or_None)
```

## 5. Fetch bundle items with live JIRA status

Parse the tracker description to extract bundle lines using
`scripts.release_cut.parse_bundle_lines`. Then for each unique `FP-XXX` key,
call `getJiraIssue` with `fields=["summary","status","labels","sprint"]` to
get live status and sprint metadata.

**Batch these calls in parallel** — they are independent reads.

Construct a list of `BundleItem` objects with `key`, `summary`, `status`,
`work_type` (from the bundle line tag), and `sprint` (from the JIRA sprint
field, or `None` if unset).

## 6. Detect current sprint

Read the `## Release manifest` section of the tracker description. Parse the
`Sprint:` line if present (e.g. `Sprint 1 (12 May - 26 May 2026)`). If absent
or `TBD`, set `current_sprint = None` (contamination detection disabled).

## 7. Build PREVIEW table

```python
from scripts.release_cut import build_preview_table, render_preview_markdown
rows = build_preview_table(items, current_version, next_version, current_sprint)
md = render_preview_markdown(rows, current_version, next_version, TRACKER_KEY)
```

Print `md` to chat.

**PREVIEW-only mode** (no `YES`): record `--outcome completed` and **stop here**.
The table is the output; nothing else should happen.

---

## CUT mode — only runs when `YES` was given

All steps below are skipped entirely in PREVIEW mode.

## 8. Confirm with operator

Print to chat (substituting live values):

```
Ready to cut v<current> → v<next>?

  Tracker:     <TRACKER_KEY> (<N> items; <M> carry-over candidates)
  VERSION:     <current> → <next>
  Chore branch: chore/release-cut-v<next>

This creates a chore branch with:
  • VERSION bump <current> → <next>
  • v<current>_draft.md → v<current>.md (if the draft exists)

JIRA side effects (applied before branch commit):
  • <TRACKER_KEY> → READY FOR DEPLOY
  • New tracker created: Release v<next> → UAT (TBD)

Revert path:
  git branch -D chore/release-cut-v<next>  (all file changes gone)
  Manually: revert <TRACKER_KEY> back to In Progress; delete new tracker.

Proceed? (Y / change-version <X> / cancel)
```

- **Y** → continue.
- **change-version `<X>`** → re-parse `<X>` as `explicit_version` and restart from step 4.
- **cancel** → record `--outcome skipped --note "operator cancelled at confirmation"` and exit.

## 9. Transition DONE items + collect carry-overs (no prompts)

### 9a. Transition READY FOR DEPLOY bundle items → DONE

For each bundle item whose live JIRA status is `READY FOR DEPLOY`, call
`getTransitionsForJiraIssue` + `transitionJiraIssue` to move it to `DONE`.
Log each transition: *"FP-XXX: READY FOR DEPLOY → DONE."*

On failure: log the error, continue — a single item's transition failure must
not block the cut. Note the failure in the `## Recovery` section of the cut
summary.

### 9b. Auto-carry all remaining non-DONE items

No per-item prompt is needed. All items not in `{"DONE", "READY FOR DEPLOY"}`
are automatically carried forward:

```python
from scripts.release_cut import auto_carry_all
carry_overs = auto_carry_all(items)
```

If `carry_overs` is empty: print `All bundle items are DONE — no carry-overs.`

### 9c. Determine document flag per carry-over

For each carry-over item, check whether `/jira-done` docs exist in the current
sprint folder:

```python
import os
from scripts.release_cut import RELEASES_DIR

folder = RELEASES_DIR / f"v{current_version}-{TRACKER_KEY}"
has_doc = any(folder.glob(f"{item.key}-*-*.md")) if folder.exists() else False
```

Pass `has_doc` into the `CarryOverTicket` when building the new tracker body
(step 15b). `/release-cut` will auto-invoke `/jira-done` for `has_doc=True`
items after the new tracker is created (step 15d).

## 10. Create chore branch

Check that `chore/release-cut-v<next>` does NOT already exist:

```bash
git branch --list chore/release-cut-v<next>
```

If it exists → **STOP.** Print:
```
Branch chore/release-cut-v<next> already exists.
A prior cut attempt may be in progress. Inspect and delete the branch before retrying:
  git branch -D chore/release-cut-v<next>
```
Record `--outcome blocked` and exit.

Otherwise:

```bash
git checkout -b chore/release-cut-v<next>
```

## 11. Promote sprint draft (file-side)

```python
from scripts.release_cut import promote_draft, RELEASES_DIR
promoted, dest_path, skip_reason = promote_draft(RELEASES_DIR, current_version)
```

- **Promoted**: stage `dest_path` (`v<current>.md`) in git. Log to chat:
  `Draft promoted: v<current>_draft.md → v<current>.md`
- **Skipped**: note in `## To follow up` of the cut summary:
  `No v<current>_draft.md found — sprint release notes not assembled.
   Run /jira-done on each READY FOR DEPLOY ticket (if not already done),
   or write docs/3.0-deployment/releases/v<current>.md manually.`
  Continue — draft absence is not a blocking error.

## 12. Bump VERSION (file-side)

```python
from scripts.release_cut import write_version
write_version(next_version)
```

Stage `VERSION` in git.

## 13. Commit all file changes

```bash
git add VERSION docs/3.0-deployment/releases/v<current>.md  # only if promoted
git commit -m "FP-214 release-cut v<current> → v<next>"
```

The chore branch now contains ALL file-side changes. Full revert:
```bash
git branch -D chore/release-cut-v<next>
```

## 14. JIRA — transition current tracker to READY FOR DEPLOY

Call `getTransitionsForJiraIssue` on `TRACKER_KEY` to find the transition id
whose target status name is `READY FOR DEPLOY`. Call `transitionJiraIssue`
with that id.

On failure: note in the cut summary `## Recovery` section; continue — do not
abort the whole cut for a JIRA transition error.

Print reminder to chat:
```
⚠️  Tracker <TRACKER_KEY> is now READY FOR DEPLOY.
    Before promoting to UAT, tick the readiness checklist and get approver sign-off in JIRA.
```

## 15. JIRA — create next tracker

### 15a. Idempotency check

```
project = FP AND labels = "release-tracker" AND text ~ "<next_version>"
```

If a tracker already exists for `<next_version>`: skip create; log the existing
key in the cut summary. Proceed to 15c.

### 15b. Build tracker body

```python
from scripts.release_docs.next_tracker import build_next_tracker_body
from scripts.release_docs.models import CarryOverTicket

carry_over_tickets = [
    CarryOverTicket(key=i.key, summary=i.summary, status=i.status, has_doc=i.has_doc)
    for i in carry_overs
]
body = build_next_tracker_body(
    prev_tracker_key=TRACKER_KEY,
    next_version=next_version,
    target_env_detail="UAT (Cloud Run: funding-paper-agent)",
    approver="Leon Ye",
    carry_over=carry_over_tickets,
)
```

`target_env_detail` and `approver` are inherited from the previous tracker's
`## Release manifest` section.

### 15c. Create via MCP

Call `createJiraIssue` with:
- `projectKey: "FP"`
- `issueType: "Task"`
- `summary: "Release v<next_version> → UAT (TBD)"`
- `description: <body>` with `contentFormat: "markdown"`
- `labels: ["release-tracker"]`

Capture the new key as `NEW_TRACKER_KEY`.

### 15d. Auto-invoke `/jira-done` for carry-overs with existing docs

For each carry-over item where `has_doc=True`, invoke `/jira-done <item.key>` so
the docs are regenerated into the **new** sprint folder
(`v<next_version>-<NEW_TRACKER_KEY>/`).

This is best-effort: a failure on one item must not block the cut. Log each
invocation result. Items with `has_doc=False` are skipped — the operator can
run `/jira-done` manually once those tickets are tested in the new sprint.

## 16. JIRA — link trackers

**Add forward link on current tracker:**

Post a comment on `TRACKER_KEY`:

```markdown
Sprint closed. Next tracker: [<NEW_TRACKER_KEY>](https://ltads.atlassian.net/browse/<NEW_TRACKER_KEY>)
(v<current> → v<next>)

---
**Agent sign-off:** Claude Code
**Workflow:** `/release-cut`
**Timestamp:** <ISO-8601 with timezone>
```

**Add backward note on new tracker:**

Post a comment on `NEW_TRACKER_KEY`:

```markdown
Opened from sprint close of [<TRACKER_KEY>](https://ltads.atlassian.net/browse/<TRACKER_KEY>)
(v<current> → v<next>). Carry-overs: <N> items.

---
**Agent sign-off:** Claude Code
**Workflow:** `/release-cut`
**Timestamp:** <ISO-8601 with timezone>
```

## 17. Print cut summary

```
Cut complete.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Closed:         <TRACKER_KEY> → READY FOR DEPLOY (v<current>)
  New tracker:    <NEW_TRACKER_KEY> (v<next>)
  VERSION:        <current> → <next>
  Chore branch:   chore/release-cut-v<next>  (push manually when ready)
  Carry-overs:    <N> items
  Dropped:        <M> items (excluded from next tracker)
  Draft promoted: <yes — v<current>.md> | <no — see To follow up below>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Include `## To follow up` section when any of these apply:
- Draft was not found / promoted
- Any JIRA transition failed
- Carry-over items have status other than `In Progress` (may need re-planning)

Include `## Recovery` section if any write step failed, listing:
1. Steps successfully completed (with JIRA links / git refs)
2. Step that failed
3. Manual commands to finish or revert

## Guardrails

- **PREVIEW never writes.** No files, no git, no JIRA calls that mutate state.
- **Chore-branch conflict is a hard stop.** Never overwrite an existing branch.
- **All non-DONE items are auto-carried.** No per-item prompt. The `Document (Y/N)`
  column drives whether `/jira-done` is re-invoked for each carry-over.
- **Never paste raw secret values** into JIRA, chat, or commits.
- **Draft absence is not an error.** Log in `## To follow up`, continue.
- **JIRA transition failure is non-blocking.** Log in `## Recovery`, continue
  with the rest of the cut so the chore branch and new tracker are created.

## End-of-run usage recording (FP-192) — MANDATORY

```bash
python scripts/record_usage.py --command /release-cut --outcome <state> [--note "<friction>"]
```

States: `completed` (full cut done: JIRA + VERSION + commit) | `partial` (some
steps done but not all, e.g. JIRA done but chore commit failed) | `blocked`
(no active tracker, chore-branch conflict, operator cancelled) | `failed`
(unhandled error mid-run) | `skipped` (PREVIEW-only run — no writes). Add
`--note` whenever state is not `completed`.

PREVIEW runs always record `--outcome skipped --note "preview-only"`.
