"""Unit tests for `scripts/active_tracker.py` (FP-212).

Covers the resolver, label-aware work-type tagging, bundle-append idempotency,
evidence-line upsert (per-ticket overwrite), and schema-drift auto-repair /
fuzzy-match hard-stop semantics agreed in the FP-212 review thread.
"""

from __future__ import annotations

import textwrap

import pytest

from scripts.active_tracker import (
    BUNDLE_HEADER,
    JIRA_BASE_URL,
    TEST_EVIDENCE_HEADER,
    SchemaDriftError,
    append_bundle_entry,
    derive_work_type,
    ensure_section,
    resolve_active_tracker,
    set_document_flag,
    upsert_evidence_entry,
)

_DEFAULT_BUNDLE = (
    "| Jira ID | Desc | Type | Status | Document (Y/N) |\n"
    "| --- | --- | --- | --- | --- |\n"
    "| [FP-100](https://ltads.atlassian.net/browse/FP-100) | Existing item | sprint | In Progress | |\n"
)


def _tracker_description(
    bundle: str = _DEFAULT_BUNDLE,
    evidence: str = "- FP-100 Run 1 _Pass_ — [evidence comment](https://example/c1)\n",
) -> str:
    """Return a realistic tracker description with substitutable bundle/evidence bodies.

    Uses plain string concatenation (not textwrap.dedent) so multi-line bundle
    or evidence values don't shift the indentation and break `^##` regex anchors.
    """
    return (
        "## Release manifest\n"
        "- Version: 0.4.7\n"
        "- Target environment: UAT\n"
        "\n"
        "## Change summary\n"
        "- Adds the active-tracker auto-append (FP-212).\n"
        "\n"
        "## Bundle\n"
        + bundle
        + "\n"
        "## PR / commit references\n"
        "- leonyap27/Funding_paper_agent#42\n"
        "\n"
        "## Readiness checklist\n"
        "- [ ] Code freeze on dev\n"
        "\n"
        "## Test evidence\n"
        + evidence
        + "\n"
        "## Known issues / limitations\n"
        "None reported.\n"
    )


# --- resolve_active_tracker -------------------------------------------------------


class TestResolveActiveTracker:
    def test_empty_returns_none(self) -> None:
        assert resolve_active_tracker([]) is None

    def test_single_match_returns_it(self) -> None:
        issue = {"key": "FP-194", "fields": {"created": "2026-05-01T00:00:00.000+0800"}}
        assert resolve_active_tracker([issue]) is issue

    def test_multiple_picks_newest_by_created(self) -> None:
        older = {"key": "FP-180", "fields": {"created": "2026-04-15T10:00:00.000+0800"}}
        newer = {"key": "FP-200", "fields": {"created": "2026-05-20T10:00:00.000+0800"}}
        # Pass in oldest-first order to verify the helper re-sorts defensively.
        result = resolve_active_tracker([older, newer])
        assert result is newer

    def test_missing_created_field_sorts_to_back(self) -> None:
        dated = {"key": "FP-200", "fields": {"created": "2026-05-20T10:00:00.000+0800"}}
        undated = {"key": "FP-201", "fields": {}}
        result = resolve_active_tracker([undated, dated])
        # The dated one wins because empty-string `created` sorts last under DESC.
        assert result is dated


# --- derive_work_type -------------------------------------------------------------


class TestDeriveWorkType:
    def test_no_relevant_labels_defaults_to_sprint(self) -> None:
        assert derive_work_type([]) == "sprint"
        assert derive_work_type(["bug", "frontend"]) == "sprint"

    def test_tech_debt_label_wins(self) -> None:
        assert derive_work_type(["release-work-type:tech-debt"]) == "tech-debt"

    def test_carry_over_label_wins_when_alone(self) -> None:
        assert derive_work_type(["release-work-type:carry-over"]) == "carry-over"

    def test_tech_debt_beats_carry_over(self) -> None:
        labels = ["release-work-type:carry-over", "release-work-type:tech-debt"]
        assert derive_work_type(labels) == "tech-debt"


# --- ensure_section ---------------------------------------------------------------


class TestEnsureSection:
    def test_present_canonical_is_noop(self) -> None:
        desc = _tracker_description()
        result = ensure_section(desc, BUNDLE_HEADER, "PR", ("bundle", "items"))
        assert result.did_repair is False
        assert result.description == desc

    def test_canonical_prefix_variant_is_not_drift(self) -> None:
        # Mirrors the RELEASE_TRACKER_SCHEMA.md sample heading.
        desc = "## Bundle (included Jira items)\n- [ ] FP-100 [sprint] foo\n"
        result = ensure_section(desc, BUNDLE_HEADER, None, ("bundle", "items"))
        assert result.did_repair is False
        assert result.description == desc

    def test_missing_with_no_fuzzy_inserts_before_anchor(self) -> None:
        desc = textwrap.dedent(
            """\
            ## Change summary
            stuff

            ## PR / commit references
            - foo
            """
        )
        result = ensure_section(desc, BUNDLE_HEADER, "PR", ("bundle", "items"))
        assert result.did_repair is True
        assert "## Bundle\n" in result.description
        # The new section comes before the anchor.
        bundle_idx = result.description.index("## Bundle")
        pr_idx = result.description.index("## PR")
        assert bundle_idx < pr_idx

    def test_missing_with_no_anchor_appends_at_end(self) -> None:
        desc = "## Change summary\nstuff\n"
        result = ensure_section(desc, BUNDLE_HEADER, "PR", ("bundle", "items"))
        assert result.did_repair is True
        assert result.description.endswith("## Bundle\n")

    def test_missing_with_fuzzy_heading_raises(self) -> None:
        desc = textwrap.dedent(
            """\
            ## Change summary
            stuff

            ## Items in this release
            - [ ] FP-100

            ## PR / commit references
            - foo
            """
        )
        with pytest.raises(SchemaDriftError) as exc_info:
            ensure_section(desc, BUNDLE_HEADER, "PR", ("bundle", "items", "tickets"))
        assert "Items in this release" in str(exc_info.value)

    def test_evidence_missing_with_fuzzy_raises(self) -> None:
        desc = "## Release manifest\nstuff\n\n## QA results\n- ok\n"
        with pytest.raises(SchemaDriftError):
            ensure_section(desc, TEST_EVIDENCE_HEADER, "Known issues", ("test", "evidence", "qa"))


# --- append_bundle_entry ----------------------------------------------------------


class TestAppendBundleEntry:
    def test_clean_tracker_adds_table_row(self) -> None:
        desc = _tracker_description()
        result = append_bundle_entry(desc, "FP-212", "sprint", "Auto-append")
        assert f"[FP-212]({JIRA_BASE_URL}/FP-212)" in result
        assert "Auto-append" in result
        assert "sprint" in result
        # The existing FP-100 row survives.
        assert "FP-100" in result
        assert "Existing item" in result

    def test_rerun_with_same_fp_key_is_noop(self) -> None:
        desc = _tracker_description()
        once = append_bundle_entry(desc, "FP-212", "sprint", "Auto-append")
        twice = append_bundle_entry(once, "FP-212", "sprint", "Auto-append")
        assert once == twice

    def test_rerun_with_different_summary_still_noop(self) -> None:
        # Idempotency keys off FP-XXX, not the summary.
        desc = _tracker_description()
        once = append_bundle_entry(desc, "FP-212", "sprint", "First")
        twice = append_bundle_entry(once, "FP-212", "sprint", "Second")
        assert once == twice
        assert "First" in twice
        assert "Second" not in twice

    def test_two_different_fp_keys_both_present(self) -> None:
        desc = _tracker_description()
        result = append_bundle_entry(desc, "FP-212", "sprint", "First")
        result = append_bundle_entry(result, "FP-213", "tech-debt", "Second")
        assert "FP-212" in result and "First" in result
        assert "FP-213" in result and "Second" in result and "tech-debt" in result

    def test_fp_key_prefix_collision_does_not_match(self) -> None:
        # FP-21 must not match the row containing FP-212.
        fp212_bundle = (
            "| Jira ID | Desc | Type | Status | Document (Y/N) |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"| [FP-212]({JIRA_BASE_URL}/FP-212) | Existing | sprint | Done | |\n"
        )
        desc = _tracker_description(bundle=fp212_bundle)
        result = append_bundle_entry(desc, "FP-21", "sprint", "Different ticket")
        assert "FP-21" in result and "Different ticket" in result
        assert "FP-212" in result and "Existing" in result

    def test_preserves_other_sections_byte_for_byte(self) -> None:
        desc = _tracker_description()
        result = append_bundle_entry(desc, "FP-212", "sprint", "New")
        for section_header in (
            "## Release manifest",
            "## Change summary",
            "## PR / commit references",
            "## Readiness checklist",
            "## Test evidence",
            "## Known issues / limitations",
        ):
            assert section_header in result
        # Content of unrelated sections unchanged.
        assert "- Version: 0.4.7" in result
        assert "- leonyap27/Funding_paper_agent#42" in result
        assert "None reported." in result

    def test_auto_repair_missing_bundle_creates_table(self) -> None:
        desc = textwrap.dedent(
            """\
            ## Change summary
            stuff

            ## PR / commit references
            - foo
            """
        )
        result = append_bundle_entry(desc, "FP-212", "sprint", "Brand new")
        assert "## Bundle" in result
        assert "| Jira ID |" in result
        assert "FP-212" in result and "Brand new" in result

    def test_legacy_checklist_section_appends_checklist_line(self) -> None:
        # Backward compat: if existing items are checklist lines, keep that format.
        legacy_bundle = "- [ ] FP-100 [sprint] Existing item\n"
        desc = _tracker_description(bundle=legacy_bundle)
        result = append_bundle_entry(desc, "FP-212", "sprint", "New item")
        assert "- [ ] FP-212 [sprint] New item" in result

    def test_fuzzy_match_bundle_raises(self) -> None:
        desc = textwrap.dedent(
            """\
            ## Change summary
            stuff

            ## Tickets included
            - FP-100

            ## PR / commit references
            - foo
            """
        )
        with pytest.raises(SchemaDriftError):
            append_bundle_entry(desc, "FP-212", "sprint", "Brand new")


# --- upsert_evidence_entry --------------------------------------------------------


class TestUpsertEvidenceEntry:
    URL_1 = "https://ltads.atlassian.net/browse/FP-212?focusedCommentId=111"
    URL_2 = "https://ltads.atlassian.net/browse/FP-212?focusedCommentId=222"

    def test_first_call_appends(self) -> None:
        desc = _tracker_description()
        result = upsert_evidence_entry(desc, "FP-212", 1, "Pass", self.URL_1)
        assert "- FP-212 Run 1 _Pass_" in result
        assert self.URL_1 in result
        # Existing FP-100 line still there.
        assert "FP-100 Run 1 _Pass_" in result

    def test_second_call_same_fp_replaces_prior(self) -> None:
        desc = _tracker_description()
        once = upsert_evidence_entry(desc, "FP-212", 1, "Fail", self.URL_1)
        twice = upsert_evidence_entry(once, "FP-212", 2, "Pass", self.URL_2)
        # Only the latest run survives for FP-212.
        assert "Run 2 _Pass_" in twice
        assert "Run 1 _Fail_" not in twice
        assert self.URL_2 in twice
        assert self.URL_1 not in twice
        # Other tickets' evidence untouched.
        assert "FP-100 Run 1 _Pass_" in twice

    def test_different_fp_keys_both_present(self) -> None:
        desc = _tracker_description()
        result = upsert_evidence_entry(desc, "FP-212", 1, "Pass", self.URL_1)
        result = upsert_evidence_entry(result, "FP-213", 1, "Fail", self.URL_2)
        assert "FP-212 Run 1 _Pass_" in result
        assert "FP-213 Run 1 _Fail_" in result

    def test_fp_key_prefix_collision_does_not_replace(self) -> None:
        # FP-21 must not overwrite a line containing FP-212.
        desc = _tracker_description(
            evidence="- FP-212 Run 1 _Pass_ — [evidence comment](https://example/x)\n"
        )
        result = upsert_evidence_entry(desc, "FP-21", 1, "Pass", self.URL_1)
        assert "FP-212 Run 1 _Pass_" in result
        assert "FP-21 Run 1 _Pass_" in result

    def test_auto_repair_missing_evidence_then_upserts(self) -> None:
        # Strip the Test evidence section entirely.
        desc = textwrap.dedent(
            """\
            ## Release manifest
            stuff

            ## Bundle
            - [ ] FP-100 [sprint] foo

            ## Known issues / limitations
            None.
            """
        )
        result = upsert_evidence_entry(desc, "FP-212", 1, "Pass", self.URL_1)
        assert "## Test evidence" in result
        assert "FP-212 Run 1 _Pass_" in result
        # Inserted before the Known issues anchor.
        assert result.index("## Test evidence") < result.index("## Known issues")


# --- set_document_flag ------------------------------------------------------------


class TestSetDocumentFlag:
    def _table_desc(self, doc_col: str = "") -> str:
        bundle = (
            "| Jira ID | Desc | Type | Status | Document (Y/N) |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"| [FP-212]({JIRA_BASE_URL}/FP-212) | summary | sprint | Done | {doc_col} |\n"
            f"| [FP-100]({JIRA_BASE_URL}/FP-100) | other | sprint | Done | |\n"
        )
        return _tracker_description(bundle=bundle)

    def test_sets_y_when_empty(self) -> None:
        result = set_document_flag(self._table_desc(""), "FP-212")
        # FP-212 row should now have Y in the last cell
        assert "FP-212" in result
        # Find the FP-212 row and check Document cell
        for line in result.splitlines():
            if "FP-212" in line and line.strip().startswith("|"):
                cells = line.split("|")
                assert cells[-2].strip() == "Y"
                break
        else:
            pytest.fail("FP-212 row not found")

    def test_noop_when_already_y(self) -> None:
        desc = self._table_desc("Y")
        result = set_document_flag(desc, "FP-212")
        assert result == desc

    def test_other_rows_unaffected(self) -> None:
        result = set_document_flag(self._table_desc(""), "FP-212")
        for line in result.splitlines():
            if "FP-100" in line and line.strip().startswith("|"):
                cells = line.split("|")
                assert cells[-2].strip() == ""
                break

    def test_key_not_found_is_noop(self) -> None:
        desc = self._table_desc("")
        result = set_document_flag(desc, "FP-999")
        assert result == desc

    def test_legacy_checklist_is_noop(self) -> None:
        legacy_bundle = "- [ ] FP-212 [sprint] summary\n"
        desc = _tracker_description(bundle=legacy_bundle)
        result = set_document_flag(desc, "FP-212")
        assert result == desc  # no Document column to update

    def test_missing_bundle_section_is_noop(self) -> None:
        desc = "## Change summary\nstuff\n"
        assert set_document_flag(desc, "FP-212") == desc
