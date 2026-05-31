---
description: Accumulate polished per-ticket release docs after /jira-test Pass — writes up to three audience-specific markdown files (technical / business / management) with a/b/c priority tags into the active release tracker's docs folder.
argument-hint: <JIRA-KEY> (e.g. FP-213)
---

Generate per-ticket release documentation for JIRA ticket: **$ARGUMENTS**

Run this **after** `/jira-test $ARGUMENTS` has reported a clean `Pass` and the ticket is `READY FOR DEPLOY`. At sprint close, `/release-cut` collects all the b-tagged (and optionally a-tagged) files and assembles the final release documents.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /jira-done --outcome started --trigger slash-command
```

This MUST run **first**, before the pre-flight gate or any JIRA reads. The `UserPromptSubmit` hook also records a `started` event when the user types `/jira-done` directly, but **chained invocations bypass that hook** — this explicit call guarantees the start is captured regardless. Duplicate `started` events are harmless.

## 1. Pre-flight gate

Fetch the ticket via `getJiraIssue` (fields: `status`, `summary`, `labels`).

| Ticket status | Skill behavior |
|---|---|
| **`READY FOR DEPLOY`** | Green light — proceed. |
| **`DONE`** | Green light — docs may have been missed at sprint close; allow re-run. |
| **`TESTING`** | **STOP.** "Ticket is still in TESTING. Human-verify items may be pending. Run `/jira-test $ARGUMENTS` to completion first, then `/jira-done`." Record `--outcome blocked` and exit. |
| **Any other status** | **STOP.** "Ticket must be `READY FOR DEPLOY` or `DONE` before generating release docs. Current status: `<status>`." Record `--outcome blocked` and exit. |

## 2. Resolve the active release tracker

Run JQL via `searchJiraIssuesUsingJql`:

```
project = FP AND labels = "release-tracker" AND status not in ("READY FOR DEPLOY", DONE) ORDER BY created DESC
```

- **Zero matches** → **STOP.** "No active release tracker found. Open one via the [RELEASE_TRACKER_SCHEMA template](../../docs/3.0-deployment/RELEASE_TRACKER_SCHEMA.md) or wait for `/release-cut` (FP-X3)." Record `--outcome blocked` and exit.
- **One match** → capture its key (e.g. `FP-194`). This is `TRACKER_KEY`.
- **Multiple matches** → take the **top** (newest by `created`). Log: *"Multiple open release-trackers; using <top-key>."*

After resolving the tracker key, read the current version from the repo:

```bash
VERSION=$(cat VERSION)
```

Form the output folder name: `FOLDER_NAME="v${VERSION}-${TRACKER_KEY}"` (e.g. `v0.4.6-FP-194`). All per-ticket docs for this sprint land under `docs/3.0-deployment/releases/${FOLDER_NAME}/`.

## 3. Gather source material

Two parallel fetches:

**3a. Ticket content** — call `getJiraIssue` on `$ARGUMENTS` with `fields=["summary","description","labels"]` and `responseContentFormat: "markdown"`.

Capture:
- `summary` — one-line ticket title
- `description` — full JIRA description (markdown)
- `labels` — used to derive bucket (step 3c)

**3b. Plan and review thread** — scan the ticket's comments chronologically.

Find the **latest `/jira-plan` comment** by signature `<!-- jira-plan v1 / auto-generated -->` — this is `plan_comment`.

Find all comments with the marker `<!-- jira-review-thread plan=<PLAN_ID> -->` (any `PLAN_ID`) — concatenate their bodies as `review_thread`. If none exist, `review_thread = ""`.

**3c. Derive bucket from labels**

Map the ticket's labels to a bucket using the table below (first match wins):

| Label pattern | Bucket |
|---|---|
| `component:frontend` | `Frontend` |
| `component:backend` or `component:api` | `Backend` |
| `component:agents` or `component:rag` | `Agents+RAG` |
| `component:infra` | `Infra` |
| `component:security` | `Security` |
| `component:docs` | `Docs` |
| *(no match)* | `Other` |

**3d. PR title (if linked in JIRA only)**

Scan the ticket's comments for a `/jira-impl` handoff comment that contains a PR URL (pattern: `https://github.com/[^)]+/pull/\d+`). If found, call `gh pr view <PR_NUMBER> --json title --jq '.title'` to fetch the title. If not found, `pr_title = ""`. Do **not** enumerate all PRs — only resolve what's already referenced in JIRA.

## 4. Generate the per-ticket documents

Using the source material from Step 3, **synthesise all three documents in this Claude session** — no external AI service call. Then write the files via the Python writer.

### 4a. Assign priority tags

Decide the a/b/c tag for each doc type based on ticket content:

| Tag | Meaning | Use when |
|---|---|---|
| `b` | must-have | Ticket has meaningful content for this audience |
| `a` | good-to-have | Minor or tangential content, useful but skippable |
| `c` | optional/skip | No value for this audience (write a one-line stub) |

Assign per document independently. Example: a cosmetic UI tweak → all `c`; a new workflow → all `b`.

### 4b. Synthesise content for each doc

Write the content now (in this session), guided by audience:

- **technical** — engineers / ops: what changed, how it works. Use mermaid diagrams, decision tables, before/after where helpful. Keep ticket key references.
- **business** — product / end users: outcome framing ("Users can now…", "The system now…"). No jargon, no file paths, no PR numbers.
- **management** — directors / sponsors: 2–4 plain bullet statements. Each bullet is a complete thought: what changed and why it matters to the org. No meta-labels (no "Talking points", "Ah-ha moment", "Strategic value").

For `c`-tagged docs, write a one-line stub: `No significant content for this audience.`

**Mermaid node-label quoting (FP-218 bug fix).** When a mermaid diagram in the technical doc has a node label that contains `/`, `:`, `-`, `(`, `)`, or any other punctuation, **wrap the label in double quotes** inside the brackets. Mermaid's lexer interprets unquoted `[/text/]` as a parallelogram shape and throws `Lexical error... Unrecognized text` on a bare `/`. Same risk with `[Status: DONE]` (colon) and similar.

Safe form:

```mermaid
A["/dfsl FP-XXX"] --> B["Pre-flight gate"]
B -->|"Fail / Blocked"| H["Stop at TESTING"]
```

Unsafe form (will error in JIRA / GitHub renderers):

```
A[/dfsl FP-XXX] --> B[Pre-flight gate]
B -->|Fail/Blocked| H[Status: DONE]
```

Edge labels in `|...|` form should also be quoted when they contain `/` or other punctuation. When in doubt, quote.

### 4c. Write the files

```python
python - <<'EOF'
import sys
sys.path.insert(0, "scripts")
from release_docs.per_ticket_writer import PerTicketDoc, write_per_ticket_docs

docs = [
    PerTicketDoc(doc_type="technical", tag="<tag-b-or-a-or-c>", content="""<synthesised content>"""),
    PerTicketDoc(doc_type="business",  tag="<tag-b-or-a-or-c>", content="""<synthesised content>"""),
    PerTicketDoc(doc_type="management",tag="<tag-b-or-a-or-c>", content="""<synthesised content>"""),
]
written = write_per_ticket_docs(
    tracker_key="<FOLDER_NAME>",
    ticket_key="$ARGUMENTS",
    docs=docs,
)
for p in written:
    print(p)
EOF
```

Output path: `docs/3.0-deployment/releases/<FOLDER_NAME>/<ticket_key>-<tag>-<type>.md`
(e.g. `docs/3.0-deployment/releases/v0.4.6-FP-194/FP-213-b-technical.md`)

Re-running is idempotent — existing files are overwritten. If the tag changes between runs (e.g. `b` → `a`), both files will exist; list them and ask the operator to remove the superseded one.

### 4c-commit. Refresh management draft then commit all

**4c-i. Regenerate the sprint management draft.**

Collect all non-`c`-tagged per-ticket management files for this sprint (`FP-XXX-[ab]-management.md` in `docs/3.0-deployment/releases/<FOLDER_NAME>/`), sort by ticket key, and overwrite `docs/3.0-deployment/releases/v<VERSION>_draft_management.md`:

```python
python - <<'EOF'
from pathlib import Path

folder = Path("docs/3.0-deployment/releases/<FOLDER_NAME>")
out    = Path("docs/3.0-deployment/releases/v<VERSION>_draft_management.md")

files = sorted(folder.glob("FP-*-[ab]-management.md"))
if not files:
    print("No non-stub management docs — skipping management draft.")
else:
    lines = ["# Release v<VERSION> — Management summary\n"]
    for f in files:
        parts = f.stem.split("-")
        ticket = f"{parts[0]}-{parts[1]}"
        lines.append(f"\n## {ticket}\n")
        lines.append(f.read_text())
    out.write_text("\n".join(lines))
    print(f"Written: {out}")
EOF
```

**4c-ii. Commit per-ticket docs + updated management draft together:**

```bash
git add docs/3.0-deployment/releases/<FOLDER_NAME>/<ticket_key>-*.md \
        docs/3.0-deployment/releases/v<VERSION>_draft_management.md
git commit -m "<ticket_key> add per-ticket release docs; refresh management draft

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

If the commit fails because there is no active branch (detached HEAD), warn the operator and skip — the files are on disk and can be staged manually. Do **not** push at this step; the operator decides when to push.

### 4d. Mark Document = Y in tracker bundle

After the files are written, update the `Document (Y/N)` column for `$ARGUMENTS` in the active tracker's `## Bundle` table.

1. Call `getJiraIssue` on `TRACKER_KEY` with `fields=["description"]` and `responseContentFormat: "markdown"`.
2. Locate the table row for `$ARGUMENTS` in the `## Bundle` section.
3. Replace the last cell (`| |` → `| Y |`).
4. Call `editJiraIssue` on `TRACKER_KEY` with the updated description (`contentFormat: "markdown"`).
5. Log: *"Tracker <TRACKER_KEY>: Document column set to Y for $ARGUMENTS."*

Skip this step (log a warning, do not fail the run) if:
- No `## Bundle` section is found.
- No row for `$ARGUMENTS` exists in the bundle (ticket was not yet added by `/jira-impl` — warn operator).

## 5. Report in chat

Print a concise summary table:

```
/jira-done $ARGUMENTS → tracker <TRACKER_KEY> (v<VERSION>)

| File | Tag | Status |
|---|---|---|
| $ARGUMENTS-b-technical.md | b (must-have) | written |
| $ARGUMENTS-a-business.md  | a (good-to-have) | written |
| $ARGUMENTS-c-management.md | c (optional/skip — stub) | written |

Docs written to docs/3.0-deployment/releases/v<VERSION>-<TRACKER_KEY>/
```

Notes to include when applicable:
- If any doc is tag=c: *"Management doc is tag=c — judged low-value for this audience. Re-run `/jira-done $ARGUMENTS` if scope changes."*
- If `pr_title` was not found in JIRA: *"PR title not found in JIRA comments — source material used summary + description only."*

## 6. Find and check existing docs

Before writing, call `find_existing_docs` to detect whether prior files exist. If prior files with a **different tag** exist for the same doc type, list them in chat:

```
Note: Prior file FP-213-b-technical.md exists; new file is FP-213-a-technical.md.
Both exist. Remove the superseded file if you no longer need it:
  rm docs/3.0-deployment/releases/v<VERSION>-<TRACKER_KEY>/FP-213-b-technical.md
```

Do **not** auto-delete prior files — the operator may have edited them manually.

> **Implementation note:** Step 4's `write_per_ticket_docs` call writes the new files. Step 6's detection should run *before* the write to surface the diff. In practice: call `find_existing_docs`, compare tags against the `PerTicketDocSet`, report any mismatches, then proceed with the write.

## Guardrails

- **Status gate is a hard stop.** Never generate docs for a ticket in TESTING — human-verify items may still be open, and the release doc would reflect incomplete work.
- **Never write outside `docs/3.0-deployment/releases/`.** The output path is fixed; do not allow `tracker_key` values that include path traversal characters.
- **Idempotent.** Re-running is safe — existing files are overwritten, nothing is appended. This is by design: `/release-cut` can safely re-invoke `/jira-done` to refresh stale docs.
- **c-tagged docs are traceability, not errors.** A c-tagged doc means that doc type has no significant content for that audience. `/release-cut` excludes c-tagged docs by default.

## End-of-run usage recording (FP-192) — MANDATORY

You **MUST** append the terminal event before exiting.

```bash
python scripts/record_usage.py --command /jira-done --outcome <state> [--note "<friction>"]
```

States: `completed` (all 3 files written, report posted) | `partial` (some files written but not all 3 — e.g. early exit after a write error) | `blocked` (pre-flight gate stopped the run — wrong status, no tracker) | `failed` (workflow errored mid-run) | `skipped` (intentional short-circuit). Add `--note` whenever state is not `completed`.
