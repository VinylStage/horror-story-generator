"""
API Services package.

Business logic layer.

Phase B+: Includes Ollama resource management.
"""

from . import research_service, dedup_service, ollama_resource

__all__ = ["research_service", "dedup_service", "ollama_resource"]
