"""Tests for infra/scripts/_release_ledger.sh.

Run the bash helper in a sandboxed mini-repo so the tests never touch the real
ledger directory. Validates that an entry is well-formed JSON with the agreed
schema and lands under ``pending/``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HELPER_SRC = _REPO_ROOT / "infra" / "scripts" / "_release_ledger.sh"


def _build_sandbox(tmp_path: Path) -> Path:
    sandbox = tmp_path / "repo"
    (sandbox / "infra" / "scripts").mkdir(parents=True)
    (sandbox / ".claude" / "usage").mkdir(parents=True)
    (sandbox / "infra" / "scripts" / "_release_ledger.sh").write_text(
        _HELPER_SRC.read_text(encoding="utf-8"), encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q"], cwd=sandbox, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t.t",
            "-c",
            "user.name=t",
            "commit",
            "--allow-empty",
            "-q",
            "-m",
            "init",
        ],
        cwd=sandbox,
        check=True,
    )
    return sandbox


def _run_helper(sandbox: Path, args: str) -> subprocess.CompletedProcess[str]:
    script = (
        f"source {sandbox}/infra/scripts/_release_ledger.sh && "
        f"write_deploy_ledger_entry {args}"
    )
    return subprocess.run(
        ["bash", "-c", script],
        cwd=sandbox,
        capture_output=True,
        text=True,
        check=False,
    )


def test_helper_writes_well_formed_entry(tmp_path):
    sandbox = _build_sandbox(tmp_path)
    result = _run_helper(sandbox, "uat 0.4.6 us-central1-docker.pkg.dev/proj/repo/img:0.4.6")
    assert result.returncode == 0, result.stderr

    pending = sandbox / ".claude" / "usage" / "deploy-ledger" / "pending"
    entries = list(pending.glob("*.json"))
    assert len(entries) == 1

    data = json.loads(entries[0].read_text(encoding="utf-8"))
    assert data["target"] == "uat"
    assert data["version"] == "0.4.6"
    assert data["image_ref"] == "us-central1-docker.pkg.dev/proj/repo/img:0.4.6"
    assert data["status"] == "pending"
    assert data["timestamp"].endswith("Z")
    assert data["deploy_id"].endswith("-uat-0.4.6")
    assert len(data["git_sha"]) == 40  # full git sha


def test_helper_filename_includes_target_segment(tmp_path):
    sandbox = _build_sandbox(tmp_path)
    _run_helper(sandbox, "dev 0.5.0 my-image:latest")
    pending = sandbox / ".claude" / "usage" / "deploy-ledger" / "pending"
    entries = list(pending.glob("*-dev.json"))
    assert len(entries) == 1


def test_helper_rejects_missing_args(tmp_path):
    sandbox = _build_sandbox(tmp_path)
    result = _run_helper(sandbox, "uat 0.4.6")  # missing image_ref
    assert result.returncode == 2
    assert "required" in result.stderr


def test_helper_creates_pending_directory_if_absent(tmp_path):
    sandbox = _build_sandbox(tmp_path)
    pending = sandbox / ".claude" / "usage" / "deploy-ledger" / "pending"
    assert not pending.exists()
    _run_helper(sandbox, "uat 0.4.6 img:1")
    assert pending.is_dir()


@pytest.mark.parametrize("target", ["dev", "uat"])
def test_helper_supports_both_targets(tmp_path, target):
    sandbox = _build_sandbox(tmp_path)
    result = _run_helper(sandbox, f"{target} 0.4.6 img:1")
    assert result.returncode == 0
    data = json.loads(
        next((sandbox / ".claude" / "usage" / "deploy-ledger" / "pending").glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert data["target"] == target
