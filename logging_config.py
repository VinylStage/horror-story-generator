"""
Logging configuration module.

Phase 3B: Daily log rotation with process start time tracking.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Process start time is captured once and reused for all daily logs
_PROCESS_START_TIME: Optional[str] = None


class DailyRotatingFileHandler(logging.FileHandler):
    """
    Phase 3B: Daily rotating file handler.

    Creates one log file per calendar day with format:
    logs/horror_story_YYYYMMDD_<START_HHMMSS>.log

    START_HHMMSS is fixed at process start, only YYYYMMDD changes.
    """

    def __init__(self, log_dir: str = "logs", encoding: str = "utf-8"):
        global _PROCESS_START_TIME

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Capture process start time once
        if _PROCESS_START_TIME is None:
            _PROCESS_START_TIME = datetime.now().strftime("%H%M%S")

        self._start_hhmmss = _PROCESS_START_TIME
        self._current_date: Optional[str] = None
        self._encoding = encoding

        # Initialize with current date's log file
        initial_path = self._get_current_log_path()
        super().__init__(initial_path, mode='a', encoding=encoding)
        self._current_date = datetime.now().strftime("%Y%m%d")

    def _get_current_log_path(self) -> str:
        """Get log file path for current date."""
        date_str = datetime.now().strftime("%Y%m%d")
        return str(self.log_dir / f"horror_story_{date_str}_{self._start_hhmmss}.log")

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record, rotating to new file if date changed."""
        current_date = datetime.now().strftime("%Y%m%d")

        # Check if we need to rotate (date changed)
        if self._current_date != current_date:
            # Close current file
            self.close()

            # Update to new file
            self.baseFilename = self._get_current_log_path()
            self._current_date = current_date
            self.stream = self._open()

        super().emit(record)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure logging and return a logger instance.

    Phase 3B: Daily log file rotation applied.
    Maintains process start time while switching to new file on date change.

    Format: logs/horror_story_YYYYMMDD_<START_HHMMSS>.log

    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging.Logger: Configured logger instance
    """
    # Set logging level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure logger
    logger = logging.getLogger("horror_story_generator")
    logger.setLevel(numeric_level)

    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False

    # Remove existing handlers (prevent duplicates)
    if logger.handlers:
        logger.handlers.clear()

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Phase 3B: Daily rotation file handler
    file_handler = DailyRotatingFileHandler(log_dir="logs", encoding='utf-8')
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Log the current log file path
    log_filename = file_handler.baseFilename
    logger.info(f"로깅 시작 - 레벨: {log_level}, 로그 파일: {log_filename}")

    return logger
