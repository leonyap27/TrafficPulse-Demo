---
description: Conventions for the Knowledge Base (KB) — content, manifest, chunking, retrieval.
globs:
  - "data/kb/**"
  - "tools/knowledge_base.py"
---

# Knowledge Base rules

Applies to `data/kb/` (the KB content + manifest) and `tools/knowledge_base.py` (the retrieval interface).

## KB content (`data/kb/`)

- Two corpora: `guidelines/` (authoritative funding rules) and `past_papers/` (example papers grouped by category).
- `kb_manifest.json` is the canonical inventory. **Never edit content without regenerating the manifest.**
- Past papers live in subdirectories that encode the category taxonomy (per FP-159). Don't dump papers loose in `past_papers/`.

## Manifest hygiene

- Chunk counts in the manifest must match the actual indexed chunks. Drift here causes silent retrieval bugs.
- Source path strings in the manifest are relative to `data/kb/` — keep that convention.
- If chunking strategy or embedding model changes, the entire index must be rebuilt. Call this out explicitly in the PR.

## No-PII rule

KB content is exposed to consuming LLMs via retrieval. Anything in here can end up in agent context, logs, and eventually outputs.

- **Never put** PII, internal credentials, draft commercially sensitive material, or anything that shouldn't be in a generated paper.
- Past papers are already-shipped documents — fine. New uploads need a sanity check before ingestion.

## Retrieval (`tools/knowledge_base.py`)

- The KB is exposed to agents as **two function tools**: `search_guidelines` and `search_past_papers`. Don't bypass these — agents call the tools, the tools call the vector store. Never let an agent reach the vector store directly.
- Top-k values are part of the agent's tool definition (Drafter k=2 / k=1, Coherence Reviewer k=3 for guidelines). Changing top-k changes context size — flag it in PR.
- Filtering by metadata (past-paper category, project) must actually apply — verify with a test query before shipping.

## Citation integrity

If the output cites sources, the citation must resolve to a real retrieved chunk — not a hallucinated path.

- When changing retrieval or chunk metadata: re-run an integration check that an output's cited source actually exists in the manifest.
- The UI source-context surface depends on this contract — see [docs/1.0-architecture/RAG_ARCHITECTURE.md](../../docs/1.0-architecture/RAG_ARCHITECTURE.md).

## Eval gate for retrieval changes

- Any change to chunking, embedding model, index, top-k, or filter logic needs a before/after run against a small set of representative queries.
- Document the eval in the PR — even if it's three queries with eyeballed output.

## Don't

- Don't change chunking + retrieval + prompt in a single PR (see also `.claude/rules/agents.md`).
- Don't claim retrieval quality improvements without an eval.
- Don't add new past papers without slotting them into a category subdirectory.
