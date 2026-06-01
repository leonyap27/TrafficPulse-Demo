"""Tests for .claude/hooks/block-env-commit.sh (subprocess-based).

Q1 review decision: subprocess so the hook runs as a real child process,
matching how Claude Code invokes it via PreToolUse.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks" / "block-env-commit.sh"


def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_blocks_git_add_env():
    result = _run({"tool_input": {"command": "git add .env"}})
    assert result.returncode == 2
    assert ".env" in result.stderr


def test_blocks_git_add_env_production():
    result = _run({"tool_input": {"command": "git add .env.production"}})
    assert result.returncode == 2


def test_blocks_git_add_env_local():
    result = _run({"tool_input": {"command": "git add .env.local"}})
    assert result.returncode == 2


def test_allows_git_add_env_example():
    result = _run({"tool_input": {"command": "git add .env.example"}})
    assert result.returncode == 0


def test_allows_git_add_env_sample():
    result = _run({"tool_input": {"command": "git add .env.sample"}})
    assert result.returncode == 0


def test_allows_git_add_env_template():
    result = _run({"tool_input": {"command": "git add .env.template"}})
    assert result.returncode == 0


def test_allows_non_git_command():
    result = _run({"tool_input": {"command": "ls -la .env"}})
    assert result.returncode == 0


def test_allows_commit_message_containing_env_word():
    # -m flag value must not be treated as a path
    result = _run({"tool_input": {"command": "git commit -m '.env config note'"}})
    assert result.returncode == 0


def test_allows_commit_non_env_file():
    result = _run({"tool_input": {"command": "git commit src/app.py"}})
    assert result.returncode == 0


def test_malformed_json_exits_clean():
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


def test_empty_command_exits_clean():
    result = _run({"tool_input": {"command": ""}})
    assert result.returncode == 0


def test_missing_tool_input_exits_clean():
    result = _run({})
    assert result.returncode == 0
