---
description: Generate release document(s) from a JIRA release tracker. Two modes — render-only (default, idempotent prose-safe regenerate) or YES super-command (close-the-sprint, also transitions READY-FOR-DEPLOY items to DONE, lists carry-over, creates next sprint's tracker, prompts to bump VERSION). FP-188 + FP-198.
argument-hint: <tracker-key, optional> [YES | technical | business | both] [--next-version <semver>]
---

Generate release document(s) for: **$ARGUMENTS**

Orchestrates the FP-188 release-doc generator and (when `YES` is passed) the FP-198 sprint-close flow. The Python renderer (`scripts/render_release_doc.py`) is deterministic and has no JIRA dependency; this slash command does the JIRA I/O via MCP and pipes structured JSON in.

### Examples

| Invocation | What happens |
|---|---|
| `/release-doc FP-194` | **Render-only** — generates both docs and posts to the tracker. No JIRA status changes, no new tickets, no VERSION bump. Idempotent. |
| `/release-doc FP-194 YES` | **Close the sprint** — render-and-post, then transition `READY FOR DEPLOY` items to `DONE`, list carry-over, create next sprint's tracker, prompt to bump `VERSION`. One-shot, side-effecting. See the Modes section. |
| `/release-doc FP-194 YES --next-version 0.5.0` | Same as YES, but the new tracker uses `0.5.0` instead of the default PATCH increment. Use when promoting a MINOR (UAT cut). |
| `/release-doc FP-194 technical` | Render-only, technical doc only. |
| `/release-doc FP-194 business` | Render-only, business doc only. |
| `/release-doc` (no arg) | Reads `.claude/usage/deploy-ledger/pending/`, picks the **oldest** entry, finds the matching `release-tracker` issue via JQL (`labels = "release-tracker"` + matching version). Render-only, both audiences. |
| `/release-doc` with empty pending dir | **Stops:** "No pending deploys and no tracker key. Pass `/release-doc FP-XXX`." |

### Modes

Two modes, selected by the presence of `YES` (case-sensitive) as a positional arg.

**Render-only (default)** — writes files, posts JIRA comments. **No** JIRA status changes, **no** new tickets, **no** `VERSION` bump. Safe to re-run for prose iteration or after a tracker description edit. Not a preview — the files and comments are real artefacts.

> **Deprecation notice (FP-214):** `/release-doc FP-XXX YES` is superseded by
> `/release-cut YES`, which handles sprint close more completely: PREVIEW mode,
> per-item carry-over prompts, sprint contamination detection, chore branch with
> full revert path, and VERSION-specific draft promotion. Use `/release-cut YES`
> for new sprint closes. `/release-doc YES` is retained for backward
> compatibility and will require explicit approval before removal.

**`YES` super-command** — does everything render-only does, then in order:

1. Walks each bundle item in JIRA; for items in `READY FOR DEPLOY`, transitions them to `DONE`.
2. Collects bundle items still not-`DONE` after transitions as carry-over; renders them in the doc's `Carry-over to next sprint` section.
3. Creates the next sprint's release-tracker JIRA issue (label `release-tracker`), pre-populated with the carry-over items. **Idempotent** — if a next-tracker for the next version already exists, skips create and reports.
4. Prompts (interactive only): `Bump VERSION <current> → <tracker-manifest>?` with explicit handover language. On `y`, edits `VERSION` and creates a single commit bundling the bump with the release docs.

`YES` is a one-shot lifecycle event. JIRA-side side effects (transitions, next-tracker) are applied **before** the VERSION-bump prompt fires, so the prompt is the 2nd-chance gate for the *code-side* commit only — not for the JIRA-side state. Code can be reverted via `git revert`; JIRA-side requires manual unwind.

### Audience semantics

- **Technical** doc (`v<version>/FP-XXX.md`) — for engineers, ops, auditors. Includes FP-XXX keys, work-type tags, component buckets (Frontend / Backend / Agents+RAG / Infra / Security / Docs), test evidence, readiness checklist, PR references, rollback note.
- **Business** doc (`v<version>/FP-XXX_business.md`) — for managers, stakeholders, exec briefings. Three layered views: Summary (manual narrative from the tracker), Talking points (LLM-distilled outcomes), What shipped (flat outcome-framed list). Strips FP-XXX, work-type tags, and engineering detail.

Outputs live under `docs/3.0-deployment/releases/v<version>/` — one subdirectory per version, with one technical + one business doc per release tracker. The ticket-key filename means two trackers that happen to share a version string won't collide.

### Versioning behaviour

The version is **read from the tracker's** `## Release manifest > Version` field — never invented by this command. Re-running against the same tracker key always produces the same version. To produce a new version, create a **new** release tracker following [`docs/3.0-deployment/RELEASE_TRACKER_SCHEMA.md`](../../docs/3.0-deployment/RELEASE_TRACKER_SCHEMA.md) with the bumped version in its manifest body, then run this command against the new tracker key — or run `YES` against the current tracker and let the command auto-create the next one.

### Idempotency / re-running

Re-running for the same tracker is safe but not silent. Effects per re-run:

- **Markdown output** (`docs/3.0-deployment/releases/v<version>/FP-XXX.md` and `FP-XXX_business.md`): **overwritten** in place. Any manual prose edits to the file are lost.
- **Tracker JIRA comment**: a **new comment is added** each run. Prior generation comments stay as history. Use the latest as authoritative.
- **Deploy ledger**: consumed only by the **first** run that auto-discovered the entry. Subsequent explicit-key runs do **not** touch ledger state.
- **YES transitions**: only items currently in `READY FOR DEPLOY` are touched; items already `DONE` are skipped silently. Re-runs cleanly catch items that finished testing between runs.
- **YES next-tracker**: idempotent — JQL detects an existing tracker for the next version and skips create. Never produces a duplicate.

### Prose edits vs. data refresh

Once a release doc is generated and reviewed, **edit the committed `.md` file directly** for prose tweaks — that file is the source of truth post-generation. Don't re-run `/release-doc` to "fix wording". Re-running runs the polish step (Vertex Gemini) afresh, which is non-deterministic and will overwrite your edits with a different paraphrase. Re-running is for refreshing from **changed tracker data** (new tickets added to the bundle, change-summary updated, etc.), not for prose iteration.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /release-doc --outcome started --trigger slash-command
```

Run this first to capture usage for direct and chained invocations (the `UserPromptSubmit` hook also records, but chained invocations through the Skill tool bypass it).

## 1. Determine target tracker and parse mode

Parse `$ARGUMENTS`:

- First positional arg matching `^FP-\d+$` → the tracker key.
- `YES` (case-sensitive) anywhere in args → enable YES mode (sprint close).
- `technical` / `business` / `both` → audience override. Default `both`. (Ignored when `YES` is set — YES always runs `both`.)
- `--next-version <semver>` → override the next-tracker version (only used by YES; ignored otherwise).

If no tracker key in args:
- Read `.claude/usage/deploy-ledger/pending/` and pick the **oldest** JSON entry (earliest `timestamp`). Use its `version` to find the matching `release-tracker` issue via JQL:
  ```
  project = FP AND labels = "release-tracker" AND text ~ "<version>" ORDER BY created DESC
  ```
  If multiple match, ask the user to disambiguate by tracker key.
- If pending ledger is empty and no argument given, **STOP**: "No pending deploys and no tracker key provided. Pass `/release-doc FP-XXX` to target a specific tracker."
- Auto-discovery never enables YES; YES must be explicit.

## 2. Fetch tracker via MCP

Use `getJiraIssue` for the tracker key. Read its description body. Verify the `labels` field contains `release-tracker`; if not, **STOP** and warn — wrong issue type.

Parse the description per `docs/3.0-deployment/RELEASE_TRACKER_SCHEMA.md` to extract:

- Release manifest (version, target_env, release_date, approver, sprint, optional uat_owner/pm)
- Change summary bullets
- Bundle entries (key, work_type tag, summary)
- PR / commit references
- Readiness checklist items
- Test evidence links
- Known issues (optional; render "None reported" if absent)

## 3. Fetch each linked ticket's metadata

For each FP-XXX in the bundle, call `getJiraIssue` with `fields=["components", "labels", "parent", "summary", "status"]`. Build the per-ticket records:

- `components`: list of component names
- `labels`: list of labels (work-type labels included)
- `parent_epic_key`: parent issue key if it's an Epic
- `parent_epic_summary`: parent issue summary
- `status`: workflow status name (`READY FOR DEPLOY`, `In Review`, `DONE`, etc.) — used by `YES` mode in step 3b; render-only mode ignores this field.

**Batch these calls in parallel** — they are independent reads. For a 15-ticket bundle, dispatch in one round-trip.

## 3b. (YES mode only) Transition `READY FOR DEPLOY` items and collect carry-over

**Skip this step entirely in render-only mode.**

For each bundle ticket whose status is `READY FOR DEPLOY`:

1. Call `getTransitionsForJiraIssue` to find the transition id whose target status is `DONE` (a.k.a. `DONE` in JIRA's status table, id `31` in this project's workflow — but always look it up rather than hardcoding).
2. Call `transitionJiraIssue` with that id.
3. Update the in-memory ticket record's `status` to `DONE` so step 4 sees the post-transition state.

If a transition call fails (workflow forbids the move, a human concurrently changed status, etc.), **log the failure and continue with the next item — do not stop the run.** The release doc + post step should still happen; the failed item naturally lands in carry-over, giving the operator a visible signal to investigate.

**Batch the transition calls in parallel** — independent writes.

After the walk, collect every bundle ticket whose status is **not** `DONE` into the `carry_over` list:

```python
carry_over = [
    {"key": t.key, "summary": t.summary, "status": t.status}
    for t in bundle
    if t.status != "DONE"
]
```

This list becomes the `carry_over` field on the `ReleaseInput` in step 4. Count of successful transitions and carry-over items are surfaced in the chat report (step 10).

## 4. Build the structured JSON

Construct a `ReleaseInput` dict matching the schema in `scripts/release_docs/SAMPLE_INPUT.json`. Required fields:

- `tracker_key`, `tracker_url`, `jira_base_url` (`https://ltads.atlassian.net`)
- `manifest`: parsed in step 2 (split `target_env` short like "UAT" from `target_env_detail` full like "UAT (Cloud Run: funding-paper-agent)")
- `change_summary`: bullet list
- `bundle`: list of BundleTicket
- `pr_references`, `readiness`, `test_evidence`, `known_issues`
- `previous_version`: derive from VERSION history (read the prior tag with `git tag --sort=-v:refname | head -3` and pick the one before current)
- `carry_over`: empty `[]` in render-only mode; populated in YES mode from step 3b's collection.

Write the dict as JSON to a temp file (e.g. `.test-evidence/FP-198/release-input-<tracker_key>.json`). This temp file is also useful evidence if the user wants to inspect inputs.

## 4b. Decide whether to compose extra technical-doc visuals (FP-200)

**You — the host LLM orchestrating `/release-doc` — are the selector.** The renderer does not pick extras; it only embeds what you pass it via `--extras-file`. The always-on components flowchart (technical) and pie + mindmap (business) are built deterministically by the Python renderer and need no input from you.

Decide which (if any) of the three extras to compose, using the bundle composition you already loaded in step 3:

- **Sequence diagram** — when 2+ bundle tickets share a `parent_epic_key` belonging to a known multi-step-workflow epic (today: `FP-92` paper generation, `FP-183` release governance) **AND** at least one of them lands in the `Agents+RAG` or `Backend` bucket. Use a `sequenceDiagram` mermaid block to show the workflow the changes touch.
- **Swimlane** — when the bundle touches 3+ distinct buckets out of {`Frontend`, `Backend`, `Agents+RAG`, `Infra`}. Cross-actor signal (user ↔ system ↔ agent ↔ DB). Use mermaid `flowchart` with `subgraph` per actor, or `sequenceDiagram` with `participant` per actor.
- **Decision table** — when any bundle ticket lands in the `Backend` bucket **AND** its summary text contains `api`, `endpoint`, `contract`, `schema`, or `migration` (case-insensitive). Render as a plain markdown table: `| Decision | Old | New |`.

**Composition rules:**

1. Apply judgement layered on top of the heuristics. The triggers above are the floor — also consider what would serve the reader of *this* specific release (engineer scanning the technical doc). If a heuristic fires but the diagram would be trivial / repeat the bullets, skip it. If a heuristic does not fire but a visual would clearly help, include it.
2. **Bugfix-only / docs-only bundle → write no extras file** (covers FP-200 AC4). Skip step 4b entirely.
3. Compose the extras as markdown with `### <Heading>` sub-headings per primitive. Multiple primitives go in the same file, separated by blank lines. Example:
   ```markdown
   ### Workflow

   ```mermaid
   sequenceDiagram
       participant U as User
       participant A as Agent
       U->>A: generate section
       A-->>U: streamed output
   ```

   ### Decision points

   | Decision | Old | New |
   |---|---|---|
   | Auth on `/api/session` | none | required Bearer token |
   ```
4. Write the file to `.test-evidence/FP-200/extras-<tracker_key>.md` (project convention for tool-agnostic evidence — Codex and any other agent uses the same path).

**Idempotency caveat (FP-200 AC5):** same host LLM + same bundle should converge to the same set of primitives most of the time, but byte-identical re-runs are not guaranteed. Idempotency is interpreted as **semantically consistent** — the same set of primitives appears across re-runs; their specific wording or layout may vary. The always-on components diagram (technical) and pie + mindmap (business) **are** byte-identical across re-runs because they are deterministic Python output.

**No host LLM extras for the business doc.** The business audience gets the always-on pie + mindmap and nothing else; the LLM does not compose extras for it. Talking-points distillation remains its own separate `--polish` LLM step (Gemini), unchanged by this step.

## 5. Render

Audience choice: `both` if YES, otherwise from `$ARGUMENTS` (default `both`).

```bash
python scripts/render_release_doc.py \
  --input <tmp-json-path> \
  --output docs/3.0-deployment/releases/v<version>/<tracker-key>.md \
  --audience <technical|business|both> \
  --polish \
  --extras-file .test-evidence/FP-200/extras-<tracker_key>.md \
  --generated-at $(date -Iseconds)
```

Pass `--extras-file` **only if** step 4b composed extras. Omit the flag entirely when no extras file was written (bugfix-only bundles, or step 4b explicitly skipped). The flag is ignored for `--audience business` (business doc never receives extras).

The orchestrator computes the `<tracker-key>` segment from `$ARGUMENTS` (e.g. `FP-194.md` for tracker `FP-194`). The `v<version>/` parent directory is created automatically by the renderer if missing.

When `--audience both`, the technical output is `FP-XXX.md` and the business output is automatically derived as `FP-XXX_business.md` in the same `v<version>/` subdirectory.

`--polish` runs Vertex Gemini polish — per-bucket for technical, and per-bucket + talking-points distillation for business. If `GOOGLE_CLOUD_PROJECT` isn't set, the build will fail loudly — fall back to running without `--polish` and note in chat that polish was skipped (the business doc's "Talking points" section will render a placeholder instead).

If render succeeds: continue. If it fails: surface the error and **STOP** before posting to JIRA — never half-deliver. In YES mode, the JIRA-side transitions from step 3b already happened — flag this clearly in the failure report so the operator knows the JIRA state is ahead of the code state.

## 6. Post to tracker

Post **one comment per generated audience**. Use `addCommentToJiraIssue` on the tracker key with each rendered markdown as `commentBody` (use `contentFormat: "markdown"`):

- Technical doc → comment headed `## Release v<version> — Technical release notes`
- Business doc → comment headed `## Release v<version> — Business highlights (for stakeholders)`

> **Note:** The management summary (`v<version>_draft_management.md`) is assembled by `/jira-done`, not here. `/release-doc` does not regenerate it.

Each comment ends with the standard audit footer:

```markdown
---
**Agent sign-off:** Claude Code
**Workflow:** `/release-doc <tracker-key> <mode-or-audience>`
**Timestamp:** <ISO-8601>
```

## 7. Mark ledger entry processed (if originated from ledger)

If step 1 sourced a ledger entry, move it from `pending/` to `processed/`, updating `status` to `done` and adding `generated_path: docs/3.0-deployment/releases/v<version>/FP-<tracker-key>.md`. Use `git mv` so the move is tracked.

## 8. (YES mode only) Create next-sprint release-tracker

**Skip this step entirely in render-only mode.**

### 8a. Determine next version

Default: PATCH increment of the current tracker's version. Use `scripts.release_docs.bump_patch(current_version)`.

If `$ARGUMENTS` includes `--next-version <semver>`, override the default with the explicit value (e.g. for a MINOR bump on UAT promotion).

### 8b. Idempotency check

Before creating, run JQL:

```
project = FP AND labels = "release-tracker" AND text ~ "<next-version>"
```

If a tracker already exists for `<next-version>`:

- **Skip create.**
- Note in the chat report: `Next tracker already exists: FP-XXX (skipped create)`.
- Proceed to step 9 — the existing tracker key is used in the VERSION-bump prompt.

If no match → continue.

### 8c. Build the next-tracker body

Call `scripts.release_docs.build_next_tracker_body(...)` with:

- `prev_tracker_key`: the tracker passed to `/release-doc`
- `next_version`: from 8a
- `target_env_detail`: inherited from previous tracker's manifest
- `approver`: inherited from previous tracker's manifest
- `carry_over`: the list collected in step 3b (may be empty)

The helper returns a markdown body string ready to use as the description.

### 8d. Create the tracker

Call `createJiraIssue` with:

- `projectKey: "FP"`
- `issueType: "Task"`
- `summary: "Release v<next-version> → UAT (TBD)"` — date placeholder; operator fills in at sprint close
- `description: <body from 8c>` with `contentFormat: "markdown"`
- `labels: ["release-tracker"]`
- Don't set assignee, fix-version, or sprint — those are operator decisions.

Capture the new tracker key (e.g. `FP-199`) for the chat report and the VERSION-bump prompt.

## 9. (YES mode only) Prompt to bump `VERSION` and bundle into one commit

**Skip this step entirely in render-only mode.** Also skip when running non-interactive (stdin is not a TTY) — emit a structured log entry and proceed:

```
VERSION_BUMP_SKIPPED reason=non-interactive tracker_manifest=<v> current=<cat VERSION>
```

### 9a. Interactive prompt with explicit handover language

Read current value: `cat VERSION` (e.g. `0.4.5`). Compare against the tracker's manifest version (e.g. `0.4.6`).

If they already match → skip the prompt; log `VERSION_BUMP_SKIPPED reason=already-current value=<v>`.

Otherwise display this prompt verbatim, substituting the live values:

```
Bump VERSION 0.4.5 → 0.4.6 and commit?

⚠️  HANDOVER — confirming creates a single commit bundling:
     • VERSION bump 0.4.5 → 0.4.6
     • Release docs under docs/3.0-deployment/releases/v0.4.6/

Revert paths if needed:
     • Code-side: git revert / reset on this commit (safe).
     • JIRA-side: status transitions (N items → DONE) and the next-sprint
       tracker (FP-XXX) were already applied earlier in this run. They
       require manual unwind in JIRA — not auto-reverted by saying no here.

Proceed? [y/N]
```

Substitute `N items → DONE` with the actual transition count from step 3b. Substitute `FP-XXX` with the next-tracker key from step 8d (or `(skipped — already exists: FP-YYY)` if step 8b found an existing one).

### 9b. On `y`

Edit `VERSION` to the new value. Stage `VERSION` plus both release-doc files. Commit with this message:

```
FP-<prev-tracker-key> release v<new-version> — bump VERSION and ship docs

Generated from <prev-tracker-key>. Next-sprint tracker: <next-tracker-key>.
```

The commit is intentionally single — bundling VERSION + docs makes the release-stage state atomic in git history.

### 9c. On `n` or any other input

Leave `VERSION` unchanged. Release docs stay in the working tree uncommitted. Note in chat: `VERSION bump declined. Release docs are in the working tree; commit manually when ready: git add docs/3.0-deployment/releases/v<version>/`.

## 10. Report

Summarise in chat:

- Current tracker key + URL
- Generated file paths (technical + business)
- JIRA comment URL(s) (from the addComment responses)
- Whether polish was applied or skipped (and why)
- Ledger entries remaining in `pending/`
- **(YES only)** Bundle item transitions: `<N> items transitioned READY FOR DEPLOY → DONE; <M> items carried over`. List the carry-over items with their statuses.
- **(YES only)** Next-sprint tracker: `Created FP-XXX (v<next-version>)` or `Existing FP-XXX (skipped create)`.
- **(YES only)** VERSION bump result: `Bumped 0.4.5 → 0.4.6 (commit <sha>)` or `Declined — left at 0.4.5` or `Skipped — non-interactive` or `Skipped — already at 0.4.6`.

## Guardrails

- Never invent tracker content — if a section is missing from the tracker description, render the empty placeholder ("None reported.", `—`) explicitly.
- Never post a partial doc to JIRA. If any step fails after rendering, stop and report.
- The polish failure-mode is per-bucket fallback to raw bullets — do not retry the whole render on a polish hiccup.
- If a bundle ticket has neither components, labels, nor parent epic that map to a known bucket, it lands in `Other`. Flag this in the chat report so the user can decide if the categorizer needs extending.
- **YES mode JIRA writes are applied before the VERSION-bump prompt.** A user saying `n` at the prompt does not undo transitions or the next-tracker creation. The prompt text MUST spell this out (the template in 9a is non-negotiable).
- **Auto-discovery never enables YES.** A no-arg invocation is always render-only. YES requires the operator to type it.

## End-of-run usage recording (FP-192) — MANDATORY

```bash
python scripts/record_usage.py --command /release-doc --outcome <state> [--note "<friction>"]
```

Terminal states: `completed` | `partial` | `blocked` | `failed` | `skipped`. Add `--note` whenever the state is not `completed`. Examples:

- `partial` if polish was skipped due to missing `GOOGLE_CLOUD_PROJECT`, or some `READY FOR DEPLOY` transitions failed in YES mode.
- `blocked` if step 1 stopped because no tracker / no ledger entry.
- `failed` if render or post crashed.
- `skipped` if the operator declined the VERSION bump but everything else completed (the YES JIRA side is done; only the bump was skipped).
