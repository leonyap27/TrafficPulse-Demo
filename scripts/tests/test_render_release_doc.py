"""Tests for scripts/render_release_doc.py CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import render_release_doc  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SAMPLE_INPUT = _REPO_ROOT / "scripts" / "release_docs" / "SAMPLE_INPUT.json"
_FROZEN_STAMP = "2026-05-25T14:00:00+08:00"


def test_sample_input_validates():
    """SAMPLE_INPUT.json is the documented schema example — it must always parse."""
    data = json.loads(_SAMPLE_INPUT.read_text(encoding="utf-8"))
    release_input = render_release_doc.ReleaseInput.model_validate(data)
    assert release_input.tracker_key == "FP-194"


def test_cli_writes_to_output_file(tmp_path):
    output = tmp_path / "release.md"
    exit_code = render_release_doc.main(
        [
            "--input",
            str(_SAMPLE_INPUT),
            "--output",
            str(output),
            "--generated-at",
            _FROZEN_STAMP,
        ]
    )
    assert exit_code == 0
    rendered = output.read_text(encoding="utf-8")
    assert "# Release v0.4.6 → UAT" in rendered
    assert "**Tracker:** [FP-194]" in rendered
    assert f"**Generated at:** {_FROZEN_STAMP}" in rendered


def test_cli_creates_parent_directory_for_output(tmp_path):
    output = tmp_path / "deep" / "nested" / "v0.4.6.md"
    exit_code = render_release_doc.main(
        ["--input", str(_SAMPLE_INPUT), "--output", str(output)]
    )
    assert exit_code == 0
    assert output.exists()


def test_cli_writes_to_stdout_when_no_output(capsys, tmp_path):
    exit_code = render_release_doc.main(
        ["--input", str(_SAMPLE_INPUT), "--generated-at", _FROZEN_STAMP]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "# Release v0.4.6 → UAT" in captured.out


def test_cli_errors_with_help_when_no_input_and_tty(monkeypatch, capsys):
    # Simulate a tty stdin (interactive terminal, no piped input).
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    with pytest.raises(SystemExit) as exc:
        render_release_doc.main([])
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "No input provided" in captured.err
    assert "/release-doc" in captured.err
    assert "SAMPLE_INPUT.json" in captured.err


def test_cli_without_polish_flag_does_not_build_client(monkeypatch, tmp_path):
    calls = {"built": False}

    def _fail_if_called() -> object:
        calls["built"] = True
        raise AssertionError("build_default_client should not be called without --polish")

    monkeypatch.setattr(render_release_doc, "build_default_client", _fail_if_called)
    output = tmp_path / "out.md"
    exit_code = render_release_doc.main(
        ["--input", str(_SAMPLE_INPUT), "--output", str(output), "--generated-at", _FROZEN_STAMP]
    )
    assert exit_code == 0
    assert calls["built"] is False


def test_cli_audience_business_writes_business_doc(tmp_path):
    output = tmp_path / "v0.4.6.business.md"
    exit_code = render_release_doc.main(
        [
            "--input",
            str(_SAMPLE_INPUT),
            "--output",
            str(output),
            "--audience",
            "business",
            "--generated-at",
            _FROZEN_STAMP,
        ]
    )
    assert exit_code == 0
    rendered = output.read_text(encoding="utf-8")
    # Business-doc-specific markers.
    assert "# Release v0.4.6 — UAT Highlights" in rendered
    assert "## Talking points" in rendered
    # Engineering sections must NOT appear in business doc.
    assert "Test evidence" not in rendered
    assert "Readiness" not in rendered
    assert "## Rollback" not in rendered
    # FP-XXX keys / work-type tags should NOT leak (renderer never injects them).
    assert "FP-185" not in rendered
    assert "[sprint]" not in rendered


def test_cli_audience_both_writes_two_files(tmp_path):
    technical_output = tmp_path / "v0.4.6.md"
    exit_code = render_release_doc.main(
        [
            "--input",
            str(_SAMPLE_INPUT),
            "--output",
            str(technical_output),
            "--audience",
            "both",
            "--generated-at",
            _FROZEN_STAMP,
        ]
    )
    assert exit_code == 0
    business_output = tmp_path / "v0.4.6.business.md"
    assert technical_output.exists()
    assert business_output.exists()
    # Technical has the engineering layout.
    tech = technical_output.read_text(encoding="utf-8")
    assert "## What shipped" in tech
    assert "### Infra" in tech
    # Business is the highlights flavour.
    biz = business_output.read_text(encoding="utf-8")
    assert "# Release v0.4.6 — UAT Highlights" in biz
    assert "## Talking points" in biz


def test_cli_with_polish_flag_builds_and_uses_client(monkeypatch, tmp_path):
    class _UppercaseClient:
        def __init__(self) -> None:
            self.invocations = 0

        def polish_lines(
            self,
            *,
            bucket: str,
            lines: list[str],
            audience: str = "technical",
        ) -> list[str]:
            self.invocations += 1
            return [line.upper() for line in lines]

        def distill_talking_points(
            self, *, lines: list[str], target_count: int = 5
        ) -> list[str]:
            return []

    instance = _UppercaseClient()
    monkeypatch.setattr(render_release_doc, "build_default_client", lambda: instance)
    output = tmp_path / "out.md"
    exit_code = render_release_doc.main(
        [
            "--input",
            str(_SAMPLE_INPUT),
            "--output",
            str(output),
            "--polish",
            "--generated-at",
            _FROZEN_STAMP,
        ]
    )
    assert exit_code == 0
    rendered = output.read_text(encoding="utf-8")
    # SAMPLE_INPUT has FP-156 "Sections layout view neatly without scrolling" — verify it got upper-cased.
    assert "SECTIONS LAYOUT VIEW NEATLY WITHOUT SCROLLING" in rendered
    assert instance.invocations > 0
