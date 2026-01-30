"""
Image prompt builder for horror story thumbnails.

Extracts visual keywords from stories and builds provider-specific prompts.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Visual Keyword Extraction Prompt
# =============================================================================

VISUAL_EXTRACTION_PROMPT = """Analyze this Korean horror story and extract visual keywords for a thumbnail image.

Story Title: {title}
Story Excerpt (first 500 characters): {excerpt}

Extract the following elements (respond in English for image generation):
1. Setting: location, time of day, weather/atmosphere
2. Mood: emotional tone, color palette, lighting
3. Central Element: main visual focus (object, figure, scene)
4. Horror Type: psychological, supernatural, body horror, etc.

Respond in this EXACT format (one line per element):
Setting: [your answer]
Mood: [your answer]
Central Element: [your answer]
Horror Type: [your answer]

Keep each answer concise (under 20 words)."""


def extract_visual_keywords(
    story_text: str,
    title: str,
    config: dict
) -> Dict[str, str]:
    """
    Extract visual keywords from story using Claude API.

    Args:
        story_text: Full story text.
        title: Story title.
        config: API configuration (for Claude API).

    Returns:
        Dict with keys: setting, mood, central_element, horror_type
    """
    excerpt = story_text[:500]
    prompt = VISUAL_EXTRACTION_PROMPT.format(title=title, excerpt=excerpt)

    # Default keywords in case extraction fails
    defaults = {
        "setting": "dark atmospheric space",
        "mood": "unsettling, dark tones, low light",
        "central_element": "mysterious shadow",
        "horror_type": "psychological horror"
    }

    try:
        # Import here to avoid circular dependency
        from src.story.api_client import call_claude_api

        result = call_claude_api(
            system_prompt="You are a visual analyst extracting image generation keywords from horror stories.",
            user_prompt=prompt,
            config={
                "api_key": config.get("api_key"),
                "model": config.get("model", "claude-sonnet-4-5-20250929"),
                "max_tokens": 300,
                "temperature": 0.3  # Lower temperature for consistent extraction
            }
        )

        response_text = result.get("story_text", "")

        # Parse response
        keywords = {}
        for line in response_text.strip().split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                key = key.strip().lower().replace(" ", "_")
                if key in defaults:
                    keywords[key] = value.strip()

        # Fill in any missing keys with defaults
        for key in defaults:
            if key not in keywords or not keywords[key]:
                keywords[key] = defaults[key]

        logger.info(f"Extracted visual keywords: {keywords}")
        return keywords

    except ImportError:
        logger.warning("Claude API not available, using default keywords")
        return defaults

    except Exception as e:
        logger.warning(f"Visual keyword extraction failed: {e}, using defaults")
        return defaults


def build_image_prompt(
    keywords: Dict[str, str],
    provider: str,
    title: Optional[str] = None
) -> str:
    """
    Build provider-specific image generation prompt.

    Args:
        keywords: Extracted visual keywords.
        provider: Provider name (openai_dalle3, stability_ai, flux, local_sd).
        title: Optional story title for context.

    Returns:
        Formatted prompt string optimized for provider.
    """
    setting = keywords.get("setting", "dark atmospheric space")
    mood = keywords.get("mood", "unsettling, dark tones")
    central_element = keywords.get("central_element", "mysterious shadow")
    horror_type = keywords.get("horror_type", "psychological horror")

    if provider == "openai_dalle3":
        # DALL-E 3: Natural language, detailed descriptions
        prompt = f"""A cinematic Korean horror movie poster composition.

Scene: {setting}
Atmosphere: {mood}, dramatic cinematic lighting
Focus: {central_element}
Style: {horror_type} aesthetic, unsettling and eerie mood

Technical specifications:
- Professional movie poster composition
- Dark, moody color palette with high contrast
- Atmospheric fog or shadows
- No text, no Korean characters, no watermarks, no logos
- Photorealistic quality with artistic horror elements"""

    elif provider == "stability_ai":
        # Stability AI: Comma-separated keywords work well
        prompt = f"""horror movie poster, {mood}, {setting}, {central_element},
{horror_type}, cinematic lighting, dramatic composition,
dark color palette, atmospheric, unsettling mood,
Korean horror aesthetic, professional photography,
high detail, moody atmosphere, no text, no watermark"""

    elif provider == "flux":
        # FLUX: Similar to DALL-E, handles natural language well
        prompt = f"""A dark and atmospheric Korean horror movie poster.
{setting} with {mood}.
Central focus on {central_element}.
{horror_type} style with cinematic composition.
Dark moody lighting, high contrast, no text or watermarks."""

    elif provider == "local_sd":
        # Local SD (SDXL): Positive prompt with style tags
        prompt = f"""(masterpiece, best quality, cinematic), horror movie poster,
{setting}, {mood}, {central_element}, {horror_type},
dark atmospheric, dramatic lighting, professional composition,
Korean horror aesthetic, moody, unsettling, high detail"""

    else:
        # Fallback generic prompt
        prompt = f"""Horror movie poster: {setting}, {central_element}, {mood}, {horror_type}.
Dark atmospheric, cinematic lighting, no text."""

    logger.debug(f"Built {provider} prompt: {prompt[:100]}...")
    return prompt


def build_negative_prompt(provider: str) -> str:
    """
    Build provider-specific negative prompt.

    Args:
        provider: Provider name.

    Returns:
        Negative prompt string (for providers that support it).
    """
    base_negative = (
        "text, words, letters, Korean characters, watermark, logo, signature, "
        "bright colors, happy, cheerful, cartoon, anime, childish, "
        "blurry, low quality, distorted, deformed, bad anatomy"
    )

    if provider == "stability_ai":
        return base_negative
    elif provider == "local_sd":
        return f"(worst quality, low quality), {base_negative}"
    else:
        # DALL-E and FLUX don't use negative prompts
        return ""
