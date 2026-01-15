"""
Story Canonical Key Extractor

Extracts canonical key dimensions from generated story text using LLM analysis.
This generates a story-specific canonical_core that reflects what was actually
written, independent of the template's predefined canonical_core.

Part of Issue #19: Generate Canonical Key for story outputs.
"""

import json
import logging
import os
from typing import Dict, Any, Optional, List

from src.research.executor.canonical_collapse import (
    collapse_canonical_affinity,
    validate_canonical_core,
    VALID_SETTINGS,
    VALID_PRIMARY_FEARS,
    VALID_ANTAGONISTS,
    VALID_MECHANISMS,
    VALID_TWISTS,
)

logger = logging.getLogger(__name__)

# Environment configuration
ENABLE_STORY_CK_EXTRACTION = os.getenv("ENABLE_STORY_CK_EXTRACTION", "true").lower() == "true"
STORY_CK_MODEL = os.getenv("STORY_CK_MODEL", None)  # None = use same model as story generation

# Enforcement policy configuration (Issue #20)
# Policy levels: none, warn, retry, strict
STORY_CK_ENFORCEMENT = os.getenv("STORY_CK_ENFORCEMENT", "warn").lower()
STORY_CK_MIN_ALIGNMENT = float(os.getenv("STORY_CK_MIN_ALIGNMENT", "0.6"))  # 60% minimum alignment

# Valid enforcement policy values
VALID_ENFORCEMENT_POLICIES = ["none", "warn", "retry", "strict"]


# Prompt template for canonical key extraction
EXTRACTION_SYSTEM_PROMPT = """You are a horror story analyst. Your task is to analyze a horror story and identify its structural canonical dimensions.

Analyze the story and output ONLY a valid JSON object with this structure:
{
  "canonical_affinity": {
    "setting": ["one or more of: apartment, hospital, rural, domestic_space, digital, liminal, infrastructure, body, abstract"],
    "primary_fear": ["one or more of: loss_of_autonomy, identity_erasure, social_displacement, contamination, isolation, annihilation"],
    "antagonist": ["one or more of: ghost, system, technology, body, collective, unknown"],
    "mechanism": ["one or more of: surveillance, possession, debt, infection, impersonation, confinement, erosion, exploitation"],
    "twist": ["one or more of: revelation, inevitability, inversion, circularity, self_is_monster, ambiguity"]
  },
  "analysis_notes": "Brief explanation of your choices (1-2 sentences)"
}

Dimension Definitions:
- setting: WHERE the horror occurs (physical/conceptual space)
- primary_fear: The ULTIMATE fear being exploited (most fundamental terror)
- antagonist: WHAT causes the horror (source of threat)
- mechanism: HOW the horror operates/persists (method of threat)
- twist: The narrative resolution structure

Focus on what is ACTUALLY in the story, not what the story could have been.
Identify the PRIMARY dimension for each category - the most dominant element.
Output ONLY the JSON object, no markdown formatting or additional text."""

EXTRACTION_USER_PROMPT_TEMPLATE = """Analyze this horror story and extract its canonical dimensions:

---
{story_text}
---

Provide your analysis in the required JSON format only."""


def extract_canonical_from_story(
    story_text: str,
    config: Dict[str, Any],
    model_spec: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Extract canonical key dimensions from generated story text.

    Uses LLM to analyze the story and identify the 5 canonical dimensions.
    Returns both the raw affinity (arrays) and collapsed core (single values).

    Args:
        story_text: The generated story text to analyze
        config: Environment config dict (with api_key, model, etc.)
        model_spec: Optional model override (e.g., "ollama:qwen3:30b")

    Returns:
        Dict with:
            - canonical_affinity: Dict[str, List[str]] - raw LLM output
            - canonical_core: Dict[str, str] - collapsed single values
            - analysis_notes: str - LLM's explanation
            - extraction_model: str - model used for extraction
        Or None if extraction fails or is disabled
    """
    if not ENABLE_STORY_CK_EXTRACTION:
        logger.debug("[StoryCK] Story canonical extraction disabled")
        return None

    # Truncate story if too long (keep first 6000 chars for cost efficiency)
    max_story_length = 6000
    truncated = False
    analysis_text = story_text
    if len(story_text) > max_story_length:
        analysis_text = story_text[:max_story_length] + "\n\n[...story truncated for analysis...]"
        truncated = True
        logger.debug(f"[StoryCK] Story truncated from {len(story_text)} to {max_story_length} chars")

    # Build prompts
    user_prompt = EXTRACTION_USER_PROMPT_TEMPLATE.format(story_text=analysis_text)

    # Determine which model to use
    extraction_model = STORY_CK_MODEL or model_spec or config.get("model")

    logger.info(f"[StoryCK] Extracting canonical key using model: {extraction_model}")

    try:
        # Import API client
        from .api_client import call_llm_api, call_claude_api

        # Call appropriate API
        if extraction_model and extraction_model.startswith("ollama:"):
            api_result = call_llm_api(
                EXTRACTION_SYSTEM_PROMPT,
                user_prompt,
                config,
                extraction_model
            )
        else:
            # Use Claude API with lower max_tokens for extraction
            extraction_config = {
                **config,
                "max_tokens": 1024,  # Extraction needs much less tokens
            }
            api_result = call_claude_api(
                EXTRACTION_SYSTEM_PROMPT,
                user_prompt,
                extraction_config
            )

        response_text = api_result.get("story_text", "")

        # Parse JSON response
        result = _parse_extraction_response(response_text)

        if result is None:
            logger.warning("[StoryCK] Failed to parse extraction response")
            return None

        # Add metadata
        result["extraction_model"] = extraction_model
        result["story_truncated"] = truncated

        logger.info(f"[StoryCK] Extraction complete: {result.get('canonical_core', {})}")
        return result

    except Exception as e:
        logger.warning(f"[StoryCK] Extraction failed: {e}")
        return None


def _parse_extraction_response(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse the LLM response and extract canonical affinity.

    Args:
        response_text: Raw LLM response text

    Returns:
        Parsed result dict or None if parsing fails
    """
    # Try to extract JSON from response
    json_str = response_text.strip()

    # Handle markdown code blocks
    if "```json" in json_str:
        start = json_str.find("```json") + 7
        end = json_str.find("```", start)
        json_str = json_str[start:end].strip()
    elif "```" in json_str:
        start = json_str.find("```") + 3
        end = json_str.find("```", start)
        json_str = json_str[start:end].strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"[StoryCK] JSON parse error: {e}")
        logger.debug(f"[StoryCK] Response was: {response_text[:500]}")
        return None

    # Extract canonical_affinity
    affinity = data.get("canonical_affinity", {})
    if not affinity:
        logger.warning("[StoryCK] No canonical_affinity in response")
        return None

    # Validate affinity structure
    if not _validate_affinity_structure(affinity):
        logger.warning("[StoryCK] Invalid affinity structure")
        return None

    # Collapse to canonical_core
    canonical_core = collapse_canonical_affinity(affinity)

    # Validate collapsed core
    is_valid, error = validate_canonical_core(canonical_core)
    if not is_valid:
        logger.warning(f"[StoryCK] Invalid canonical_core: {error}")
        # Return anyway with validation flag
        return {
            "canonical_affinity": affinity,
            "canonical_core": canonical_core,
            "analysis_notes": data.get("analysis_notes", ""),
            "validation_error": error,
        }

    return {
        "canonical_affinity": affinity,
        "canonical_core": canonical_core,
        "analysis_notes": data.get("analysis_notes", ""),
    }


def _validate_affinity_structure(affinity: Dict[str, Any]) -> bool:
    """
    Validate that affinity has the expected structure.

    Args:
        affinity: Canonical affinity dict to validate

    Returns:
        True if valid structure, False otherwise
    """
    required_keys = ["setting", "primary_fear", "antagonist", "mechanism"]

    for key in required_keys:
        if key not in affinity:
            logger.debug(f"[StoryCK] Missing required key: {key}")
            return False

        value = affinity[key]
        if not isinstance(value, list):
            logger.debug(f"[StoryCK] Key {key} is not a list: {type(value)}")
            return False

        if len(value) == 0:
            logger.debug(f"[StoryCK] Key {key} is empty")
            return False

    return True


def compare_canonical_cores(
    template_core: Dict[str, str],
    story_core: Dict[str, str]
) -> Dict[str, Any]:
    """
    Compare template's canonical_core with story's extracted canonical_core.

    This helps identify divergence between what was intended (template)
    and what was actually written (story).

    Args:
        template_core: The template's predefined canonical_core
        story_core: The story's extracted canonical_core

    Returns:
        Dict with comparison results:
            - matches: List of matching dimensions
            - divergences: List of divergent dimensions with details
            - match_score: Float 0.0-1.0 indicating alignment
    """
    dimensions = [
        ("setting_archetype", "setting"),
        ("primary_fear", "primary_fear"),
        ("antagonist_archetype", "antagonist"),
        ("threat_mechanism", "mechanism"),
        ("twist_family", "twist"),
    ]

    matches = []
    divergences = []

    for full_key, short_key in dimensions:
        # Handle both key naming conventions
        template_value = template_core.get(full_key) or template_core.get(short_key)
        story_value = story_core.get(full_key) or story_core.get(short_key)

        if template_value == story_value:
            matches.append(full_key)
        else:
            divergences.append({
                "dimension": full_key,
                "template": template_value,
                "story": story_value,
            })

    match_score = len(matches) / len(dimensions) if dimensions else 0.0

    return {
        "matches": matches,
        "divergences": divergences,
        "match_score": match_score,
        "match_count": len(matches),
        "total_dimensions": len(dimensions),
    }


def check_alignment_enforcement(
    comparison: Dict[str, Any],
    policy: Optional[str] = None,
    min_alignment: Optional[float] = None
) -> Dict[str, Any]:
    """
    Check if story-template alignment meets enforcement requirements.

    Part of Issue #20: Enforce Canonical Key constraints on story output.

    Args:
        comparison: Result from compare_canonical_cores()
        policy: Enforcement policy (none/warn/retry/strict). Uses env default if None.
        min_alignment: Minimum alignment score (0.0-1.0). Uses env default if None.

    Returns:
        Dict with enforcement result:
            - passed: bool - Whether alignment meets threshold
            - action: str - Recommended action (accept/warn/retry/reject)
            - reason: str - Human-readable explanation
            - match_score: float - The alignment score
            - threshold: float - The threshold used
    """
    # Use defaults from environment if not specified
    effective_policy = policy or STORY_CK_ENFORCEMENT
    effective_threshold = min_alignment if min_alignment is not None else STORY_CK_MIN_ALIGNMENT

    # Validate policy
    if effective_policy not in VALID_ENFORCEMENT_POLICIES:
        logger.warning(f"[StoryCK] Invalid enforcement policy '{effective_policy}', using 'warn'")
        effective_policy = "warn"

    match_score = comparison.get("match_score", 0.0)
    passed = match_score >= effective_threshold

    # Determine action based on policy and result
    if effective_policy == "none":
        action = "accept"
        reason = "Enforcement disabled"
    elif passed:
        action = "accept"
        reason = f"Alignment {match_score:.0%} meets threshold {effective_threshold:.0%}"
    else:
        # Alignment below threshold - action depends on policy
        if effective_policy == "warn":
            action = "warn"
            reason = f"Alignment {match_score:.0%} below threshold {effective_threshold:.0%} (warning only)"
        elif effective_policy == "retry":
            action = "retry"
            reason = f"Alignment {match_score:.0%} below threshold {effective_threshold:.0%} (retry requested)"
        elif effective_policy == "strict":
            action = "reject"
            reason = f"Alignment {match_score:.0%} below threshold {effective_threshold:.0%} (strict mode)"
        else:
            action = "accept"
            reason = "Unknown policy"

    logger.info(f"[StoryCK][Enforcement] Policy={effective_policy}, Score={match_score:.0%}, "
                f"Threshold={effective_threshold:.0%}, Action={action}")

    return {
        "passed": passed,
        "action": action,
        "reason": reason,
        "match_score": match_score,
        "threshold": effective_threshold,
        "policy": effective_policy,
        "divergences": comparison.get("divergences", []),
    }


def should_retry_for_alignment(enforcement_result: Dict[str, Any]) -> bool:
    """
    Determine if story should be retried based on alignment enforcement.

    Args:
        enforcement_result: Result from check_alignment_enforcement()

    Returns:
        True if retry is recommended, False otherwise
    """
    return enforcement_result.get("action") == "retry"


def should_reject_for_alignment(enforcement_result: Dict[str, Any]) -> bool:
    """
    Determine if story should be rejected based on alignment enforcement.

    Args:
        enforcement_result: Result from check_alignment_enforcement()

    Returns:
        True if rejection is recommended, False otherwise
    """
    return enforcement_result.get("action") == "reject"
