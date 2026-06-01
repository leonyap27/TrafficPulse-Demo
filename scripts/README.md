# Scripts

*Last updated: 2026-04-09*

Dev utilities and integration tests. All require the virtual environment active: `source .venv/bin/activate`

> To start the full system: `./run_system.sh` from project root.

---

## Integration Tests

These hit the live API — start the server first (`./run_system.sh`).

| Script | What it tests | Needs API? |
|--------|--------------|-----------|
| `test_streaming.py` | SSE endpoint, real-time progress events | Yes |
| `test_agent_tracking.py` | Agent event emission, audit trail, timing | Yes |
| `test_paper_generation.py` | End-to-end paper generation (all 8 sections) | Yes |
| `test_vertex_ai.py` | Google Vertex AI / Gemini API connectivity | Yes |
| `list_models.py` | List available Gemini model deployments | Yes |

```bash
# Start server first
./run_system.sh

# Then in another terminal
source .venv/bin/activate
python scripts/test_streaming.py
python scripts/test_paper_generation.py
```

---

## Utility Scripts

| Script | Purpose | Needs API? |
|--------|---------|-----------|
| `sync_kb_from_gcs.py` | Sync Knowledge Base from GCS bucket → local ChromaDB | Yes (port 8000) |
| `test_gcs_access.py` | Verify GCS connectivity and bucket permissions | No |
| `create_sample_docx.py` | Generate a sample DOCX for use as test input | No |

```bash
# Test GCS connection
python scripts/test_gcs_access.py

# Create a sample test document
python scripts/create_sample_docx.py
```

### Sync KB from GCS

Authenticate via the `POWER_USER_API_KEY` env var (or `--api-key`).

```bash
export POWER_USER_API_KEY=YOUR_KEY

# Safe sync — downloads new/updated files only, never deletes
python scripts/sync_kb_from_gcs.py

# Mirror sync — DESTRUCTIVE. Removes local files (and their ChromaDB
# embeddings and tag mappings) for anything no longer in GCS.
python scripts/sync_kb_from_gcs.py --delete

# Target DEV or UAT Cloud Run directly (instead of localhost)
python scripts/sync_kb_from_gcs.py --env dev
python scripts/sync_kb_from_gcs.py --env uat
python scripts/sync_kb_from_gcs.py --env uat --delete

# Inspect bucket without syncing
python scripts/sync_kb_from_gcs.py --action status
python scripts/sync_kb_from_gcs.py --action list
```

Run `python scripts/sync_kb_from_gcs.py --help` for the full flag reference.
See [docs/2.0-setup/GCS_SETUP.md](../docs/2.0-setup/GCS_SETUP.md) for GCS configuration.

---

## Test Inputs

Sample input files (DOCX, PDF, TXT) used for testing live in [`test_inputs/`](../test_inputs/).
