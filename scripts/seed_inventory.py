"""Walk .claude/ + AGENTS.md and emit .claude/usage/inventory.json.

The dashboard joins this inventory against usage events to identify stale
or unused assets. Re-run whenever an asset is added/removed/renamed.

Usage:
    python scripts/seed_inventory.py [--output PATH]

FP-192.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / ".claude" / "usage" / "inventory.json"

# (relative_root, asset_type, file_glob)
SCAN_TARGETS: list[tuple[str, str, str]] = [
    (".claude/commands", "command", "*.md"),
    (".claude/rules", "rule", "*.md"),
    (".claude/hooks", "hook", "*"),
    (".claude/agents", "agent", "*.md"),
]

BRIDGE_FILES: list[str] = [
    ".claude/CLAUDE.md",
    ".claude/ONBOARDING.md",
    "AGENTS.md",
]


@dataclass
class InventoryEntry:
    asset_path: str
    asset_type: str
    name: str
    description: Optional[str]


def _frontmatter_description(text: str) -> Optional[str]:
    """Pull `description:` from YAML-ish frontmatter, if present."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    match = re.search(r"^\s*description:\s*(.+)$", block, re.MULTILINE)
    if match:
        return match.group(1).strip().strip('"').strip("'")
    return None


def _heading_description(text: str) -> Optional[str]:
    """Fallback: first non-empty markdown heading or paragraph (truncated)."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("---"):
            continue
        if stripped.startswith("#"):
            cleaned = stripped.lstrip("#").strip()
            if cleaned:
                return cleaned[:160]
            continue
        # First content paragraph.
        return stripped[:160]
    return None


def _extract_description(path: Path) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return _frontmatter_description(text) or _heading_description(text)


def _command_name(filename: str) -> str:
    """Map jira-plan.md -> /jira-plan."""
    return "/" + filename.rsplit(".", 1)[0]


def _name_for(asset_type: str, path: Path) -> str:
    if asset_type == "command":
        return _command_name(path.name)
    if asset_type == "bridge":
        return path.name
    return path.stem


def _collect_glob(root: Path, asset_type: str, glob: str) -> list[InventoryEntry]:
    entries: list[InventoryEntry] = []
    base = REPO_ROOT / root
    if not base.is_dir():
        return entries
    for item in sorted(base.glob(glob)):
        if not item.is_file():
            continue
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        rel = item.relative_to(REPO_ROOT).as_posix()
        entries.append(
            InventoryEntry(
                asset_path=rel,
                asset_type=asset_type,
                name=_name_for(asset_type, item),
                description=_extract_description(item),
            )
        )
    return entries


def _collect_bridge() -> list[InventoryEntry]:
    entries: list[InventoryEntry] = []
    for rel_path in BRIDGE_FILES:
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue
        entries.append(
            InventoryEntry(
                asset_path=rel_path,
                asset_type="bridge",
                name=path.name,
                description=_extract_description(path),
            )
        )
    return entries


def build_inventory() -> list[InventoryEntry]:
    """Walk all scan targets and bridge files, return a sorted entry list."""
    entries: list[InventoryEntry] = []
    for root, asset_type, glob in SCAN_TARGETS:
        entries.extend(_collect_glob(Path(root), asset_type, glob))
    entries.extend(_collect_bridge())
    entries.sort(key=lambda e: (e.asset_type, e.asset_path))
    return entries


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the local asset inventory.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write inventory.json",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    entries = build_inventory()
    payload = {
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).astimezone().isoformat(timespec="seconds"),
        "count": len(entries),
        "entries": [asdict(e) for e in entries],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        display = args.output.relative_to(REPO_ROOT)
    except ValueError:
        display = args.output
    print(f"wrote {len(entries)} entries to {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
