"""Test script for agent-level progress tracking and audit trail."""

import asyncio
import uuid
import json
from datetime import datetime
from pathlib import Path

# Import agent components
from agents.supervisor import generate_sections_content
from agents.event_collector import event_collector
from tools.knowledge_base import kb

# KB paths
KB_DIR = Path(__file__).parent / "data" / "kb"
KB_MANIFEST_PATH = KB_DIR / "kb_manifest.json"


def get_kb_status():
    """Get KB status for testing."""
    kb_status = {
        "ready": False,
        "guidelines_count": 0,
        "past_papers_count": 0,
        "last_indexed_at": None
    }

    try:
        if KB_MANIFEST_PATH.exists():
            with KB_MANIFEST_PATH.open("r", encoding="utf-8") as f:
                manifest = json.load(f)
                kb_status["last_indexed_at"] = manifest.get("last_indexed_at")

        kb_guidelines_dir = KB_DIR / "guidelines"
        kb_past_papers_dir = KB_DIR / "past_papers"

        if kb_guidelines_dir.exists():
            guidelines_files = [f for f in kb_guidelines_dir.iterdir() if f.is_file() and not f.name.startswith('.')]
            kb_status["guidelines_count"] = len(guidelines_files)

        if kb_past_papers_dir.exists():
            past_papers_files = [f for f in kb_past_papers_dir.iterdir() if f.is_file() and not f.name.startswith('.')]
            kb_status["past_papers_count"] = len(past_papers_files)

        kb_status["ready"] = kb_status["guidelines_count"] > 0 or kb_status["past_papers_count"] > 0
    except:
        pass

    return kb_status


async def test_agent_tracking():
    """Test complete agent tracking flow."""

    print("=" * 70)
    print("🧪 Testing Agent-Level Progress Tracking & Audit Trail")
    print("=" * 70)
    print()

    # Test data
    project_title = "AI Traffic Management System"
    project_details = """
Project: AI-powered Traffic Light Control for Orchard Road
Purpose: Reduce congestion and improve traffic flow using adaptive AI
Development Cost: S$12M (Hardware: S$8M, Software: S$3M, Fees: S$1M)
Annual Cost: S$800K (Maintenance: S$500K, Operations: S$300K)
Benefits:
- Reduce average wait time by 30% (from 90s to 60s)
- Decrease CO2 emissions by 15%
- Improve emergency vehicle response by 20%
Timeline: 18 months (6 months design + 12 months implementation)
"""
    sections = ["Executive Summary"]  # Test with 1 section for speed

    # Create session
    session_id = str(uuid.uuid4())[:8]
    paper_id = "test-paper-001"
    kb_status = get_kb_status()

    print(f"📝 Session ID: {session_id}")
    print(f"📋 Paper ID: {paper_id}")
    print(f"📚 KB Status: {kb_status}")
    print(f"🎯 Sections to generate: {sections}")
    print()

    # Start session tracking
    print("▶️  Starting session tracking...")
    session = event_collector.start_session(
        session_id, paper_id, project_title, sections, kb_status
    )
    print(f"✅ Session started at: {session.started_at.isoformat()}")
    print()

    # Generate content with tracking
    print("🤖 Starting agent generation (Drafter → Reviewer)...")
    print("-" * 70)

    start_time = datetime.now()

    try:
        result = await generate_sections_content(
            project_title=project_title,
            project_details=project_details,
            sections_to_generate=sections,
            session_id=session_id  # Pass session ID for tracking
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print("-" * 70)
        print(f"✅ Generation completed in {duration:.1f} seconds")
        print()

        # Mark session complete
        event_collector.complete_session(session_id, "complete")

    except Exception as e:
        print(f"❌ Generation failed: {e}")
        event_collector.complete_session(session_id, "error")
        return

    # Retrieve session summary
    print("=" * 70)
    print("📊 SESSION SUMMARY")
    print("=" * 70)

    summary = event_collector.get_session_summary(session_id)

    print(f"Session ID: {summary['session_id']}")
    print(f"Paper ID: {summary['paper_id']}")
    print(f"Project: {summary['project_title']}")
    print(f"Status: {summary['status']}")
    print(f"Duration: {summary['total_duration_seconds']:.1f}s")
    print(f"Total Events: {summary['total_events']}")
    print()

    # Show section progress
    print("=" * 70)
    print("📝 SECTION PROGRESS")
    print("=" * 70)

    for section_name, progress in summary['section_progress'].items():
        print(f"\n📄 {section_name}")
        print(f"   Status: {progress['status']}")
        print(f"   Duration: {progress['duration_seconds']:.1f}s" if progress['duration_seconds'] else "   Duration: N/A")

        if progress['draft_preview']:
            print(f"   Draft preview: {progress['draft_preview'][:100]}...")

        if progress['final_preview']:
            print(f"   Final preview: {progress['final_preview'][:100]}...")

    print()

    # Show detailed audit trail
    print("=" * 70)
    print("🔍 DETAILED AUDIT TRAIL")
    print("=" * 70)

    session_obj = event_collector.get_session(session_id)

    for section_name, progress_obj in session_obj.section_progress.items():
        print(f"\n📄 {section_name} - Event Timeline:")
        print(f"   Total events: {len(progress_obj.events)}")
        print()

        for event in progress_obj.events:
            timestamp = event.timestamp.strftime("%H:%M:%S.%f")[:-3]
            print(f"   [{timestamp}] {event.event_type.value.upper()}")
            print(f"      Agent: {event.agent_type.value}")

            if event.tool_name:
                print(f"      Tool: {event.tool_name}")
                if event.tool_args and 'query' in event.tool_args:
                    print(f"      Query: {event.tool_args['query'][:80]}...")

            if event.tool_result:
                print(f"      Result: {event.tool_result[:100]}...")

            if event.content:
                print(f"      Content preview: {event.content[:80]}...")

            print()

    # Show final generated content
    print("=" * 70)
    print("📄 GENERATED CONTENT")
    print("=" * 70)

    for section_name, content in result.items():
        print(f"\n{section_name}:")
        print("-" * 70)
        print(content[:500] + "..." if len(content) > 500 else content)
        print(f"\n[Full length: {len(content)} characters]")

    print()
    print("=" * 70)
    print("✅ Test completed successfully!")
    print("=" * 70)
    print()
    print("💡 Key Features Demonstrated:")
    print("   ✓ Total generation time tracking")
    print("   ✓ Agent-level visibility (Drafter → Reviewer)")
    print("   ✓ Draft and final content previews")
    print("   ✓ Complete audit trail with timestamps")
    print("   ✓ Error detection capability")
    print()
    print("📝 Session will be auto-cleaned after 7 days")
    print()


if __name__ == "__main__":
    asyncio.run(test_agent_tracking())
