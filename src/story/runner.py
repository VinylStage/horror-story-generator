"""
Story Runner - Subprocess entry point for scheduler executor.

Replaces the legacy main.py CLI for story generation tasks.
Invoked as: python -m src.story.runner

Supports all scheduler executor params:
  --max-stories, --duration-seconds, --interval-seconds,
  --enable-dedup, --db-path, --load-history, --model,
  --target-length, --topic, --tags, --no-auto-research,
  --research-model, --thumbnail-provider
"""

import argparse
import logging
import os
import signal
import sys
import time
from typing import Dict, Any, Optional

from dotenv import load_dotenv

# Load environment variables before any other project imports
load_dotenv()

from src.story.generator import (
    generate_horror_story,
    generate_with_dedup_control,
    generate_with_topic,
)
from src.infra.logging_config import setup_logging
from src.dedup.similarity import load_past_stories_into_memory
from src.registry.story_registry import init_registry, get_registry, close_registry


# Graceful shutdown flag
shutdown_requested = False

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger = setup_logging(log_level)


def signal_handler(signum, frame):
    """SIGINT / SIGTERM handler - finish current generation then exit."""
    global shutdown_requested
    signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    logger.info(f"\n{'=' * 80}")
    logger.info(f"{signal_name} received - will exit after current task completes")
    logger.info(f"{'=' * 80}")
    shutdown_requested = True


def parse_args():
    """Parse CLI arguments matching scheduler executor params."""
    parser = argparse.ArgumentParser(
        description="Story Runner - subprocess entry point for scheduler",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=None,
        help="Run duration in seconds. If omitted, runs until --max-stories or manual stop.",
    )
    parser.add_argument(
        "--max-stories",
        type=int,
        default=1,
        help="Maximum number of stories to generate. Default=1.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=0,
        help="Delay between story generations in seconds. Default=0.",
    )
    parser.add_argument(
        "--enable-dedup",
        action="store_true",
        default=False,
        help="Enable HIGH-only dedup control via SQLite registry.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="SQLite registry path. Default=./data/story_registry.db",
    )
    parser.add_argument(
        "--load-history",
        type=int,
        default=200,
        help="Number of past stories to load at startup. Default=200.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model selection. Default=Claude Sonnet. Format: 'ollama:llama3', 'ollama:qwen', or Claude model name.",
    )
    parser.add_argument(
        "--target-length",
        type=int,
        default=None,
        help="Target story length in characters. Range 300-10000.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Story topic. When set, uses topic-based generation.",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=None,
        help="Custom tags for the story.",
    )
    parser.add_argument(
        "--auto-research",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Auto-generate research cards (default: True). Use --no-auto-research to disable.",
    )
    parser.add_argument(
        "--research-model",
        type=str,
        default=None,
        help="Model for research generation.",
    )
    parser.add_argument(
        "--thumbnail-provider",
        type=str,
        default=None,
        help="Thumbnail provider. Options: openai_dalle3, stability_ai, flux, local_sd.",
    )
    return parser.parse_args()


def main() -> None:
    """Main execution loop for story generation."""
    global shutdown_requested

    args = parse_args()

    # Set thumbnail provider env if specified
    if args.thumbnail_provider:
        os.environ["THUMBNAIL_PROVIDER"] = args.thumbnail_provider

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize story registry for dedup
    registry = None
    if args.enable_dedup:
        logger.info("Dedup mode enabled")
        registry = init_registry(db_path=args.db_path)

        past_stories = registry.load_recent_accepted(limit=args.load_history)
        if past_stories:
            load_past_stories_into_memory(past_stories)

        counts = registry.get_total_count()
        logger.info(f"Registry: accepted={counts['accepted']}, skipped={counts['skipped']}")

    # Log configuration
    logger.info("=" * 80)
    logger.info("Story Runner started")
    logger.info("=" * 80)
    logger.info(f"  max_stories: {args.max_stories}")
    logger.info(f"  duration_seconds: {args.duration_seconds}")
    logger.info(f"  interval_seconds: {args.interval_seconds}")
    logger.info(f"  enable_dedup: {args.enable_dedup}")
    logger.info(f"  model: {args.model or 'default'}")
    logger.info(f"  target_length: {args.target_length or 'default'}")
    if args.topic:
        logger.info(f"  topic: {args.topic}")
    if args.tags:
        logger.info(f"  tags: {args.tags}")
    if args.research_model:
        logger.info(f"  research_model: {args.research_model}")
    if args.thumbnail_provider:
        logger.info(f"  thumbnail_provider: {args.thumbnail_provider}")
    logger.info("=" * 80)

    # Statistics
    start_time = time.time()
    stories_generated = 0
    stories_skipped = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0

    try:
        while True:
            if shutdown_requested:
                logger.info("Shutdown requested - exiting loop")
                break

            if args.duration_seconds:
                elapsed = time.time() - start_time
                if elapsed >= args.duration_seconds:
                    logger.info(f"Duration limit reached ({elapsed:.1f}s) - exiting loop")
                    break

            if args.max_stories and stories_generated >= args.max_stories:
                logger.info(f"Story limit reached ({stories_generated}) - exiting loop")
                break

            iteration_start = time.time()
            logger.info(f"\n[{stories_generated + 1}] Generating story...")

            # Topic-based generation takes priority
            if args.topic is not None:
                result = generate_with_topic(
                    topic=args.topic,
                    auto_research=args.auto_research,
                    model_spec=args.model,
                    research_model_spec=args.research_model,
                    save_output=True,
                    registry=registry,
                    target_length=args.target_length,
                    custom_tags=args.tags,
                )
            elif args.enable_dedup and registry:
                result = generate_with_dedup_control(
                    registry=registry,
                    model_spec=args.model,
                    target_length=args.target_length,
                )
                if result is None:
                    stories_skipped += 1
                    logger.info(f"SKIP (HIGH similarity) - skipped total: {stories_skipped}")
                    iteration_duration = time.time() - iteration_start
                    logger.info(f"Iteration time: {iteration_duration:.1f}s")
                    continue
            else:
                result = generate_horror_story(
                    model_spec=args.model,
                    target_length=args.target_length,
                )

            # Update statistics
            stories_generated += 1
            if result and "metadata" in result:
                usage = result["metadata"].get("usage")
                if usage:
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)
                    total_tokens += usage.get("total_tokens", 0)

            # Log result summary
            if result and "story" in result:
                logger.info(f"Generated - length: {result['metadata']['word_count']} chars")
                logger.info(f"Saved to: {result.get('file_path', 'N/A')}")
                if result["metadata"].get("usage"):
                    usage = result["metadata"]["usage"]
                    logger.info(
                        f"Tokens: input={usage['input_tokens']}, "
                        f"output={usage['output_tokens']}, "
                        f"total={usage['total_tokens']}"
                    )

                if result["metadata"].get("phase2c_signal"):
                    logger.info(
                        f"Dedup: signal={result['metadata']['phase2c_signal']}, "
                        f"attempt={result['metadata']['phase2c_attempt']}"
                    )

            iteration_duration = time.time() - iteration_start
            logger.info(f"Iteration time: {iteration_duration:.1f}s")

            if shutdown_requested:
                logger.info("Shutdown requested after generation - exiting loop")
                break

            # Wait between generations
            if args.max_stories is None or stories_generated < args.max_stories:
                if args.interval_seconds > 0:
                    logger.info(f"Waiting {args.interval_seconds}s before next generation...")
                    for _ in range(args.interval_seconds):
                        if shutdown_requested:
                            logger.info("Shutdown during wait - exiting loop")
                            break
                        time.sleep(1)
                    if shutdown_requested:
                        break

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt - shutting down")
    except Exception as e:
        logger.error(f"Error during execution: {e}", exc_info=True)
        raise
    finally:
        end_time = time.time()
        total_duration = end_time - start_time

        logger.info("\n" + "=" * 80)
        logger.info("Story Runner - Final Statistics")
        logger.info("=" * 80)
        logger.info(f"Total duration: {total_duration:.1f}s ({total_duration / 3600:.2f}h)")
        logger.info(f"Stories generated: {stories_generated}")
        if args.enable_dedup:
            logger.info(f"Stories skipped: {stories_skipped} (HIGH similarity)")
        if stories_generated > 0:
            logger.info(f"Avg generation time: {total_duration / stories_generated:.1f}s/story")
        logger.info(f"Token usage:")
        logger.info(f"  Input: {total_input_tokens:,}")
        logger.info(f"  Output: {total_output_tokens:,}")
        logger.info(f"  Total: {total_tokens:,}")
        if stories_generated > 0:
            logger.info(f"  Avg: {total_tokens / stories_generated:.0f} tokens/story")
        logger.info("=" * 80)

        if registry:
            close_registry()
            logger.info("Registry connection closed")


if __name__ == "__main__":
    main()
