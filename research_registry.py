"""
Research Registry - SQLite-based tracking for research cards.

Phase B+: Tracks research card metadata without blocking execution.

Schema:
- card_id: Unique identifier (RC-YYYY-MM-DD-XXX)
- topic: Research topic
- created_at: Timestamp
- embedding_indexed: Whether embedding is in FAISS
- dedup_score: Highest similarity score to existing cards
- dedup_signal: LOW/MEDIUM/HIGH
- file_path: Path to card JSON file
- status: pending/completed/failed
"""

import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

from data_paths import get_research_registry_path

logger = logging.getLogger("horror_story_generator")


@dataclass
class ResearchCardRecord:
    """Research card registry record."""
    card_id: str
    topic: str
    created_at: datetime
    file_path: Optional[str] = None
    embedding_indexed: bool = False
    dedup_score: float = 0.0
    dedup_signal: str = "LOW"
    status: str = "pending"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "card_id": self.card_id,
            "topic": self.topic,
            "created_at": self.created_at.isoformat(),
            "file_path": self.file_path,
            "embedding_indexed": self.embedding_indexed,
            "dedup_score": self.dedup_score,
            "dedup_signal": self.dedup_signal,
            "status": self.status,
        }


class ResearchRegistry:
    """
    SQLite-based registry for tracking research cards.

    Non-blocking design: All operations are quick SQLite queries.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS research_cards (
        card_id TEXT PRIMARY KEY,
        topic TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_path TEXT,
        embedding_indexed INTEGER DEFAULT 0,
        dedup_score REAL DEFAULT 0.0,
        dedup_signal TEXT DEFAULT 'LOW',
        status TEXT DEFAULT 'pending'
    );

    CREATE INDEX IF NOT EXISTS idx_created_at ON research_cards(created_at);
    CREATE INDEX IF NOT EXISTS idx_status ON research_cards(status);
    CREATE INDEX IF NOT EXISTS idx_dedup_signal ON research_cards(dedup_signal);
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the registry.

        Args:
            db_path: Path to SQLite database (uses default if not provided)
        """
        self.db_path = db_path or get_research_registry_path()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            logger.debug(f"[ResearchRegistry] Schema ensured at {self.db_path}")

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
        card_id: str,
        topic: str,
        file_path: Optional[str] = None,
        status: str = "pending"
    ) -> bool:
        """
        Register a new research card.

        Args:
            card_id: Unique card identifier
            topic: Research topic
            file_path: Path to card JSON file
            status: Initial status

        Returns:
            True if registered successfully
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO research_cards
                    (card_id, topic, file_path, status, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (card_id, topic, file_path, status, datetime.now())
                )
            logger.debug(f"[ResearchRegistry] Registered {card_id}")
            return True
        except Exception as e:
            logger.error(f"[ResearchRegistry] Register failed: {e}")
            return False

    def update_status(self, card_id: str, status: str) -> bool:
        """Update card status."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE research_cards SET status = ? WHERE card_id = ?",
                    (status, card_id)
                )
            return True
        except Exception as e:
            logger.error(f"[ResearchRegistry] Update status failed: {e}")
            return False

    def update_dedup_info(
        self,
        card_id: str,
        dedup_score: float,
        dedup_signal: str,
        embedding_indexed: bool = True
    ) -> bool:
        """
        Update deduplication information for a card.

        Args:
            card_id: Card identifier
            dedup_score: Similarity score
            dedup_signal: Signal level (LOW/MEDIUM/HIGH)
            embedding_indexed: Whether embedding is in FAISS
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE research_cards
                    SET dedup_score = ?, dedup_signal = ?, embedding_indexed = ?
                    WHERE card_id = ?
                    """,
                    (dedup_score, dedup_signal, int(embedding_indexed), card_id)
                )
            logger.debug(f"[ResearchRegistry] Updated dedup for {card_id}: {dedup_signal}")
            return True
        except Exception as e:
            logger.error(f"[ResearchRegistry] Update dedup failed: {e}")
            return False

    def get(self, card_id: str) -> Optional[ResearchCardRecord]:
        """Get a card record by ID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM research_cards WHERE card_id = ?",
                    (card_id,)
                ).fetchone()

            if row:
                return ResearchCardRecord(
                    card_id=row["card_id"],
                    topic=row["topic"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                    file_path=row["file_path"],
                    embedding_indexed=bool(row["embedding_indexed"]),
                    dedup_score=row["dedup_score"] or 0.0,
                    dedup_signal=row["dedup_signal"] or "LOW",
                    status=row["status"] or "pending",
                )
            return None
        except Exception as e:
            logger.error(f"[ResearchRegistry] Get failed: {e}")
            return None

    def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ResearchCardRecord]:
        """
        List research cards with optional filtering.

        Args:
            status: Filter by status
            limit: Maximum records to return
            offset: Offset for pagination
        """
        try:
            with self._get_connection() as conn:
                if status:
                    rows = conn.execute(
                        """
                        SELECT * FROM research_cards
                        WHERE status = ?
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                        """,
                        (status, limit, offset)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM research_cards
                        ORDER BY created_at DESC
                        LIMIT ? OFFSET ?
                        """,
                        (limit, offset)
                    ).fetchall()

            return [
                ResearchCardRecord(
                    card_id=row["card_id"],
                    topic=row["topic"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                    file_path=row["file_path"],
                    embedding_indexed=bool(row["embedding_indexed"]),
                    dedup_score=row["dedup_score"] or 0.0,
                    dedup_signal=row["dedup_signal"] or "LOW",
                    status=row["status"] or "pending",
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"[ResearchRegistry] List failed: {e}")
            return []

    def list_high_similarity(self, threshold: float = 0.85) -> List[ResearchCardRecord]:
        """List cards with high dedup scores."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM research_cards
                    WHERE dedup_score >= ?
                    ORDER BY dedup_score DESC
                    """,
                    (threshold,)
                ).fetchall()

            return [
                ResearchCardRecord(
                    card_id=row["card_id"],
                    topic=row["topic"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                    file_path=row["file_path"],
                    embedding_indexed=bool(row["embedding_indexed"]),
                    dedup_score=row["dedup_score"] or 0.0,
                    dedup_signal=row["dedup_signal"] or "LOW",
                    status=row["status"] or "pending",
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"[ResearchRegistry] List high similarity failed: {e}")
            return []

    def list_not_indexed(self) -> List[ResearchCardRecord]:
        """List cards not yet indexed in FAISS."""
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM research_cards
                    WHERE embedding_indexed = 0 AND status = 'completed'
                    ORDER BY created_at ASC
                    """
                ).fetchall()

            return [
                ResearchCardRecord(
                    card_id=row["card_id"],
                    topic=row["topic"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(),
                    file_path=row["file_path"],
                    embedding_indexed=bool(row["embedding_indexed"]),
                    dedup_score=row["dedup_score"] or 0.0,
                    dedup_signal=row["dedup_signal"] or "LOW",
                    status=row["status"] or "pending",
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"[ResearchRegistry] List not indexed failed: {e}")
            return []

    def count(self, status: Optional[str] = None) -> int:
        """Get count of cards, optionally filtered by status."""
        try:
            with self._get_connection() as conn:
                if status:
                    result = conn.execute(
                        "SELECT COUNT(*) FROM research_cards WHERE status = ?",
                        (status,)
                    ).fetchone()
                else:
                    result = conn.execute(
                        "SELECT COUNT(*) FROM research_cards"
                    ).fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"[ResearchRegistry] Count failed: {e}")
            return 0

    def delete(self, card_id: str) -> bool:
        """Delete a card record."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM research_cards WHERE card_id = ?",
                    (card_id,)
                )
            logger.debug(f"[ResearchRegistry] Deleted {card_id}")
            return True
        except Exception as e:
            logger.error(f"[ResearchRegistry] Delete failed: {e}")
            return False

    def get_stats(self) -> dict:
        """Get registry statistics."""
        try:
            with self._get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM research_cards").fetchone()[0]
                completed = conn.execute(
                    "SELECT COUNT(*) FROM research_cards WHERE status = 'completed'"
                ).fetchone()[0]
                indexed = conn.execute(
                    "SELECT COUNT(*) FROM research_cards WHERE embedding_indexed = 1"
                ).fetchone()[0]
                high_sim = conn.execute(
                    "SELECT COUNT(*) FROM research_cards WHERE dedup_signal = 'HIGH'"
                ).fetchone()[0]

            return {
                "total": total,
                "completed": completed,
                "indexed": indexed,
                "high_similarity": high_sim,
                "not_indexed": completed - indexed,
            }
        except Exception as e:
            logger.error(f"[ResearchRegistry] Stats failed: {e}")
            return {}


# Global registry instance
_registry: Optional[ResearchRegistry] = None


def get_registry(db_path: Optional[Path] = None) -> ResearchRegistry:
    """
    Get or create global registry instance.

    Args:
        db_path: Optional custom database path

    Returns:
        ResearchRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ResearchRegistry(db_path=db_path)
    return _registry
