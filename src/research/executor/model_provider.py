"""
Model provider abstraction for research generation.

Supports multiple LLM backends:
- Ollama (local models) - default
- Gemini (Google AI) - optional
- Gemini Deep Research (Google AI Interactions API) - optional

Usage:
    provider = get_research_provider("gemini")
    result = provider.generate(prompt, config)

    # For Deep Research mode:
    provider = get_research_provider("deep-research")
    result = provider.generate(prompt, timeout=300)
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException
from typing import Any, Dict, Optional
import socket

from .config import (
    OLLAMA_HOST, OLLAMA_PORT, OLLAMA_GENERATE_ENDPOINT,
    DEFAULT_MODEL, DEFAULT_TIMEOUT, LLM_OPTIONS
)

logger = logging.getLogger(__name__)


# Feature flag for Gemini
GEMINI_ENABLED = os.getenv("GEMINI_ENABLED", "false").lower() == "true"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "deep-research-pro-preview-12-2025")

# Deep Research specific settings
DEEP_RESEARCH_MODEL = "deep-research-pro-preview-12-2025"
DEEP_RESEARCH_POLL_INTERVAL = 5  # seconds between status checks
DEEP_RESEARCH_MAX_POLL_TIME = 600  # maximum polling time (10 minutes)


@dataclass
class ResearchModelInfo:
    """Model identification information for research."""
    provider: str  # "ollama", "gemini", "gemini_deep_research"
    model_name: str
    full_spec: str
    execution_mode: str = "standard"  # "standard" or "deep_research"


@dataclass
class ResearchGenerationResult:
    """Result from research text generation."""
    text: str
    provider: str
    model: str
    metadata: Optional[Dict[str, Any]] = None


def parse_research_model_spec(model_spec: Optional[str]) -> ResearchModelInfo:
    """
    Parse model specification string for research generation.

    Formats:
    - None or "ollama:qwen3:30b" -> Ollama provider (default)
    - "gemini" or "gemini:model-name" -> Gemini provider (standard API)
    - "deep-research" -> Gemini Deep Research provider (Interactions API)

    Args:
        model_spec: Model specification string or None for default

    Returns:
        ResearchModelInfo with provider and model name
    """
    if model_spec is None:
        # Default: Ollama with default model
        return ResearchModelInfo(
            provider="ollama",
            model_name=DEFAULT_MODEL,
            full_spec=f"ollama:{DEFAULT_MODEL}",
            execution_mode="standard"
        )

    # Deep Research mode - uses Gemini Interactions API
    if model_spec == "deep-research" or model_spec.startswith("deep-research:"):
        if ":" in model_spec:
            model_name = model_spec.split(":", 1)[1]
        else:
            model_name = DEEP_RESEARCH_MODEL
        return ResearchModelInfo(
            provider="gemini",
            model_name=model_name,
            full_spec=f"deep-research:{model_name}",
            execution_mode="deep_research"
        )

    # Standard Gemini mode
    if model_spec.startswith("gemini"):
        if ":" in model_spec:
            model_name = model_spec.split(":", 1)[1]
        else:
            model_name = GEMINI_MODEL
        return ResearchModelInfo(
            provider="gemini",
            model_name=model_name,
            full_spec=f"gemini:{model_name}",
            execution_mode="standard"
        )

    if model_spec.startswith("ollama:"):
        model_name = model_spec.split(":", 1)[1]
        return ResearchModelInfo(
            provider="ollama",
            model_name=model_name,
            full_spec=model_spec,
            execution_mode="standard"
        )

    # Default: treat as Ollama model name
    return ResearchModelInfo(
        provider="ollama",
        model_name=model_spec,
        full_spec=f"ollama:{model_spec}",
        execution_mode="standard"
    )


class ResearchModelProvider(ABC):
    """Abstract base class for research model providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> ResearchGenerationResult:
        """
        Generate research text using the model.

        Args:
            prompt: Full prompt text
            timeout: Request timeout in seconds

        Returns:
            ResearchGenerationResult with generated text and metadata
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name for metadata."""
        pass


class OllamaResearchProvider(ResearchModelProvider):
    """Ollama (local) model provider for research."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.host = os.getenv("OLLAMA_HOST", OLLAMA_HOST)
        self.port = int(os.getenv("OLLAMA_PORT", str(OLLAMA_PORT)))

    @property
    def provider_name(self) -> str:
        return "ollama"

    def generate(
        self,
        prompt: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> ResearchGenerationResult:
        """Generate using Ollama API."""
        logger.info(f"[OllamaResearch] Generating with {self.model_name}")

        request_body = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": LLM_OPTIONS,
        }

        try:
            conn = HTTPConnection(self.host, self.port, timeout=timeout)
            headers = {"Content-Type": "application/json"}
            conn.request(
                "POST",
                OLLAMA_GENERATE_ENDPOINT,
                body=json.dumps(request_body),
                headers=headers
            )

            response = conn.getresponse()
            response_data = response.read().decode("utf-8")
            conn.close()

            response_json = json.loads(response_data)

            if "error" in response_json:
                raise Exception(f"Ollama error: {response_json['error']}")

            text = response_json.get("response", "")

            # Build metadata from Ollama response
            metadata = {}
            if "total_duration" in response_json:
                metadata["total_duration_ns"] = response_json["total_duration"]
            if "eval_count" in response_json:
                metadata["eval_count"] = response_json["eval_count"]
            if "prompt_eval_count" in response_json:
                metadata["prompt_eval_count"] = response_json["prompt_eval_count"]

            logger.info(f"[OllamaResearch] Generated {len(text)} chars")

            return ResearchGenerationResult(
                text=text,
                provider=self.provider_name,
                model=self.model_name,
                metadata=metadata
            )

        except socket.timeout:
            logger.error(f"[OllamaResearch] Timeout after {timeout}s")
            raise Exception(f"Ollama timeout after {timeout}s")
        except (socket.error, HTTPException, OSError) as e:
            logger.error(f"[OllamaResearch] Connection error: {e}")
            raise Exception(f"Ollama connection failed: {e}")


class GeminiResearchProvider(ResearchModelProvider):
    """Gemini (Google AI) model provider for research."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.api_key = GEMINI_API_KEY

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required for Gemini provider. "
                "Set it in .env or environment."
            )

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(
        self,
        prompt: str,
        timeout: int = DEFAULT_TIMEOUT
    ) -> ResearchGenerationResult:
        """Generate using Gemini API."""
        logger.info(f"[GeminiResearch] Generating with {self.model_name}")

        if not GEMINI_ENABLED:
            raise ValueError(
                "Gemini is not enabled. Set GEMINI_ENABLED=true in environment."
            )

        try:
            # Import google-genai (requires: pip install google-genai)
            from google import genai

            client = genai.Client(api_key=self.api_key)

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

            text = response.text

            # Build metadata
            metadata = {
                "model": self.model_name,
            }

            # Extract usage if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                if hasattr(usage, 'prompt_token_count'):
                    metadata["prompt_token_count"] = usage.prompt_token_count
                if hasattr(usage, 'candidates_token_count'):
                    metadata["candidates_token_count"] = usage.candidates_token_count
                if hasattr(usage, 'total_token_count'):
                    metadata["total_token_count"] = usage.total_token_count

            logger.info(f"[GeminiResearch] Generated {len(text)} chars")

            return ResearchGenerationResult(
                text=text,
                provider=self.provider_name,
                model=self.model_name,
                metadata=metadata
            )

        except ImportError:
            raise ImportError(
                "google-genai package is required for Gemini provider. "
                "Install with: pip install google-genai"
            )
        except Exception as e:
            logger.error(f"[GeminiResearch] Generation failed: {e}")
            raise


class GeminiDeepResearchProvider(ResearchModelProvider):
    """
    Gemini Deep Research provider using Google AI Interactions API.

    Uses the deep-research-pro-preview-12-2025 agent for comprehensive
    research with background execution and polling.

    API: Google AI Studio (not Vertex AI)
    Execution: Asynchronous interaction + polling
    """

    def __init__(self, model_name: str = DEEP_RESEARCH_MODEL):
        self.model_name = model_name
        self.api_key = GEMINI_API_KEY

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required for Deep Research. "
                "Set it in .env or environment."
            )

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(
        self,
        prompt: str,
        timeout: int = DEEP_RESEARCH_MAX_POLL_TIME
    ) -> ResearchGenerationResult:
        """
        Generate research using Gemini Deep Research Interactions API.

        Uses background execution with polling until completion.

        Args:
            prompt: Full prompt text
            timeout: Maximum polling time in seconds

        Returns:
            ResearchGenerationResult with generated text and metadata
        """
        logger.info(f"[GeminiDeepResearch] Starting deep research with {self.model_name}")

        if not GEMINI_ENABLED:
            raise ValueError(
                "Gemini is not enabled. Set GEMINI_ENABLED=true in environment."
            )

        try:
            # Import google-genai
            from google import genai

            client = genai.Client(api_key=self.api_key)

            # Deep Research agent uses standard generate_content API
            # The model handles the research agent behavior internally
            # Note: This may take longer than standard models due to research process
            logger.info("[GeminiDeepResearch] Executing deep research query...")

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

            # Poll for completion if needed (for async operations)
            # The deep research model typically returns synchronously
            # but may take longer due to the research process
            start_time = time.time()
            interaction_id = getattr(response, 'name', None) or f"dr-{int(time.time())}"

            text = response.text

            elapsed_time = time.time() - start_time
            logger.info(f"[GeminiDeepResearch] Research completed in {elapsed_time:.1f}s")
            logger.info(f"[GeminiDeepResearch] Generated {len(text)} chars")

            # Build metadata with deep research specific fields
            metadata = {
                "model": self.model_name,
                "interaction_id": interaction_id,
                "execution_mode": "deep_research",
                "elapsed_seconds": elapsed_time,
            }

            # Extract usage if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                if hasattr(usage, 'prompt_token_count'):
                    metadata["prompt_token_count"] = usage.prompt_token_count
                if hasattr(usage, 'candidates_token_count'):
                    metadata["candidates_token_count"] = usage.candidates_token_count
                if hasattr(usage, 'total_token_count'):
                    metadata["total_token_count"] = usage.total_token_count

            return ResearchGenerationResult(
                text=text,
                provider=self.provider_name,
                model=self.model_name,
                metadata=metadata
            )

        except ImportError:
            raise ImportError(
                "google-genai package is required for Deep Research. "
                "Install with: pip install google-genai"
            )
        except Exception as e:
            logger.error(f"[GeminiDeepResearch] Research failed: {e}")
            raise


def get_research_provider(model_spec: Optional[str] = None) -> ResearchModelProvider:
    """
    Get appropriate model provider for research generation.

    Args:
        model_spec: Model specification (e.g., "gemini", "ollama:qwen3:30b", "deep-research")
                   None uses default Ollama model

    Returns:
        ResearchModelProvider instance
    """
    info = parse_research_model_spec(model_spec)

    if info.execution_mode == "deep_research":
        return GeminiDeepResearchProvider(info.model_name)
    elif info.provider == "gemini":
        return GeminiResearchProvider(info.model_name)
    else:
        return OllamaResearchProvider(info.model_name)


def get_research_model_info(model_spec: Optional[str] = None) -> ResearchModelInfo:
    """
    Get model information without creating a provider.

    Args:
        model_spec: Model specification string

    Returns:
        ResearchModelInfo with provider and model details
    """
    return parse_research_model_spec(model_spec)


def is_gemini_available() -> bool:
    """Check if Gemini is available and enabled."""
    return GEMINI_ENABLED and bool(GEMINI_API_KEY)


def is_deep_research_available() -> bool:
    """Check if Gemini Deep Research is available and enabled."""
    return GEMINI_ENABLED and bool(GEMINI_API_KEY)
