"""
Phase 2C: Story Registry - SQLite Persistent Storage

This module provides persistent storage for accepted stories,
enabling dedup control across process restarts.

Design principles:
- Minimal schema, extensible for future migrations
- Configurable DB path via environment variable
- No external dependencies (stdlib sqlite3 only)
- Designed for future DB replacement (abstraction layer)
"""

import logging
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_DB_PATH = "./data/story_registry.db"
SCHEMA_VERSION = "1.1.0"  # Added story_signature, canonical_core_json, research_used_json

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class StoryRegistryRecord:
    """Represents a story in the persistent registry."""
    id: str
    created_at: str
    title: Optional[str]
    template_id: Optional[str]
    template_name: Optional[str]
    semantic_summary: str
    similarity_method: str
    accepted: bool
    decision_reason: str
    source_run_id: Optional[str] = None
    # v1.1.0 additions for story-level dedup
    story_signature: Optional[str] = None
    canonical_core_json: Optional[str] = None
    research_used_json: Optional[str] = None


# =============================================================================
# Story Registry Class
# =============================================================================

class StoryRegistry:
    """
    Phase 2C: Persistent story registry using SQLite.

    Provides:
    - Schema versioning for future migrations
    - CRUD operations for story records
    - Load recent stories for dedup comparison

    Designed to allow future replacement with other DBs.
    """

    def __init__(self, db_path: Optional[str] = None, run_id: Optional[str] = None):
        """
        Initialize the story registry.

        Args:
            db_path: Path to SQLite database file. If None, uses env var or default.
            run_id: Unique identifier for this process run.
        """
        self.db_path = db_path or os.getenv("STORY_REGISTRY_DB_PATH", DEFAULT_DB_PATH)
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._conn: Optional[sqlite3.Connection] = None

        logger.info(f"[Phase2C][CONTROL] Story Registry 초기화: {self.db_path}")
        logger.info(f"[Phase2C][CONTROL] Run ID: {self.run_id}")

        self._ensure_directory()
        self._init_db()

    def _ensure_directory(self) -> None:
        """Create parent directory if it doesn't exist."""
        db_dir = Path(self.db_path).parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[Phase2C][CONTROL] 디렉토리 생성: {db_dir}")

    def _backup_before_migration(self, from_version: str) -> Optional[str]:
        """
        Create a one-time backup before schema migration.

        Only called when migration is needed. Uses shutil.copy2 to preserve metadata.

        Args:
            from_version: Version being migrated from

        Returns:
            Backup file path if created, None otherwise
        """
        db_path = Path(self.db_path)
        if not db_path.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{db_path.stem}.backup.{from_version}.{timestamp}{db_path.suffix}"
        backup_path = db_path.parent / backup_name

        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"[RegistryBackup] Backup created at {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.warning(f"[RegistryBackup] Backup failed: {e}")
            return None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """Initialize database schema with version tracking."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create meta table for schema versioning
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Check current schema version
        cursor.execute("SELECT value FROM meta WHERE key = 'schema_version'")
        row = cursor.fetchone()
        current_version = row["value"] if row else None

        if current_version is None:
            # Fresh install - create all tables
            self._create_schema(cursor)
            cursor.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,)
            )
            logger.info(f"[Phase2C][CONTROL] 스키마 생성 완료 (v{SCHEMA_VERSION})")
        elif current_version != SCHEMA_VERSION:
            # Backup before migration
            self._backup_before_migration(current_version)
            # Handle migrations
            self._migrate_schema(cursor, current_version)
            cursor.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (SCHEMA_VERSION,)
            )
            logger.info(f"[Phase2C][CONTROL] 스키마 마이그레이션 완료: {current_version} -> {SCHEMA_VERSION}")
        else:
            logger.info(f"[Phase2C][CONTROL] 스키마 버전 확인: v{current_version}")

        conn.commit()

    def _create_schema(self, cursor: sqlite3.Cursor) -> None:
        """Create the database schema."""
        # Main stories table (v1.1.0 with story-level dedup columns)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                title TEXT,
                template_id TEXT,
                template_name TEXT,
                semantic_summary TEXT NOT NULL,
                similarity_method TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                decision_reason TEXT NOT NULL,
                source_run_id TEXT,
                story_signature TEXT,
                canonical_core_json TEXT,
                research_used_json TEXT
            )
        """)

        # Index for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stories_created_at
            ON stories(created_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stories_accepted
            ON stories(accepted)
        """)

        # v1.1.0: Index for story signature lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stories_signature
            ON stories(story_signature)
        """)

        # Similarity edges table (optional but useful for evidence)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS story_similarity_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                story_id TEXT NOT NULL,
                compared_story_id TEXT NOT NULL,
                similarity_score REAL NOT NULL,
                signal TEXT NOT NULL,
                method TEXT NOT NULL,
                FOREIGN KEY (story_id) REFERENCES stories(id),
                FOREIGN KEY (compared_story_id) REFERENCES stories(id)
            )
        """)

    def _migrate_schema(self, cursor: sqlite3.Cursor, from_version: str) -> None:
        """
        Migrate schema from older version to current.

        Args:
            cursor: Database cursor
            from_version: Version to migrate from
        """
        logger.info(f"[Phase2C][CONTROL] 스키마 마이그레이션 시작: {from_version} -> {SCHEMA_VERSION}")

        if from_version == "1.0.0":
            # Migration from 1.0.0 to 1.1.0
            # Add story-level dedup columns
            try:
                cursor.execute("ALTER TABLE stories ADD COLUMN story_signature TEXT")
                logger.info("[Phase2C][CONTROL] Added column: story_signature")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE stories ADD COLUMN canonical_core_json TEXT")
                logger.info("[Phase2C][CONTROL] Added column: canonical_core_json")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE stories ADD COLUMN research_used_json TEXT")
                logger.info("[Phase2C][CONTROL] Added column: research_used_json")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Add index for signature lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stories_signature
                ON stories(story_signature)
            """)
            logger.info("[Phase2C][CONTROL] Created index: idx_stories_signature")

        else:
            logger.warning(f"[Phase2C][CONTROL] 알 수 없는 버전에서 마이그레이션: {from_version}")

    def add_story(
        self,
        story_id: str,
        title: Optional[str],
        template_id: Optional[str],
        template_name: Optional[str],
        semantic_summary: str,
        accepted: bool,
        decision_reason: str,
        similarity_method: str = "jaccard_summary_v1",
        story_signature: Optional[str] = None,
        canonical_core_json: Optional[str] = None,
        research_used_json: Optional[str] = None
    ) -> None:
        """
        Add a story to the registry.

        Args:
            story_id: Unique story identifier
            title: Story title (if available)
            template_id: Template ID used
            template_name: Template name used
            semantic_summary: Phase 2B semantic summary
            accepted: Whether the story was accepted (True) or skipped (False)
            decision_reason: Reason for the decision
            similarity_method: Method used for similarity comparison
            story_signature: v1.1.0 - SHA256 signature for dedup
            canonical_core_json: v1.1.0 - JSON string of canonical_core
            research_used_json: v1.1.0 - JSON array of research card IDs
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO stories
            (id, created_at, title, template_id, template_name,
             semantic_summary, similarity_method, accepted, decision_reason, source_run_id,
             story_signature, canonical_core_json, research_used_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            story_id,
            datetime.now().isoformat(),
            title,
            template_id,
            template_name,
            semantic_summary,
            similarity_method,
            1 if accepted else 0,
            decision_reason,
            self.run_id,
            story_signature,
            canonical_core_json,
            research_used_json
        ))

        conn.commit()

        status = "ACCEPTED" if accepted else "SKIPPED"
        sig_short = story_signature[:16] if story_signature else "none"
        logger.info(f"[Phase2C][CONTROL] Registry 저장: {story_id} ({status}, sig={sig_short}...)")

    def add_similarity_edge(
        self,
        story_id: str,
        compared_story_id: str,
        similarity_score: float,
        signal: str,
        method: str = "jaccard_summary_v1"
    ) -> None:
        """
        Record a similarity comparison edge.

        Args:
            story_id: The story being compared
            compared_story_id: The story it was compared against
            similarity_score: Numeric similarity score
            signal: Signal level (LOW/MEDIUM/HIGH)
            method: Comparison method used
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO story_similarity_edges
            (created_at, story_id, compared_story_id, similarity_score, signal, method)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            story_id,
            compared_story_id,
            similarity_score,
            signal,
            method
        ))

        conn.commit()

    def load_recent_accepted(self, limit: int = 200) -> List[StoryRegistryRecord]:
        """
        Load the most recent accepted stories for dedup comparison.

        Args:
            limit: Maximum number of stories to load

        Returns:
            List of StoryRegistryRecord objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, title, template_id, template_name,
                   semantic_summary, similarity_method, accepted,
                   decision_reason, source_run_id
            FROM stories
            WHERE accepted = 1
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        records = []

        for row in rows:
            records.append(StoryRegistryRecord(
                id=row["id"],
                created_at=row["created_at"],
                title=row["title"],
                template_id=row["template_id"],
                template_name=row["template_name"],
                semantic_summary=row["semantic_summary"],
                similarity_method=row["similarity_method"],
                accepted=bool(row["accepted"]),
                decision_reason=row["decision_reason"],
                source_run_id=row["source_run_id"]
            ))

        logger.info(f"[Phase2C][CONTROL] 과거 스토리 {len(records)}개 로드 완료")
        return records

    def get_total_count(self) -> Dict[str, int]:
        """Get total counts of accepted and skipped stories."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as cnt FROM stories WHERE accepted = 1")
        accepted = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM stories WHERE accepted = 0")
        skipped = cursor.fetchone()["cnt"]

        return {"accepted": accepted, "skipped": skipped}

    def find_by_signature(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        Find an existing story by its signature.

        Used for story-level dedup to check if a structurally identical
        story already exists.

        Args:
            signature: SHA256 story signature

        Returns:
            Dict with story id and created_at if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, created_at, title, template_id
            FROM stories
            WHERE story_signature = ? AND accepted = 1
            LIMIT 1
        """, (signature,))

        row = cursor.fetchone()
        if row:
            return {
                "id": row["id"],
                "created_at": row["created_at"],
                "title": row["title"],
                "template_id": row["template_id"],
            }

        return None

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("[Phase2C][CONTROL] Registry 연결 종료")


# =============================================================================
# Module-level convenience functions
# =============================================================================

_registry: Optional[StoryRegistry] = None


def init_registry(db_path: Optional[str] = None, run_id: Optional[str] = None) -> StoryRegistry:
    """
    Initialize the global story registry.

    Call this at process start to set up persistent storage.
    """
    global _registry
    _registry = StoryRegistry(db_path=db_path, run_id=run_id)
    return _registry


def get_registry() -> Optional[StoryRegistry]:
    """Get the global story registry instance."""
    return _registry


def close_registry() -> None:
    """Close the global story registry."""
    global _registry
    if _registry:
        _registry.close()
        _registry = None
