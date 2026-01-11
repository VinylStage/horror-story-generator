"""
Tests for embedder module with comprehensive mocking.

Phase B+: Tests Ollama embedding generation with mocked HTTP calls.
"""

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestOllamaEmbedderSync:
    """Sync embedding tests with mocked HTTP."""

    def test_get_embedding_success(self):
        """Should get embedding via mocked Ollama API."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        # Mock urllib response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "embeddings": [[0.1, 0.2, 0.3] * 100]  # 300-dim vector
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = embedder.get_embedding("Test text for embedding")

            assert result is not None
            assert len(result) == 300
            assert embedder.dimension == 300

    def test_get_embedding_empty_text(self):
        """Should return None for empty text."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        result = embedder.get_embedding("")
        assert result is None

        result = embedder.get_embedding("   ")
        assert result is None

    def test_get_embedding_connection_error(self):
        """Should handle connection error gracefully."""
        from src.dedup.research.embedder import OllamaEmbedder
        import urllib.error

        embedder = OllamaEmbedder()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            result = embedder.get_embedding("Test text")

            assert result is None

    def test_get_embedding_invalid_json(self):
        """Should handle invalid JSON response."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = embedder.get_embedding("Test text")

            assert result is None

    def test_get_embedding_no_embeddings_in_response(self):
        """Should handle response without embeddings field."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "model": "qwen3:30b",
            "created_at": "2026-01-11T12:00:00Z"
            # No embeddings field
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = embedder.get_embedding("Test text")

            assert result is None

    def test_get_embedding_fallback_field(self):
        """Should use 'embedding' field as fallback."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "embedding": [0.5, 0.6, 0.7]  # Single vector format
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = embedder.get_embedding("Test text")

            assert result is not None
            assert result == [0.5, 0.6, 0.7]

    def test_get_embeddings_batch(self):
        """Should get embeddings for batch of texts."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        def mock_urlopen(*args, **kwargs):
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({
                "embeddings": [[0.1] * 100]
            }).encode("utf-8")
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            texts = ["Text 1", "Text 2", "Text 3"]
            results = embedder.get_embeddings_batch(texts)

            assert len(results) == 3
            for result in results:
                assert result is not None
                assert len(result) == 100

    def test_is_available_true(self):
        """Should return True when Ollama is available."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder(model="qwen3:30b")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [{"name": "qwen3:30b"}, {"name": "llama3:8b"}]
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = embedder.is_available()

            assert result is True

    def test_is_available_false(self):
        """Should return False when model not in Ollama."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder(model="nonexistent:model")

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [{"name": "qwen3:30b"}]
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = embedder.is_available()

            assert result is False

    def test_is_available_connection_error(self):
        """Should return False on connection error."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")

            result = embedder.is_available()

            assert result is False


class TestOllamaEmbedderAsync:
    """Async embedding tests with mocked httpx."""

    @pytest.mark.asyncio
    async def test_get_embedding_async_success(self):
        """Should get embedding asynchronously via httpx."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2, 0.3] * 100]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await embedder.get_embedding_async("Test text")

            assert result is not None
            assert len(result) == 300

    @pytest.mark.asyncio
    async def test_get_embedding_async_empty_text(self):
        """Should return None for empty text."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        result = await embedder.get_embedding_async("")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_embedding_async_http_error(self):
        """Should handle HTTP error gracefully."""
        from src.dedup.research.embedder import OllamaEmbedder
        import httpx

        embedder = OllamaEmbedder()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())
            )
            mock_client.return_value = mock_instance

            result = await embedder.get_embedding_async("Test text")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_embedding_async_request_error(self):
        """Should handle request error gracefully."""
        from src.dedup.research.embedder import OllamaEmbedder
        import httpx

        embedder = OllamaEmbedder()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.RequestError("Connection refused")
            )
            mock_client.return_value = mock_instance

            result = await embedder.get_embedding_async("Test text")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_embeddings_batch_async(self):
        """Should get batch embeddings concurrently."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder()

        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1] * 50]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            texts = ["Text 1", "Text 2", "Text 3", "Text 4", "Text 5"]
            results = await embedder.get_embeddings_batch_async(texts, max_concurrent=2)

            assert len(results) == 5
            for result in results:
                assert result is not None

    @pytest.mark.asyncio
    async def test_is_available_async(self):
        """Should check availability asynchronously."""
        from src.dedup.research.embedder import OllamaEmbedder

        embedder = OllamaEmbedder(model="qwen3:30b")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "qwen3:30b"}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await embedder.is_available_async()

            assert result is True


class TestGetEmbeddingFunctions:
    """Tests for module-level embedding functions."""

    def test_get_embedding_function(self):
        """Should use global embedder instance."""
        from src.dedup.research.embedder import get_embedding

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "embeddings": [[0.1] * 100]
        }).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = get_embedding("Test text")

            assert result is not None

    @pytest.mark.asyncio
    async def test_get_embedding_async_function(self):
        """Should use global embedder for async."""
        from src.dedup.research.embedder import get_embedding_async

        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1] * 100]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await get_embedding_async("Test text")

            assert result is not None

    def test_get_embedder_singleton(self):
        """Should return same embedder instance for same model."""
        from src.dedup.research.embedder import get_embedder
        import src.dedup.research.embedder as module

        # Reset global state
        module._embedder = None

        embedder1 = get_embedder("qwen3:30b")
        embedder2 = get_embedder("qwen3:30b")

        assert embedder1 is embedder2

        # Different model creates new instance
        embedder3 = get_embedder("llama3:8b")
        assert embedder3 is not embedder1

        # Cleanup
        module._embedder = None


class TestCreateCardTextForEmbedding:
    """Tests for card text extraction function."""

    def test_full_card_data(self):
        """Should extract all fields from full card."""
        from src.dedup.research.embedder import create_card_text_for_embedding

        card_data = {
            "input": {"topic": "Korean apartment horror"},
            "output": {
                "title": "The Walls That Listen",
                "summary": "An exploration of paranoia in dense urban living",
                "key_concepts": ["surveillance", "paranoia", "isolation"],
                "horror_applications": ["eerie neighbor sounds", "thin walls as threat"]
            }
        }

        result = create_card_text_for_embedding(card_data)

        assert "Topic: Korean apartment horror" in result
        assert "Title: The Walls That Listen" in result
        assert "Summary: An exploration" in result
        assert "Concepts: surveillance, paranoia, isolation" in result
        assert "Applications: eerie neighbor sounds; thin walls as threat" in result

    def test_partial_card_data(self):
        """Should handle partial card data."""
        from src.dedup.research.embedder import create_card_text_for_embedding

        card_data = {
            "input": {"topic": "Test Topic"}
            # No output section
        }

        result = create_card_text_for_embedding(card_data)

        assert "Topic: Test Topic" in result
        assert "Title:" not in result

    def test_output_only(self):
        """Should handle output-only card."""
        from src.dedup.research.embedder import create_card_text_for_embedding

        card_data = {
            "output": {
                "title": "Test Title",
                "summary": "Test Summary"
            }
        }

        result = create_card_text_for_embedding(card_data)

        assert "Title: Test Title" in result
        assert "Summary: Test Summary" in result
        assert "Topic:" not in result
