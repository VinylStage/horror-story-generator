"""
Ollama API executor for research generation.
"""

import json
import logging
import socket
import time
from http.client import HTTPConnection, HTTPException
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse

from .config import (
    OLLAMA_HOST,
    OLLAMA_PORT,
    OLLAMA_GENERATE_ENDPOINT,
    OLLAMA_TAGS_ENDPOINT,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    PREFLIGHT_TIMEOUT,
    LLM_OPTIONS,
)
from .prompt_template import build_prompt

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Base exception for Ollama-related errors."""
    pass


class OllamaConnectionError(OllamaError):
    """Ollama server is not reachable."""
    pass


class OllamaModelNotFoundError(OllamaError):
    """Requested model is not available."""
    pass


class OllamaTimeoutError(OllamaError):
    """Request timed out."""
    pass


def check_ollama_available() -> bool:
    """
    Check if Ollama server is running.

    Returns:
        True if server is reachable, False otherwise
    """
    try:
        conn = HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=PREFLIGHT_TIMEOUT)
        conn.request("GET", OLLAMA_TAGS_ENDPOINT)
        response = conn.getresponse()
        conn.close()
        return response.status == 200
    except (socket.error, HTTPException, OSError) as e:
        logger.debug(f"[ResearchExec] Ollama check failed: {e}")
        return False


def check_model_available(model: str) -> bool:
    """
    Check if the specified model is available in Ollama.

    Args:
        model: Model name to check

    Returns:
        True if model is available, False otherwise
    """
    try:
        conn = HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=PREFLIGHT_TIMEOUT)
        conn.request("GET", OLLAMA_TAGS_ENDPOINT)
        response = conn.getresponse()
        data = response.read().decode("utf-8")
        conn.close()

        if response.status != 200:
            return False

        tags_data = json.loads(data)
        models = tags_data.get("models", [])

        # Check both exact match and prefix match (qwen3:30b matches qwen3:30b-q4_0)
        for m in models:
            model_name = m.get("name", "")
            if model_name == model or model_name.startswith(f"{model}-"):
                return True

        # Also check without tag suffix
        base_model = model.split(":")[0] if ":" in model else model
        for m in models:
            model_name = m.get("name", "")
            if model_name.startswith(base_model):
                return True

        return False

    except (socket.error, HTTPException, OSError, json.JSONDecodeError) as e:
        logger.debug(f"[ResearchExec] Model check failed: {e}")
        return False


def execute_research(
    topic: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT
) -> Tuple[str, Dict[str, Any]]:
    """
    Execute a research prompt against Ollama.

    Args:
        topic: Research topic to analyze
        model: Ollama model name
        timeout: Request timeout in seconds

    Returns:
        Tuple of (raw_response_text, metadata_dict)

    Raises:
        OllamaConnectionError: If server is not reachable
        OllamaModelNotFoundError: If model is not available
        OllamaTimeoutError: If request times out
    """
    logger.info(f"[ResearchExec] Starting research execution")
    logger.info(f"[ResearchExec] Topic: \"{topic}\"")
    logger.info(f"[ResearchExec] Model: {model}")

    # Build prompt
    prompt = build_prompt(topic)
    logger.debug(f"[ResearchExec] Prompt length: {len(prompt)} chars")

    # Prepare request
    request_body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": LLM_OPTIONS
    }

    request_json = json.dumps(request_body)

    # Execute request
    start_time = time.time()
    logger.info("[ResearchExec] Calling Ollama API...")

    try:
        conn = HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=timeout)
        headers = {"Content-Type": "application/json"}
        conn.request("POST", OLLAMA_GENERATE_ENDPOINT, body=request_json, headers=headers)
        response = conn.getresponse()
        response_data = response.read().decode("utf-8")
        conn.close()

    except socket.timeout:
        elapsed = time.time() - start_time
        logger.error(f"[ResearchExec] Request timed out after {elapsed:.1f}s")
        raise OllamaTimeoutError(f"Request timed out after {timeout}s")

    except (socket.error, HTTPException, OSError) as e:
        logger.error(f"[ResearchExec] Connection error: {e}")
        raise OllamaConnectionError(f"Failed to connect to Ollama: {e}")

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[ResearchExec] Response received in {elapsed_ms}ms")

    # Parse response
    try:
        response_json = json.loads(response_data)
    except json.JSONDecodeError as e:
        logger.error(f"[ResearchExec] Invalid JSON response from Ollama: {e}")
        # Return raw response anyway
        return response_data, {
            "generation_time_ms": elapsed_ms,
            "status": "ollama_error",
            "error": str(e)
        }

    # Check for Ollama-level errors
    if "error" in response_json:
        error_msg = response_json["error"]
        if "not found" in error_msg.lower():
            raise OllamaModelNotFoundError(f"Model not found: {error_msg}")
        logger.error(f"[ResearchExec] Ollama error: {error_msg}")
        return "", {
            "generation_time_ms": elapsed_ms,
            "status": "ollama_error",
            "error": error_msg
        }

    # Extract response text
    raw_response = response_json.get("response", "")
    logger.debug(f"[ResearchExec] Response length: {len(raw_response)} chars")

    # Build metadata
    metadata = {
        "generation_time_ms": elapsed_ms,
        "model": response_json.get("model", model),
        "provider": "ollama",
        "prompt_tokens_est": len(prompt) // 4,  # Rough estimate
        "output_tokens_est": len(raw_response) // 4,
        "status": "complete"
    }

    # Add Ollama-provided metrics if available
    if "total_duration" in response_json:
        metadata["ollama_total_duration_ns"] = response_json["total_duration"]
    if "eval_count" in response_json:
        metadata["ollama_eval_count"] = response_json["eval_count"]

    return raw_response, metadata


def unload_model(model: str = DEFAULT_MODEL, timeout: int = 10) -> bool:
    """
    Unload a model from Ollama memory.

    Sends a request with keep_alive=0 to release VRAM/memory.
    Should be called after CLI execution completes.

    Args:
        model: Model name to unload
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"[ResearchExec] Unloading model: {model}")

    request_body = {
        "model": model,
        "prompt": "",
        "keep_alive": 0,  # Tells Ollama to unload immediately
    }

    try:
        conn = HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=timeout)
        headers = {"Content-Type": "application/json"}
        conn.request(
            "POST",
            OLLAMA_GENERATE_ENDPOINT,
            body=json.dumps(request_body),
            headers=headers
        )
        response = conn.getresponse()
        response.read()  # Consume response
        conn.close()

        if response.status < 400:
            logger.info(f"[ResearchExec] Model unloaded: {model}")
            return True
        else:
            logger.warning(f"[ResearchExec] Unload returned status {response.status}")
            return False

    except (socket.error, socket.timeout, HTTPException, OSError) as e:
        logger.warning(f"[ResearchExec] Failed to unload model: {e}")
        return False


def execute_research_with_provider(
    topic: str,
    model_spec: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> Tuple[str, Dict[str, Any]]:
    """
    Execute research using the model provider abstraction.

    Supports multiple providers:
    - Ollama (default): model_spec=None or "ollama:qwen3:30b"
    - Gemini: model_spec="gemini" or "gemini:model-name"

    Args:
        topic: Research topic to analyze
        model_spec: Model specification (e.g., "gemini", "ollama:qwen3:30b")
        timeout: Request timeout in seconds

    Returns:
        Tuple of (raw_response_text, metadata_dict)

    Raises:
        OllamaConnectionError: If Ollama server is not reachable
        ValueError: If Gemini is not configured or enabled
        Exception: On other generation failures
    """
    from .model_provider import (
        get_research_provider,
        get_research_model_info,
        is_gemini_available
    )
    from .prompt_template import build_prompt

    # Parse model spec
    model_info = get_research_model_info(model_spec)
    logger.info(f"[ResearchExec] Provider: {model_info.provider}")
    logger.info(f"[ResearchExec] Model: {model_info.model_name}")

    # Check Gemini availability if requested
    if model_info.provider == "gemini" and not is_gemini_available():
        raise ValueError(
            "Gemini is not available. Set GEMINI_ENABLED=true and GEMINI_API_KEY in environment."
        )

    # Build prompt
    prompt = build_prompt(topic)
    logger.debug(f"[ResearchExec] Prompt length: {len(prompt)} chars")

    # Get provider and execute
    start_time = time.time()
    provider = get_research_provider(model_spec)

    try:
        result = provider.generate(prompt, timeout)
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Build metadata
        metadata = {
            "generation_time_ms": elapsed_ms,
            "model": result.model,
            "provider": result.provider,
            "prompt_tokens_est": len(prompt) // 4,
            "output_tokens_est": len(result.text) // 4,
            "status": "complete"
        }

        # Merge provider-specific metadata
        if result.metadata:
            metadata.update(result.metadata)

        return result.text, metadata

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[ResearchExec] Generation failed: {e}")
        return "", {
            "generation_time_ms": elapsed_ms,
            "model": model_info.model_name,
            "provider": model_info.provider,
            "status": "error",
            "error": str(e)
        }


def run_research_pipeline(
    topic: str,
    tags: Optional[List[str]] = None,
    model_spec: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the complete research pipeline programmatically.

    This is a high-level function that executes the entire research workflow:
    1. Execute LLM research generation
    2. Validate and parse response
    3. Collapse canonical affinity to canonical core
    4. Run dedup check
    5. Write output files

    Args:
        topic: Research topic to analyze
        tags: Optional list of tags
        model_spec: Model specification (e.g., "gemini", "ollama:qwen3:30b")
        timeout: Request timeout in seconds
        output_dir: Output directory (default: ./data/research)

    Returns:
        Dict with:
            - success: bool
            - card_id: str (if successful)
            - card_path: str (path to JSON file)
            - card_data: Dict (full research card data)
            - error: str (if failed)
    """
    from .validator import process_llm_response
    from .output_writer import generate_card_id, write_output
    from .model_provider import get_research_model_info
    from pathlib import Path

    logger.info(f"[ResearchPipeline] Starting pipeline for topic: {topic}")

    # Parse model spec
    model_info = get_research_model_info(model_spec)
    model_name = model_info.model_name
    tags = tags or []

    # Step 1: Execute research
    try:
        raw_response, exec_metadata = execute_research_with_provider(
            topic=topic,
            model_spec=model_spec,
            timeout=timeout
        )
    except Exception as e:
        logger.error(f"[ResearchPipeline] Execution failed: {e}")
        return {
            "success": False,
            "card_id": None,
            "card_path": None,
            "card_data": None,
            "error": str(e)
        }

    if not raw_response:
        error_msg = exec_metadata.get("error", "Empty response from LLM")
        logger.error(f"[ResearchPipeline] Empty response: {error_msg}")
        return {
            "success": False,
            "card_id": None,
            "card_path": None,
            "card_data": None,
            "error": error_msg
        }

    # Step 2: Validate and process response
    processed, validation = process_llm_response(raw_response)

    if not processed:
        error_msg = validation.get("parse_error", "Failed to parse response")
        logger.error(f"[ResearchPipeline] Validation failed: {error_msg}")
        return {
            "success": False,
            "card_id": None,
            "card_path": None,
            "card_data": None,
            "error": error_msg
        }

    # Step 3: Collapse canonical affinity to canonical core
    canonical_core = None
    affinity = processed.get("canonical_affinity", {})
    if affinity:
        canonical_core = {
            "setting_archetype": (affinity.get("setting", [None]) or [None])[0],
            "primary_fear": (affinity.get("primary_fear", [None]) or [None])[0],
            "antagonist_archetype": (affinity.get("antagonist", [None]) or [None])[0],
            "threat_mechanism": (affinity.get("mechanism", [None]) or [None])[0],
            "twist_family": "inevitability"  # Default twist
        }

    # Step 4: Run dedup check (optional - requires FAISS)
    dedup_result = None
    try:
        from src.dedup.research import check_duplicate
        if canonical_core:
            dedup_result = check_duplicate(
                canonical_core=canonical_core,
                summary=processed.get("summary", "")
            )
            logger.info(f"[ResearchPipeline] Dedup result: {dedup_result.get('signal', 'LOW')}")
    except ImportError:
        logger.debug("[ResearchPipeline] Dedup module not available, skipping")
    except Exception as e:
        logger.warning(f"[ResearchPipeline] Dedup check failed: {e}")

    # Step 5: Generate card ID and write output
    card_id = generate_card_id()
    out_dir = Path(output_dir) if output_dir else None

    paths = write_output(
        card_id=card_id,
        topic=topic,
        tags=tags,
        model=model_name,
        output=processed,
        validation=validation,
        metadata=exec_metadata,
        output_dir=out_dir,
        canonical_core=canonical_core,
        dedup_result=dedup_result
    )

    if not paths.get("json"):
        return {
            "success": False,
            "card_id": card_id,
            "card_path": None,
            "card_data": None,
            "error": "Failed to write output file"
        }

    # Load the written card for return
    import json as json_module
    card_data = None
    try:
        with open(paths["json"], "r", encoding="utf-8") as f:
            card_data = json_module.load(f)
    except Exception as e:
        logger.warning(f"[ResearchPipeline] Failed to reload card: {e}")

    logger.info(f"[ResearchPipeline] Pipeline complete: {card_id}")

    return {
        "success": True,
        "card_id": card_id,
        "card_path": str(paths["json"]),
        "card_data": card_data,
        "error": None
    }
