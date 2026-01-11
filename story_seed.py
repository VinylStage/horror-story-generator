"""
Story Seed Generation Module.

Phase B+: Distills Research Cards into Story Seeds for story generation.

Story Seed (SS-*) format:
{
    "seed_id": "SS-YYYY-MM-DD-XXX",
    "source_card_id": "RC-YYYY-MM-DD-XXX",
    "key_themes": ["theme1", "theme2", "theme3"],
    "atmosphere_tags": ["atmospheric", "tense", "isolation"],
    "suggested_hooks": ["hook1", "hook2"],
    "cultural_elements": ["element1", "element2"],
    "created_at": "ISO timestamp"
}
"""

import json
import logging
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from data_paths import get_seeds_root

logger = logging.getLogger("horror_story_generator")

# Ollama settings
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_GENERATE_ENDPOINT = "/api/generate"
DEFAULT_MODEL = "qwen3:30b"
DEFAULT_TIMEOUT = 180

# Seed generation prompt
SEED_GENERATION_PROMPT = """You are a horror story seed distiller.

Given a research card about a topic, extract the essential elements for horror story creation.

Research Card:
---
Topic: {topic}
Title: {title}
Summary: {summary}
Key Concepts: {concepts}
Horror Applications: {applications}
---

Generate a Story Seed in JSON format with these fields:
1. key_themes: 3-5 core thematic elements suitable for horror (existential dread, isolation, transformation, etc.)
2. atmosphere_tags: 3-5 atmospheric descriptors (oppressive, uncanny, claustrophobic, etc.)
3. suggested_hooks: 2-3 story opening hooks based on the research
4. cultural_elements: 2-3 cultural or contextual elements that add authenticity

Output ONLY valid JSON, no explanation:
{{"key_themes": [...], "atmosphere_tags": [...], "suggested_hooks": [...], "cultural_elements": [...]}}"""


@dataclass
class StorySeed:
    """Story seed data structure."""
    seed_id: str
    source_card_id: str
    key_themes: List[str] = field(default_factory=list)
    atmosphere_tags: List[str] = field(default_factory=list)
    suggested_hooks: List[str] = field(default_factory=list)
    cultural_elements: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "seed_id": self.seed_id,
            "source_card_id": self.source_card_id,
            "key_themes": self.key_themes,
            "atmosphere_tags": self.atmosphere_tags,
            "suggested_hooks": self.suggested_hooks,
            "cultural_elements": self.cultural_elements,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StorySeed":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            seed_id=data["seed_id"],
            source_card_id=data["source_card_id"],
            key_themes=data.get("key_themes", []),
            atmosphere_tags=data.get("atmosphere_tags", []),
            suggested_hooks=data.get("suggested_hooks", []),
            cultural_elements=data.get("cultural_elements", []),
            created_at=created_at,
        )


def generate_seed_id() -> str:
    """
    Generate a unique seed ID.

    Format: SS-YYYY-MM-DD-XXX
    """
    now = datetime.now()
    date_part = now.strftime("%Y-%m-%d")

    # Find next sequence number
    seeds_dir = get_seeds_root()
    seeds_dir.mkdir(parents=True, exist_ok=True)

    existing = list(seeds_dir.glob(f"SS-{date_part}-*.json"))
    seq = len(existing) + 1

    return f"SS-{date_part}-{seq:03d}"


def extract_card_fields(card_data: dict) -> dict:
    """Extract relevant fields from research card for seed generation."""
    fields = {
        "topic": "",
        "title": "",
        "summary": "",
        "concepts": "",
        "applications": "",
    }

    if "input" in card_data:
        fields["topic"] = card_data["input"].get("topic", "")

    if "output" in card_data:
        output = card_data["output"]
        fields["title"] = output.get("title", "")
        fields["summary"] = output.get("summary", "")
        fields["concepts"] = ", ".join(output.get("key_concepts", []))
        fields["applications"] = "; ".join(output.get("horror_applications", []))

    return fields


def generate_seed_from_card(
    card_data: dict,
    card_id: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT
) -> Optional[StorySeed]:
    """
    Generate a Story Seed from a Research Card.

    Uses Ollama to distill the card into key story elements.

    Args:
        card_data: Research card JSON data
        card_id: Source card ID
        model: Ollama model to use
        timeout: Request timeout in seconds

    Returns:
        StorySeed if successful, None otherwise
    """
    # Extract fields
    fields = extract_card_fields(card_data)

    if not fields["topic"] and not fields["title"]:
        logger.warning("[SeedGen] Empty card data")
        return None

    # Build prompt
    prompt = SEED_GENERATION_PROMPT.format(**fields)

    # Call Ollama
    url = f"{OLLAMA_BASE_URL}{OLLAMA_GENERATE_ENDPOINT}"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 1024,
        }
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        logger.info(f"[SeedGen] Generating seed from {card_id}")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))

        response_text = result.get("response", "")

        # Parse JSON from response
        seed_data = parse_seed_json(response_text)

        if seed_data is None:
            logger.error(f"[SeedGen] Failed to parse seed JSON from response")
            return None

        # Create StorySeed
        seed_id = generate_seed_id()
        seed = StorySeed(
            seed_id=seed_id,
            source_card_id=card_id,
            key_themes=seed_data.get("key_themes", []),
            atmosphere_tags=seed_data.get("atmosphere_tags", []),
            suggested_hooks=seed_data.get("suggested_hooks", []),
            cultural_elements=seed_data.get("cultural_elements", []),
        )

        logger.info(f"[SeedGen] Generated {seed_id} from {card_id}")
        return seed

    except urllib.error.URLError as e:
        logger.error(f"[SeedGen] Ollama connection failed: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"[SeedGen] Invalid JSON response: {e}")
        return None
    except Exception as e:
        logger.error(f"[SeedGen] Seed generation failed: {e}")
        return None


def parse_seed_json(response_text: str) -> Optional[dict]:
    """
    Parse JSON from Ollama response.

    Handles thinking tags and extracts JSON object.
    """
    # Remove thinking tags if present
    text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL)
    text = text.strip()

    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Try to find JSON with arrays
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def save_seed(seed: StorySeed, output_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Save a Story Seed to JSON file.

    Args:
        seed: StorySeed to save
        output_dir: Output directory (uses default if not provided)

    Returns:
        Path to saved file, or None on failure
    """
    if output_dir is None:
        output_dir = get_seeds_root()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{seed.seed_id}.json"

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(seed.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"[SeedGen] Saved seed to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"[SeedGen] Failed to save seed: {e}")
        return None


def load_seed(seed_path: Path) -> Optional[StorySeed]:
    """Load a Story Seed from JSON file."""
    try:
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return StorySeed.from_dict(data)
    except Exception as e:
        logger.error(f"[SeedGen] Failed to load seed: {e}")
        return None


def list_seeds(seeds_dir: Optional[Path] = None) -> List[Path]:
    """List all seed files."""
    if seeds_dir is None:
        seeds_dir = get_seeds_root()

    if not seeds_dir.exists():
        return []

    seeds = list(seeds_dir.glob("SS-*.json"))
    seeds.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return seeds


def get_random_seed(seeds_dir: Optional[Path] = None) -> Optional[StorySeed]:
    """Get a random Story Seed for story generation."""
    import random

    seeds = list_seeds(seeds_dir)
    if not seeds:
        return None

    seed_path = random.choice(seeds)
    return load_seed(seed_path)


def generate_and_save_seed(
    card_data: dict,
    card_id: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT
) -> Optional[StorySeed]:
    """
    Generate and save a Story Seed from a Research Card.

    Convenience function that combines generation and saving.

    Args:
        card_data: Research card JSON data
        card_id: Source card ID
        model: Ollama model to use
        timeout: Request timeout

    Returns:
        StorySeed if successful, None otherwise
    """
    seed = generate_seed_from_card(card_data, card_id, model=model, timeout=timeout)

    if seed:
        save_seed(seed)

    return seed
