"""
CleanStat Infrastructure - Dependencies
FastAPI dependency injection
"""
from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

def get_db_dependency():
    """Database dependency for FastAPI"""
    return Depends(get_db)
