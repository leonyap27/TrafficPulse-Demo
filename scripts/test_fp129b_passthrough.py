"""FP-129B: Verify the snippets pass-through does not alter the drafter prompt.

This is the safety net for FP-129B's "no prompt change" guarantee.

Approach: monkeypatch draft_section + review_section + review_document_coherence
to capture the exact arguments they receive. Run the supervisor twice with
identical inputs — once without source_text_snippets, once with a populated
list — and assert byte-equality of every argument the drafter saw.

No real Gemini call, no KB load, no network. Run from project root:

    python scripts/test_fp129b_passthrough.py

Exits non-zero on any mismatch.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import agents.supervisor as supervisor


PASS = 0
FAIL = 0


def _check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}{(' — ' + detail) if detail else ''}")


# ── Capture-everything stand-ins for the inner agent calls ──────────────────

class CallRecorder:
    def __init__(self) -> None:
        self.draft_calls: list[tuple] = []   # (positional_args, kwargs)
        self.review_calls: list[tuple] = []
        self.coherence_calls: list[dict] = []

    def reset(self) -> None:
        self.draft_calls.clear()
        self.review_calls.clear()
        self.coherence_calls.clear()


async def _fake_draft_section(*args, **kwargs):
    _RECORDER.draft_calls.append((args, kwargs))
    section_name = args[0] if args else kwargs.get("section_name", "?")
    return f"DRAFT for {section_name}"


async def _fake_review_section(*args, **kwargs):
    _RECORDER.review_calls.append((args, kwargs))
    section_name = args[0] if args else kwargs.get("section_name", "?")
    return f"REVIEWED {section_name}"


async def _fake_review_document_coherence(**kwargs):
    _RECORDER.coherence_calls.append(kwargs)
    return {"overall_coherence_score": 9, "suggested_improvements": {}}


_RECORDER = CallRecorder()


def _install_patches() -> None:
    supervisor.draft_section = _fake_draft_section  # type: ignore[assignment]
    supervisor.review_section = _fake_review_section  # type: ignore[assignment]
    supervisor.review_document_coherence = _fake_review_document_coherence  # type: ignore[assignment]


# ── Test fixtures ────────────────────────────────────────────────────────────

PROJECT_TITLE = "Test Project"
PROJECT_DETAILS = "Detailed description of the project."
SECTIONS = ["Executive Summary", "Background"]

SNIPPETS = [
    {
        "text": "Budget: S$5,000,000 over 3 years.",
        "source_file": "doc.pdf",
        "section": None,
        "page": 2,
        "reason_used": "budget commitment",
    },
    {
        "text": "Objective: deliver pilot in 2026.",
        "source_file": "doc.pdf",
        "section": None,
        "page": 1,
        "reason_used": "objective",
    },
]


async def _run(entrypoint, snippets):
    _RECORDER.reset()
    result = await entrypoint(
        project_title=PROJECT_TITLE,
        project_details=PROJECT_DETAILS,
        sections_to_generate=SECTIONS,
        source_text_snippets=snippets,
    )
    # Snapshot recorded calls (sort by section so async ordering doesn't matter).
    drafts = sorted(
        _RECORDER.draft_calls,
        key=lambda c: c[0][0] if c[0] else c[1].get("section_name", ""),
    )
    reviews = sorted(
        _RECORDER.review_calls,
        key=lambda c: c[0][0] if c[0] else c[1].get("section_name", ""),
    )
    coh = list(_RECORDER.coherence_calls)
    return result, drafts, reviews, coh


# ── Tests ────────────────────────────────────────────────────────────────────

def test_parallel_byte_equal() -> None:
    print("generate_sections_content_parallel — drafter args byte-equal with/without snippets")
    none_result, none_drafts, _, none_coh = asyncio.run(
        _run(supervisor.generate_sections_content_parallel, None)
    )
    snip_result, snip_drafts, _, snip_coh = asyncio.run(
        _run(supervisor.generate_sections_content_parallel, SNIPPETS)
    )
    _check("draft_section call count identical",
           len(none_drafts) == len(snip_drafts) == len(SECTIONS),
           f"{len(none_drafts)} vs {len(snip_drafts)}")
    _check("draft_section positional args identical",
           [c[0] for c in none_drafts] == [c[0] for c in snip_drafts])
    _check("draft_section kwargs identical",
           [c[1] for c in none_drafts] == [c[1] for c in snip_drafts])
    _check("no draft_section kwarg mentions source_text_snippets",
           all("source_text_snippets" not in c[1] for c in snip_drafts))
    _check("coherence reviewer args identical",
           none_coh == snip_coh)
    _check("returned content identical",
           none_result == snip_result)


def test_sequential_byte_equal() -> None:
    print("generate_sections_content — drafter+reviewer args byte-equal with/without snippets")
    none_result, none_drafts, none_reviews, _ = asyncio.run(
        _run(supervisor.generate_sections_content, None)
    )
    snip_result, snip_drafts, snip_reviews, _ = asyncio.run(
        _run(supervisor.generate_sections_content, SNIPPETS)
    )
    _check("draft_section positional args identical",
           [c[0] for c in none_drafts] == [c[0] for c in snip_drafts])
    _check("draft_section kwargs identical",
           [c[1] for c in none_drafts] == [c[1] for c in snip_drafts])
    _check("review_section positional args identical",
           [c[0] for c in none_reviews] == [c[0] for c in snip_reviews])
    _check("review_section kwargs identical",
           [c[1] for c in none_reviews] == [c[1] for c in snip_reviews])
    _check("no draft_section kwarg mentions source_text_snippets",
           all("source_text_snippets" not in c[1] for c in snip_drafts))
    _check("no review_section kwarg mentions source_text_snippets",
           all("source_text_snippets" not in c[1] for c in snip_reviews))
    _check("returned content identical",
           none_result == snip_result)


def test_signature_accepts_field() -> None:
    print("supervisor signatures accept source_text_snippets")
    import inspect

    sig_par = inspect.signature(supervisor.generate_sections_content_parallel)
    sig_seq = inspect.signature(supervisor.generate_sections_content)
    _check("parallel entrypoint has source_text_snippets",
           "source_text_snippets" in sig_par.parameters)
    _check("sequential entrypoint has source_text_snippets",
           "source_text_snippets" in sig_seq.parameters)
    _check("default is None (parallel)",
           sig_par.parameters["source_text_snippets"].default is None)
    _check("default is None (sequential)",
           sig_seq.parameters["source_text_snippets"].default is None)


def test_pydantic_models() -> None:
    print("Pydantic models accept and validate source_text_snippets")
    from api.main import ProjectInput
    from api.streaming_generation import StreamingProjectInput

    pi = ProjectInput(
        project_title="t", project_details="d", user_instructions="u",
        sections=["Executive Summary"],
        source_text_snippets=[{
            "text": "x", "source_file": "f.pdf",
            "page": 1, "reason_used": "r",
        }],
    )
    _check("ProjectInput stores snippet",
           len(pi.source_text_snippets or []) == 1)
    _check("ProjectInput defaults to None",
           ProjectInput(project_title="t", project_details="d",
                        user_instructions="u", sections=["X"]
                        ).source_text_snippets is None)

    sp = StreamingProjectInput(
        project_title="t", project_details="d",
        sections=["Executive Summary"],
        source_text_snippets=[{
            "text": "x", "source_file": "f.pdf",
            "reason_used": "r",
        }],
    )
    _check("StreamingProjectInput stores snippet",
           len(sp.source_text_snippets or []) == 1)
    _check("StreamingProjectInput defaults to None",
           StreamingProjectInput(project_title="t", project_details="d",
                                 sections=["X"]
                                 ).source_text_snippets is None)


def test_persistence_dict_excludes_snippets() -> None:
    """Static-source check: the auto-save block in api/main.py never mentions
    source_text_snippets inside the paper_data dict that gets json.dump'd."""
    print("auto-save block does not include source_text_snippets")
    main_path = Path(__file__).parent.parent / "api" / "main.py"
    src = main_path.read_text(encoding="utf-8")
    # Locate the paper_data dict and the json.dump call that follows.
    start = src.find("paper_data = {")
    dump_idx = src.find("json.dump(paper_data", start)
    _check("paper_data dict exists", start != -1)
    _check("json.dump call exists", dump_idx != -1)
    block = src[start:dump_idx]
    _check("source_text_snippets absent from paper_data block",
           "source_text_snippets" not in block,
           "found mention inside paper_data block")


def main() -> int:
    _install_patches()
    test_signature_accepts_field()
    test_pydantic_models()
    test_parallel_byte_equal()
    test_sequential_byte_equal()
    test_persistence_dict_excludes_snippets()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
