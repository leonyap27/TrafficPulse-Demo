# Deploy Ledger

Append-only ledger of GCP Cloud Run deploys. Written by
`infra/scripts/deploy-gcp*.sh` after a successful deploy. Consumed by the
`release-doc-prompt` `SessionStart` hook and the `/release-doc` slash command
(FP-188).

## Why
Every deploy should produce a release document, regardless of who launched
it. The deploy script is the always-on trigger that records the event; Claude
is the optional smart UX that picks the entry up next session and offers to
generate the doc. A `.claude/` event listener alone would miss deploys
launched from a plain terminal — the ledger handshake fixes that.

## Layout

```
.claude/usage/deploy-ledger/
├── README.md       (this file)
├── pending/        (entries awaiting release-doc generation)
└── processed/      (entries handled — done or dismissed)
```

## Entry schema (one JSON file per deploy)

Path: `pending/<YYYYMMDDTHHMMSSZ>-<target>.json`

```json
{
  "deploy_id": "2026-05-27T08:30:00Z-uat-0.4.6",
  "target": "uat",
  "version": "0.4.6",
  "image_ref": "us-central1-docker.pkg.dev/<project>/<repo>/funding-paper-agent:0.4.6",
  "timestamp": "2026-05-27T08:30:00Z",
  "git_sha": "abc1234...",
  "status": "pending"
}
```

## State transitions
- `pending` — initial state; file lives in `pending/`.
- `done` — release doc generated; file moves to `processed/` with `status: done` and the rendered doc path added as `generated_path`.
- `dismissed` — user explicitly skipped doc generation; file moves to `processed/` with `status: dismissed`.

Files are never deleted — they form a per-deploy audit trail.
