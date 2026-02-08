"""
Infrastructure module - logging, paths, and common utilities.
"""

from .data_paths import (
    get_project_root,
    get_data_root,
    get_research_root,
    get_research_cards_dir,
    get_research_vectors_dir,
    get_faiss_index_path,
    get_vector_metadata_path,
    get_seeds_root,
    get_seed_registry_path,
    get_story_registry_path,
    ensure_data_directories,
)

from .logging_config import setup_logging

__all__ = [
    # data_paths
    "get_project_root",
    "get_data_root",
    "get_research_root",
    "get_research_cards_dir",
    "get_research_vectors_dir",
    "get_faiss_index_path",
    "get_vector_metadata_path",
    "get_seeds_root",
    "get_seed_registry_path",
    "get_story_registry_path",
    "ensure_data_directories",
    # logging
    "setup_logging",
]
