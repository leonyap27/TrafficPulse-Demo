"""Unit tests for scripts/release_cut.py (FP-214).

Covers the algorithmic spec used by the /release-cut slash command.
All tests use mocked JIRA + filesystem; no live API calls.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from scripts.release_cut import (
    BundleItem,
    CarryOverCandidate,
    CarryOverDecision,
    DONE_STATUSES,
    apply_decisions,
    auto_carry_all,
    build_preview_table,
    collect_carry_over_candidates,
    detect_sprint_contamination,
    locate_draft,
    parse_bundle_lines,
    promote_draft,
    read_version,
    render_preview_markdown,
    resolve_next_version,
    validate_version,
    write_version,
)

# ---------------------------------------------------------------------------
# validate_version / resolve_next_version
# ---------------------------------------------------------------------------


class TestValidateVersion:
    def test_valid_patch(self):
        assert validate_version("0.4.5") == "0.4.5"

    def test_valid_minor(self):
        assert validate_version("1.0.0") == "1.0.0"

    def test_strips_whitespace(self):
        assert validate_version("  0.4.5  ") == "0.4.5"

    def test_rejects_prerelease(self):
        with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
            validate_version("0.4.5-rc.1")

    def test_rejects_two_part(self):
        with pytest.raises(ValueError):
            validate_version("0.4")

    def test_rejects_alpha(self):
        with pytest.raises(ValueError):
            validate_version("v0.4.5")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_version("")


class TestResolveNextVersion:
    def test_default_patch_bump(self):
        assert resolve_next_version("0.4.5", None) == "0.4.6"

    def test_explicit_minor_bump(self):
        assert resolve_next_version("0.4.5", "0.5.0") == "0.5.0"

    def test_explicit_major_bump(self):
        assert resolve_next_version("0.4.5", "1.0.0") == "1.0.0"

    def test_explicit_same_version(self):
        # allowed — operator's call
        assert resolve_next_version("0.4.5", "0.4.5") == "0.4.5"

    def test_invalid_explicit_raises(self):
        with pytest.raises(ValueError):
            resolve_next_version("0.4.5", "notasemver")

    def test_current_version_stripped(self):
        assert resolve_next_version("0.4.5\n", None) == "0.4.6"


# ---------------------------------------------------------------------------
# parse_bundle_lines
# ---------------------------------------------------------------------------


class TestParseBundleLines:
    _TABLE_DESC = textwrap.dedent("""\
        ## Bundle (included Jira items)

        | Jira ID | Desc | Type | Status | Document (Y/N) |
        | --- | --- | --- | --- | --- |
        | [FP-185](https://ltads.atlassian.net/browse/FP-185) | Design Jira tracker | sprint | Done | |
        | [FP-186](https://ltads.atlassian.net/browse/FP-186) | Versioning standard | sprint | Done | Y |
        | [FP-184](https://ltads.atlassian.net/browse/FP-184) | Strip SA grants | tech-debt | Done | |
        | [FP-95](https://ltads.atlassian.net/browse/FP-95) | POC story | carry-over | Done | |
    """)

    _LEGACY_DESC = textwrap.dedent("""\
        ## Bundle (included Jira items)

        - [ ] FP-185 [sprint]      Design Jira tracker
        - [x] FP-186 [sprint]      Versioning standard
        - [ ] FP-184 [tech-debt]   Strip SA grants
        - [ ] FP-95  [carry-over]  POC story
    """)

    def test_table_all_lines_parsed(self):
        result = parse_bundle_lines(self._TABLE_DESC)
        assert [r[0] for r in result] == ["FP-185", "FP-186", "FP-184", "FP-95"]

    def test_table_work_type_extracted(self):
        result = parse_bundle_lines(self._TABLE_DESC)
        assert result[0][1] == "sprint"
        assert result[2][1] == "tech-debt"
        assert result[3][1] == "carry-over"

    def test_table_summary_extracted(self):
        result = parse_bundle_lines(self._TABLE_DESC)
        assert result[0][2] == "Design Jira tracker"

    def test_table_has_doc_flag(self):
        result = parse_bundle_lines(self._TABLE_DESC)
        assert result[0][3] is False   # no Y
        assert result[1][3] is True    # Y present
        assert result[2][3] is False

    def test_table_skips_header_and_separator_rows(self):
        result = parse_bundle_lines(self._TABLE_DESC)
        # Should only have 4 data rows, not the header or separator
        assert len(result) == 4

    def test_legacy_checklist_fallback(self):
        result = parse_bundle_lines(self._LEGACY_DESC)
        assert [r[0] for r in result] == ["FP-185", "FP-186", "FP-184", "FP-95"]
        assert result[0][1] == "sprint"
        assert result[0][2] == "Design Jira tracker"
        assert result[0][3] is False  # legacy rows have no Document column

    def test_empty_description(self):
        assert parse_bundle_lines("") == []

    def test_no_bundle_section(self):
        assert parse_bundle_lines("## Change summary\n\n* bullet") == []


class TestAutoCarryAll:
    def _item(self, key: str, status: str) -> BundleItem:
        return BundleItem(key=key, summary="s", status=status, work_type="sprint")

    def test_done_excluded(self):
        items = [self._item("FP-1", "DONE"), self._item("FP-2", "In Progress")]
        result = auto_carry_all(items)
        assert [i.key for i in result] == ["FP-2"]

    def test_ready_for_deploy_excluded(self):
        items = [self._item("FP-1", "READY FOR DEPLOY"), self._item("FP-2", "TESTING")]
        result = auto_carry_all(items)
        assert [i.key for i in result] == ["FP-2"]

    def test_all_done_returns_empty(self):
        items = [self._item("FP-1", "DONE"), self._item("FP-2", "READY FOR DEPLOY")]
        assert auto_carry_all(items) == []

    def test_all_non_done_carries_all(self):
        statuses = ["In Progress", "In Review", "TESTING", "To Do", "Backlog"]
        items = [self._item(f"FP-{i}", s) for i, s in enumerate(statuses)]
        assert len(auto_carry_all(items)) == len(statuses)

    def test_preserves_order(self):
        items = [self._item("FP-3", "TESTING"), self._item("FP-1", "In Progress")]
        result = auto_carry_all(items)
        assert [i.key for i in result] == ["FP-3", "FP-1"]


# ---------------------------------------------------------------------------
# detect_sprint_contamination
# ---------------------------------------------------------------------------


class TestDetectSprintContamination:
    def _make(self, key: str, sprint: str | None) -> BundleItem:
        return BundleItem(key=key, summary="s", status="In Progress", work_type="sprint", sprint=sprint)

    def test_no_contamination_same_sprint(self):
        items = [self._make("FP-1", "Sprint 2"), self._make("FP-2", "Sprint 2")]
        assert detect_sprint_contamination(items, "Sprint 2") == []

    def test_detects_different_sprint(self):
        items = [self._make("FP-1", "Sprint 2"), self._make("FP-2", "Sprint 3")]
        result = detect_sprint_contamination(items, "Sprint 2")
        assert len(result) == 1
        assert result[0].key == "FP-2"

    def test_none_sprint_on_item_not_flagged(self):
        items = [self._make("FP-1", None)]
        assert detect_sprint_contamination(items, "Sprint 2") == []

    def test_none_current_sprint_no_flags(self):
        items = [self._make("FP-1", "Sprint 2")]
        assert detect_sprint_contamination(items, None) == []

    def test_all_contaminated(self):
        items = [self._make(f"FP-{i}", "Sprint 3") for i in range(3)]
        result = detect_sprint_contamination(items, "Sprint 2")
        assert len(result) == 3


# ---------------------------------------------------------------------------
# build_preview_table / render_preview_markdown
# ---------------------------------------------------------------------------


def _make_item(key: str, status: str, sprint: str | None = "Sprint 2") -> BundleItem:
    return BundleItem(key=key, summary="some work", status=status, work_type="sprint", sprint=sprint)


class TestBuildPreviewTable:
    def test_done_item_ships(self):
        items = [_make_item("FP-1", "DONE")]
        rows = build_preview_table(items, "0.4.5", "0.4.6")
        assert rows[0].outcome == "✓ ships in v0.4.5"

    def test_ready_for_deploy_ships(self):
        items = [_make_item("FP-1", "READY FOR DEPLOY")]
        rows = build_preview_table(items, "0.4.5", "0.4.6")
        assert rows[0].outcome == "✓ ships in v0.4.5"

    def test_in_progress_carry_over(self):
        items = [_make_item("FP-1", "In Progress")]
        rows = build_preview_table(items, "0.4.5", "0.4.6")
        assert "carry-over" in rows[0].outcome
        assert "0.4.6" in rows[0].outcome

    def test_contamination_flagged(self):
        items = [_make_item("FP-1", "In Progress", sprint="Sprint 3")]
        rows = build_preview_table(items, "0.4.5", "0.4.6", current_sprint="Sprint 2")
        assert rows[0].sprint_contaminated is True

    def test_same_sprint_not_flagged(self):
        items = [_make_item("FP-1", "In Progress", sprint="Sprint 2")]
        rows = build_preview_table(items, "0.4.5", "0.4.6", current_sprint="Sprint 2")
        assert rows[0].sprint_contaminated is False

    def test_empty_bundle(self):
        assert build_preview_table([], "0.4.5", "0.4.6") == []


class TestRenderPreviewMarkdown:
    def test_contains_header(self):
        rows = build_preview_table(
            [_make_item("FP-1", "DONE")], "0.4.5", "0.4.6"
        )
        md = render_preview_markdown(rows, "0.4.5", "0.4.6", "FP-194")
        assert "PREVIEW" in md
        assert "no writes" in md

    def test_contains_tracker_key(self):
        rows = build_preview_table([_make_item("FP-1", "DONE")], "0.4.5", "0.4.6")
        md = render_preview_markdown(rows, "0.4.5", "0.4.6", "FP-194")
        assert "FP-194" in md

    def test_contamination_warning_shown(self):
        items = [_make_item("FP-1", "In Progress", sprint="Sprint 3")]
        rows = build_preview_table(items, "0.4.5", "0.4.6", current_sprint="Sprint 2")
        md = render_preview_markdown(rows, "0.4.5", "0.4.6", "FP-194")
        assert "Sprint contamination" in md

    def test_no_contamination_no_warning(self):
        rows = build_preview_table([_make_item("FP-1", "DONE")], "0.4.5", "0.4.6")
        md = render_preview_markdown(rows, "0.4.5", "0.4.6", "FP-194")
        assert "Sprint contamination" not in md


# ---------------------------------------------------------------------------
# collect_carry_over_candidates / apply_decisions
# ---------------------------------------------------------------------------


class TestCollectCarryOverCandidates:
    def test_done_excluded(self):
        items = [_make_item("FP-1", "DONE"), _make_item("FP-2", "READY FOR DEPLOY")]
        assert collect_carry_over_candidates(items) == []

    def test_non_done_included(self):
        items = [_make_item("FP-1", "In Progress"), _make_item("FP-2", "DONE")]
        result = collect_carry_over_candidates(items)
        assert len(result) == 1
        assert result[0].item.key == "FP-1"
        assert result[0].decision is None

    def test_all_statuses_except_done(self):
        non_done = ["In Progress", "In Review", "TESTING", "To Do", "Backlog"]
        items = [_make_item(f"FP-{i}", s) for i, s in enumerate(non_done)]
        result = collect_carry_over_candidates(items)
        assert len(result) == len(non_done)

    def test_all_done_returns_empty(self):
        items = [_make_item("FP-1", "DONE"), _make_item("FP-2", "DONE")]
        assert collect_carry_over_candidates(items) == []


class TestApplyDecisions:
    def _candidate(self, key: str, decision: CarryOverDecision) -> CarryOverCandidate:
        c = CarryOverCandidate(item=_make_item(key, "In Progress"))
        c.decision = decision
        return c

    def test_y_becomes_carry_over(self):
        candidates = [self._candidate("FP-1", "Y")]
        carry, dropped = apply_decisions(candidates)
        assert [i.key for i in carry] == ["FP-1"]
        assert dropped == []

    def test_drop_becomes_dropped(self):
        candidates = [self._candidate("FP-1", "drop")]
        carry, dropped = apply_decisions(candidates)
        assert carry == []
        assert [i.key for i in dropped] == ["FP-1"]

    def test_mixed(self):
        candidates = [
            self._candidate("FP-1", "Y"),
            self._candidate("FP-2", "drop"),
            self._candidate("FP-3", "Y"),
        ]
        carry, dropped = apply_decisions(candidates)
        assert [i.key for i in carry] == ["FP-1", "FP-3"]
        assert [i.key for i in dropped] == ["FP-2"]

    def test_unresolved_raises(self):
        candidates = [self._candidate("FP-1", "Y")]
        candidates[0].decision = "skip"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unresolved"):
            apply_decisions(candidates)

    def test_all_y_no_drops(self):
        candidates = [self._candidate(f"FP-{i}", "Y") for i in range(5)]
        carry, dropped = apply_decisions(candidates)
        assert len(carry) == 5
        assert dropped == []

    def test_all_drop_no_carry(self):
        candidates = [self._candidate(f"FP-{i}", "drop") for i in range(3)]
        carry, dropped = apply_decisions(candidates)
        assert carry == []
        assert len(dropped) == 3


# ---------------------------------------------------------------------------
# locate_draft / promote_draft
# ---------------------------------------------------------------------------


class TestLocateDraft:
    def test_found_when_exists(self, tmp_path: Path):
        draft = tmp_path / "v0.4.5_draft.md"
        draft.write_text("# draft", encoding="utf-8")
        assert locate_draft(tmp_path, "0.4.5") == draft

    def test_returns_none_when_missing(self, tmp_path: Path):
        assert locate_draft(tmp_path, "0.4.5") is None

    def test_does_not_match_other_versions(self, tmp_path: Path):
        (tmp_path / "v0.4.6_draft.md").write_text("other", encoding="utf-8")
        assert locate_draft(tmp_path, "0.4.5") is None


class TestPromoteDraft:
    def test_promotes_successfully(self, tmp_path: Path):
        draft = tmp_path / "v0.4.5_draft.md"
        draft.write_text("# sprint notes", encoding="utf-8")
        promoted, dest, reason = promote_draft(tmp_path, "0.4.5")
        assert promoted is True
        assert dest == tmp_path / "v0.4.5.md"
        assert dest.exists()
        assert not draft.exists()
        assert reason is None

    def test_no_draft_graceful_skip(self, tmp_path: Path):
        promoted, dest, reason = promote_draft(tmp_path, "0.4.5")
        assert promoted is False
        assert dest is None
        assert "No v0.4.5_draft.md" in reason  # type: ignore[arg-type]

    def test_dest_already_exists_skip(self, tmp_path: Path):
        draft = tmp_path / "v0.4.5_draft.md"
        draft.write_text("draft", encoding="utf-8")
        (tmp_path / "v0.4.5.md").write_text("existing", encoding="utf-8")
        promoted, dest, reason = promote_draft(tmp_path, "0.4.5")
        assert promoted is False
        assert dest == tmp_path / "v0.4.5.md"
        assert "already exists" in reason  # type: ignore[arg-type]
        assert draft.exists()


# ---------------------------------------------------------------------------
# VERSION file helpers
# ---------------------------------------------------------------------------


class TestVersionFile:
    def test_read_valid(self, tmp_path: Path):
        f = tmp_path / "VERSION"
        f.write_text("0.4.5\n", encoding="utf-8")
        assert read_version(f) == "0.4.5"

    def test_read_strips_whitespace(self, tmp_path: Path):
        f = tmp_path / "VERSION"
        f.write_text("  0.4.5  \n", encoding="utf-8")
        assert read_version(f) == "0.4.5"

    def test_read_invalid_raises(self, tmp_path: Path):
        f = tmp_path / "VERSION"
        f.write_text("not-a-version\n", encoding="utf-8")
        with pytest.raises(ValueError):
            read_version(f)

    def test_read_missing_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_version(tmp_path / "VERSION")

    def test_write_valid(self, tmp_path: Path):
        f = tmp_path / "VERSION"
        write_version("0.4.6", f)
        assert f.read_text(encoding="utf-8") == "0.4.6\n"

    def test_write_invalid_raises(self, tmp_path: Path):
        f = tmp_path / "VERSION"
        with pytest.raises(ValueError):
            write_version("notvalid", f)
        assert not f.exists()
