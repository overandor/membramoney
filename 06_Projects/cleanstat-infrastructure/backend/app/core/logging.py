"""
CleanStat Infrastructure - Logging Configuration
Structured JSON logging for production
"""
import structlog
import logging
import sys
from app.core.config import get_settings

settings = get_settings()


def configure_logging() -> None:
    """
    Configure structured logging for the application
    """
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Add JSON renderer for production
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.stdlib.BoundLogger,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level),
        stream=sys.stdout,
    )
    
    # Configure sentry if DSN is provided
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
            ],
            environment=settings.environment.value,
            release=settings.app_version,
            traces_sample_rate=0.1,
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger for a module
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)
