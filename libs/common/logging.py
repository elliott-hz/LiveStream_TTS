"""
Structured JSON logging for all microservices.

Usage:
    from libs.common.logging import get_logger
    logger = get_logger(__name__)
    logger.info("User logged in", extra={"user_id": "u_123"})
"""

import logging
import os
import sys
from datetime import datetime, timezone

import structlog


def setup_logging(
    service_name: str,
    level: str = "INFO",
    json_format: bool = True,
) -> None:
    """Initialize structured logging for a service.

    Args:
        service_name: Name of the service (e.g. "gateway-svc")
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Whether to output JSON (prod) or colored console (dev)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_format:
        # Production: JSON to stdout (consumed by ELK / Loki)
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # Development: colored console
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%H:%M:%S", utc=False),
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    # Set root logger level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silence noisy libraries
    logging.getLogger("grpc").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    logger = structlog.get_logger(name or __name__)
    return logger.bind()  # type: ignore[return-value]
