"""
Tests for logging_config module.
"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.infra.logging_config import DailyRotatingFileHandler, setup_logging


class TestDailyRotatingFileHandler:
    """Tests for DailyRotatingFileHandler class."""

    def test_handler_creates_log_directory(self, tmp_path):
        """Test that handler creates log directory if it doesn't exist."""
        log_dir = tmp_path / "new_logs"
        assert not log_dir.exists()

        handler = DailyRotatingFileHandler(log_dir=str(log_dir))
        assert log_dir.exists()
        handler.close()

    def test_handler_creates_log_file(self, tmp_path):
        """Test that handler creates a log file with correct naming."""
        handler = DailyRotatingFileHandler(log_dir=str(tmp_path))

        log_files = list(tmp_path.glob("horror_story_*.log"))
        assert len(log_files) == 1

        # Verify filename pattern
        filename = log_files[0].name
        assert filename.startswith("horror_story_")
        assert filename.endswith(".log")
        handler.close()

    def test_handler_emits_record(self, tmp_path):
        """Test that handler writes log records to file."""
        handler = DailyRotatingFileHandler(log_dir=str(tmp_path))
        handler.setFormatter(logging.Formatter('%(message)s'))

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None
        )
        handler.emit(record)
        handler.close()

        log_files = list(tmp_path.glob("horror_story_*.log"))
        assert len(log_files) == 1

        content = log_files[0].read_text()
        assert "Test message" in content


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_returns_logger(self):
        """Test that setup_logging returns a logger instance."""
        test_logger = logging.getLogger("horror_story_generator")
        test_logger.handlers.clear()

        logger = setup_logging("INFO")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "horror_story_generator"

        logger.handlers.clear()

    def test_sets_correct_log_level(self):
        """Test that setup_logging sets the correct log level."""
        # Reset handlers for clean test
        test_logger = logging.getLogger("horror_story_generator")
        test_logger.handlers.clear()

        logger = setup_logging("DEBUG")
        assert logger.level == logging.DEBUG

        logger.handlers.clear()
        logger = setup_logging("WARNING")
        assert logger.level == logging.WARNING

        logger.handlers.clear()

    def test_adds_console_handler(self):
        """Test that setup_logging adds a console handler."""
        test_logger = logging.getLogger("horror_story_generator")
        test_logger.handlers.clear()

        logger = setup_logging("INFO")

        has_stream_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
            for h in logger.handlers
        )
        assert has_stream_handler

        logger.handlers.clear()

    def test_prevents_propagation(self):
        """Test that logger propagation is disabled."""
        test_logger = logging.getLogger("horror_story_generator")
        test_logger.handlers.clear()

        logger = setup_logging("INFO")
        assert logger.propagate is False

        logger.handlers.clear()
