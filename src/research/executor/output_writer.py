"""
Output file writer for research results.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .config import (
    DEFAULT_OUTPUT_DIR,
    CARD_ID_PREFIX,
    SCHEMA_VERSION,
)

logger = logging.getLogger(__name__)


def generate_card_id() -> str:
    """
    Generate a unique card ID based on current timestamp.

    Format: RC-YYYYMMDD-HHMMSS

    Returns:
        Card ID string
    """
    now = datetime.now()
    return f"{CARD_ID_PREFIX}-{now.strftime('%Y%m%d-%H%M%S')}"


def get_output_paths(card_id: str, output_dir: Path) -> Dict[str, Path]:
    """
    Get output file paths for a card ID.

    Args:
        card_id: The card ID (e.g., RC-20260111-143052)
        output_dir: Base output directory

    Returns:
        Dict with 'json' and 'md' paths
    """
    # Extract date from card_id: RC-YYYYMMDD-HHMMSS
    parts = card_id.split("-")
    if len(parts) >= 2:
        date_str = parts[1]
        year = date_str[:4]
        month = date_str[4:6]
    else:
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")

    # Create subdirectory: YYYY/MM/
    subdir = output_dir / year / month
    subdir.mkdir(parents=True, exist_ok=True)

    return {
        "json": subdir / f"{card_id}.json",
        "md": subdir / f"{card_id}.md"
    }


def build_json_output(
    card_id: str,
    topic: str,
    tags: List[str],
    model: str,
    output: Dict[str, Any],
    validation: Dict[str, Any],
    metadata: Dict[str, Any],
    canonical_core: Optional[Dict[str, str]] = None,
    dedup_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build the complete JSON output structure.

    Args:
        card_id: Unique card identifier
        topic: Original research topic
        tags: User-provided tags
        model: LLM model used
        output: Processed LLM output
        validation: Validation results
        metadata: Execution metadata
        canonical_core: Collapsed single-value canonical key (optional)
        dedup_result: Deduplication check result (optional)

    Returns:
        Complete JSON structure for file output
    """
    now = datetime.now()

    # Build metadata section with provider info
    result_metadata = {
        "created_at": now.isoformat(),
        "model": model,
        "generation_time_ms": metadata.get("generation_time_ms", 0),
        "prompt_tokens_est": metadata.get("prompt_tokens_est", 0),
        "output_tokens_est": metadata.get("output_tokens_est", 0),
        "status": metadata.get("status", "unknown")
    }

    # Add provider info (from metadata if available)
    if metadata.get("provider"):
        result_metadata["provider"] = metadata["provider"]

    # Add deep research specific metadata
    if metadata.get("execution_mode") == "deep_research":
        result_metadata["execution_mode"] = "deep_research"
        if metadata.get("interaction_id"):
            result_metadata["interaction_id"] = metadata["interaction_id"]
        if metadata.get("elapsed_seconds"):
            result_metadata["elapsed_seconds"] = metadata["elapsed_seconds"]

    result = {
        "card_id": card_id,
        "version": SCHEMA_VERSION,
        "metadata": result_metadata,
        "input": {
            "topic": topic,
            "tags": tags
        },
        "output": {
            "title": output.get("title", ""),
            "summary": output.get("summary", ""),
            "key_concepts": output.get("key_concepts", []),
            "horror_applications": output.get("horror_applications", []),
            "canonical_affinity": output.get("canonical_affinity", {}),
            "raw_response": output.get("raw_response", "")
        },
        "validation": validation
    }

    # Add canonical_core if provided
    if canonical_core:
        result["canonical_core"] = canonical_core

    # Add dedup metadata if provided
    if dedup_result:
        result["dedup"] = {
            "similarity_score": dedup_result.get("similarity_score", 0.0),
            "level": dedup_result.get("signal", "LOW"),
            "nearest_card_id": dedup_result.get("nearest_card_id"),
        }

    return result


def build_markdown_output(
    card_id: str,
    topic: str,
    tags: List[str],
    model: str,
    output: Dict[str, Any],
    validation: Dict[str, Any],
    metadata: Dict[str, Any]
) -> str:
    """
    Build human-readable Markdown output.

    Args:
        card_id: Unique card identifier
        topic: Original research topic
        tags: User-provided tags
        model: LLM model used
        output: Processed LLM output
        validation: Validation results
        metadata: Execution metadata

    Returns:
        Markdown formatted string
    """
    now = datetime.now()
    title = output.get("title", "Untitled Research")
    status = metadata.get("status", "unknown")
    quality = validation.get("quality_score", "unknown")

    lines = [
        f"# {card_id}: {title}",
        "",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Model:** {model}  ",
        f"**Topic:** {topic}  ",
        f"**Tags:** {', '.join(tags) if tags else 'none'}",
        "",
        "---",
        "",
        "## Summary",
        "",
        output.get("summary", "*No summary available*"),
        "",
    ]

    # Key concepts
    concepts = output.get("key_concepts", [])
    if concepts:
        lines.append("## Key Concepts")
        lines.append("")
        for i, concept in enumerate(concepts, 1):
            lines.append(f"{i}. {concept}")
        lines.append("")

    # Horror applications
    applications = output.get("horror_applications", [])
    if applications:
        lines.append("## Horror Story Applications")
        lines.append("")
        for app in applications:
            lines.append(f"- {app}")
        lines.append("")

    # Canonical affinity
    affinity = output.get("canonical_affinity", {})
    if any(affinity.get(k) for k in ["setting", "primary_fear", "antagonist", "mechanism"]):
        lines.append("## Canonical Affinity")
        lines.append("")
        lines.append("| Dimension | Values |")
        lines.append("|-----------|--------|")

        for dim in ["setting", "primary_fear", "antagonist", "mechanism"]:
            values = affinity.get(dim, [])
            if values:
                lines.append(f"| {dim.replace('_', ' ').title()} | {', '.join(values)} |")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Status: {status} | Quality: {quality}*")

    return "\n".join(lines)


def write_output(
    card_id: str,
    topic: str,
    tags: List[str],
    model: str,
    output: Dict[str, Any],
    validation: Dict[str, Any],
    metadata: Dict[str, Any],
    output_dir: Optional[Path] = None,
    skip_markdown: bool = False,
    canonical_core: Optional[Dict[str, str]] = None,
    dedup_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Optional[Path]]:
    """
    Write output files to disk.

    Args:
        card_id: Unique card identifier
        topic: Original research topic
        tags: User-provided tags
        model: LLM model used
        output: Processed LLM output
        validation: Validation results
        metadata: Execution metadata
        output_dir: Output directory (default: ./data/research)
        skip_markdown: If True, skip .md file generation
        canonical_core: Collapsed single-value canonical key (optional)
        dedup_result: Deduplication check result (optional)

    Returns:
        Dict with paths to written files (None if write failed)
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    output_dir = Path(output_dir)
    paths = get_output_paths(card_id, output_dir)

    result = {"json": None, "md": None}

    # Write JSON
    json_data = build_json_output(
        card_id, topic, tags, model, output, validation, metadata,
        canonical_core=canonical_core,
        dedup_result=dedup_result
    )

    try:
        with open(paths["json"], "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        result["json"] = paths["json"]
        logger.info(f"[ResearchExec] Output: {paths['json']}")
    except IOError as e:
        logger.error(f"[ResearchExec] Failed to write JSON: {e}")

    # Write Markdown
    if not skip_markdown:
        md_content = build_markdown_output(card_id, topic, tags, model, output, validation, metadata)

        try:
            with open(paths["md"], "w", encoding="utf-8") as f:
                f.write(md_content)
            result["md"] = paths["md"]
            logger.info(f"[ResearchExec] Output: {paths['md']}")
        except IOError as e:
            logger.error(f"[ResearchExec] Failed to write Markdown: {e}")

    return result


def update_last_run(card_id: str, topic: str, model: str, output_dir: Optional[Path] = None) -> None:
    """
    Update .last_run metadata file.

    Args:
        card_id: Card ID from this run
        topic: Research topic
        model: Model used
        output_dir: Output directory
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    output_dir = Path(output_dir)
    last_run_path = output_dir / ".last_run"

    # Read existing data
    existing = {}
    if last_run_path.exists():
        try:
            with open(last_run_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (IOError, json.JSONDecodeError):
            pass

    # Get today's date for counting
    today = datetime.now().strftime("%Y-%m-%d")
    if existing.get("last_run_date") == today:
        total_today = existing.get("total_runs_today", 0) + 1
    else:
        total_today = 1

    # Update
    data = {
        "last_card_id": card_id,
        "last_topic": topic,
        "last_model": model,
        "last_run_at": datetime.now().isoformat(),
        "last_run_date": today,
        "total_runs_today": total_today
    }

    try:
        with open(last_run_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning(f"[ResearchExec] Failed to update .last_run: {e}")
