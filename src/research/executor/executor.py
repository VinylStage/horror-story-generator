"""
Ollama API executor for research generation.
"""

import json
import logging
import socket
import time
from http.client import HTTPConnection, HTTPException
from typing import Dict, Any, Optional, Tuple
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
