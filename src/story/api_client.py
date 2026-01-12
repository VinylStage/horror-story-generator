"""
LLM API client module.

Handles all LLM API interactions for story generation.
Supports multiple providers: Claude (Anthropic), Ollama.
"""

import logging
from typing import Any, Dict, Optional, Union

import anthropic

from .model_provider import get_provider, get_model_info, GenerationResult

logger = logging.getLogger("horror_story_generator")


def call_claude_api(
    system_prompt: str,
    user_prompt: str,
    config: Dict[str, Union[str, int, float]]
) -> Dict[str, Any]:
    """
    Call Claude API to generate a horror story.

    Uses Anthropic Messages API to send system and user prompts
    and returns generated text with token usage.

    Args:
        system_prompt (str): System prompt (writer role and guidelines)
        user_prompt (str): User prompt (specific request)
        config (Dict[str, Union[str, int, float]]): API configuration
            - api_key: API key
            - model: Model name
            - max_tokens: Maximum tokens
            - temperature: Generation temperature

    Returns:
        Dict[str, Any]: Generation result
            - story_text (str): Generated horror story text
            - usage (Dict): Token usage info
                - input_tokens (int): Input token count
                - output_tokens (int): Output token count

    Raises:
        Exception: On API call failure (network error, auth failure, etc.)

    Example:
        >>> result = call_claude_api(system_prompt, user_prompt, config)
        >>> print(result['story_text'][:100])
        >>> print(f"Used {result['usage']['input_tokens']} input tokens")
    """
    logger.info("Claude API 호출 시작...")
    client = anthropic.Anthropic(api_key=config["api_key"])

    try:
        message = client.messages.create(
            model=config["model"],
            max_tokens=int(config["max_tokens"]),
            temperature=float(config["temperature"]),
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )

        story_text = message.content[0].text

        # Phase 1: Defensive usage extraction - handle missing usage gracefully
        if hasattr(message, 'usage') and message.usage:
            try:
                usage = {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                    "total_tokens": message.usage.input_tokens + message.usage.output_tokens
                }
                logger.info(f"소설 생성 완료 - 길이: {len(story_text)}자")
                logger.info(f"토큰 사용량 - Input: {usage['input_tokens']}, Output: {usage['output_tokens']}, Total: {usage['total_tokens']}")
            except (AttributeError, TypeError) as e:
                logger.warning(f"토큰 사용량 추출 실패 (usage 구조 이상): {e}")
                usage = None
        else:
            logger.warning("토큰 사용량 정보 없음 (message.usage missing)")
            usage = None

        return {
            "story_text": story_text,
            "usage": usage
        }

    except Exception as e:
        logger.error(f"Claude API 호출 중 오류 발생: {str(e)}", exc_info=True)
        raise Exception(f"Claude API 호출 중 오류 발생: {str(e)}")


def call_llm_api(
    system_prompt: str,
    user_prompt: str,
    config: Dict[str, Union[str, int, float]],
    model_spec: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call LLM API to generate a story using the specified model.

    Supports multiple providers:
    - Claude (Anthropic) - default
    - Ollama (local models) - prefix with "ollama:"

    Args:
        system_prompt (str): System prompt (writer role and guidelines)
        user_prompt (str): User prompt (specific request)
        config (Dict): API configuration with api_key, max_tokens, temperature
        model_spec (Optional[str]): Model specification
            - None: use default Claude model from CLAUDE_MODEL env var
            - "claude-sonnet-4-5-20250929": explicit Claude model
            - "ollama:llama3": Ollama model
            - "ollama:qwen": Ollama model

    Returns:
        Dict[str, Any]: Generation result
            - story_text (str): Generated text
            - usage (Dict): Token usage info
            - provider (str): "anthropic" or "ollama"
            - model (str): Model name used
    """
    # Get model info for logging
    model_info = get_model_info(model_spec)
    logger.info(f"[LLM] Using provider={model_info.provider}, model={model_info.model_name}")

    # Get provider and generate
    provider = get_provider(model_spec)

    try:
        result = provider.generate(system_prompt, user_prompt, config)

        return {
            "story_text": result.text,
            "usage": result.usage,
            "provider": result.provider,
            "model": result.model
        }

    except Exception as e:
        logger.error(f"[LLM] Generation failed: {e}", exc_info=True)
        raise Exception(f"LLM generation failed: {e}")


def generate_semantic_summary(
    story_text: str,
    title: str,
    config: Dict[str, Any]
) -> str:
    """
    Generate a semantic summary of the story (for observation).

    Uses LLM to generate a 1-3 sentence short summary.
    This summary is used for similarity observation only.

    Args:
        story_text: Full story text
        title: Story title
        config: API configuration

    Returns:
        str: 1-3 sentence summary
    """
    logger.info("[Phase2B][OBSERVE] 의미적 요약 생성 시작")

    try:
        client = anthropic.Anthropic(api_key=config["api_key"])

        # Use a fast, cheap call for summarization
        message = client.messages.create(
            model=config["model"],
            max_tokens=200,
            temperature=0.0,  # Deterministic for consistency
            system="You are a story summarizer. Generate a 1-3 sentence summary focusing on: setting, protagonist situation, type of horror, and ending pattern. Be concise and factual.",
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this horror story in 1-3 sentences (Korean):\n\nTitle: {title}\n\n{story_text[:2000]}"  # Limit input
                }
            ]
        )

        summary = message.content[0].text.strip()
        logger.info(f"[Phase2B][OBSERVE] 의미적 요약 생성 완료: {summary[:100]}...")
        return summary

    except Exception as e:
        logger.warning(f"[Phase2B][OBSERVE] 요약 생성 실패, 폴백 사용: {e}")
        # Fallback: use first 200 chars of story
        return story_text[:200].strip()
