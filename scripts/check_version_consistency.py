"""Pre-release consistency check for version artifacts.

Verifies that the canonical version string in the repo-root ``VERSION`` file
matches the top heading version in ``CHANGELOG.md``. The frontend badge,
backend ``__version__``, KB manifest, and deploy image tag all read from
``VERSION``; ``CHANGELOG.md`` is the release tracker (see ``VERSIONING.md``).
Drift between them means the release record disagrees with what shipped.

Run from the repo root before tagging a release:

    python scripts/check_version_consistency.py

Exit codes:
    0 -- VERSION matches the CHANGELOG.md top heading.
    1 -- mismatch, or required file missing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"

CHANGELOG_HEADING_PATTERN = re.compile(r"^##\s*\[v(?P<version>[^\]]+)\]")


def read_version() -> str:
    """Return the canonical version string from the repo-root VERSION file."""
    if not VERSION_FILE.exists():
        raise FileNotFoundError(f"VERSION file missing at {VERSION_FILE}")
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"VERSION file at {VERSION_FILE} is empty")
    return value


def read_changelog_top_version() -> str:
    """Return the version from the first ``## [vX.Y.Z]`` heading in CHANGELOG.md."""
    if not CHANGELOG_FILE.exists():
        raise FileNotFoundError(f"CHANGELOG.md missing at {CHANGELOG_FILE}")
    for line in CHANGELOG_FILE.read_text(encoding="utf-8").splitlines():
        match = CHANGELOG_HEADING_PATTERN.match(line)
        if match:
            return match.group("version")
    raise ValueError(
        f"No '## [vX.Y.Z]' heading found in {CHANGELOG_FILE}. "
        "Expected at least one release section."
    )


def main() -> int:
    """Compare VERSION against CHANGELOG.md top heading and report drift."""
    try:
        version = read_version()
        changelog_version = read_changelog_top_version()
    except (FileNotFoundError, ValueError) as exc:
        print(f"check_version_consistency: {exc}", file=sys.stderr)
        return 1

    if version != changelog_version:
        print(
            "check_version_consistency: MISMATCH\n"
            f"  VERSION         = {version!r}\n"
            f"  CHANGELOG.md    = {changelog_version!r}\n"
            "Update one of them so the release record matches the shipped version.",
            file=sys.stderr,
        )
        return 1

    print(f"check_version_consistency: OK (VERSION = CHANGELOG.md = {version})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
