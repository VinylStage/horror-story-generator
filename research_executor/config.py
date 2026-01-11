"""
Configuration constants for Research Executor.
"""

from pathlib import Path

# Ollama settings
OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
OLLAMA_GENERATE_ENDPOINT = "/api/generate"
OLLAMA_TAGS_ENDPOINT = "/api/tags"

# Default model
DEFAULT_MODEL = "qwen3:30b"

# Timeouts (seconds)
DEFAULT_TIMEOUT = 300
PREFLIGHT_TIMEOUT = 10

# Output settings
DEFAULT_OUTPUT_DIR = Path("./data/research")
LOG_DIR = DEFAULT_OUTPUT_DIR / "logs"
CARD_ID_PREFIX = "RC"

# Topic constraints
MIN_TOPIC_LENGTH = 10
MAX_TOPIC_LENGTH = 200

# LLM generation options
LLM_OPTIONS = {
    "temperature": 0.7,
    "num_predict": 2048
}

# Exit codes (per design spec)
EXIT_SUCCESS = 0
EXIT_INVALID_INPUT = 1
EXIT_OLLAMA_NOT_RUNNING = 2
EXIT_MODEL_NOT_FOUND = 3
EXIT_TIMEOUT = 4
EXIT_DISK_ERROR = 5

# Canonical dimensions (for validation)
VALID_SETTINGS = [
    "digital", "domestic_space", "hospital", "body",
    "liminal", "rural", "apartment", "infrastructure", "abstract"
]

VALID_PRIMARY_FEARS = [
    "social_displacement", "loss_of_autonomy", "annihilation",
    "identity_erasure", "contamination", "isolation"
]

VALID_ANTAGONISTS = [
    "system", "technology", "body", "unknown", "collective", "ghost"
]

VALID_MECHANISMS = [
    "erosion", "confinement", "debt", "impersonation",
    "surveillance", "infection", "exploitation", "possession"
]

# Output schema version
SCHEMA_VERSION = "1.0"
