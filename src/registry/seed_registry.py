"""
Seed Registry - SQLite-based tracking for Story Seeds.

Phase B+: Tracks seed usage and availability for story generation.

Schema:
- seed_id: Unique identifier (SS-YYYY-MM-DD-XXX)
- source_card_id: Source research card ID
- created_at: Timestamp
- file_path: Path to seed JSON file
- times_used: Number of times used in story generation
- last_used_at: Last usage timestamp
- is_available: Whether seed is available for use
"""

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

from src.infra.data_paths import get_seed_registry_path

logger = logging.getLogger("horror_story_generator")


@dataclass
class SeedRecord:
    """Seed registry record."""
    seed_id: str
    source_card_id: str
    created_at: datetime
    file_path: Optional[str] = None
    times_used: int = 0
    last_used_at: Optional[datetime] = None
    is_available: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "seed_id": self.seed_id,
            "source_card_id": self.source_card_id,
            "created_at": self.created_at.isoformat(),
            "file_path": self.file_path,
            "times_used": self.times_used,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_available": self.is_available,
        }


class SeedRegistry:
    """
    SQLite-based registry for tracking Story Seeds.

    Supports usage tracking and availability management.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS story_seeds (
        seed_id TEXT PRIMARY KEY,
        source_card_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_path TEXT,
        times_used INTEGER DEFAULT 0,
        last_used_at TIMESTAMP,
        is_available INTEGER DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_seed_created ON story_seeds(created_at);
    CREATE INDEX IF NOT EXISTS idx_seed_source ON story_seeds(source_card_id);
    CREATE INDEX IF NOT EXISTS idx_seed_available ON story_seeds(is_available);
    CREATE INDEX IF NOT EXISTS idx_seed_usage ON story_seeds(times_used);
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the registry.

        Args:
            db_path: Path to SQLite database (uses default if not provided)
        """
        self.db_path = db_path or get_seed_registry_path()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            logger.debug(f"[SeedRegistry] Schema ensured at {self.db_path}")

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def register(
        self,
        seed_id: str,
        source_card_id: str,
        file_path: Optional[str] = None
    ) -> bool:
        """
        Register a new Story Seed.

        Args:
            seed_id: Unique seed identifier
            source_card_id: Source research card ID
            file_path: Path to seed JSON file

        Returns:
            True if registered successfully
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO story_seeds
                    (seed_id, source_card_id, file_path, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (seed_id, source_card_id, file_path, datetime.now().isoformat())
                )
            logger.debug(f"[SeedRegistry] Registered {seed_id}")
            return True
        except Exception as e:
            logger.error(f"[SeedRegistry] Register failed: {e}")
            return False

    def mark_used(self, seed_id: str) -> bool:
        """
        Mark a seed as used (increment usage counter).

        Args:
            seed_id: Seed identifier

        Returns:
            True if updated successfully
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE story_seeds
                    SET times_used = times_used + 1, last_used_at = ?
                    WHERE seed_id = ?
                    """,
                    (datetime.now().isoformat(), seed_id)
                )
            logger.debug(f"[SeedRegistry] Marked {seed_id} as used")
            return True
        except Exception as e:
            logger.error(f"[SeedRegistry] Mark used failed: {e}")
            return False

    def set_availability(self, seed_id: str, is_available: bool) -> bool:
        """Set seed availability status."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE story_seeds SET is_available = ? WHERE seed_id = ?",
                    (int(is_available), seed_id)
                )
            return True
        except Exception as e:
            logger.error(f"[SeedRegistry] Set availability failed: {e}")
            return False

    def get(self, seed_id: str) -> Optional[SeedRecord]:
        """Get a seed record by ID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM story_seeds WHERE seed_id = ?",
                    (seed_id,)
                ).fetchone()

            if row:
                return self._row_to_record(row)
            return None
        except Exception as e:
            logger.error(f"[SeedRegistry] Get failed: {e}")
            return None

    def _row_to_record(self, row: sqlite3.Row) -> SeedRecord:
        """Convert database row to SeedRecord."""
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        last_used_at = row["last_used_at"]
        if isinstance(last_used_at, str):
            last_used_at = datetime.fromisoformat(last_used_at)

        return SeedRecord(
            seed_id=row["seed_id"],
            source_card_id=row["source_card_id"],
            created_at=created_at,
            file_path=row["file_path"],
            times_used=row["times_used"] or 0,
            last_used_at=last_used_at,
            is_available=bool(row["is_available"]),
        )

    def list_available(self, limit: int = 100) -> List[SeedRecord]:
        """List available seeds, ordered by least recently used."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM story_seeds
                    WHERE is_available = 1
                    ORDER BY times_used ASC, last_used_at ASC NULLS FIRST
                    LIMIT ?
                    """,
                    (limit,)
                ).fetchall()

            return [self._row_to_record(row) for row in rows]
        except Exception as e:
            logger.error(f"[SeedRegistry] List available failed: {e}")
            return []

    def list_all(self, limit: int = 100, offset: int = 0) -> List[SeedRecord]:
        """List all seeds with pagination."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM story_seeds
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                ).fetchall()

            return [self._row_to_record(row) for row in rows]
        except Exception as e:
            logger.error(f"[SeedRegistry] List all failed: {e}")
            return []

    def get_least_used(self) -> Optional[SeedRecord]:
        """
        Get the least used available seed.

        Returns:
            Least used seed, or None if no seeds available
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM story_seeds
                    WHERE is_available = 1
                    ORDER BY times_used ASC, last_used_at ASC NULLS FIRST
                    LIMIT 1
                    """
                ).fetchone()

            if row:
                return self._row_to_record(row)
            return None
        except Exception as e:
            logger.error(f"[SeedRegistry] Get least used failed: {e}")
            return None

    def get_by_source_card(self, card_id: str) -> List[SeedRecord]:
        """Get all seeds generated from a specific research card."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM story_seeds
                    WHERE source_card_id = ?
                    ORDER BY created_at DESC
                    """,
                    (card_id,)
                ).fetchall()

            return [self._row_to_record(row) for row in rows]
        except Exception as e:
            logger.error(f"[SeedRegistry] Get by source card failed: {e}")
            return []

    def count(self, available_only: bool = False) -> int:
        """Get count of seeds."""
        try:
            with self._get_connection() as conn:
                if available_only:
                    result = conn.execute(
                        "SELECT COUNT(*) FROM story_seeds WHERE is_available = 1"
                    ).fetchone()
                else:
                    result = conn.execute(
                        "SELECT COUNT(*) FROM story_seeds"
                    ).fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"[SeedRegistry] Count failed: {e}")
            return 0

    def delete(self, seed_id: str) -> bool:
        """Delete a seed record."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM story_seeds WHERE seed_id = ?",
                    (seed_id,)
                )
            logger.debug(f"[SeedRegistry] Deleted {seed_id}")
            return True
        except Exception as e:
            logger.error(f"[SeedRegistry] Delete failed: {e}")
            return False

    def get_stats(self) -> dict:
        """Get registry statistics."""
        try:
            with self._get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM story_seeds").fetchone()[0]
                available = conn.execute(
                    "SELECT COUNT(*) FROM story_seeds WHERE is_available = 1"
                ).fetchone()[0]
                total_uses = conn.execute(
                    "SELECT SUM(times_used) FROM story_seeds"
                ).fetchone()[0] or 0
                never_used = conn.execute(
                    "SELECT COUNT(*) FROM story_seeds WHERE times_used = 0"
                ).fetchone()[0]

            return {
                "total": total,
                "available": available,
                "unavailable": total - available,
                "total_uses": total_uses,
                "never_used": never_used,
            }
        except Exception as e:
            logger.error(f"[SeedRegistry] Stats failed: {e}")
            return {}


# Global registry instance
_registry: Optional[SeedRegistry] = None


def get_seed_registry(db_path: Optional[Path] = None) -> SeedRegistry:
    """
    Get or create global seed registry instance.

    Args:
        db_path: Optional custom database path

    Returns:
        SeedRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = SeedRegistry(db_path=db_path)
    return _registry
