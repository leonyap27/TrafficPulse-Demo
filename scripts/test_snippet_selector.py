"""FP-129A: Deterministic checks for snippet selection.

No LLM call required — the LLM is mocked. Run from the project root:

    python scripts/test_snippet_selector.py

Exits non-zero on any failed assertion.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.document_extractor import iter_structured_chunks
from tools.snippet_selector import (
    SnippetCaps,
    apply_caps,
    heuristic_snippets,
    select_snippets,
    verify_and_attach_provenance,
)


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


# ── iter_structured_chunks ───────────────────────────────────────────────────

def test_iter_structured_chunks_pdf() -> None:
    print("iter_structured_chunks(pdf)")
    extraction = {
        "file_type": "pdf",
        "file_name": "doc.pdf",
        "text": "ignored",
        "pages": [
            "--- Page 1 ---\nIntroduction line.\nProject objective: enable X.",
            "--- Page 2 ---\nBudget: S$5,000,000 over 3 years.",
        ],
    }
    chunks = iter_structured_chunks(extraction)
    pages = {c["page"] for c in chunks}
    _check("page numbers parsed", pages == {1, 2}, str(pages))
    _check("contains objective line", any("objective" in c["text"] for c in chunks))
    _check("contains budget line", any("Budget" in c["text"] for c in chunks))


def test_iter_structured_chunks_pptx() -> None:
    print("iter_structured_chunks(pptx)")
    extraction = {
        "file_type": "pptx",
        "slides": [
            "--- Slide 1 ---\nTitle slide",
            "--- Slide 2 ---\nKey deliverable: dashboard\nKPI: latency < 1s",
        ],
    }
    chunks = iter_structured_chunks(extraction)
    sections = [c["section"] for c in chunks]
    _check("slide labels assigned", sections == ["Slide 1", "Slide 2"], str(sections))
    _check("page is None for pptx", all(c["page"] is None for c in chunks))


def test_iter_structured_chunks_xlsx() -> None:
    print("iter_structured_chunks(xlsx)")
    extraction = {
        "file_type": "xlsx",
        "sheets": [
            "--- Sheet: Costs ---\nItem | Amount\nLicences | 50000",
            "--- Sheet: Risks ---\nID | Description\nR1 | Vendor delay",
        ],
    }
    chunks = iter_structured_chunks(extraction)
    sheets = sorted({c["section"] for c in chunks})
    _check("sheet names captured", sheets == ["Costs", "Risks"], str(sheets))
    _check("rows split per line", len(chunks) == 4, f"got {len(chunks)}")


def test_iter_structured_chunks_docx_and_txt() -> None:
    print("iter_structured_chunks(docx/txt)")
    docx = {"file_type": "docx", "sections": ["Para one.", "", "Para two."]}
    chunks = iter_structured_chunks(docx)
    _check("docx skips empty paras", len(chunks) == 2 and all(c["page"] is None for c in chunks))

    txt = {"file_type": "txt", "text": "Para one.\n\nPara two.\n\n\nPara three."}
    chunks = iter_structured_chunks(txt)
    _check("txt splits on blank lines", len(chunks) == 3, f"got {len(chunks)}")
    _check("txt section is body", all(c["section"] == "body" for c in chunks))


# ── verify_and_attach_provenance ─────────────────────────────────────────────

def test_verify_attach() -> None:
    print("verify_and_attach_provenance")
    chunks = [
        {"text": "Project objective: enable X.", "section": None, "page": 1},
        {"text": "Budget: S$5,000,000 over 3 years.", "section": None, "page": 2},
    ]
    candidates = [
        {"quote": "Project objective: enable X.", "reason": "states objective"},
        {"quote": "Hallucinated content not in source.", "reason": "fake"},
        {"quote": "  Budget:  S$5,000,000  over 3 years.  ", "reason": "budget"},
    ]
    out = verify_and_attach_provenance(candidates, chunks)
    _check("hallucinated quote dropped", len(out) == 2, f"got {len(out)}")
    by_text = {s["text"][:20] for s in out}
    _check("exact match kept", any(t.startswith("Project objective") for t in by_text))
    _check("whitespace-normalised match kept", any("Budget" in t for t in by_text))
    pages = {s["page"] for s in out}
    _check("provenance attached", pages == {1, 2}, str(pages))


# ── apply_caps ──────────────────────────────────────────────────────────────

def test_apply_caps() -> None:
    print("apply_caps")
    snippets = [
        {"text": "a" * 800, "section": None, "page": None, "reason_used": "r1"},
        {"text": "b" * 200, "section": None, "page": None, "reason_used": "r2"},
        {"text": "c" * 200, "section": None, "page": None, "reason_used": "r3"},
        {"text": "d" * 200, "section": None, "page": None, "reason_used": "r4"},
    ]
    caps = SnippetCaps(max_count=3, max_chars_per=500, max_chars_total=1000)
    out = apply_caps(snippets, caps)
    _check("count cap respected", len(out) <= caps.max_count)
    _check("per-snippet cap respected", all(len(s["text"]) <= caps.max_chars_per for s in out))
    total = sum(len(s["text"]) for s in out)
    _check("total cap respected", total <= caps.max_chars_total, f"total={total}")
    _check("first truncated with ellipsis", out[0]["text"].endswith("…"))


# ── heuristic_snippets ───────────────────────────────────────────────────────

def test_heuristic() -> None:
    print("heuristic_snippets")
    chunks = [
        {"text": "short", "section": None, "page": None},
        {"text": "Generic prose with no signal at all in this sentence." * 2, "section": None, "page": None},
        {"text": "Project objective: deliver dashboard within S$2,000,000 budget by Q4.", "section": None, "page": 3},
    ]
    out = heuristic_snippets(chunks)
    _check("heuristic picks signal-bearing chunks", len(out) >= 1, f"got {len(out)}")
    _check("highest-score first carries provenance", out[0]["page"] == 3)
    _check("reason_used annotated", out[0]["reason_used"].startswith("heuristic_fallback"))


# ── select_snippets (integration with mocked LLM) ────────────────────────────

def test_select_snippets_llm_path() -> None:
    print("select_snippets — LLM path")
    chunks = [
        {"text": "Objective: launch pilot in 2026.", "section": None, "page": 1},
        {"text": "Budget allocation: S$1,200,000.", "section": None, "page": 2},
    ]

    async def fake_llm(_prompt: str) -> str:
        return json.dumps([
            {"quote": "Objective: launch pilot in 2026.", "reason": "objective"},
            {"quote": "INVENTED text not present.", "reason": "fake"},
            {"quote": "Budget allocation: S$1,200,000.", "reason": "budget"},
        ])

    caps = SnippetCaps(max_count=5, max_chars_per=500, max_chars_total=2000)
    out = asyncio.run(select_snippets(
        file_name="doc.pdf",
        full_text="Objective: launch pilot in 2026. Budget allocation: S$1,200,000.",
        structured_chunks=chunks,
        llm_call=fake_llm,
        caps=caps,
    ))
    _check("hallucination dropped, two real snippets kept", len(out) == 2, f"got {len(out)}")
    _check("source_file omitted at this layer", "source_file" not in out[0])


def test_select_snippets_llm_failure_falls_back() -> None:
    print("select_snippets — LLM failure → heuristic")
    chunks = [
        {"text": "Objective: deliver platform with KPI uptime > 99% and S$3,000,000 budget.",
         "section": None, "page": 4},
    ]

    async def boom(_prompt: str) -> str:
        raise RuntimeError("simulated LLM outage")

    caps = SnippetCaps(max_count=3, max_chars_per=500, max_chars_total=1000)
    out = asyncio.run(select_snippets(
        file_name="doc.pdf",
        full_text="Objective: deliver platform with KPI uptime > 99% and S$3,000,000 budget.",
        structured_chunks=chunks,
        llm_call=boom,
        caps=caps,
    ))
    _check("non-empty after fallback", len(out) >= 1)
    _check("fallback reason annotated", out[0]["reason_used"].startswith("heuristic_fallback"))


def test_select_snippets_malformed_json() -> None:
    print("select_snippets — malformed JSON → heuristic")
    chunks = [
        {"text": "Risk: vendor lock-in mitigated via dual-supplier strategy with S$500,000 reserve.",
         "section": "Risks", "page": None},
    ]

    async def garbage(_prompt: str) -> str:
        return "this is not json at all"

    caps = SnippetCaps(max_count=3, max_chars_per=500, max_chars_total=1000)
    out = asyncio.run(select_snippets(
        file_name="doc.pdf",
        full_text=chunks[0]["text"],
        structured_chunks=chunks,
        llm_call=garbage,
        caps=caps,
    ))
    _check("falls back to heuristic on bad JSON", len(out) >= 1)
    _check("fallback section preserved", out[0]["section"] == "Risks")


def test_select_snippets_empty_doc() -> None:
    print("select_snippets — empty doc")
    caps = SnippetCaps(max_count=3, max_chars_per=500, max_chars_total=1000)
    out = asyncio.run(select_snippets(
        file_name="empty.pdf",
        full_text="",
        structured_chunks=[],
        llm_call=None,
        caps=caps,
    ))
    _check("empty input → empty output", out == [])


def main() -> int:
    test_iter_structured_chunks_pdf()
    test_iter_structured_chunks_pptx()
    test_iter_structured_chunks_xlsx()
    test_iter_structured_chunks_docx_and_txt()
    test_verify_attach()
    test_apply_caps()
    test_heuristic()
    test_select_snippets_llm_path()
    test_select_snippets_llm_failure_falls_back()
    test_select_snippets_malformed_json()
    test_select_snippets_empty_doc()
    print(f"\n{PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
