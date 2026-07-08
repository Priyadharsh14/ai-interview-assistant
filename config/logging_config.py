"""
Logging Configuration Module.

Production-grade structured logging with environment-aware formatting.

Environments:
    development  → human-readable format with colour hints
    production   → JSON-structured format for log aggregation (CloudWatch, Datadog)

Usage:
    from config.logging_config import configure_logging, get_logger
    configure_logging(level="INFO", env="production")
    logger = get_logger(__name__)
    logger.info("Processing resume", extra={"resume_id": "r-123", "words": 450})
"""

from __future__ import annotations

import json
import logging
import logging.config
import sys
from datetime import datetime, timezone
from typing import Any


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for production environments.

    Produces one JSON object per line — compatible with CloudWatch,
    Datadog, GCP Logging, and any log aggregation system that
    expects structured JSON logs.

    Output example:
        {"timestamp": "2024-01-15T12:34:56Z", "level": "INFO",
         "logger": "core.services.ats_engine", "message": "ATS scoring complete",
         "resume_id": "r-abc123", "score": 72.5}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include any extra fields passed via extra={} in log calls
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "taskName",
                "message",
            }:
                try:
                    json.dumps(value)   # Only include JSON-serialisable values
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def configure_logging(
    level: str = "INFO",
    env: str = "development",
) -> None:
    """
    Configure application-wide logging.

    Args:
        level: Log level string — DEBUG, INFO, WARNING, ERROR, CRITICAL.
        env: Deployment environment — "development" or "production".
             Production uses JSON format; development uses human-readable.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    use_json = env == "production"

    formatter_class = "config.logging_config.JSONFormatter" if use_json else "logging.Formatter"
    formatter_kwargs = {} if use_json else {"format": LOG_FORMAT, "datefmt": DATE_FORMAT}

    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "app": {
                "()": JSONFormatter if use_json else logging.Formatter,
                **formatter_kwargs,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "app",
                "stream": sys.stdout,
                "level": numeric_level,
            },
        },
        "root": {
            "handlers": ["console"],
            "level": numeric_level,
        },
        # Silence noisy third-party loggers
        "loggers": {
            "httpx":                 {"level": "WARNING", "propagate": True},
            "httpcore":              {"level": "WARNING", "propagate": True},
            "chromadb":              {"level": "WARNING", "propagate": True},
            "sentence_transformers": {"level": "WARNING", "propagate": True},
            "langchain":             {"level": "WARNING", "propagate": True},
            "urllib3":               {"level": "WARNING", "propagate": True},
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger for a module.

    Args:
        name: Module name — always pass __name__.

    Returns:
        Configured Logger instance.

    Example:
        logger = get_logger(__name__)
        logger.info("Service started", extra={"version": "1.0.0"})
    """
    return logging.getLogger(name)
