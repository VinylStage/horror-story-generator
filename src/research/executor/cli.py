"""
CLI entry point for Research Executor.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import (
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    DEFAULT_OUTPUT_DIR,
    LOG_DIR,
    MIN_TOPIC_LENGTH,
    MAX_TOPIC_LENGTH,
    EXIT_SUCCESS,
    EXIT_INVALID_INPUT,
    EXIT_OLLAMA_NOT_RUNNING,
    EXIT_MODEL_NOT_FOUND,
    EXIT_TIMEOUT,
    EXIT_DISK_ERROR,
)
from .executor import (
    check_ollama_available,
    check_model_available,
    execute_research,
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)
from .validator import process_llm_response
from .output_writer import (
    generate_card_id,
    write_output,
    update_last_run,
)
from .prompt_template import get_prompt_for_display


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging for CLI execution.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Create log directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Daily log file
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"research_{today}.log"

    # Configure handlers
    handlers = [
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
    )


def validate_topic(topic: str) -> Optional[str]:
    """
    Validate topic string.

    Args:
        topic: Raw topic input

    Returns:
        Error message if invalid, None if valid
    """
    if not topic or not topic.strip():
        return "Topic cannot be empty"

    topic = topic.strip()

    if len(topic) < MIN_TOPIC_LENGTH:
        return f"Topic too short (min {MIN_TOPIC_LENGTH} chars)"

    if len(topic) > MAX_TOPIC_LENGTH:
        return f"Topic too long (max {MAX_TOPIC_LENGTH} chars)"

    return None


def cmd_run(args: argparse.Namespace) -> int:
    """
    Execute research command.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    logger = logging.getLogger(__name__)

    topic = args.topic.strip()
    model = args.model
    tags = args.tags if args.tags else []
    dry_run = args.dry_run
    skip_markdown = args.skip_markdown
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR

    # Validate topic
    error = validate_topic(topic)
    if error:
        logger.error(f"[ResearchExec] Invalid topic: {error}")
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    logger.info(f"[ResearchExec] === Research Execution Started ===")
    logger.info(f"[ResearchExec] Topic: \"{topic}\"")
    logger.info(f"[ResearchExec] Model: {model}")
    logger.info(f"[ResearchExec] Tags: {tags}")

    # Dry run mode
    if dry_run:
        print("=== DRY RUN MODE ===")
        print()
        print(get_prompt_for_display(topic))
        print("=== END DRY RUN ===")
        return EXIT_SUCCESS

    # Preflight checks
    logger.info("[ResearchExec] Running preflight checks...")

    if not check_ollama_available():
        logger.error("[ResearchExec] Ollama server is not running")
        print("Error: Ollama server is not running at localhost:11434", file=sys.stderr)
        print("Start Ollama with: ollama serve", file=sys.stderr)
        return EXIT_OLLAMA_NOT_RUNNING

    if not check_model_available(model):
        logger.error(f"[ResearchExec] Model not found: {model}")
        print(f"Error: Model '{model}' is not available", file=sys.stderr)
        print(f"Pull the model with: ollama pull {model}", file=sys.stderr)
        return EXIT_MODEL_NOT_FOUND

    logger.info("[ResearchExec] Preflight checks passed")

    # Execute research
    try:
        raw_response, metadata = execute_research(
            topic=topic,
            model=model,
            timeout=args.timeout
        )
    except OllamaConnectionError as e:
        logger.error(f"[ResearchExec] Connection error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_OLLAMA_NOT_RUNNING
    except OllamaModelNotFoundError as e:
        logger.error(f"[ResearchExec] Model error: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_MODEL_NOT_FOUND
    except OllamaTimeoutError as e:
        logger.error(f"[ResearchExec] Timeout: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_TIMEOUT

    # Process response
    output, validation = process_llm_response(raw_response)

    logger.info(f"[ResearchExec] Quality: {validation.get('quality_score', 'unknown')}")

    # Generate card ID and write output
    card_id = generate_card_id()

    try:
        paths = write_output(
            card_id=card_id,
            topic=topic,
            tags=tags,
            model=model,
            output=output,
            validation=validation,
            metadata=metadata,
            output_dir=output_dir,
            skip_markdown=skip_markdown
        )
    except IOError as e:
        logger.error(f"[ResearchExec] Disk error: {e}")
        print(f"Error: Failed to write output files: {e}", file=sys.stderr)
        return EXIT_DISK_ERROR

    # Update last run
    update_last_run(card_id, topic, model, output_dir)

    # Print summary
    print(f"Card ID: {card_id}")
    print(f"Title: {output.get('title', 'Untitled')}")
    print(f"Quality: {validation.get('quality_score', 'unknown')}")

    if paths.get("json"):
        print(f"JSON: {paths['json']}")
    if paths.get("md"):
        print(f"Markdown: {paths['md']}")

    logger.info(f"[ResearchExec] === Research Execution Complete ===")

    return EXIT_SUCCESS


def cmd_list(args: argparse.Namespace) -> int:
    """
    List existing research cards.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR

    if not output_dir.exists():
        print("No research cards found (output directory does not exist)")
        return EXIT_SUCCESS

    # Find all JSON files
    json_files = sorted(output_dir.glob("**/*.json"), reverse=True)

    # Filter out hidden files
    json_files = [f for f in json_files if not f.name.startswith(".")]

    if not json_files:
        print("No research cards found")
        return EXIT_SUCCESS

    # Limit output
    limit = args.limit if args.limit else 20
    json_files = json_files[:limit]

    print(f"Recent research cards (showing {len(json_files)}):")
    print()

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            card_id = data.get("card_id", json_path.stem)
            title = data.get("output", {}).get("title", "Untitled")[:50]
            quality = data.get("validation", {}).get("quality_score", "?")
            created = data.get("metadata", {}).get("created_at", "")[:10]

            print(f"  {card_id}  {created}  [{quality}]  {title}")

        except (IOError, json.JSONDecodeError):
            print(f"  {json_path.stem}  [error reading file]")

    return EXIT_SUCCESS


def cmd_dedup(args: argparse.Namespace) -> int:
    """
    Check deduplication status for a research card.

    Phase B+: Uses FAISS for semantic similarity checking.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    logger = logging.getLogger(__name__)
    card_path = Path(args.card)

    if not card_path.exists():
        print(f"Error: Card not found: {card_path}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    try:
        with open(card_path, "r", encoding="utf-8") as f:
            card_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    card_id = card_data.get("card_id", card_path.stem)
    logger.info(f"[Dedup] Checking card: {card_id}")

    try:
        from src.dedup.research import check_duplicate, DedupResult
        result = check_duplicate(card_data, model=args.model)

        print(f"Card: {card_id}")
        print()
        print("Deduplication Check:")
        print(f"  similarity_score: {result.similarity_score:.4f}")
        print(f"  nearest_card_id: {result.nearest_card_id or 'None'}")
        print(f"  signal: {result.signal.value}")
        print(f"  is_duplicate: {result.is_duplicate}")

        if result.is_duplicate:
            logger.warning(f"[Dedup] HIGH similarity detected: {result.similarity_score:.4f}")

        return EXIT_SUCCESS

    except ImportError:
        print("Error: research_dedup module not available", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except Exception as e:
        logger.error(f"[Dedup] Check failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT


def cmd_index(args: argparse.Namespace) -> int:
    """
    Add research card(s) to FAISS index or rebuild index.

    Phase B+: Manages vector index for deduplication.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    logger = logging.getLogger(__name__)

    try:
        from src.dedup.research import add_card_to_index, get_dedup_signal
        from src.dedup.research.index import get_index, is_faiss_available

        if not is_faiss_available():
            print("Error: FAISS not available", file=sys.stderr)
            return EXIT_INVALID_INPUT

        index = get_index()

        if args.rebuild:
            # Rebuild index from all cards
            logger.info("[Index] Rebuilding index from all cards...")

            from src.infra.data_paths import find_all_research_cards
            card_paths = find_all_research_cards()

            if not card_paths:
                print("No research cards found to index")
                return EXIT_SUCCESS

            added = 0
            for card_path in card_paths:
                try:
                    with open(card_path, "r", encoding="utf-8") as f:
                        card_data = json.load(f)

                    card_id = card_data.get("card_id", card_path.stem)

                    if add_card_to_index(card_data, card_id, index=index, save=False):
                        added += 1
                        print(f"  Indexed: {card_id}")

                except Exception as e:
                    logger.warning(f"[Index] Failed to index {card_path}: {e}")

            index.save()
            print(f"\nRebuilt index with {added} cards (total: {index.size})")

        elif args.card:
            # Index single card
            card_path = Path(args.card)

            if not card_path.exists():
                print(f"Error: Card not found: {card_path}", file=sys.stderr)
                return EXIT_INVALID_INPUT

            with open(card_path, "r", encoding="utf-8") as f:
                card_data = json.load(f)

            card_id = card_data.get("card_id", card_path.stem)

            if add_card_to_index(card_data, card_id, index=index):
                print(f"Indexed: {card_id} (total: {index.size})")
            else:
                print(f"Failed to index: {card_id}")
                return EXIT_INVALID_INPUT

        else:
            # Show index status
            print(f"Index Status:")
            print(f"  Total vectors: {index.size}")
            print(f"  FAISS available: {is_faiss_available()}")

        return EXIT_SUCCESS

    except ImportError as e:
        print(f"Error: Required module not available: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except Exception as e:
        logger.error(f"[Index] Operation failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT


def cmd_seed_gen(args: argparse.Namespace) -> int:
    """
    Generate Story Seed from a research card.

    Phase B+: Distills research card into story seed.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    logger = logging.getLogger(__name__)
    card_path = Path(args.card)

    if not card_path.exists():
        print(f"Error: Card not found: {card_path}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    try:
        with open(card_path, "r", encoding="utf-8") as f:
            card_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    card_id = card_data.get("card_id", card_path.stem)
    logger.info(f"[SeedGen] Generating seed from: {card_id}")

    try:
        from src.story.story_seed import generate_and_save_seed
        from src.registry.seed_registry import get_seed_registry

        print(f"Generating seed from: {card_id}")
        print("This may take a moment...")
        print()

        seed = generate_and_save_seed(card_data, card_id, model=args.model)

        if seed:
            # Register in seed registry
            registry = get_seed_registry()
            from src.infra.data_paths import get_seeds_root
            seed_path = get_seeds_root() / f"{seed.seed_id}.json"
            registry.register(seed.seed_id, card_id, str(seed_path))

            print(f"Seed ID: {seed.seed_id}")
            print(f"Source: {seed.source_card_id}")
            print(f"Key Themes: {', '.join(seed.key_themes)}")
            print(f"Atmosphere: {', '.join(seed.atmosphere_tags)}")
            print(f"Hooks: {len(seed.suggested_hooks)}")
            print(f"Cultural Elements: {len(seed.cultural_elements)}")
            return EXIT_SUCCESS
        else:
            print("Failed to generate seed")
            return EXIT_INVALID_INPUT

    except ImportError as e:
        print(f"Error: Required module not available: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except Exception as e:
        logger.error(f"[SeedGen] Generation failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT


def cmd_seed_list(args: argparse.Namespace) -> int:
    """
    List available Story Seeds.

    Phase B+: Shows registered seeds and their usage.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    try:
        from src.registry.seed_registry import get_seed_registry
        from src.story.story_seed import list_seeds

        registry = get_seed_registry()
        stats = registry.get_stats()

        print("Story Seeds Status:")
        print(f"  Total: {stats.get('total', 0)}")
        print(f"  Available: {stats.get('available', 0)}")
        print(f"  Total Uses: {stats.get('total_uses', 0)}")
        print(f"  Never Used: {stats.get('never_used', 0)}")
        print()

        # List seeds
        seeds = registry.list_all(limit=args.limit)

        if not seeds:
            # Try filesystem fallback
            seed_files = list_seeds()
            if seed_files:
                print(f"Seed Files (not in registry): {len(seed_files)}")
                for sf in seed_files[:args.limit]:
                    print(f"  {sf.stem}")
            else:
                print("No seeds found")
            return EXIT_SUCCESS

        print(f"Recent Seeds (showing {len(seeds)}):")
        print()

        for record in seeds:
            used_str = f"used {record.times_used}x" if record.times_used else "never used"
            avail_str = "✓" if record.is_available else "✗"
            print(f"  {avail_str} {record.seed_id}  from {record.source_card_id}  ({used_str})")

        return EXIT_SUCCESS

    except ImportError as e:
        print(f"Error: Required module not available: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT


def cmd_validate(args: argparse.Namespace) -> int:
    """
    Validate an existing research card.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    card_path = Path(args.card)

    if not card_path.exists():
        print(f"Error: Card not found: {card_path}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    try:
        with open(card_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    # Display validation info
    card_id = data.get("card_id", "unknown")
    validation = data.get("validation", {})

    print(f"Card: {card_id}")
    print()
    print("Validation Results:")
    print(f"  has_title: {validation.get('has_title', False)}")
    print(f"  has_summary: {validation.get('has_summary', False)}")
    print(f"  has_concepts: {validation.get('has_concepts', False)}")
    print(f"  has_applications: {validation.get('has_applications', False)}")
    print(f"  canonical_parsed: {validation.get('canonical_parsed', False)}")
    print(f"  quality_score: {validation.get('quality_score', 'unknown')}")

    if validation.get("parse_error"):
        print(f"  parse_error: {validation['parse_error']}")

    return EXIT_SUCCESS


def create_parser() -> argparse.ArgumentParser:
    """
    Create argument parser.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="research-executor",
        description="Research Executor - Generate horror research cards using local LLM",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Execute research on a topic")
    run_parser.add_argument(
        "topic",
        help="Research topic to analyze"
    )
    run_parser.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL})"
    )
    run_parser.add_argument(
        "-t", "--tags",
        nargs="*",
        default=[],
        help="Tags to attach to the research card"
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})"
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show prompt without executing"
    )
    run_parser.add_argument(
        "--skip-markdown",
        action="store_true",
        help="Skip generating markdown file"
    )
    run_parser.add_argument(
        "-o", "--output-dir",
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )

    # list command
    list_parser = subparsers.add_parser("list", help="List existing research cards")
    list_parser.add_argument(
        "-n", "--limit",
        type=int,
        default=20,
        help="Maximum number of cards to show (default: 20)"
    )
    list_parser.add_argument(
        "-o", "--output-dir",
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a research card")
    validate_parser.add_argument(
        "card",
        help="Path to research card JSON file"
    )

    # Phase B+: dedup command
    dedup_parser = subparsers.add_parser("dedup", help="Check deduplication for a research card")
    dedup_parser.add_argument(
        "card",
        help="Path to research card JSON file"
    )
    dedup_parser.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model for embeddings (default: {DEFAULT_MODEL})"
    )

    # Phase B+: index command
    index_parser = subparsers.add_parser("index", help="Manage FAISS vector index")
    index_parser.add_argument(
        "-c", "--card",
        help="Path to research card to index"
    )
    index_parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild entire index from all cards"
    )

    # Phase B+: seed-gen command
    seed_gen_parser = subparsers.add_parser("seed-gen", help="Generate Story Seed from research card")
    seed_gen_parser.add_argument(
        "card",
        help="Path to research card JSON file"
    )
    seed_gen_parser.add_argument(
        "-m", "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model to use (default: {DEFAULT_MODEL})"
    )

    # Phase B+: seed-list command
    seed_list_parser = subparsers.add_parser("seed-list", help="List available Story Seeds")
    seed_list_parser.add_argument(
        "-n", "--limit",
        type=int,
        default=20,
        help="Maximum number of seeds to show (default: 20)"
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point.

    Args:
        argv: Command line arguments (default: sys.argv[1:])

    Returns:
        Exit code
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Setup logging
    setup_logging(verbose=args.verbose)

    # Dispatch command
    if args.command == "run":
        return cmd_run(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "dedup":
        return cmd_dedup(args)
    elif args.command == "index":
        return cmd_index(args)
    elif args.command == "seed-gen":
        return cmd_seed_gen(args)
    elif args.command == "seed-list":
        return cmd_seed_list(args)
    else:
        parser.print_help()
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
