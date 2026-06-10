"""Tests for scripts/open_dashboard.py (unit-level only — does not start a server)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import open_dashboard  # noqa: E402


class _FakeSocket:
    def __init__(self, should_bind: bool) -> None:
        self.should_bind = should_bind

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def bind(self, _addr) -> None:
        if not self.should_bind:
            raise OSError("port busy")


def test_port_is_free_returns_true_for_unbound_port(monkeypatch):
    monkeypatch.setattr(open_dashboard.socket, "socket", lambda *_args, **_kwargs: _FakeSocket(True))
    assert open_dashboard._port_is_free(8765) is True


def test_port_is_free_returns_false_for_bound_port(monkeypatch):
    monkeypatch.setattr(open_dashboard.socket, "socket", lambda *_args, **_kwargs: _FakeSocket(False))
    assert open_dashboard._port_is_free(8765) is False


def test_pick_port_finds_a_free_slot(monkeypatch):
    monkeypatch.setattr(open_dashboard, "_port_is_free", lambda p: p == 8003)
    assert open_dashboard._pick_port(8000) == 8003


def test_pick_port_raises_when_range_exhausted(monkeypatch):
    monkeypatch.setattr(open_dashboard, "_port_is_free", lambda p: False)
    with pytest.raises(RuntimeError, match="no free port"):
        open_dashboard._pick_port(8000)


def test_read_team_events_returns_empty_when_dir_missing(tmp_path):
    assert open_dashboard._read_team_events(tmp_path / "team-missing") == b""


def test_read_team_events_concatenates_every_events_file(tmp_path):
    team = tmp_path / "team"
    team.mkdir()
    (team / "events-aaa.jsonl").write_text("line-a\n", encoding="utf-8")
    (team / "events-bbb.jsonl").write_text("line-b1\nline-b2\n", encoding="utf-8")
    # A non-matching file should be ignored.
    (team / "notes.txt").write_text("ignored\n", encoding="utf-8")

    body = open_dashboard._read_team_events(team).decode("utf-8")
    lines = [line for line in body.splitlines() if line]
    assert sorted(lines) == ["line-a", "line-b1", "line-b2"]
    assert "ignored" not in body


def test_read_team_events_normalises_trailing_newline(tmp_path):
    team = tmp_path / "team"
    team.mkdir()
    (team / "events-aaa.jsonl").write_text("line-a", encoding="utf-8")  # no newline
    (team / "events-bbb.jsonl").write_text("line-b\n", encoding="utf-8")
    body = open_dashboard._read_team_events(team).decode("utf-8")
    # Both files should end up separated by a newline.
    assert body == "line-a\nline-b\n"


def test_read_live_events_returns_empty_when_missing(tmp_path):
    assert open_dashboard._read_live_events(tmp_path / "no-live.jsonl") == b""


def test_read_live_events_returns_raw_bytes(tmp_path):
    path = tmp_path / "live.jsonl"
    path.write_text("payload\n", encoding="utf-8")
    assert open_dashboard._read_live_events(path) == b"payload\n"
