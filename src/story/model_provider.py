"""
Model provider abstraction for story generation.

Supports multiple LLM backends:
- Claude (Anthropic) - default
- Ollama (local models)

Usage:
    provider = get_provider("ollama:llama3")
    result = provider.generate(system_prompt, user_prompt, config)
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException
from typing import Any, Dict, Optional, Union
import socket

logger = logging.getLogger("horror_story_generator")


@dataclass
class ModelInfo:
    """Model identification information."""
    provider: str  # "anthropic", "ollama"
    model_name: str  # e.g., "claude-sonnet-4-5-20250929", "llama3"
    full_spec: str  # e.g., "claude-sonnet-4-5-20250929", "ollama:llama3"


@dataclass
class GenerationResult:
    """Result from text generation."""
    text: str
    usage: Optional[Dict[str, int]]
    provider: str
    model: str


def parse_model_spec(model_spec: Optional[str]) -> ModelInfo:
    """
    Parse model specification string into provider and model name.

    Formats:
    - "ollama:llama3" -> provider="ollama", model="llama3"
    - "ollama:qwen" -> provider="ollama", model="qwen"
    - "claude-sonnet-4-5-20250929" -> provider="anthropic", model="claude-sonnet-4-5-20250929"
    - None -> default Claude model from env

    Args:
        model_spec: Model specification string or None for default

    Returns:
        ModelInfo with provider and model name
    """
    if model_spec is None:
        # Default: use Claude from environment
        default_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        return ModelInfo(
            provider="anthropic",
            model_name=default_model,
            full_spec=default_model
        )

    if model_spec.startswith("ollama:"):
        model_name = model_spec.split(":", 1)[1]
        return ModelInfo(
            provider="ollama",
            model_name=model_name,
            full_spec=model_spec
        )

    # Default: treat as Claude model
    return ModelInfo(
        provider="anthropic",
        model_name=model_spec,
        full_spec=model_spec
    )


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        config: Dict[str, Any]
    ) -> GenerationResult:
        """
        Generate text using the model.

        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            config: Configuration dict with max_tokens, temperature, etc.

        Returns:
            GenerationResult with generated text and metadata
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name for metadata."""
        pass


class ClaudeProvider(ModelProvider):
    """Claude (Anthropic) model provider."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        config: Dict[str, Any]
    ) -> GenerationResult:
        """Generate using Claude API."""
        import anthropic

        logger.info(f"[ClaudeProvider] Generating with {self.model_name}")
        client = anthropic.Anthropic(api_key=config["api_key"])

        try:
            message = client.messages.create(
                model=self.model_name,
                max_tokens=int(config.get("max_tokens", 8192)),
                temperature=float(config.get("temperature", 0.8)),
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            text = message.content[0].text

            # Extract usage
            usage = None
            if hasattr(message, 'usage') and message.usage:
                try:
                    usage = {
                        "input_tokens": message.usage.input_tokens,
                        "output_tokens": message.usage.output_tokens,
                        "total_tokens": message.usage.input_tokens + message.usage.output_tokens
                    }
                except (AttributeError, TypeError):
                    pass

            logger.info(f"[ClaudeProvider] Generated {len(text)} chars")

            return GenerationResult(
                text=text,
                usage=usage,
                provider=self.provider_name,
                model=self.model_name
            )

        except Exception as e:
            logger.error(f"[ClaudeProvider] Generation failed: {e}")
            raise


class OllamaProvider(ModelProvider):
    """Ollama (local) model provider."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.host = os.getenv("OLLAMA_HOST", "localhost")
        self.port = int(os.getenv("OLLAMA_PORT", "11434"))

    @property
    def provider_name(self) -> str:
        return "ollama"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        config: Dict[str, Any]
    ) -> GenerationResult:
        """Generate using Ollama API."""
        logger.info(f"[OllamaProvider] Generating with {self.model_name}")

        # Build combined prompt (Ollama doesn't have system prompt in same way)
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        request_body = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": float(config.get("temperature", 0.8)),
                "num_predict": int(config.get("max_tokens", 8192)),
            }
        }

        timeout = int(config.get("timeout", 600))  # 10 min default for stories

        try:
            conn = HTTPConnection(self.host, self.port, timeout=timeout)
            headers = {"Content-Type": "application/json"}
            conn.request(
                "POST",
                "/api/generate",
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

            # Build usage info from Ollama response
            usage = None
            if "eval_count" in response_json:
                usage = {
                    "input_tokens": response_json.get("prompt_eval_count", 0),
                    "output_tokens": response_json.get("eval_count", 0),
                    "total_tokens": response_json.get("prompt_eval_count", 0) + response_json.get("eval_count", 0)
                }

            logger.info(f"[OllamaProvider] Generated {len(text)} chars")

            return GenerationResult(
                text=text,
                usage=usage,
                provider=self.provider_name,
                model=self.model_name
            )

        except socket.timeout:
            logger.error(f"[OllamaProvider] Timeout after {timeout}s")
            raise Exception(f"Ollama timeout after {timeout}s")
        except (socket.error, HTTPException, OSError) as e:
            logger.error(f"[OllamaProvider] Connection error: {e}")
            raise Exception(f"Ollama connection failed: {e}")


def get_provider(model_spec: Optional[str] = None) -> ModelProvider:
    """
    Get appropriate model provider for the given model specification.

    Args:
        model_spec: Model specification (e.g., "ollama:llama3" or "claude-sonnet-4-5-20250929")
                   None uses default Claude model from environment

    Returns:
        ModelProvider instance
    """
    info = parse_model_spec(model_spec)

    if info.provider == "ollama":
        return OllamaProvider(info.model_name)
    else:
        return ClaudeProvider(info.model_name)


def get_model_info(model_spec: Optional[str] = None) -> ModelInfo:
    """
    Get model information without creating a provider.

    Args:
        model_spec: Model specification string

    Returns:
        ModelInfo with provider and model details
    """
    return parse_model_spec(model_spec)
