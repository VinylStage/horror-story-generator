"""
Infrastructure module - jobs, logging, paths, and common utilities.
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

from .job_manager import (
    Job,
    JobStatus,
    JobType,
    create_job,
    save_job,
    load_job,
    update_job_status,
    list_jobs,
    delete_job,
    get_running_jobs,
    get_queued_jobs,
)

from .job_monitor import (
    is_process_running,
    monitor_job,
    monitor_all_running_jobs,
    cancel_job,
)

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
    # job_manager
    "Job",
    "JobStatus",
    "JobType",
    "create_job",
    "save_job",
    "load_job",
    "update_job_status",
    "list_jobs",
    "delete_job",
    "get_running_jobs",
    "get_queued_jobs",
    # job_monitor
    "is_process_running",
    "monitor_job",
    "monitor_all_running_jobs",
    "cancel_job",
]
