"""Tests for scripts/seed_inventory.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import seed_inventory  # noqa: E402


def test_frontmatter_description_extracts_value():
    text = '---\ndescription: Plan implementation for a JIRA ticket.\nargument-hint: <KEY>\n---\nbody'
    assert seed_inventory._frontmatter_description(text) == "Plan implementation for a JIRA ticket."


def test_frontmatter_description_returns_none_without_block():
    assert seed_inventory._frontmatter_description("# Just a heading\n\ntext") is None


def test_heading_description_falls_back_to_first_paragraph():
    text = "\n\nFirst meaningful line."
    assert seed_inventory._heading_description(text) == "First meaningful line."


def test_command_name_maps_filename_to_slash_command():
    assert seed_inventory._command_name("jira-plan.md") == "/jira-plan"


def test_build_inventory_covers_repo_assets():
    entries = seed_inventory.build_inventory()
    asset_types = {e.asset_type for e in entries}
    # The actual repo has commands, rules, hooks, agents, and bridge files.
    assert {"command", "rule", "hook", "agent", "bridge"}.issubset(asset_types)
    # Every entry has a stable repo-relative path.
    for entry in entries:
        assert not entry.asset_path.startswith("/")
        assert entry.name


def test_main_writes_inventory_json(tmp_path):
    output = tmp_path / "inventory.json"
    rc = seed_inventory.main(["--output", str(output)])
    assert rc == 0
    payload = json.loads(output.read_text())
    assert payload["count"] == len(payload["entries"])
    assert payload["count"] > 0
    # Sanity check that the four jira commands are present.
    names = {e["name"] for e in payload["entries"] if e["asset_type"] == "command"}
    assert {"/jira-plan", "/jira-review", "/jira-impl", "/jira-test"}.issubset(names)
