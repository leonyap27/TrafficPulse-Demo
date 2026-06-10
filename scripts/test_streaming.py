#!/usr/bin/env python3
"""Test streaming generation endpoint for real-time progress updates."""

import asyncio
import json
import sys
from datetime import datetime


async def test_streaming_generation():
    """Test the streaming endpoint with a simple project."""
    print("🧪 Testing Streaming Generation Endpoint\n")
    print("="*80)

    # Test data
    test_project = {
        "project_title": "Test AI Traffic System",
        "project_details": """
Develop an AI-powered traffic management system to optimize traffic flow
in Singapore's central business district.

Budget: S$10M
Timeline: 18 months
Benefits: 30% reduction in congestion, improved emergency response times
        """.strip(),
        "sections": ["Executive Summary"],
        "user_instructions": "Generate a professional funding paper section",
        "paper_name": "Test Streaming Paper"
    }

    print(f"📝 Test Project: {test_project['project_title']}")
    print(f"📋 Sections: {', '.join(test_project['sections'])}")
    print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}\n")
    print("="*80)
    print()

    try:
        # Import after dependencies are loaded
        from api.streaming_generation import generate_with_progress

        print("🔄 Starting streaming generation...\n")

        # Track progress
        last_progress = 0
        sections_received = []

        # Consume the stream
        async for event in generate_with_progress(
            project_title=test_project["project_title"],
            project_details=test_project["project_details"],
            sections=test_project["sections"]
        ):
            event_type = event.get("event", "unknown")
            event_data = json.loads(event.get("data", "{}"))

            if event_type == "progress":
                progress = event_data.get("progress", 0)
                message = event_data.get("message", "")
                status = event_data.get("status", "")

                # Print progress update
                if progress != last_progress:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"📊 {progress:>3}% | {status:>12} | {message}")
                    last_progress = progress

            elif event_type == "section_complete":
                section_name = event_data.get("section_name", "Unknown")
                content_preview = event_data.get("content", "")[:100]
                full_length = event_data.get("full_length", 0)

                sections_received.append(section_name)
                print(f"\n✅ Section completed: {section_name}")
                print(f"   Length: {full_length} chars")
                print(f"   Preview: {content_preview}...\n")

            elif event_type == "complete":
                sections = event_data.get("sections", {})
                timestamp = event_data.get("timestamp", "")

                print("="*80)
                print(f"✅ GENERATION COMPLETE at {timestamp}")
                print(f"   Total sections: {len(sections)}")
                print(f"   Sections received: {', '.join(sections_received)}")
                print("="*80)

                # Display section summaries
                print("\n📄 Generated Sections:\n")
                for section_name, content in sections.items():
                    print(f"  • {section_name}")
                    print(f"    Length: {len(content)} characters")
                    print(f"    Preview: {content[:150].strip()}...")
                    print()

                return True

            elif event_type == "error":
                error_message = event_data.get("message", "Unknown error")
                error_type = event_data.get("error_type", "Unknown")

                print("="*80)
                print(f"❌ ERROR: {error_type}")
                print(f"   Message: {error_message}")
                print("="*80)
                return False

        print("⚠️  Stream ended without completion event")
        return False

    except Exception as e:
        print("="*80)
        print(f"❌ Test failed with exception:")
        print(f"   {type(e).__name__}: {str(e)}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return False


async def test_kb_availability():
    """Test that KB is loaded and available."""
    print("\n🔍 Checking Knowledge Base Status...\n")

    try:
        from tools.knowledge_base import kb

        # Initialize KB
        kb.initialize_kb()

        # Check guidelines
        if kb.guidelines_store:
            count = kb.guidelines_store._collection.count()
            print(f"✅ Guidelines store: {count} documents indexed")
        else:
            print("⚠️  Guidelines store: Not initialized")

        # Check past papers
        if kb.past_papers_store:
            count = kb.past_papers_store._collection.count()
            print(f"✅ Past papers store: {count} documents indexed")
        else:
            print("⚠️  Past papers store: Not initialized")

        # Test search
        if kb.guidelines_store:
            print("\n🔍 Testing KB search...")
            result = kb.search_guidelines("Executive Summary requirements", k=1)
            print(f"   Search returned: {len(result)} characters")
            print(f"   Preview: {result[:200]}...")

        return True

    except Exception as e:
        print(f"❌ KB check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print(" "*20 + "STREAMING GENERATION TEST")
    print("="*80 + "\n")

    # Test KB first
    kb_ok = asyncio.run(test_kb_availability())

    if not kb_ok:
        print("\n⚠️  WARNING: KB not available. Generation will continue without KB reference.")
        print("   To fix: Sync KB files with `curl -X POST http://localhost:8000/admin/kb/gcs/sync`\n")

    # Run streaming test
    success = asyncio.run(test_streaming_generation())

    # Exit status
    print("\n" + "="*80)
    if success:
        print("✅ TEST PASSED: Streaming generation works!")
        print("="*80 + "\n")
        sys.exit(0)
    else:
        print("❌ TEST FAILED: Check errors above")
        print("="*80 + "\n")
        sys.exit(1)
