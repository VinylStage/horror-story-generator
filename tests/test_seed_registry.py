"""
Tests for seed_registry module.

Phase B+: SQLite-based seed tracking tests.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestSeedRecord:
    """Tests for SeedRecord dataclass."""

    def test_create_record(self):
        """Should create record with correct fields."""
        from seed_registry import SeedRecord

        record = SeedRecord(
            seed_id="SS-2026-01-11-001",
            source_card_id="RC-2026-01-11-001",
            created_at=datetime.now()
        )

        assert record.seed_id == "SS-2026-01-11-001"
        assert record.source_card_id == "RC-2026-01-11-001"
        assert record.times_used == 0
        assert record.is_available is True

    def test_to_dict(self):
        """Should convert to dictionary."""
        from seed_registry import SeedRecord

        record = SeedRecord(
            seed_id="SS-001",
            source_card_id="RC-001",
            created_at=datetime.now(),
            times_used=5
        )

        d = record.to_dict()

        assert d["seed_id"] == "SS-001"
        assert d["source_card_id"] == "RC-001"
        assert d["times_used"] == 5
        assert "created_at" in d


class TestSeedRegistry:
    """Tests for SeedRegistry class."""

    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry for testing."""
        from seed_registry import SeedRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_seed_registry.sqlite"
            registry = SeedRegistry(db_path=db_path)
            yield registry

    def test_create_registry(self, temp_registry):
        """Should create registry with schema."""
        assert temp_registry.db_path.exists()

    def test_register_seed(self, temp_registry):
        """Should register a new seed."""
        success = temp_registry.register(
            seed_id="SS-2026-01-11-001",
            source_card_id="RC-2026-01-11-001",
            file_path="/path/to/seed.json"
        )

        assert success is True

    def test_get_seed(self, temp_registry):
        """Should retrieve registered seed."""
        temp_registry.register("SS-001", "RC-001")

        record = temp_registry.get("SS-001")

        assert record is not None
        assert record.seed_id == "SS-001"
        assert record.source_card_id == "RC-001"

    def test_get_nonexistent_seed(self, temp_registry):
        """Should return None for nonexistent seed."""
        record = temp_registry.get("SS-NONEXISTENT")
        assert record is None

    def test_mark_used(self, temp_registry):
        """Should increment usage counter."""
        temp_registry.register("SS-001", "RC-001")

        temp_registry.mark_used("SS-001")
        temp_registry.mark_used("SS-001")

        record = temp_registry.get("SS-001")
        assert record.times_used == 2
        assert record.last_used_at is not None

    def test_set_availability(self, temp_registry):
        """Should update availability status."""
        temp_registry.register("SS-001", "RC-001")

        temp_registry.set_availability("SS-001", False)

        record = temp_registry.get("SS-001")
        assert record.is_available is False

    def test_list_available(self, temp_registry):
        """Should list available seeds."""
        temp_registry.register("SS-001", "RC-001")
        temp_registry.register("SS-002", "RC-002")
        temp_registry.register("SS-003", "RC-003")

        temp_registry.set_availability("SS-002", False)

        records = temp_registry.list_available()

        assert len(records) == 2
        seed_ids = [r.seed_id for r in records]
        assert "SS-002" not in seed_ids

    def test_list_all(self, temp_registry):
        """Should list all seeds."""
        temp_registry.register("SS-001", "RC-001")
        temp_registry.register("SS-002", "RC-002")

        records = temp_registry.list_all()

        assert len(records) == 2

    def test_get_least_used(self, temp_registry):
        """Should return least used seed."""
        temp_registry.register("SS-001", "RC-001")
        temp_registry.register("SS-002", "RC-002")
        temp_registry.register("SS-003", "RC-003")

        temp_registry.mark_used("SS-001")
        temp_registry.mark_used("SS-001")
        temp_registry.mark_used("SS-003")

        record = temp_registry.get_least_used()

        assert record is not None
        assert record.seed_id == "SS-002"  # Never used

    def test_get_by_source_card(self, temp_registry):
        """Should find seeds by source card."""
        temp_registry.register("SS-001", "RC-001")
        temp_registry.register("SS-002", "RC-001")
        temp_registry.register("SS-003", "RC-002")

        records = temp_registry.get_by_source_card("RC-001")

        assert len(records) == 2
        for record in records:
            assert record.source_card_id == "RC-001"

    def test_count(self, temp_registry):
        """Should count seeds."""
        temp_registry.register("SS-001", "RC-001")
        temp_registry.register("SS-002", "RC-002")
        temp_registry.set_availability("SS-002", False)

        total = temp_registry.count()
        available = temp_registry.count(available_only=True)

        assert total == 2
        assert available == 1

    def test_delete(self, temp_registry):
        """Should delete seed."""
        temp_registry.register("SS-001", "RC-001")

        success = temp_registry.delete("SS-001")

        assert success is True
        assert temp_registry.get("SS-001") is None

    def test_get_stats(self, temp_registry):
        """Should return statistics."""
        temp_registry.register("SS-001", "RC-001")
        temp_registry.register("SS-002", "RC-002")
        temp_registry.register("SS-003", "RC-003")

        temp_registry.mark_used("SS-001")
        temp_registry.mark_used("SS-001")
        temp_registry.set_availability("SS-003", False)

        stats = temp_registry.get_stats()

        assert stats["total"] == 3
        assert stats["available"] == 2
        assert stats["unavailable"] == 1
        assert stats["total_uses"] == 2
        assert stats["never_used"] == 2  # SS-002 and SS-003


class TestGetSeedRegistry:
    """Tests for get_seed_registry function."""

    def test_returns_registry_instance(self):
        """Should return SeedRegistry instance."""
        from seed_registry import get_seed_registry, SeedRegistry

        registry = get_seed_registry()
        assert isinstance(registry, SeedRegistry)

    def test_returns_same_instance(self):
        """Should return same instance on multiple calls."""
        from seed_registry import get_seed_registry

        registry1 = get_seed_registry()
        registry2 = get_seed_registry()

        assert registry1 is registry2
