#!/usr/bin/env python3
"""Test script to simulate paper generation with mock data."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.supervisor import generate_sections_content

# Mock project data
MOCK_PROJECT = {
    "project_title": "Smart Traffic Light System",
    "project_details": """
    Project: Smart Traffic Light System for Downtown Singapore

    Objective: Implement AI-powered traffic lights to reduce congestion by 30%
    Budget: S$15 million (Year 1: S$10M for development, Year 2-3: S$2.5M each for operations)
    Timeline: 24 months
    Stakeholders: Land Transport Authority, Smart Nation Initiative
    Expected Outcomes:
    - 30% reduction in peak hour congestion
    - 20% improvement in emergency vehicle response times
    - Real-time traffic optimization using ML

    Key Requirements:
    - AI/ML traffic prediction models
    - Integration with existing infrastructure
    - 24/7 monitoring and maintenance
    """,
    "user_instructions": """
    Write in formal ministerial tone suitable for Singapore government.
    Emphasize cost-benefit analysis and alignment with Smart Nation goals.
    Include risk mitigation strategies and sustainability considerations.
    """
}

SECTIONS_TO_GENERATE = [
    "Executive Summary",
    "Project Background",
    "Recommendation"
]

async def test_generation():
    """Test paper generation with mock data."""
    print("=" * 70)
    print("PAPER GENERATION TEST - Mock Data")
    print("=" * 70)

    print(f"\n📋 Project: {MOCK_PROJECT['project_title']}")
    print(f"📝 Generating {len(SECTIONS_TO_GENERATE)} sections...")
    print(f"   Sections: {', '.join(SECTIONS_TO_GENERATE)}\n")

    try:
        print("🚀 Starting generation process...\n")

        # Combine project details with user instructions
        combined_details = f"""{MOCK_PROJECT['project_details']}

USER INSTRUCTIONS:
{MOCK_PROJECT['user_instructions']}"""

        result = await generate_sections_content(
            project_title=MOCK_PROJECT['project_title'],
            project_details=combined_details,
            sections_to_generate=SECTIONS_TO_GENERATE
        )

        print("\n" + "=" * 70)
        print("✅ GENERATION SUCCESSFUL!")
        print("=" * 70)

        # Display results (result is Dict[str, str] where keys are section names)
        for section_name, content in result.items():
            print(f"\n{'─' * 70}")
            print(f"📄 SECTION: {section_name}")
            print(f"{'─' * 70}")
            print(content[:500] + "..." if len(content) > 500 else content)

        print(f"\n{'═' * 70}")
        print(f"✓ Total Sections Generated: {len(result)}")
        print(f"{'═' * 70}\n")

        return True

    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ GENERATION FAILED!")
        print("=" * 70)
        print(f"\n🔴 Error Type: {type(e).__name__}")
        print(f"🔴 Error Message: {str(e)}\n")

        # Print detailed traceback
        import traceback
        print("📍 Full Traceback:")
        print("-" * 70)
        traceback.print_exc()
        print("-" * 70)

        return False

if __name__ == "__main__":
    print("\n🧪 Testing Paper Generation System\n")

    # Run the async test
    success = asyncio.run(test_generation())

    # Exit with appropriate code
    sys.exit(0 if success else 1)
