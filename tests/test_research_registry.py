"""
Tests for research_registry module.

Phase B+: SQLite-based research card tracking tests.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestResearchCardRecord:
    """Tests for ResearchCardRecord dataclass."""

    def test_create_record(self):
        """Should create record with correct fields."""
        from research_registry import ResearchCardRecord

        record = ResearchCardRecord(
            card_id="RC-2026-01-11-001",
            topic="Test Topic",
            created_at=datetime.now()
        )

        assert record.card_id == "RC-2026-01-11-001"
        assert record.topic == "Test Topic"
        assert record.embedding_indexed is False
        assert record.dedup_score == 0.0
        assert record.dedup_signal == "LOW"
        assert record.status == "pending"

    def test_to_dict(self):
        """Should convert to dictionary."""
        from research_registry import ResearchCardRecord

        now = datetime.now()
        record = ResearchCardRecord(
            card_id="RC-001",
            topic="Test",
            created_at=now,
            dedup_score=0.75,
            dedup_signal="MEDIUM"
        )

        d = record.to_dict()

        assert d["card_id"] == "RC-001"
        assert d["topic"] == "Test"
        assert d["dedup_score"] == 0.75
        assert d["dedup_signal"] == "MEDIUM"
        assert "created_at" in d


class TestResearchRegistry:
    """Tests for ResearchRegistry class."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry for testing."""
        from research_registry import ResearchRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_registry.sqlite"
            registry = ResearchRegistry(db_path=db_path)
            yield registry

    def test_create_registry(self, temp_registry):
        """Should create registry with schema."""
        assert temp_registry.db_path.exists()

    def test_register_card(self, temp_registry):
        """Should register a new card."""
        success = temp_registry.register(
            card_id="RC-2026-01-11-001",
            topic="Test Topic",
            file_path="/path/to/card.json",
            status="completed"
        )

        assert success is True

    def test_get_card(self, temp_registry):
        """Should retrieve registered card."""
        temp_registry.register("RC-001", "Topic 1")

        record = temp_registry.get("RC-001")

        assert record is not None
        assert record.card_id == "RC-001"
        assert record.topic == "Topic 1"

    def test_get_nonexistent_card(self, temp_registry):
        """Should return None for nonexistent card."""
        record = temp_registry.get("RC-NONEXISTENT")
        assert record is None

    def test_update_status(self, temp_registry):
        """Should update card status."""
        temp_registry.register("RC-001", "Topic")

        success = temp_registry.update_status("RC-001", "completed")

        assert success is True
        record = temp_registry.get("RC-001")
        assert record.status == "completed"

    def test_update_dedup_info(self, temp_registry):
        """Should update dedup information."""
        temp_registry.register("RC-001", "Topic")

        success = temp_registry.update_dedup_info(
            card_id="RC-001",
            dedup_score=0.85,
            dedup_signal="HIGH",
            embedding_indexed=True
        )

        assert success is True
        record = temp_registry.get("RC-001")
        assert record.dedup_score == 0.85
        assert record.dedup_signal == "HIGH"
        assert record.embedding_indexed is True

    def test_list_all(self, temp_registry):
        """Should list all cards."""
        temp_registry.register("RC-001", "Topic 1")
        temp_registry.register("RC-002", "Topic 2")
        temp_registry.register("RC-003", "Topic 3")

        records = temp_registry.list_all()

        assert len(records) == 3

    def test_list_all_with_limit(self, temp_registry):
        """Should respect limit parameter."""
        for i in range(5):
            temp_registry.register(f"RC-{i:03d}", f"Topic {i}")

        records = temp_registry.list_all(limit=3)

        assert len(records) == 3

    def test_list_all_with_status_filter(self, temp_registry):
        """Should filter by status."""
        temp_registry.register("RC-001", "Topic 1", status="completed")
        temp_registry.register("RC-002", "Topic 2", status="pending")
        temp_registry.register("RC-003", "Topic 3", status="completed")

        records = temp_registry.list_all(status="completed")

        assert len(records) == 2
        for record in records:
            assert record.status == "completed"

    def test_list_high_similarity(self, temp_registry):
        """Should list high similarity cards."""
        temp_registry.register("RC-001", "Topic 1")
        temp_registry.register("RC-002", "Topic 2")

        temp_registry.update_dedup_info("RC-001", 0.90, "HIGH")
        temp_registry.update_dedup_info("RC-002", 0.50, "LOW")

        records = temp_registry.list_high_similarity()

        assert len(records) == 1
        assert records[0].card_id == "RC-001"

    def test_list_not_indexed(self, temp_registry):
        """Should list cards not indexed in FAISS."""
        temp_registry.register("RC-001", "Topic 1", status="completed")
        temp_registry.register("RC-002", "Topic 2", status="completed")

        temp_registry.update_dedup_info("RC-001", 0.5, "LOW", embedding_indexed=True)
        # RC-002 remains not indexed

        records = temp_registry.list_not_indexed()

        assert len(records) == 1
        assert records[0].card_id == "RC-002"

    def test_count(self, temp_registry):
        """Should count cards."""
        temp_registry.register("RC-001", "Topic 1", status="completed")
        temp_registry.register("RC-002", "Topic 2", status="pending")

        total = temp_registry.count()
        completed = temp_registry.count(status="completed")

        assert total == 2
        assert completed == 1

    def test_delete(self, temp_registry):
        """Should delete card."""
        temp_registry.register("RC-001", "Topic")

        success = temp_registry.delete("RC-001")

        assert success is True
        assert temp_registry.get("RC-001") is None

    def test_get_stats(self, temp_registry):
        """Should return statistics."""
        temp_registry.register("RC-001", "Topic 1", status="completed")
        temp_registry.register("RC-002", "Topic 2", status="completed")
        temp_registry.register("RC-003", "Topic 3", status="pending")

        temp_registry.update_dedup_info("RC-001", 0.5, "LOW", embedding_indexed=True)
        temp_registry.update_dedup_info("RC-002", 0.90, "HIGH", embedding_indexed=True)

        stats = temp_registry.get_stats()

        assert stats["total"] == 3
        assert stats["completed"] == 2
        assert stats["indexed"] == 2
        assert stats["high_similarity"] == 1
        assert stats["not_indexed"] == 0


class TestGetRegistry:
    """Tests for get_registry function."""

    def test_returns_registry_instance(self):
        """Should return ResearchRegistry instance."""
        from research_registry import get_registry, ResearchRegistry

        registry = get_registry()
        assert isinstance(registry, ResearchRegistry)

    def test_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        from research_registry import get_registry

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2
