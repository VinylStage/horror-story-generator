"""
API Routers package.

Phase 3: Added scheduler router for independent scheduler control plane.
Phase 4: Added tasks router (/tasks) for scheduler-based task management.
"""

from . import research, dedup, tasks, story, scheduler

__all__ = ["research", "dedup", "tasks", "story", "scheduler"]
