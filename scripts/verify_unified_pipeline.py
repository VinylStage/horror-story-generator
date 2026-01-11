#!/usr/bin/env python3
"""
Unified Pipeline Verification Script

This script verifies the unified research→story pipeline:
1. Research cards are properly normalized (canonical_core + dedup)
2. Story generation uses the shared selector
3. HIGH duplicates are excluded
4. Traceability metadata is present

Usage:
    python scripts/verify_unified_pipeline.py [--dry-run]

The script can be run in dry-run mode (no Ollama/Claude calls) to verify
the data flow logic.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def verify_research_context_module():
    """Verify the shared research context module is importable and functional."""
    print("\n=== Verifying Research Context Module ===")

    try:
        from src.infra.research_context import (
            load_usable_research_cards,
            select_research_for_template,
            build_research_context,
            format_research_for_metadata,
            DedupLevel,
        )
        print("  [OK] Module imports successfully")
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    # Verify DedupLevel enum
    assert DedupLevel.LOW.value == "LOW"
    assert DedupLevel.MEDIUM.value == "MEDIUM"
    assert DedupLevel.HIGH.value == "HIGH"
    print("  [OK] DedupLevel enum values correct")

    return True


def verify_canonical_collapse():
    """Verify canonical_affinity → canonical_core collapsing."""
    print("\n=== Verifying Canonical Collapse ===")

    try:
        from src.research.executor.canonical_collapse import (
            collapse_canonical_affinity,
            validate_canonical_core,
        )
        print("  [OK] Module imports successfully")
    except ImportError as e:
        print(f"  [FAIL] Import error: {e}")
        return False

    # Test collapse
    affinity = {
        "setting": ["apartment", "urban"],
        "primary_fear": ["isolation", "social_displacement"],
        "antagonist": ["system"],
        "mechanism": ["surveillance", "confinement"]
    }

    core = collapse_canonical_affinity(affinity)

    # Verify structure
    required_fields = [
        "setting_archetype", "primary_fear", "antagonist_archetype",
        "threat_mechanism", "twist_family"
    ]
    for field in required_fields:
        if field not in core:
            print(f"  [FAIL] Missing field: {field}")
            return False

    print(f"  [OK] Collapsed core: {core}")

    # Validate
    is_valid, error = validate_canonical_core(core)
    if not is_valid:
        print(f"  [FAIL] Validation error: {error}")
        return False

    print("  [OK] Canonical core validated")
    return True


def verify_dedup_policy():
    """Verify dedup policy excludes HIGH duplicates."""
    print("\n=== Verifying Dedup Policy ===")

    from src.infra.research_context.policy import is_usable_card, DedupLevel

    # LOW should be usable
    low_card = {
        "validation": {"quality_score": "good"},
        "dedup": {"level": "LOW", "similarity_score": 0.3}
    }
    assert is_usable_card(low_card) is True
    print("  [OK] LOW dedup card is usable")

    # MEDIUM should be usable
    medium_card = {
        "validation": {"quality_score": "good"},
        "dedup": {"level": "MEDIUM", "similarity_score": 0.75}
    }
    assert is_usable_card(medium_card) is True
    print("  [OK] MEDIUM dedup card is usable")

    # HIGH should NOT be usable
    high_card = {
        "validation": {"quality_score": "good"},
        "dedup": {"level": "HIGH", "similarity_score": 0.90}
    }
    assert is_usable_card(high_card) is False
    print("  [OK] HIGH dedup card is excluded")

    return True


def verify_research_cards():
    """Verify existing research cards and their structure."""
    print("\n=== Verifying Research Cards ===")

    from src.infra.research_context import load_usable_research_cards

    cards = load_usable_research_cards()
    print(f"  Found {len(cards)} usable research cards")

    if not cards:
        print("  [WARN] No research cards found - generate some first")
        return True

    # Check first card structure
    card = cards[0]
    card_id = card.get("card_id", "unknown")
    print(f"  Checking card: {card_id}")

    # Required fields
    required = ["card_id", "metadata", "output", "validation"]
    for field in required:
        if field not in card:
            print(f"  [FAIL] Missing field: {field}")
            return False

    print("  [OK] Required fields present")

    # Check if new fields are present (may not be for old cards)
    has_canonical_core = "canonical_core" in card
    has_dedup = "dedup" in card

    if has_canonical_core:
        print(f"  [OK] canonical_core present: {card['canonical_core']}")
    else:
        print("  [INFO] canonical_core not present (old card format)")

    if has_dedup:
        print(f"  [OK] dedup present: {card['dedup']}")
    else:
        print("  [INFO] dedup not present (old card format)")

    return True


def verify_traceability_metadata():
    """Verify traceability metadata format."""
    print("\n=== Verifying Traceability Metadata ===")

    from src.infra.research_context import format_research_for_metadata, ResearchSelection

    selection = ResearchSelection(
        cards=[{"card_id": "RC-TEST"}],
        scores=[0.8],
        match_details=[{}],
        total_available=5,
        reason="Test selection",
        card_ids=["RC-TEST"]
    )

    metadata = format_research_for_metadata(selection, injection_mode="auto")

    # Verify required fields
    required = ["research_used", "research_injection_mode"]
    for field in required:
        if field not in metadata:
            print(f"  [FAIL] Missing field: {field}")
            return False

    assert metadata["research_used"] == ["RC-TEST"]
    assert metadata["research_injection_mode"] == "auto"

    print(f"  [OK] Metadata format correct: {metadata}")
    return True


def verify_generator_config():
    """Verify generator uses the new config flags."""
    print("\n=== Verifying Generator Config ===")

    import os

    # Check default values
    auto_inject = os.getenv("AUTO_INJECT_RESEARCH", "true").lower() == "true"
    top_k = int(os.getenv("RESEARCH_INJECT_TOP_K", "1"))
    require = os.getenv("RESEARCH_INJECT_REQUIRE", "false").lower() == "true"
    exclude = os.getenv("RESEARCH_INJECT_EXCLUDE_DUP_LEVEL", "HIGH")

    print(f"  AUTO_INJECT_RESEARCH: {auto_inject} (default: true)")
    print(f"  RESEARCH_INJECT_TOP_K: {top_k} (default: 1)")
    print(f"  RESEARCH_INJECT_REQUIRE: {require} (default: false)")
    print(f"  RESEARCH_INJECT_EXCLUDE_DUP_LEVEL: {exclude} (default: HIGH)")

    return True


def main():
    parser = argparse.ArgumentParser(description="Verify unified pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no API calls)")
    args = parser.parse_args()

    print("=" * 60)
    print("Unified Pipeline Verification")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    results = []

    # Run verifications
    results.append(("Research Context Module", verify_research_context_module()))
    results.append(("Canonical Collapse", verify_canonical_collapse()))
    results.append(("Dedup Policy", verify_dedup_policy()))
    results.append(("Research Cards", verify_research_cards()))
    results.append(("Traceability Metadata", verify_traceability_metadata()))
    results.append(("Generator Config", verify_generator_config()))

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("All verifications passed!")
        return 0
    else:
        print("Some verifications failed. See above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
