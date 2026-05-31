# Onboarding — Funding Paper Agent

Welcome. This file is what to read first when joining the project. Skim end-to-end (~10 min), then come back to sections as needed.

For the *why* behind this Claude Code setup, see [APP-1685](https://ltads.atlassian.net/browse/APP-1685).

---

## 1. First-time setup

```bash
git clone https://github.com/leonyap27/Funding_paper_agent
cd Funding_paper_agent
```

Open Claude Code in the repo. The team baseline (settings, rules, commands, agent) loads automatically — there's nothing in `.claude/` for you to configure.

**One manual step** — Atlassian Rovo (Jira) integration is a per-user OAuth, not configurable via the repo:

1. Open https://claude.ai/settings/connectors
2. Find **Atlassian Rovo** → Connect → authenticate with your work Atlassian account
3. Done. Future Claude Code sessions will inherit this connection.

Estimated total setup: 5 min.

---

## 1b. If your Claude quota runs out — switch to Codex

You don't lose the workflow when Claude hits its quota. A bridge skill teaches Codex to read `.claude/commands/*.md` directly, so every slash command still works.

**One-time install (per machine):**

```bash
cd ~/my_project/codex-config   # or wherever you cloned it — ask Leon for the repo
./install.sh
```

This copies `claude-project-bridge` into `~/.codex/skills/`. Restart Codex after installing.

**Then use Codex exactly like Claude Code:**

```text
/jira-plan FP-160
/jira-impl FP-160
```

Codex reads the workflow file from `.claude/commands/` and follows it manually. The JIRA artefacts (plan comment, audit footer, status transition) come out in the same shape.

**One difference — usage recording needs an explicit platform flag:**

```bash
python scripts/record_usage.py --command /jira-plan --outcome started --platform codex
```

Codex can't auto-detect its own platform the way Claude Code's hook does, so pass `--platform codex` on every call. The `AGENTS.md` file at the repo root spells this out.

**Which CLI to use for each step:**

| Step | Best fit | Why |
|---|---|---|
| `/jira-plan` | Codex | Research-heavy; Codex (o3/o4-mini) uses fewer tokens |
| `/jira-review` | Either | Simple Q&A loop |
| `/jira-impl` | Claude Code | Multi-file editing + Bash; Claude Code tooling is more reliable |
| `/jira-test` | Codex | Test-case generation; saves Claude quota for impl |
| `/release-doc` | Claude Code + Opus | Needs MCP to pull live JIRA data; route to `claude-opus-4-7` for quality |

---

## 2. What's in `.claude/` (and why)

```
.claude/
├── CLAUDE.md             # Project facts (stack, JIRA, branching) — auto-loaded
├── settings.json         # Team permission baseline + .env safety hook — auto-loaded
├── settings.local.json   # YOUR personal overrides (gitignored, not in repo)
├── rules/                # Path-scoped rules — auto-loaded based on what you're editing
│   ├── backend.md          → applies to api/, tools/
│   ├── agents.md           → applies to agents/
│   ├── mcp-service.md      → applies to mcp_server/
│   ├── frontend.md         → applies to frontend-react/
│   ├── kb.md               → applies to data/kb/, tools/knowledge_base.py
│   └── python-style.md     → applies to **/*.py
├── commands/             # Slash commands — invoke with /<name>
│   ├── jira-plan.md        → /jira-plan <FP-KEY>
│   ├── jira-impl.md        → /jira-impl <FP-KEY>
│   ├── api-change.md       → /api-change
│   ├── ui-change.md        → /ui-change
│   ├── rag-review.md       → /rag-review
│   └── mcp-tool-review.md  → /mcp-tool-review
├── agents/               # Project subagents — invoke with @<name>
│   └── rag-architect.md    → @rag-architect (read-only RAG specialist)
└── hooks/                # Deterministic safety scripts
    └── block-env-commit.sh # PreToolUse: blocks .env* from git add/commit
```

---

## 3. Standard workflow for an FP-92 child issue

```text
1. /jira-plan FP-160          → Claude reads the ticket, reconciles vs code,
                                proposes a plan. Stop here. Review the plan.

2. /jira-impl FP-160          → Claude branches, implements, tests, and
                                opens a PR against `dev`. You approve at
                                each step.
```

For specialised reviews along the way:

| Command | When |
|---|---|
| `/api-change` | Backend route or schema change |
| `/ui-change` | Frontend (React) change |
| `/rag-review` | KB, retrieval, chunking, or prompt change |
| `/mcp-tool-review` | Anything in `mcp_server/` |

For an out-of-flow RAG sanity check:

```text
@rag-architect can you sanity check the new top-k change in tools/knowledge_base.py?
```

---

## 4. Active hooks in this repo

| Hook | What it does | When you'll see it |
|---|---|---|
| `block-env-commit.sh` | Denies `git add` / `git commit` on `.env*` files | If you accidentally try to stage a dotenv |

**Exception**: `.env.example`, `.env.sample`, `.env.template` are allowed (templates without secrets).

If the hook fires unexpectedly, the *why* behind our hook choices is in [APP-1685 hook design rationale](https://ltads.atlassian.net/browse/APP-1685?focusedCommentId=17568). If you need to bypass for a legitimate reason, edit your personal `.claude/settings.local.json` (gitignored) — don't modify the team `settings.json`.

---

## 5. Personal vs project Claude config

- **Project `.claude/`** (this repo, what you're reading) — what the team uses. Auto-loads when you open Claude Code in this repo. You don't configure anything; it ships with the clone.
- **Your personal `~/.claude/`** — yours alone. Add personal preferences (`settings.local.json` overrides, custom prompts, your preferred model/effort) here. Optional.

If you see a workflow `@`-referenced from `~/.claude/workflows/...` in chat history or old commits, that's a previous owner's personal setup — ignore it; the equivalent is available as a slash command in this repo.

---

## 6. Self-check (run after setup)

In a fresh Claude Code session in this repo:

| Check | How | Pass |
|---|---|---|
| Settings loaded | `/permissions` | Allow list shows bash, gh, docker, gcloud, 6 Atlassian read-only MCP entries |
| Rules loaded | Open `api/main.py`, run `/memory` | `.claude/rules/backend.md` and `python-style.md` listed |
| Slash commands listed | Type `/` at the prompt | See `jira-plan`, `jira-impl`, `api-change`, `ui-change`, `rag-review`, `mcp-tool-review` |
| Subagent registered | `/agents` | `rag-architect` listed |
| Hook fires | `touch .env.test`, then ask Claude to `git add .env.test` | Hook blocks with message; `rm .env.test` after |
| Hook doesn't false-positive | Ask Claude to `git commit -m "docs: how .env files work"` | Succeeds (`.env` in message body skipped) |
| MCP works | Ask Claude to look up `APP-1685` in Jira | Claude reads the ticket (assumes you've connected Atlassian Rovo via claude.ai/settings) |

If anything in the table fails, surface it in a comment on [APP-1685](https://ltads.atlassian.net/browse/APP-1685).

---

## 7. Where to learn more

| Topic | File |
|---|---|
| Stack, JIRA epic, branching | `.claude/CLAUDE.md` |
| RAG architecture (current shipping flow) | `docs/1.0-architecture/RAG_ARCHITECTURE.md` |
| Cross-tool memory (Codex, Cursor) | `AGENTS.md` |
| Hook rationale and decision rule | [APP-1685 comment 17568](https://ltads.atlassian.net/browse/APP-1685?focusedCommentId=17568) |
| MCP runtime governance (separate epic) | [FP-170](https://ltads.atlassian.net/browse/FP-170) |
| Applying this baseline to other AIDP projects | [APP-1688](https://ltads.atlassian.net/browse/APP-1688) |

---

## 8. Stuck?

- Hook blocking something you think it shouldn't? Comment on APP-1685 with the command and stderr.
- Slash command not showing in `/` menu? Restart your Claude Code session (commands load at session start).
- Rule not auto-loading? Run `/memory` — if the rule isn't listed for the file you're editing, the path glob may not match. Flag it.
- Anything else: tag the project owner.
