"""
Research prompt templates for LLM execution.
"""

SYSTEM_PROMPT = """You are a horror research assistant. Your task is to analyze a topic and extract elements that could be used in psychological horror fiction.

Output MUST be valid JSON with this structure:
{
  "title": "Brief title (max 80 chars)",
  "summary": "2-3 sentence summary of horror potential",
  "key_concepts": ["concept1", "concept2", "concept3"],
  "horror_applications": ["application1", "application2", "application3"],
  "canonical_affinity": {
    "setting": ["one or more of: digital, domestic_space, hospital, body, liminal, rural, apartment, infrastructure, abstract"],
    "primary_fear": ["one or more of: social_displacement, loss_of_autonomy, annihilation, identity_erasure, contamination, isolation"],
    "antagonist": ["one or more of: system, technology, body, unknown, collective, ghost"],
    "mechanism": ["one or more of: erosion, confinement, debt, impersonation, surveillance, infection, exploitation, possession"]
  }
}

Focus on psychological horror rooted in everyday life.
Avoid supernatural explanations - prefer systemic, technological, or social horrors.
Output ONLY the JSON object, no additional text or markdown formatting."""

USER_PROMPT_TEMPLATE = """Research topic: {topic}

Analyze this topic for psychological horror potential.
Provide your analysis in the required JSON format only."""


def build_prompt(topic: str) -> str:
    """
    Build the full prompt for Ollama.

    Ollama's generate API takes a single prompt string.
    We combine system and user prompts with clear separation.

    Args:
        topic: The research topic to analyze

    Returns:
        Combined prompt string
    """
    user_prompt = USER_PROMPT_TEMPLATE.format(topic=topic)

    # Combine with clear separation for the model
    full_prompt = f"""{SYSTEM_PROMPT}

---

{user_prompt}"""

    return full_prompt


def get_prompt_for_display(topic: str) -> str:
    """
    Get a formatted prompt for dry-run display.

    Args:
        topic: The research topic

    Returns:
        Formatted prompt with headers
    """
    return f"""=== SYSTEM PROMPT ===
{SYSTEM_PROMPT}

=== USER PROMPT ===
{USER_PROMPT_TEMPLATE.format(topic=topic)}
"""
