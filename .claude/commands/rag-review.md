---
description: Review a RAG / retrieval / KB / prompt change — KB integrity, retrieval sanity, prompt diff, eval, attribution.
argument-hint: <change or area to review, optional>
---

Review a RAG / retrieval / KB / prompt change: **$ARGUMENTS**

Applies when the change touches any of:
- `data/kb/` content or `kb_manifest.json`
- Embedding model, chunking, or index
- Retrieval logic (filters, top-k, reranking)
- Agent prompts (`agents/`) or tool definitions used by agents
- Output formatting / citation / source attribution

When working in `data/kb/` or `tools/knowledge_base.py`, `.claude/rules/kb.md` is already loaded with the full conventions.

## 0. Record `started` event — MANDATORY first step

```bash
python scripts/record_usage.py --command /rag-review --outcome started --trigger slash-command
```

Run this first to capture usage for direct and chained invocations.

## 1. Name what changed
- Component: ingestion / retrieval / prompt / tool / output
- Model or provider involved
- Inputs and outputs of the changed step

## 2. KB integrity
- If KB content changed: regenerate `kb_manifest.json`, confirm chunk counts and source paths match.
- If chunking or embedding changed: the entire index must be rebuilt — note explicitly in the PR.
- Confirm no source documents contain PII, secrets, or material that should not be embedded.

## 3. Retrieval sanity
- Run a small set of representative queries.
- Inspect retrieved chunks: on-topic, deduplicated, within token budget?
- If filtering by metadata (past-paper category, project): verify the filter actually applies, not just that it compiles.

## 4. Prompt / agent behaviour
- Diff the prompt; flag any change to role, constraints, or output format.
- For tool/agent changes: confirm tool schemas match what the consuming model is being told.
- Run the agent on representative inputs; capture the full transcript (prompt → tool calls → final).

## 5. Evaluation
- At minimum: a handful of golden inputs with expected behaviour, run before and after.
- Note regressions even if the headline metric improves.
- If no eval harness exists for this surface, say so — don't fabricate metrics.

## 6. Source attribution
- If the output cites sources, confirm citations resolve to real retrieved chunks, not hallucinated paths.
- Confirm UI source-context surface still renders for the new shape (see `docs/1.0-architecture/RAG_ARCHITECTURE.md`).

## 7. Logging & cost
- Prompts, retrievals, and model responses logged at the expected level — no new PII, no dropped fields.
- Note expected token / cost delta if non-trivial.

## PR documentation
Include:
- Model / provider
- Prompt or agent changed (link or diff)
- Input / output format
- Evaluation method and results
- Logging impact

## Guardrails
- Do not change chunking + retrieval + prompt in a single PR unless they must ship together — isolate to keep regressions diagnosable.
- Do not claim quality improvements without an eval; "looks better on one example" is not evidence.

Walk through these steps and report findings.

## End-of-run usage recording (FP-192) — MANDATORY

```bash
python scripts/record_usage.py --command /rag-review --outcome <state> [--note "<friction>"]
```

Terminal states: `completed` | `partial` | `blocked` | `failed` | `skipped`. Add `--note` whenever the state is not `completed`.
