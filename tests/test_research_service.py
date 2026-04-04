"""
Tests for research_service module.

Validates in-process execution path without subprocess CLI calls.
"""

import pytest
from unittest.mock import patch, MagicMock


# Test card ID constants
TEST_CARD_ID = "RC-20260111-120000"


class TestExecuteResearch:
    """Tests for execute_research function."""

    @pytest.mark.asyncio
    async def test_execute_research_success(self):
        """Should execute research pipeline and return card info."""
        from src.api.services.research_service import execute_research

        with patch("src.api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch(
                "src.api.services.research_service.run_research_pipeline",
                return_value={
                    "success": True,
                    "card_id": TEST_CARD_ID,
                    "card_path": "/path/to/card.json",
                },
            ):
                result = await execute_research(
                    topic="Korean horror",
                    tags=["urban", "psychological"],
                    model="qwen3:30b",
                    timeout=300,
                )

                assert result["status"] == "complete"
                assert result["card_id"] == TEST_CARD_ID
                assert result["output_path"] == "/path/to/card.json"

    @pytest.mark.asyncio
    async def test_execute_research_error(self):
        """Should handle pipeline error."""
        from src.api.services.research_service import execute_research

        with patch("src.api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch(
                "src.api.services.research_service.run_research_pipeline",
                return_value={"success": False, "error": "Pipeline failed"},
            ):
                result = await execute_research(topic="Test topic", tags=[])

                assert result["status"] == "error"
                assert "Pipeline failed" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_research_timeout(self):
        """Should map timeout-like errors to timeout status."""
        from src.api.services.research_service import execute_research

        with patch("src.api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch(
                "src.api.services.research_service.run_research_pipeline",
                return_value={"success": False, "error": "Request timed out after 30s"},
            ):
                result = await execute_research(topic="Test", tags=[], timeout=1)

                assert result["status"] == "timeout"
                assert "timed out" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_research_exception(self):
        """Should handle general exception."""
        from src.api.services.research_service import execute_research

        with patch("src.api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch(
                "src.api.services.research_service.run_research_pipeline",
                side_effect=Exception("Process error"),
            ):
                result = await execute_research(topic="Test", tags=[])

                assert result["status"] == "error"
                assert "Process error" in result["message"]


class TestValidateCard:
    """Tests for validate_card function."""

    @pytest.mark.asyncio
    async def test_validate_invalid_card_id(self):
        """Should reject invalid card ID format."""
        from src.api.services.research_service import validate_card

        result = await validate_card("invalid")

        assert result["is_valid"] is False
        assert result["quality_score"] == "invalid_id"

    @pytest.mark.asyncio
    async def test_validate_card_not_found(self):
        """Should handle card file not found."""
        from src.api.services.research_service import validate_card

        with patch("src.api.services.research_service.get_card_by_id", return_value=None):
            result = await validate_card(TEST_CARD_ID)

            assert result["is_valid"] is False
            assert result["quality_score"] == "not_found"

    @pytest.mark.asyncio
    async def test_validate_card_success(self):
        """Should validate card successfully."""
        from src.api.services.research_service import validate_card

        mock_card = {
            "validation": {
                "quality_score": "excellent",
                "parse_error": None,
            }
        }
        with patch("src.api.services.research_service.get_card_by_id", return_value=mock_card):
            result = await validate_card(TEST_CARD_ID)

            assert result["is_valid"] is True
            assert result["quality_score"] == "excellent"

    @pytest.mark.asyncio
    async def test_validate_card_error(self):
        """Should handle invalid validation data."""
        from src.api.services.research_service import validate_card

        mock_card = {"validation": "invalid"}
        with patch("src.api.services.research_service.get_card_by_id", return_value=mock_card):
            result = await validate_card(TEST_CARD_ID)

            assert result["is_valid"] is False
            assert result["quality_score"] == "error"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("quality", ["invalid", "error"])
    async def test_validate_card_invalid_quality(self, quality):
        """Should mark invalid/error quality as not valid."""
        from src.api.services.research_service import validate_card

        mock_card = {"validation": {"quality_score": quality}}
        with patch("src.api.services.research_service.get_card_by_id", return_value=mock_card):
            result = await validate_card(TEST_CARD_ID)
            assert result["is_valid"] is False
            assert result["quality_score"] == quality

    @pytest.mark.asyncio
    async def test_validate_card_parse_error(self):
        """Should mark parse_error as invalid."""
        from src.api.services.research_service import validate_card

        mock_card = {
            "validation": {
                "quality_score": "good",
                "parse_error": "failed to parse",
            }
        }
        with patch("src.api.services.research_service.get_card_by_id", return_value=mock_card):
            result = await validate_card(TEST_CARD_ID)
            assert result["is_valid"] is False
            assert "failed to parse" in result["message"]

    @pytest.mark.asyncio
    async def test_validate_card_exception(self):
        """Should handle exception during validation."""
        from src.api.services.research_service import validate_card

        with patch("src.api.services.research_service.get_card_by_id", side_effect=Exception("Process error")):
            result = await validate_card(TEST_CARD_ID)

            assert result["is_valid"] is False
            assert "Process error" in result["message"]


class TestListCards:
    """Tests for list_cards function."""

    @pytest.mark.asyncio
    async def test_list_cards_success(self):
        """Should list cards successfully."""
        from src.api.services.research_service import list_cards

        mock_cards = [
            {
                "card_id": "RC-20260111-001",
                "output": {"title": "Card One"},
                "input": {"topic": "Topic One"},
                "validation": {"quality_score": "good"},
                "metadata": {"created_at": "2026-01-11T12:00:00Z"},
            },
            {
                "card_id": "RC-20260111-002",
                "output": {"title": "Card Two"},
                "input": {"topic": "Topic Two"},
                "validation": {"quality_score": "excellent"},
                "metadata": {"created_at": "2026-01-11T11:00:00Z"},
            },
        ]

        with patch(
            "src.api.services.research_service.load_all_research_cards",
            return_value=mock_cards,
        ):
            result = await list_cards(limit=10, offset=0)

            assert len(result["cards"]) == 2
            assert result["cards"][0]["card_id"] == "RC-20260111-001"
            assert result["cards"][0]["quality_score"] == "good"

    @pytest.mark.asyncio
    async def test_list_cards_with_quality_filter(self):
        """Should filter cards by quality."""
        from src.api.services.research_service import list_cards

        mock_cards = [
            {
                "card_id": "RC-1",
                "output": {"title": "One"},
                "input": {"topic": "Topic"},
                "validation": {"quality_score": "good"},
                "metadata": {"created_at": "2026-01-11"},
            },
            {
                "card_id": "RC-2",
                "output": {"title": "Two"},
                "input": {"topic": "Topic"},
                "validation": {"quality_score": "excellent"},
                "metadata": {"created_at": "2026-01-10"},
            },
        ]
        with patch(
            "src.api.services.research_service.load_all_research_cards",
            return_value=mock_cards,
        ):
            result = await list_cards(limit=10, offset=0, quality="good")
            assert len(result["cards"]) == 1
            assert result["cards"][0]["card_id"] == "RC-1"
            assert result["cards"][0]["quality_score"] == "good"

    @pytest.mark.asyncio
    async def test_list_cards_exception(self):
        """Should handle exception."""
        from src.api.services.research_service import list_cards

        with patch(
            "src.api.services.research_service.load_all_research_cards",
            side_effect=Exception("Error"),
        ):
            result = await list_cards()

            assert result["cards"] == []
            assert "Error" in result["message"]
