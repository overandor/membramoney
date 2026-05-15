"""
CleanStat Infrastructure - Database Session Management
Enhanced session handling with context and error handling
"""
from typing import Generator
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.db.base import SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    Get database session with error handling
    
    Yields:
        Database session
    
    Usage:
        with get_db() as db:
            # database operations
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error("Database error", error=str(e))
        db.rollback()
        raise
    finally:
        db.close()


class DatabaseSession:
    """
    Context manager for database sessions
    Provides automatic commit/rollback handling
    """
    
    def __init__(self):
        self.db = SessionLocal()
    
    def __enter__(self) -> Session:
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.db.rollback()
            logger.error(
                "Database session rollback",
                error=str(exc_val)
            )
        else:
            self.db.commit()
        self.db.close()
