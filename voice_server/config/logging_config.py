"""Logging configuration for the voice server."""

import logging
import logging.handlers
import sys
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VOICE_SERVER_LOG__",
        case_sensitive=False,
    )

    level: str = "INFO"
    json_format: bool = True
    file_enabled: bool = True
    file_path: str = "./logs/voice-server.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter for logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json
        from datetime import datetime, timezone

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, default=str)


class DetailedFormatter(logging.Formatter):
    """Detailed formatter for file logging with rotation."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with detailed information."""
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).isoformat()
        base = f"[{timestamp}] {record.levelname:8} {record.name}:{record.module}:{record.funcName}:{record.lineno}\n"
        message = f"{record.getMessage()}\n"

        if record.exc_info:
            base += f"{self.formatException(record.exc_info)}\n"

        return base + message


def setup_logging(settings: LoggingSettings) -> None:
    """Set up logging configuration.

    Args:
        settings: Logging configuration settings.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.level.upper()))

    # Console handler (JSON format)
    console_handler = logging.StreamHandler(sys.stdout)
    if settings.json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
    root_logger.addHandler(console_handler)

    # File handler with rotation (detailed format)
    if settings.file_enabled:
        log_path = Path(settings.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            settings.file_path,
            maxBytes=settings.max_bytes,
            backupCount=settings.backup_count,
        )
        file_handler.setLevel(logging.DEBUG)  # File gets all levels
        file_handler.setFormatter(DetailedFormatter())
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
