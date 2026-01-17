"""
Research service - business logic for research operations.

Connects to src.research.executor CLI via subprocess.

Phase B+: Integrates with Ollama resource manager for model lifecycle.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

from .ollama_resource import get_resource_manager

logger = logging.getLogger(__name__)

# Path to research_executor module
RESEARCH_EXECUTOR_MODULE = "src.research.executor"


# Default model from config
DEFAULT_MODEL = "qwen3:30b"


async def execute_research(
    topic: str,
    tags: List[str],
    model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute research generation via research_executor CLI.

    Args:
        topic: Research topic
        tags: Optional tags
        model: Model override
        timeout: Timeout override

    Returns:
        Execution result dict with card_id, status, message, output_path
    """
    # Track model usage for resource management
    used_model = model or DEFAULT_MODEL
    resource_manager = get_resource_manager()
    resource_manager.mark_model_used(used_model)

    # Build command
    cmd = [sys.executable, "-m", RESEARCH_EXECUTOR_MODULE, "run", topic]

    if model:
        cmd.extend(["--model", model])

    if tags:
        cmd.extend(["--tags"] + tags)

    if timeout:
        cmd.extend(["--timeout", str(timeout)])

    logger.info(f"[ResearchAPI] Executing: {' '.join(cmd)}")

    try:
        # Run subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout or 300
        )

        stdout_text = stdout.decode("utf-8").strip()
        stderr_text = stderr.decode("utf-8").strip()

        if process.returncode != 0:
            logger.error(f"[ResearchAPI] CLI error: {stderr_text}")
            return {
                "card_id": "",
                "status": "error",
                "message": stderr_text or f"Exit code: {process.returncode}",
                "output_path": None,
            }

        # Parse output (CLI prints "Card ID: RC-XXXXXX-XXXXXX")
        result = parse_cli_output(stdout_text)
        result["status"] = "complete"
        return result

    except asyncio.TimeoutError:
        logger.error(f"[ResearchAPI] Subprocess timeout")
        return {
            "card_id": "",
            "status": "timeout",
            "message": f"Research execution timed out after {timeout}s",
            "output_path": None,
        }
    except Exception as e:
        logger.error(f"[ResearchAPI] Subprocess error: {e}")
        return {
            "card_id": "",
            "status": "error",
            "message": str(e),
            "output_path": None,
        }


def parse_cli_output(output: str) -> Dict[str, Any]:
    """
    Parse CLI output to extract card info.

    Expected format:
        Card ID: RC-YYYYMMDD-HHMMSS
        Title: Some Title
        Quality: good
        JSON: /path/to/file.json
        Markdown: /path/to/file.md
    """
    result = {
        "card_id": "",
        "title": "",
        "quality": "",
        "output_path": None,
        "message": None,
    }

    for line in output.splitlines():
        if line.startswith("Card ID:"):
            result["card_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("Title:"):
            result["title"] = line.split(":", 1)[1].strip()
        elif line.startswith("Quality:"):
            result["quality"] = line.split(":", 1)[1].strip()
        elif line.startswith("JSON:"):
            result["output_path"] = line.split(":", 1)[1].strip()

    return result


async def validate_card(card_id: str) -> Dict[str, Any]:
    """
    Validate a research card via CLI.

    Args:
        card_id: Card ID to validate

    Returns:
        Validation result dict
    """
    # Find the card file
    # Cards are stored in data/research/YYYY/MM/RC-YYYYMMDD-HHMMSS.json
    parts = card_id.split("-")
    if len(parts) >= 2:
        date_str = parts[1]
        year = date_str[:4]
        month = date_str[4:6]
        card_path = Path(f"data/research/{year}/{month}/{card_id}.json")
    else:
        return {
            "card_id": card_id,
            "is_valid": False,
            "quality_score": "invalid_id",
            "message": "Invalid card ID format",
        }

    if not card_path.exists():
        return {
            "card_id": card_id,
            "is_valid": False,
            "quality_score": "not_found",
            "message": f"Card not found: {card_path}",
        }

    cmd = [sys.executable, "-m", RESEARCH_EXECUTOR_MODULE, "validate", str(card_path)]

    logger.info(f"[ResearchAPI] Executing: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )

        stdout_text = stdout.decode("utf-8").strip()

        if process.returncode != 0:
            return {
                "card_id": card_id,
                "is_valid": False,
                "quality_score": "error",
                "message": stderr.decode("utf-8").strip(),
            }

        # Parse validation output
        quality_score = "unknown"
        for line in stdout_text.splitlines():
            if "quality_score:" in line:
                quality_score = line.split(":")[-1].strip()

        return {
            "card_id": card_id,
            "is_valid": True,
            "quality_score": quality_score,
            "message": "Validation passed",
        }

    except Exception as e:
        logger.error(f"[ResearchAPI] Validate error: {e}")
        return {
            "card_id": card_id,
            "is_valid": False,
            "quality_score": "error",
            "message": str(e),
        }


async def list_cards(
    limit: int = 10,
    offset: int = 0,
    quality: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List research cards via CLI.

    Args:
        limit: Max cards to return
        offset: Pagination offset
        quality: Quality filter

    Returns:
        List result dict with cards array
    """
    cmd = [sys.executable, "-m", RESEARCH_EXECUTOR_MODULE, "list", "--limit", str(limit + offset)]

    logger.info(f"[ResearchAPI] Executing: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )

        stdout_text = stdout.decode("utf-8").strip()

        if process.returncode != 0:
            return {
                "cards": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "message": stderr.decode("utf-8").strip(),
            }

        # Parse list output
        cards = parse_list_output(stdout_text, offset, limit, quality)

        return {
            "cards": cards,
            "total": len(cards),
            "limit": limit,
            "offset": offset,
            "message": None,
        }

    except Exception as e:
        logger.error(f"[ResearchAPI] List error: {e}")
        return {
            "cards": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "message": str(e),
        }


def parse_list_output(
    output: str,
    offset: int,
    limit: int,
    quality_filter: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Parse CLI list output.

    Expected format per line:
        RC-YYYYMMDD-HHMMSS  YYYY-MM-DD  [quality]  Title
    """
    cards = []
    lines = output.splitlines()

    for line in lines:
        # Skip header lines
        if not line.strip().startswith("RC-"):
            continue

        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue

        card_id = parts[0]
        created_at = parts[1]
        quality_match = parts[2].strip("[]")
        title = parts[3] if len(parts) > 3 else ""

        # Apply quality filter
        if quality_filter and quality_match != quality_filter:
            continue

        cards.append({
            "card_id": card_id,
            "title": title,
            "topic": "",  # Not available from list output
            "quality_score": quality_match,
            "created_at": created_at,
        })

    # Apply pagination
    return cards[offset:offset + limit]


async def check_semantic_dedup(card_id: str) -> Dict[str, Any]:
    """
    Check semantic duplicates for a research card using FAISS embeddings.

    Args:
        card_id: Card ID to check

    Returns:
        Dedup result dict with signal, similarity_score, similar_cards
    """
    import json as json_module
    from src.dedup.research.dedup import check_duplicate, get_similar_cards
    from src.dedup.research.index import get_index

    # Parse card ID to find file path
    parts = card_id.split("-")
    if len(parts) >= 2:
        date_str = parts[1]
        year = date_str[:4]
        month = date_str[4:6]
        card_path = Path(f"data/research/{year}/{month}/{card_id}.json")
    else:
        return {
            "card_id": card_id,
            "signal": "LOW",
            "similarity_score": 0.0,
            "nearest_card_id": None,
            "similar_cards": [],
            "index_size": 0,
            "message": "Invalid card ID format",
        }

    if not card_path.exists():
        return {
            "card_id": card_id,
            "signal": "LOW",
            "similarity_score": 0.0,
            "nearest_card_id": None,
            "similar_cards": [],
            "index_size": 0,
            "message": f"Card not found: {card_path}",
        }

    try:
        # Load card data
        with open(card_path, "r", encoding="utf-8") as f:
            card_data = json_module.load(f)

        # Get FAISS index
        index = get_index()

        # Check for duplicates
        result = check_duplicate(card_data, index=index)

        # Get similar cards for more detail
        similar = get_similar_cards(card_data, k=5, index=index)

        # Filter out self from similar cards
        similar_cards = [
            {
                "card_id": sim_id,
                "similarity_score": round(sim_score, 4),
                "title": None,  # Would need to load each card to get title
            }
            for sim_id, sim_score in similar
            if sim_id != card_id
        ][:5]

        return {
            "card_id": card_id,
            "signal": result.signal.value,
            "similarity_score": round(result.similarity_score, 4),
            "nearest_card_id": result.nearest_card_id if result.nearest_card_id != card_id else (
                similar_cards[0]["card_id"] if similar_cards else None
            ),
            "similar_cards": similar_cards,
            "index_size": index.size,
            "message": None,
        }

    except Exception as e:
        logger.error(f"[ResearchAPI] Semantic dedup error: {e}")
        return {
            "card_id": card_id,
            "signal": "LOW",
            "similarity_score": 0.0,
            "nearest_card_id": None,
            "similar_cards": [],
            "index_size": 0,
            "message": f"Dedup error: {str(e)}",
        }


# =============================================================================
# Issue #21: Cross-pipeline Canonical Key Matching (Research → Templates)
# =============================================================================


async def get_matching_templates(
    card_id: str,
    max_templates: int = 5,
    min_score: float = 0.5,
) -> Dict[str, Any]:
    """
    Find matching templates for a research card based on canonical affinity.

    Uses reverse direction matching: research card's canonical_affinity
    is matched against each template's canonical_core.

    Args:
        card_id: Research card ID to match
        max_templates: Maximum templates to return
        min_score: Minimum match score threshold

    Returns:
        Dict with matching_templates list and metadata
    """
    from src.infra.research_context.repository import get_card_by_id, get_canonical_affinity
    from src.infra.research_context.selector import select_templates_for_research

    # Load the research card
    card = get_card_by_id(card_id)

    if card is None:
        return {
            "card_id": card_id,
            "matching_templates": [],
            "total_templates": 0,
            "card_affinity": None,
            "message": f"Research card not found: {card_id}",
        }

    # Get card's canonical affinity for response
    card_affinity = get_canonical_affinity(card)

    # Select matching templates
    selection = select_templates_for_research(
        card=card,
        max_templates=max_templates,
        min_score=min_score,
    )

    # Build response
    matching_templates = []
    for i, template in enumerate(selection.templates):
        matching_templates.append({
            "template_id": template.get("template_id", "unknown"),
            "template_name": template.get("template_name", "Unknown"),
            "match_score": round(selection.scores[i], 4),
            "canonical_core": template.get("canonical_core", {}),
            "match_details": selection.match_details[i] if i < len(selection.match_details) else None,
        })

    return {
        "card_id": card_id,
        "matching_templates": matching_templates,
        "total_templates": selection.total_available,
        "card_affinity": card_affinity,
        "message": selection.reason if not selection.has_matches else None,
    }
