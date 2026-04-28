# app/core/_logging.py

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional


class LoggerConfig:
    """
    Centralized logging configuration for the AI Workforce Orchestrator.
    
    Features:
    - Rotating file handlers with size limits
    - Separate log files for different components
    - Configurable log levels per environment
    - Structured logging with timestamps and context
    """
    
    def __init__(self):
        self.log_dir = Path(os.getenv("LOG_DIR", "./logs"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.console_level = os.getenv("LOG_CONSOLE_LEVEL", self.log_level).upper()
        self.log_to_stdout = os.getenv("LOG_TO_STDOUT", "true").lower() == "true"
        self.log_file_enabled = os.getenv("LOG_FILE_ENABLED", "true").lower() == "true"
        self.max_bytes = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))  # 10MB default
        self.backup_count = int(os.getenv("LOG_BACKUP_COUNT", 5))
        self.log_format = os.getenv(
            "LOG_FORMAT",
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        self.date_format = "%Y-%m-%d %H:%M:%S"
        
        # Disable file logging when running in stdout-only mode (e.g. Cloud Run)
        if self.log_to_stdout:
            self.log_file_enabled = False
        elif self.log_file_enabled:
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                self.log_file_enabled = False
        
        # Track configured loggers to avoid duplicate handlers
        self._configured_loggers = set()
    
    def get_logger(self, name: str, log_file: Optional[str] = None) -> logging.Logger:
        """
        Get or create a logger with rotating file handler.
        
        Args:
            name: Logger name (typically __name__)
            log_file: Optional custom log file name (defaults to component-specific)
        
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)
        
        # Avoid adding duplicate handlers
        if name in self._configured_loggers:
            return logger
        
        # Set log level
        logger.setLevel(getattr(logging, self.log_level, logging.INFO))
        
        # Remove any existing handlers to avoid duplicates
        logger.handlers.clear()
        
        # Set formatter
        formatter = logging.Formatter(self.log_format, datefmt=self.date_format)

        if self.log_file_enabled:
            if log_file is None:
                component = name.split(".")[-1] if "." in name else name
                log_file = f"{component}.log"
            log_path = self.log_dir / log_file
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding="utf-8"
            )
            file_handler.setLevel(getattr(logging, self.log_level, logging.INFO))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        if self.log_to_stdout:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, self.console_level, logging.INFO))
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # Mark as configured
        self._configured_loggers.add(name)
        
        return logger
    
    def get_main_logger(self) -> logging.Logger:
        """Get the main application logger."""
        return self.get_logger("app.main", "orchestrator.log")
    
    def get_agent_logger(self) -> logging.Logger:
        """Get logger for agent operations."""
        return self.get_logger("app.agents", "agents.log")
    
    def get_service_logger(self) -> logging.Logger:
        """Get logger for service layer."""
        return self.get_logger("app.services", "services.log")
    
    def get_api_logger(self) -> logging.Logger:
        """Get logger for API routes."""
        return self.get_logger("app.api", "api.log")
    
    def get_event_logger(self) -> logging.Logger:
        """Get logger for event processing."""
        return self.get_logger("app.events", "events.log")
    
    def get_llm_logger(self) -> logging.Logger:
        """Get logger for LLM service."""
        return self.get_logger("app.llm", "llm.log")


# Global logger configuration instance
_logger_config = LoggerConfig()


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Convenience function to get a configured logger.
    
    Usage:
        from app.core._logging import get_logger
        logger = get_logger(__name__)
    """
    return _logger_config.get_logger(name, log_file)
