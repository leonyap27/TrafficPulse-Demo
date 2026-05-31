# .claude/usage/ — Local Workflow Usage Tracker

Tracks usage of local development workflow assets (slash commands, rules, hooks, agents, bridge docs) so the team can see which assets are useful, stale, or high-friction. **Local-only — not deployed telemetry.**

Scope authority: [FP-192](https://ltads.atlassian.net/browse/FP-192). Storage layout: [FP-196](https://ltads.atlassian.net/browse/FP-196).

## Two-zone model (FP-196)

Events live in **two separate places** so branch switching and stash never drop in-flight events:

| Zone | Path | In git? | Who writes |
|---|---|---|---|
| **Live (private)** | `~/.claude-usage/<owner>/<repo>/events.jsonl` | No | `scripts/record_usage.py` on every slash command |
| **Team (shared)** | `.claude/usage/team/events-<hash>.jsonl` (one per developer) | Yes | `scripts/publish_usage.py` only ever writes the current developer's own file |

The live zone lives outside the git worktree on purpose: `git stash`, `git checkout`, `git switch` cannot touch a file git does not see. The team zone is per-developer (file name keyed by a 10-char hash of `git config user.email`) so two developers never edit the same file — merges into `dev` therefore never conflict.

## Files in this directory

| File | What it is | Edited by |
|---|---|---|
| `schema.md` | Event field/enum reference | Humans (when schema evolves) |
| `team/events-<hash>.jsonl` | Per-developer published events | `scripts/publish_usage.py` (own file only) |
| `inventory.json` | Asset inventory (commands/rules/hooks/agents/bridge) | `scripts/seed_inventory.py` |
| `viewer/index.html` | Dashboard UI (served by `scripts/open_dashboard.py`) | Humans (when UI changes) |
| `stale-assets-test-playbook.md` | FP-199 walkthrough for testing stale/unused assets one by one | Humans / agents during knowledge-sharing runs |

`.claude/usage/events.jsonl` and `.claude/usage/events/` are **gitignored** (residue from pre-FP-196 layouts).

## How events get recorded

1. **Claude Code slash commands** — `UserPromptSubmit` hook in `.claude/settings.json` auto-records a `started` event for any prompt beginning with `/`.
2. **Workflow doc end-of-run** — each `.claude/commands/jira-*.md` includes an explicit step that calls `scripts/record_usage.py --outcome <state>` to record the terminal lifecycle event.
3. **Codex / AGENTS.md bridge** — bridge instructions document a manual call to the same recorder.
4. **Direct manual** — any developer can run `python scripts/record_usage.py --command <name> --outcome <state> --note <text>` for ad-hoc usage events.

All four paths write into the live zone only. Nothing under `.claude/usage/` is touched at record time.

## How events get published (service, not developer choice)

`scripts/publish_usage.py` runs automatically via the `Stop` hook in `.claude/settings.json` at the end of every Claude Code session. It:

1. Reads the current developer's live JSONL.
2. Upserts new entries (dedup on `timestamp + command + outcome + trigger`) into the developer's **own** `team/events-<hash>.jsonl`.
3. Stages that file (`git add`) so the developer's next normal `git commit` carries usage to the repo.

Side-effect to expect: after each session, `git status` will show your `team/events-<hash>.jsonl` as staged. Commit it alongside your normal work; `git push` shares your profile, `git pull` brings back the team's updates. The publisher never commits or pushes by itself.

## Viewing usage

```bash
python scripts/open_dashboard.py
```

Starts a tiny local HTTP server on the first free port from 8765 and opens the dashboard. The server exposes two virtual endpoints the viewer fetches at load time:

- `GET /_usage/team-events.jsonl` — concatenation of every `team/events-*.jsonl` (the team-wide view)
- `GET /_usage/live-events.jsonl` — the current developer's private live file (so the dashboard shows new events even before they're published)

Opening `.claude/usage/viewer/index.html` directly via `file://` still works for legacy-file imports, but the two-zone live view requires the local server.

## Regenerating inventory

```bash
python scripts/seed_inventory.py
```

Walks `.claude/commands/`, `.claude/rules/`, `.claude/hooks/`, `.claude/agents/`, plus `.claude/CLAUDE.md`, `.claude/ONBOARDING.md`, `AGENTS.md`, and writes `inventory.json`.

## Validation gate (recommended before merge)

```bash
python scripts/validate_usage_tracking.py
```

Fails when:
- `inventory.json` is out of sync with current `.claude/` assets
- any command doc is missing recorder snippets for both `started` and terminal outcomes
- the merged team + live events have schema/enum issues, or there are abandoned `started` events older than the threshold

Use `--max-open-hours` to tighten/relax the abandoned-start threshold.

## Testing stale / unused assets

For new-joiner walkthroughs and dashboard evidence collection, follow
[`stale-assets-test-playbook.md`](stale-assets-test-playbook.md). It covers
one-by-one asset testing, with-skill vs without-skill comparison, screenshot
capture, synthetic event cleanup, and the Jira summary format for FP-199.

## Legacy migration

To migrate pre-FP-196 data (any `events.jsonl` or `events/YYYY-MM/*.json` left over in your checkout) into the new per-user team files:

```bash
python scripts/migrate_events_to_files.py
```

The migrator groups legacy entries by `developer` and writes each developer's events into their `team/events-<hash>.jsonl`. Legacy paths are removed after a successful run.

## Cross-repo aggregation

Each event carries its own `repo` field. Aggregation works the same as before — concatenate `team/events-*.jsonl` files from sibling repos and load them into the dashboard. The live zone is keyed by repo (`~/.claude-usage/<owner>/<repo>/`) so cross-repo data does not collide.
