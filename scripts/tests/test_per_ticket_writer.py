"""Unit tests for scripts/release_docs/per_ticket_writer.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from release_docs.per_ticket_writer import (
    DocType,
    PerTicketDoc,
    find_existing_docs,
    filename_for,
    make_stub_doc,
    write_per_ticket_docs,
)


# ---------------------------------------------------------------------------
# filename_for
# ---------------------------------------------------------------------------


def test_filename_for_produces_canonical_name() -> None:
    assert filename_for("FP-213", "b", "technical") == "FP-213-b-technical.md"
    assert filename_for("FP-213", "a", "business") == "FP-213-a-business.md"
    assert filename_for("FP-213", "c", "management") == "FP-213-c-management.md"


# ---------------------------------------------------------------------------
# make_stub_doc
# ---------------------------------------------------------------------------


def test_make_stub_doc_returns_c_tag() -> None:
    stub = make_stub_doc("FP-213", "business")
    assert stub.tag == "c"
    assert stub.doc_type == "business"
    assert "FP-213" in stub.content


# ---------------------------------------------------------------------------
# write_per_ticket_docs — happy path
# ---------------------------------------------------------------------------


def test_write_creates_files_in_tracker_subdir(tmp_path: Path) -> None:
    docs = [
        PerTicketDoc(doc_type="technical", tag="b", content="# Technical\nSome detail."),
        PerTicketDoc(doc_type="business", tag="b", content="# Business\nUser outcome."),
        PerTicketDoc(doc_type="management", tag="a", content="# Management\nAh-ha moment."),
    ]
    written = write_per_ticket_docs("FP-194", "FP-213", docs, releases_dir=tmp_path)

    assert len(written) == 3
    assert (tmp_path / "FP-194" / "FP-213-b-technical.md").exists()
    assert (tmp_path / "FP-194" / "FP-213-b-business.md").exists()
    assert (tmp_path / "FP-194" / "FP-213-a-management.md").exists()


def test_write_returns_sorted_paths(tmp_path: Path) -> None:
    docs = [
        PerTicketDoc(doc_type="management", tag="a", content="mgmt"),
        PerTicketDoc(doc_type="technical", tag="b", content="tech"),
        PerTicketDoc(doc_type="business", tag="b", content="biz"),
    ]
    written = write_per_ticket_docs("FP-194", "FP-213", docs, releases_dir=tmp_path)
    assert written == sorted(written)


def test_write_creates_missing_parent_dirs(tmp_path: Path) -> None:
    releases = tmp_path / "deep" / "nested"
    docs = [PerTicketDoc(doc_type="technical", tag="b", content="x")]
    write_per_ticket_docs("FP-194", "FP-213", docs, releases_dir=releases)
    assert (releases / "FP-194" / "FP-213-b-technical.md").exists()


def test_write_content_is_correct(tmp_path: Path) -> None:
    content = "# My doc\nDetailed content here."
    docs = [PerTicketDoc(doc_type="technical", tag="b", content=content)]
    write_per_ticket_docs("FP-194", "FP-213", docs, releases_dir=tmp_path)
    written_content = (tmp_path / "FP-194" / "FP-213-b-technical.md").read_text(encoding="utf-8")
    assert written_content == content


# ---------------------------------------------------------------------------
# write_per_ticket_docs — idempotency
# ---------------------------------------------------------------------------


def test_write_overwrites_existing_file(tmp_path: Path) -> None:
    docs_v1 = [PerTicketDoc(doc_type="technical", tag="b", content="version 1")]
    write_per_ticket_docs("FP-194", "FP-213", docs_v1, releases_dir=tmp_path)

    docs_v2 = [PerTicketDoc(doc_type="technical", tag="b", content="version 2")]
    write_per_ticket_docs("FP-194", "FP-213", docs_v2, releases_dir=tmp_path)

    content = (tmp_path / "FP-194" / "FP-213-b-technical.md").read_text(encoding="utf-8")
    assert content == "version 2"


def test_write_tag_change_creates_new_file_does_not_delete_old(tmp_path: Path) -> None:
    # First run: tag b
    docs_v1 = [PerTicketDoc(doc_type="technical", tag="b", content="v1")]
    write_per_ticket_docs("FP-194", "FP-213", docs_v1, releases_dir=tmp_path)

    # Second run: tag a (e.g., AI re-evaluated)
    docs_v2 = [PerTicketDoc(doc_type="technical", tag="a", content="v2")]
    write_per_ticket_docs("FP-194", "FP-213", docs_v2, releases_dir=tmp_path)

    # Both exist — caller is responsible for cleaning up the old tag
    assert (tmp_path / "FP-194" / "FP-213-b-technical.md").exists()
    assert (tmp_path / "FP-194" / "FP-213-a-technical.md").exists()


# ---------------------------------------------------------------------------
# write_per_ticket_docs — stub docs
# ---------------------------------------------------------------------------


def test_write_stub_doc(tmp_path: Path) -> None:
    stub = make_stub_doc("FP-213", "business")
    written = write_per_ticket_docs("FP-194", "FP-213", [stub], releases_dir=tmp_path)
    assert (tmp_path / "FP-194" / "FP-213-c-business.md").exists()
    content = written[0].read_text(encoding="utf-8")
    assert "optional/skip" in content


# ---------------------------------------------------------------------------
# find_existing_docs
# ---------------------------------------------------------------------------


def test_find_existing_docs_returns_empty_when_none(tmp_path: Path) -> None:
    result = find_existing_docs("FP-194", "FP-213", releases_dir=tmp_path)
    assert result == {}


def test_find_existing_docs_finds_written_files(tmp_path: Path) -> None:
    docs = [
        PerTicketDoc(doc_type="technical", tag="b", content="tech"),
        PerTicketDoc(doc_type="management", tag="a", content="mgmt"),
    ]
    write_per_ticket_docs("FP-194", "FP-213", docs, releases_dir=tmp_path)
    found = find_existing_docs("FP-194", "FP-213", releases_dir=tmp_path)

    assert "technical" in found
    assert "management" in found
    assert "business" not in found
