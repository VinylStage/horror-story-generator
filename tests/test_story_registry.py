"""Tests for StoryRegistry - SQLite persistent storage for stories."""

import json
import os
import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.registry.story_registry import (
    StoryRegistry,
    StoryRegistryRecord,
    init_registry,
    get_registry,
    close_registry,
    SCHEMA_VERSION,
)


class TestStoryRegistryInit:
    """Test StoryRegistry initialization."""

    def test_init_creates_db_file(self, tmp_path):
        """Test that initialization creates the database file."""
        db_path = str(tmp_path / "test_registry.db")
        registry = StoryRegistry(db_path=db_path)

        assert Path(db_path).exists()
        registry.close()

    def test_init_creates_parent_directory(self, tmp_path):
        """Test that initialization creates parent directories if needed."""
        nested_path = tmp_path / "nested" / "dir" / "test.db"
        registry = StoryRegistry(db_path=str(nested_path))

        assert nested_path.parent.exists()
        assert nested_path.exists()
        registry.close()

    def test_init_with_custom_run_id(self, tmp_path):
        """Test initialization with a custom run ID."""
        db_path = str(tmp_path / "test.db")
        registry = StoryRegistry(db_path=db_path, run_id="custom_run_123")

        assert registry.run_id == "custom_run_123"
        registry.close()

    def test_init_uses_env_var_for_db_path(self, tmp_path):
        """Test that DB path can be set via environment variable."""
        env_db_path = str(tmp_path / "env_registry.db")

        with patch.dict(os.environ, {"STORY_REGISTRY_DB_PATH": env_db_path}):
            registry = StoryRegistry()
            assert registry.db_path == env_db_path
            registry.close()

    def test_schema_version_is_set(self, tmp_path):
        """Test that schema version is recorded in meta table."""
        db_path = str(tmp_path / "test.db")
        registry = StoryRegistry(db_path=db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM meta WHERE key = 'schema_version'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == SCHEMA_VERSION
        registry.close()


class TestStoryRegistryAddStory:
    """Test adding stories to the registry."""

    @pytest.fixture
    def registry(self, tmp_path):
        """Create a temporary registry for testing."""
        db_path = str(tmp_path / "test.db")
        reg = StoryRegistry(db_path=db_path, run_id="test_run")
        yield reg
        reg.close()

    def test_add_accepted_story(self, registry):
        """Test adding an accepted story."""
        registry.add_story(
            story_id="story_001",
            title="Test Horror Story",
            template_id="tmpl_001",
            template_name="Haunted House",
            semantic_summary="A scary story about ghosts",
            accepted=True,
            decision_reason="Unique story",
        )

        # Verify story was added
        conn = sqlite3.connect(registry.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stories WHERE id = ?", ("story_001",))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["title"] == "Test Horror Story"
        assert row["accepted"] == 1
        assert row["source_run_id"] == "test_run"

    def test_add_skipped_story(self, registry):
        """Test adding a skipped story."""
        registry.add_story(
            story_id="story_002",
            title="Duplicate Story",
            template_id="tmpl_001",
            template_name="Haunted House",
            semantic_summary="Similar to existing",
            accepted=False,
            decision_reason="Too similar to story_001",
        )

        conn = sqlite3.connect(registry.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT accepted FROM stories WHERE id = ?", ("story_002",))
        row = cursor.fetchone()
        conn.close()

        assert row["accepted"] == 0

    def test_add_story_with_signature_and_canonical_core(self, registry):
        """Test adding a story with v1.1.0 fields."""
        canonical_core = {"setting": "urban", "fear": "isolation"}
        research_used = ["RC-001", "RC-002"]

        registry.add_story(
            story_id="story_003",
            title="Modern Horror",
            template_id="tmpl_002",
            template_name="Urban Legend",
            semantic_summary="City horror story",
            accepted=True,
            decision_reason="Unique",
            story_signature="abc123def456",
            canonical_core_json=json.dumps(canonical_core),
            research_used_json=json.dumps(research_used),
        )

        conn = sqlite3.connect(registry.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT story_signature, canonical_core_json FROM stories WHERE id = ?", ("story_003",))
        row = cursor.fetchone()
        conn.close()

        assert row["story_signature"] == "abc123def456"
        assert json.loads(row["canonical_core_json"]) == canonical_core

    def test_add_story_replaces_existing(self, registry):
        """Test that adding a story with same ID replaces the existing one."""
        registry.add_story(
            story_id="story_replace",
            title="Original Title",
            template_id="tmpl_001",
            template_name="Test",
            semantic_summary="Original",
            accepted=True,
            decision_reason="First add",
        )

        registry.add_story(
            story_id="story_replace",
            title="Updated Title",
            template_id="tmpl_001",
            template_name="Test",
            semantic_summary="Updated",
            accepted=False,
            decision_reason="Second add",
        )

        conn = sqlite3.connect(registry.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT title, accepted FROM stories WHERE id = ?", ("story_replace",))
        row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) as cnt FROM stories WHERE id = ?", ("story_replace",))
        count = cursor.fetchone()["cnt"]
        conn.close()

        assert count == 1
        assert row["title"] == "Updated Title"
        assert row["accepted"] == 0


class TestStoryRegistrySimilarityEdge:
    """Test similarity edge recording."""

    @pytest.fixture
    def registry(self, tmp_path):
        """Create a temporary registry for testing."""
        db_path = str(tmp_path / "test.db")
        reg = StoryRegistry(db_path=db_path)
        yield reg
        reg.close()

    def test_add_similarity_edge(self, registry):
        """Test adding a similarity edge between stories."""
        # First add some stories
        registry.add_story(
            story_id="story_a",
            title="Story A",
            template_id=None,
            template_name=None,
            semantic_summary="First story",
            accepted=True,
            decision_reason="Unique",
        )
        registry.add_story(
            story_id="story_b",
            title="Story B",
            template_id=None,
            template_name=None,
            semantic_summary="Second story",
            accepted=True,
            decision_reason="Unique",
        )

        # Add similarity edge
        registry.add_similarity_edge(
            story_id="story_b",
            compared_story_id="story_a",
            similarity_score=0.75,
            signal="MEDIUM",
            method="jaccard_v1",
        )

        # Verify edge was added
        conn = sqlite3.connect(registry.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM story_similarity_edges
            WHERE story_id = ? AND compared_story_id = ?
        """, ("story_b", "story_a"))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row["similarity_score"] == 0.75
        assert row["signal"] == "MEDIUM"
        assert row["method"] == "jaccard_v1"


class TestStoryRegistryQueries:
    """Test query methods."""

    @pytest.fixture
    def registry_with_data(self, tmp_path):
        """Create a registry with test data."""
        db_path = str(tmp_path / "test.db")
        reg = StoryRegistry(db_path=db_path)

        # Add multiple stories
        for i in range(5):
            reg.add_story(
                story_id=f"story_{i:03d}",
                title=f"Story {i}",
                template_id=f"tmpl_{i % 2}",
                template_name=f"Template {i % 2}",
                semantic_summary=f"Summary for story {i}",
                accepted=(i % 2 == 0),  # Even IDs are accepted
                decision_reason="Test reason",
                story_signature=f"sig_{i:03d}" if i < 3 else None,
            )

        yield reg
        reg.close()

    def test_load_recent_accepted(self, registry_with_data):
        """Test loading recent accepted stories."""
        records = registry_with_data.load_recent_accepted(limit=10)

        # Only accepted stories (even IDs: 0, 2, 4)
        assert len(records) == 3
        assert all(r.accepted for r in records)

    def test_load_recent_accepted_respects_limit(self, registry_with_data):
        """Test that limit is respected."""
        records = registry_with_data.load_recent_accepted(limit=2)
        assert len(records) == 2

    def test_load_recent_accepted_returns_records(self, registry_with_data):
        """Test that returned objects are StoryRegistryRecord instances."""
        records = registry_with_data.load_recent_accepted(limit=1)

        assert len(records) == 1
        record = records[0]
        assert isinstance(record, StoryRegistryRecord)
        assert record.id is not None
        assert record.semantic_summary is not None

    def test_get_total_count(self, registry_with_data):
        """Test getting total counts."""
        counts = registry_with_data.get_total_count()

        assert counts["accepted"] == 3  # 0, 2, 4
        assert counts["skipped"] == 2   # 1, 3

    def test_find_by_signature_found(self, registry_with_data):
        """Test finding a story by its signature."""
        result = registry_with_data.find_by_signature("sig_000")

        assert result is not None
        assert result["id"] == "story_000"

    def test_find_by_signature_not_found(self, registry_with_data):
        """Test finding a non-existent signature."""
        result = registry_with_data.find_by_signature("nonexistent_sig")

        assert result is None

    def test_find_by_signature_only_accepted(self, registry_with_data):
        """Test that find_by_signature only returns accepted stories."""
        # story_001 has sig_001 but is not accepted (odd ID)
        result = registry_with_data.find_by_signature("sig_001")

        assert result is None


class TestStoryRegistryMigration:
    """Test schema migration functionality."""

    def test_migration_from_1_0_0(self, tmp_path):
        """Test migration from schema version 1.0.0 to current."""
        db_path = str(tmp_path / "test_migration.db")

        # Create a v1.0.0 database manually
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create meta table with old version
        cursor.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '1.0.0')")

        # Create old schema without v1.1.0 columns
        cursor.execute("""
            CREATE TABLE stories (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                title TEXT,
                template_id TEXT,
                template_name TEXT,
                semantic_summary TEXT NOT NULL,
                similarity_method TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                decision_reason TEXT NOT NULL,
                source_run_id TEXT
            )
        """)

        # Add a test story
        cursor.execute("""
            INSERT INTO stories (id, created_at, title, template_id, template_name,
                               semantic_summary, similarity_method, accepted, decision_reason)
            VALUES ('old_story', '2024-01-01T00:00:00', 'Old Story', 'tmpl', 'Template',
                   'Summary', 'jaccard', 1, 'Test')
        """)

        conn.commit()
        conn.close()

        # Now open with StoryRegistry which should trigger migration
        registry = StoryRegistry(db_path=db_path)

        # Verify migration completed
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check version was updated
        cursor.execute("SELECT value FROM meta WHERE key = 'schema_version'")
        version = cursor.fetchone()["value"]
        assert version == SCHEMA_VERSION

        # Check new columns exist by inserting with them
        registry.add_story(
            story_id="new_story",
            title="New Story",
            template_id="tmpl",
            template_name="Template",
            semantic_summary="Summary",
            accepted=True,
            decision_reason="Test",
            story_signature="test_sig",
            canonical_core_json='{"test": true}',
            research_used_json='["RC-001"]',
        )

        cursor.execute("SELECT story_signature FROM stories WHERE id = 'new_story'")
        row = cursor.fetchone()
        assert row["story_signature"] == "test_sig"

        conn.close()
        registry.close()

    def test_backup_created_before_migration(self, tmp_path):
        """Test that backup is created before migration."""
        db_path = str(tmp_path / "test_backup.db")

        # Create a v1.0.0 database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '1.0.0')")
        cursor.execute("""
            CREATE TABLE stories (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                title TEXT,
                template_id TEXT,
                template_name TEXT,
                semantic_summary TEXT NOT NULL,
                similarity_method TEXT NOT NULL,
                accepted INTEGER NOT NULL,
                decision_reason TEXT NOT NULL,
                source_run_id TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Open registry to trigger migration
        registry = StoryRegistry(db_path=db_path)
        registry.close()

        # Check backup file exists
        backup_files = list(tmp_path.glob("*.backup.1.0.0.*"))
        assert len(backup_files) == 1


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_init_and_get_registry(self, tmp_path):
        """Test init_registry and get_registry functions."""
        db_path = str(tmp_path / "global_test.db")

        # Initialize
        reg = init_registry(db_path=db_path, run_id="global_run")

        # Get should return the same instance
        retrieved = get_registry()
        assert retrieved is reg
        assert retrieved.run_id == "global_run"

        # Clean up
        close_registry()

    def test_close_registry(self, tmp_path):
        """Test close_registry function."""
        db_path = str(tmp_path / "close_test.db")

        init_registry(db_path=db_path)
        close_registry()

        # After close, get should return None
        assert get_registry() is None

    def test_close_registry_when_none(self):
        """Test close_registry when no registry is initialized."""
        # Ensure no registry exists
        close_registry()

        # Should not raise
        close_registry()
        assert get_registry() is None


class TestStoryRegistryClose:
    """Test connection closing."""

    def test_close_connection(self, tmp_path):
        """Test that close properly closes the connection."""
        db_path = str(tmp_path / "test.db")
        registry = StoryRegistry(db_path=db_path)

        # Verify connection exists
        assert registry._conn is not None

        registry.close()

        # Connection should be None after close
        assert registry._conn is None

    def test_close_twice_is_safe(self, tmp_path):
        """Test that closing twice doesn't raise an error."""
        db_path = str(tmp_path / "test.db")
        registry = StoryRegistry(db_path=db_path)

        registry.close()
        registry.close()  # Should not raise

        assert registry._conn is None
