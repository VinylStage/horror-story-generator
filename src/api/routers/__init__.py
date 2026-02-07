"""
API Routers package.

Phase 3: Added scheduler router for independent scheduler control plane.
Phase 4: Added tasks router (/tasks); /jobs kept for legacy endpoints.
"""

from . import research, dedup, jobs, tasks, story, scheduler

__all__ = ["research", "dedup", "jobs", "tasks", "story", "scheduler"]
