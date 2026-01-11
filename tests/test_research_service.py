"""
Tests for research_service module.

Phase B+: Comprehensive subprocess mocking for 100% coverage.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestExecuteResearch:
    """Tests for execute_research function."""

    @pytest.mark.asyncio
    async def test_execute_research_success(self):
        """Should execute research and return card info."""
        from research_api.services.research_service import execute_research

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(
            b"Card ID: RC-20260111-120000\nTitle: Test Card\nQuality: good\nJSON: /path/to/card.json",
            b""
        ))

        with patch("research_api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.wait_for", return_value=(
                    b"Card ID: RC-20260111-120000\nTitle: Test Card\nQuality: good\nJSON: /path/to/card.json",
                    b""
                )):
                    mock_process.communicate = AsyncMock(return_value=(
                        b"Card ID: RC-20260111-120000\nTitle: Test Card\nQuality: good\nJSON: /path/to/card.json",
                        b""
                    ))
                    result = await execute_research(
                        topic="Korean horror",
                        tags=["urban", "psychological"],
                        model="qwen3:30b",
                        timeout=300
                    )

                    assert result["status"] == "complete"
                    assert result["card_id"] == "RC-20260111-120000"

    @pytest.mark.asyncio
    async def test_execute_research_cli_error(self):
        """Should handle CLI error."""
        from research_api.services.research_service import execute_research

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(
            b"",
            b"Ollama connection failed"
        ))

        with patch("research_api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.wait_for", return_value=(b"", b"Ollama connection failed")):
                    result = await execute_research(
                        topic="Test topic",
                        tags=[]
                    )

                    assert result["status"] == "error"
                    assert "Ollama" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_research_timeout(self):
        """Should handle timeout."""
        from research_api.services.research_service import execute_research
        import asyncio

        with patch("research_api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock):
                with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                    result = await execute_research(
                        topic="Test",
                        tags=[],
                        timeout=1
                    )

                    assert result["status"] == "timeout"
                    assert "timed out" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_research_exception(self):
        """Should handle general exception."""
        from research_api.services.research_service import execute_research

        with patch("research_api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch("asyncio.create_subprocess_exec", side_effect=Exception("Process error")):
                result = await execute_research(
                    topic="Test",
                    tags=[]
                )

                assert result["status"] == "error"
                assert "Process error" in result["message"]

    @pytest.mark.asyncio
    async def test_execute_research_with_model_override(self):
        """Should pass model and timeout to subprocess."""
        from research_api.services.research_service import execute_research

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Card ID: RC-001", b""))

        with patch("research_api.services.research_service.get_resource_manager") as mock_rm:
            mock_rm.return_value = MagicMock()
            with patch("asyncio.create_subprocess_exec", return_value=mock_process) as mock_exec:
                with patch("asyncio.wait_for", return_value=(b"Card ID: RC-001", b"")):
                    await execute_research(
                        topic="Test",
                        tags=["tag1"],
                        model="llama3:8b",
                        timeout=600
                    )

                    # Check that model and timeout were included in cmd
                    call_args = mock_exec.call_args
                    cmd = call_args[0]
                    assert "--model" in cmd
                    assert "llama3:8b" in cmd
                    assert "--timeout" in cmd
                    assert "600" in cmd


class TestParseCliOutput:
    """Tests for parse_cli_output function."""

    def test_parse_full_output(self):
        """Should parse all fields from CLI output."""
        from research_api.services.research_service import parse_cli_output

        output = """Card ID: RC-20260111-120000
Title: The Haunted Apartment
Quality: good
JSON: /data/research/2026/01/RC-20260111-120000.json
Markdown: /data/research/2026/01/RC-20260111-120000.md"""

        result = parse_cli_output(output)

        assert result["card_id"] == "RC-20260111-120000"
        assert result["title"] == "The Haunted Apartment"
        assert result["quality"] == "good"
        assert result["output_path"] == "/data/research/2026/01/RC-20260111-120000.json"

    def test_parse_partial_output(self):
        """Should handle partial output."""
        from research_api.services.research_service import parse_cli_output

        output = "Card ID: RC-001"
        result = parse_cli_output(output)

        assert result["card_id"] == "RC-001"
        assert result["title"] == ""
        assert result["quality"] == ""

    def test_parse_empty_output(self):
        """Should handle empty output."""
        from research_api.services.research_service import parse_cli_output

        result = parse_cli_output("")

        assert result["card_id"] == ""
        assert result["title"] == ""


class TestValidateCard:
    """Tests for validate_card function."""

    @pytest.mark.asyncio
    async def test_validate_invalid_card_id(self):
        """Should reject invalid card ID format."""
        from research_api.services.research_service import validate_card

        result = await validate_card("invalid")

        assert result["is_valid"] is False
        assert result["quality_score"] == "invalid_id"

    @pytest.mark.asyncio
    async def test_validate_card_not_found(self):
        """Should handle card file not found."""
        from research_api.services.research_service import validate_card

        with patch("pathlib.Path.exists", return_value=False):
            result = await validate_card("RC-20260111-120000")

            assert result["is_valid"] is False
            assert result["quality_score"] == "not_found"

    @pytest.mark.asyncio
    async def test_validate_card_success(self):
        """Should validate card successfully."""
        from research_api.services.research_service import validate_card

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(
            b"Validation passed\nquality_score: excellent",
            b""
        ))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.wait_for", return_value=(
                    b"Validation passed\nquality_score: excellent",
                    b""
                )):
                    result = await validate_card("RC-20260111-120000")

                    assert result["is_valid"] is True
                    assert result["quality_score"] == "excellent"

    @pytest.mark.asyncio
    async def test_validate_card_cli_error(self):
        """Should handle CLI validation error."""
        from research_api.services.research_service import validate_card

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(
            b"",
            b"Validation failed: missing required fields"
        ))

        with patch("pathlib.Path.exists", return_value=True):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch("asyncio.wait_for", return_value=(
                    b"",
                    b"Validation failed: missing required fields"
                )):
                    result = await validate_card("RC-20260111-120000")

                    assert result["is_valid"] is False
                    assert result["quality_score"] == "error"

    @pytest.mark.asyncio
    async def test_validate_card_exception(self):
        """Should handle exception during validation."""
        from research_api.services.research_service import validate_card

        with patch("pathlib.Path.exists", return_value=True):
            with patch("asyncio.create_subprocess_exec", side_effect=Exception("Process error")):
                result = await validate_card("RC-20260111-120000")

                assert result["is_valid"] is False
                assert "Process error" in result["message"]


class TestListCards:
    """Tests for list_cards function."""

    @pytest.mark.asyncio
    async def test_list_cards_success(self):
        """Should list cards successfully."""
        from research_api.services.research_service import list_cards

        mock_output = """Research Cards:
RC-20260111-001  2026-01-11  [good]  Card One
RC-20260111-002  2026-01-11  [excellent]  Card Two"""

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(
            mock_output.encode("utf-8"),
            b""
        ))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(mock_output.encode("utf-8"), b"")):
                result = await list_cards(limit=10, offset=0)

                assert len(result["cards"]) == 2
                assert result["cards"][0]["card_id"] == "RC-20260111-001"
                assert result["cards"][0]["quality_score"] == "good"

    @pytest.mark.asyncio
    async def test_list_cards_with_quality_filter(self):
        """Should filter cards by quality."""
        from research_api.services.research_service import list_cards

        mock_output = """RC-20260111-001  2026-01-11  [good]  Card One
RC-20260111-002  2026-01-11  [excellent]  Card Two
RC-20260111-003  2026-01-11  [good]  Card Three"""

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(mock_output.encode("utf-8"), b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(mock_output.encode("utf-8"), b"")):
                result = await list_cards(limit=10, offset=0, quality="good")

                # Should only include cards with quality "good"
                assert all(c["quality_score"] == "good" for c in result["cards"])

    @pytest.mark.asyncio
    async def test_list_cards_cli_error(self):
        """Should handle CLI error."""
        from research_api.services.research_service import list_cards

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"CLI error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(b"", b"CLI error")):
                result = await list_cards()

                assert result["cards"] == []
                assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_cards_exception(self):
        """Should handle exception."""
        from research_api.services.research_service import list_cards

        with patch("asyncio.create_subprocess_exec", side_effect=Exception("Error")):
            result = await list_cards()

            assert result["cards"] == []
            assert "Error" in result["message"]


class TestParseListOutput:
    """Tests for parse_list_output function."""

    def test_parse_list_with_header(self):
        """Should skip header lines."""
        from research_api.services.research_service import parse_list_output

        output = """Research Cards:
================
RC-20260111-001  2026-01-11  [good]  Card One"""

        result = parse_list_output(output, offset=0, limit=10, quality_filter=None)

        assert len(result) == 1
        assert result[0]["card_id"] == "RC-20260111-001"

    def test_parse_list_pagination(self):
        """Should apply pagination."""
        from research_api.services.research_service import parse_list_output

        output = """RC-001  2026-01-11  [good]  Card 1
RC-002  2026-01-11  [good]  Card 2
RC-003  2026-01-11  [good]  Card 3
RC-004  2026-01-11  [good]  Card 4"""

        result = parse_list_output(output, offset=1, limit=2, quality_filter=None)

        assert len(result) == 2
        assert result[0]["card_id"] == "RC-002"
        assert result[1]["card_id"] == "RC-003"

    def test_parse_list_quality_filter(self):
        """Should filter by quality."""
        from research_api.services.research_service import parse_list_output

        output = """RC-001  2026-01-11  [good]  Card 1
RC-002  2026-01-11  [excellent]  Card 2
RC-003  2026-01-11  [good]  Card 3"""

        result = parse_list_output(output, offset=0, limit=10, quality_filter="excellent")

        assert len(result) == 1
        assert result[0]["card_id"] == "RC-002"

    def test_parse_list_short_lines(self):
        """Should skip malformed lines."""
        from research_api.services.research_service import parse_list_output

        output = """RC-001  2026-01-11  [good]  Card 1
RC-002  short
RC-003  2026-01-11  [good]  Card 3"""

        result = parse_list_output(output, offset=0, limit=10, quality_filter=None)

        assert len(result) == 2
