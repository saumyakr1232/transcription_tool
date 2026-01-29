"""Logging configuration for development and production environments."""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    """JSON formatter for production logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id

        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id

        return json.dumps(log_obj)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for development console logging."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname:8}{self.RESET}"
        record.name = f"\033[34m{record.name}\033[0m"  # Blue for logger name
        return super().format(record)


def setup_logging() -> logging.Logger:
    """Configure and return the application logger.

    Returns:
        logging.Logger: Configured application logger.
    """
    logger = logging.getLogger("transcription_tool")

    # Clear existing handlers
    logger.handlers.clear()

    # Set log level based on environment
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if settings.DEBUG:
        # Development: colored, verbose output
        formatter = ColoredFormatter(
            "%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s", datefmt="%H:%M:%S"
        )
    else:
        # Production: JSON formatted logs
        formatter = JsonFormatter()

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Initialize logger
logger = setup_logging()


def get_logger(name: str) -> logging.Logger:
    """Get a child logger with the given name.

    Args:
        name: Name for the child logger.

    Returns:
        logging.Logger: Child logger instance.
    """
    return logger.getChild(name)
