"""
Validator for LLM research output.
"""

import json
import logging
import re
from typing import Dict, Any, Tuple, Optional

from .config import (
    VALID_SETTINGS,
    VALID_PRIMARY_FEARS,
    VALID_ANTAGONISTS,
    VALID_MECHANISMS,
)

logger = logging.getLogger(__name__)


def extract_json_from_response(raw_response: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Extract JSON object from LLM response.

    The LLM may include markdown formatting or extra text.
    This function attempts to find and parse the JSON object.

    Args:
        raw_response: Raw text from LLM

    Returns:
        Tuple of (parsed_json_or_None, error_message_or_None)
    """
    if not raw_response or not raw_response.strip():
        return None, "Empty response"

    text = raw_response.strip()

    # Try direct parse first
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip()), None
        except json.JSONDecodeError:
            continue

    # Try to find JSON object by braces
    brace_start = text.find("{")
    brace_end = text.rfind("}")

    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        potential_json = text[brace_start:brace_end + 1]
        try:
            return json.loads(potential_json), None
        except json.JSONDecodeError as e:
            return None, f"JSON parse error: {e}"

    return None, "No JSON object found in response"


def validate_research_output(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the structure and content of parsed research output.

    Args:
        parsed: Parsed JSON from LLM response

    Returns:
        Validation result dict with field-level checks
    """
    validation = {
        "has_title": False,
        "has_summary": False,
        "has_concepts": False,
        "has_applications": False,
        "canonical_parsed": False,
        "quality_score": "incomplete"
    }

    # Check required fields
    if "title" in parsed and isinstance(parsed["title"], str) and parsed["title"].strip():
        validation["has_title"] = True

    if "summary" in parsed and isinstance(parsed["summary"], str) and parsed["summary"].strip():
        validation["has_summary"] = True

    if "key_concepts" in parsed and isinstance(parsed["key_concepts"], list) and len(parsed["key_concepts"]) > 0:
        validation["has_concepts"] = True

    if "horror_applications" in parsed and isinstance(parsed["horror_applications"], list) and len(parsed["horror_applications"]) > 0:
        validation["has_applications"] = True

    # Check canonical_affinity
    if "canonical_affinity" in parsed and isinstance(parsed["canonical_affinity"], dict):
        affinity = parsed["canonical_affinity"]
        has_valid_affinity = False

        for key in ["setting", "primary_fear", "antagonist", "mechanism"]:
            if key in affinity and isinstance(affinity[key], list) and len(affinity[key]) > 0:
                has_valid_affinity = True
                break

        validation["canonical_parsed"] = has_valid_affinity

    # Calculate quality score
    checks = [
        validation["has_title"],
        validation["has_summary"],
        validation["has_concepts"],
        validation["has_applications"],
        validation["canonical_parsed"]
    ]

    passed = sum(checks)
    if passed == 5:
        validation["quality_score"] = "good"
    elif passed >= 3:
        validation["quality_score"] = "partial"
    else:
        validation["quality_score"] = "incomplete"

    return validation


def validate_canonical_values(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that canonical affinity values are from allowed sets.

    Args:
        parsed: Parsed JSON from LLM response

    Returns:
        Dict with valid/invalid values per dimension
    """
    result = {
        "setting": {"valid": [], "invalid": []},
        "primary_fear": {"valid": [], "invalid": []},
        "antagonist": {"valid": [], "invalid": []},
        "mechanism": {"valid": [], "invalid": []}
    }

    valid_sets = {
        "setting": set(VALID_SETTINGS),
        "primary_fear": set(VALID_PRIMARY_FEARS),
        "antagonist": set(VALID_ANTAGONISTS),
        "mechanism": set(VALID_MECHANISMS)
    }

    affinity = parsed.get("canonical_affinity", {})

    for dim, valid_set in valid_sets.items():
        values = affinity.get(dim, [])
        if isinstance(values, list):
            for v in values:
                if isinstance(v, str):
                    if v in valid_set:
                        result[dim]["valid"].append(v)
                    else:
                        result[dim]["invalid"].append(v)

    return result


def process_llm_response(raw_response: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Process and validate LLM response.

    This is the main entry point for validation.
    Never raises exceptions - always returns usable results.

    Args:
        raw_response: Raw text from LLM

    Returns:
        Tuple of (output_dict, validation_dict)
        output_dict contains parsed fields or empty defaults
        validation_dict contains validation results
    """
    # Initialize with empty defaults
    output = {
        "title": "",
        "summary": "",
        "key_concepts": [],
        "horror_applications": [],
        "canonical_affinity": {
            "setting": [],
            "primary_fear": [],
            "antagonist": [],
            "mechanism": []
        },
        "raw_response": raw_response
    }

    validation = {
        "has_title": False,
        "has_summary": False,
        "has_concepts": False,
        "has_applications": False,
        "canonical_parsed": False,
        "quality_score": "parse_failed",
        "parse_error": None
    }

    # Try to extract JSON
    parsed, error = extract_json_from_response(raw_response)

    if parsed is None:
        logger.warning(f"[ResearchExec] Failed to parse LLM output: {error}")
        validation["parse_error"] = error
        return output, validation

    # Merge parsed values into output
    if "title" in parsed:
        output["title"] = str(parsed["title"])[:80]  # Enforce max length
    if "summary" in parsed:
        output["summary"] = str(parsed["summary"])
    if "key_concepts" in parsed and isinstance(parsed["key_concepts"], list):
        output["key_concepts"] = [str(c) for c in parsed["key_concepts"][:10]]
    if "horror_applications" in parsed and isinstance(parsed["horror_applications"], list):
        output["horror_applications"] = [str(a) for a in parsed["horror_applications"][:10]]
    if "canonical_affinity" in parsed and isinstance(parsed["canonical_affinity"], dict):
        for key in ["setting", "primary_fear", "antagonist", "mechanism"]:
            if key in parsed["canonical_affinity"] and isinstance(parsed["canonical_affinity"][key], list):
                output["canonical_affinity"][key] = [str(v) for v in parsed["canonical_affinity"][key]]

    # Validate
    validation = validate_research_output(output)
    validation["parse_error"] = None

    logger.info(f"[ResearchExec] Validation: quality={validation['quality_score']}")

    return output, validation
