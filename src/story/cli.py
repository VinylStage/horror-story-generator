"""
Story CLI - Test interface for story generation.

v1.2.0: Adds topic-based generation support.
"""

import argparse
import json
import sys
import logging

from src.infra.logging_config import setup_logging

logger = setup_logging()


def main():
    parser = argparse.ArgumentParser(description="Story Generation CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Generate a story")
    run_parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Story topic. If provided, searches for matching research card."
    )
    run_parser.add_argument(
        "--auto-research",
        action="store_true",
        default=True,
        help="Auto-generate research if no matching card found (default: True)"
    )
    run_parser.add_argument(
        "--no-auto-research",
        action="store_true",
        default=False,
        help="Disable auto-research generation"
    )
    run_parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Story model. Format: 'ollama:llama3', 'ollama:qwen', or Claude model name"
    )
    run_parser.add_argument(
        "--research-model",
        type=str,
        default=None,
        help="Research model for auto-research. Format: 'qwen3:30b', 'gemini', 'deep-research'"
    )
    run_parser.add_argument(
        "--no-save",
        action="store_true",
        default=False,
        help="Do not save story to file"
    )
    run_parser.add_argument(
        "--enable-dedup",
        action="store_true",
        default=False,
        help="Enable story registry dedup control"
    )
    run_parser.add_argument(
        "--target-length",
        type=int,
        default=None,
        help="Target story length in characters (300-5000). Default: ~3000-4000"
    )

    args = parser.parse_args()

    if args.command == "run":
        run_story_generation(args)
    else:
        parser.print_help()
        sys.exit(1)


def run_story_generation(args):
    """Execute story generation based on args."""
    from src.story.generator import generate_with_topic, generate_horror_story
    from src.registry.story_registry import StoryRegistry

    auto_research = args.auto_research and not args.no_auto_research
    save_output = not args.no_save

    # Initialize registry if dedup enabled
    registry = None
    if args.enable_dedup:
        try:
            registry = StoryRegistry()
            logger.info("[CLI] Story registry initialized for dedup")
        except Exception as e:
            logger.warning(f"[CLI] Registry init failed: {e}")

    logger.info("=" * 80)
    logger.info("[CLI] Story Generation Started")
    logger.info(f"[CLI] Topic: {args.topic or '(random)'}")
    logger.info(f"[CLI] Model: {args.model or '(default Claude)'}")
    logger.info(f"[CLI] Auto-research: {auto_research}")
    logger.info(f"[CLI] Save output: {save_output}")
    logger.info(f"[CLI] Target length: {args.target_length or '(default ~3000-4000)'}")
    logger.info("=" * 80)

    # Use topic-based generation if topic provided
    if args.topic:
        result = generate_with_topic(
            topic=args.topic,
            auto_research=auto_research,
            model_spec=args.model,
            research_model_spec=args.research_model,
            save_output=save_output,
            registry=registry,
            target_length=args.target_length
        )
    else:
        # Use standard generation
        result = generate_horror_story(
            save_output=save_output,
            model_spec=args.model,
            target_length=args.target_length
        )
        result["success"] = True

    # Output result summary
    print("\n" + "=" * 80)
    print("RESULT SUMMARY")
    print("=" * 80)

    if result.get("success", True):
        metadata = result.get("metadata", {})
        print(f"Status: SUCCESS")
        print(f"Story ID: {metadata.get('story_id', metadata.get('generated_at', 'N/A')[:15])}")
        print(f"Model: {metadata.get('model', 'N/A')}")
        print(f"Provider: {metadata.get('provider', 'N/A')}")
        print(f"Word Count: {metadata.get('word_count', 'N/A')}")
        print(f"Research Used: {metadata.get('research_used', [])}")
        print(f"Research Mode: {metadata.get('research_injection_mode', 'N/A')}")

        skeleton = metadata.get("skeleton_template", {})
        if skeleton:
            print(f"Template: {skeleton.get('template_id', 'N/A')} - {skeleton.get('template_name', 'N/A')}")
            print(f"Canonical Core: {json.dumps(skeleton.get('canonical_core', {}), ensure_ascii=False)}")

        print(f"Story Signature: {metadata.get('story_signature', 'N/A')[:20]}..." if metadata.get('story_signature') else "Story Signature: N/A")

        if result.get("file_path"):
            print(f"File Path: {result['file_path']}")

        # Output full metadata as JSON
        print("\n--- Full Metadata JSON ---")
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
    else:
        print(f"Status: FAILED")
        print(f"Error: {result.get('error', 'Unknown error')}")

    print("=" * 80)


if __name__ == "__main__":
    main()
