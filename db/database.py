# db/database.py
"""
Database connection and session management for iMat.
Supports SQLite with optional migration to PostgreSQL/MySQL.
"""

import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager

# Setup logger
logger = logging.getLogger(__name__)

# Determine database path
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "aimat.db"
BACKUP_DIR = BASE_DIR / "backups"

# Default database URL
DEFAULT_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Global variables
_engine = None
_SessionLocal = None
_current_db_url = None

# Base class for ORM models
Base = declarative_base()


def get_engine(database_url: Optional[str] = None, echo: bool = False):
    """
    Get or create SQLAlchemy engine.
    
    Args:
        database_url: Database connection URL (default: SQLite at DB_PATH)
        echo: Print SQL statements for debugging
        
    Returns:
        SQLAlchemy engine instance
    """
    global _engine, _current_db_url
    
    if database_url is None:
        database_url = os.environ.get('DATABASE_URL', DEFAULT_DATABASE_URL)
    
    # If engine exists and URL hasn't changed, return cached
    if _engine is not None and _current_db_url == database_url:
        return _engine
    
    # Create new engine
    if database_url.startswith('sqlite'):
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=echo,
            poolclass=StaticPool,
            pool_pre_ping=True
        )
    else:
        # PostgreSQL / MySQL / etc.
        _engine = create_engine(
            database_url,
            echo=echo,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600
        )
    
    _current_db_url = database_url
    logger.info(f"Database engine created: {database_url}")
    return _engine


def get_session_factory():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
    return _SessionLocal


# Session factory (for backward compatibility)
SessionLocal = property(lambda self: get_session_factory())


def _get_session_local():
    """Internal: get the actual session factory."""
    return get_session_factory()


# Module-level SessionLocal accessor
class SessionLocalProxy:
    """Proxy to allow SessionLocal to be called directly."""
    def __call__(self, *args, **kwargs):
        return _get_session_local()(*args, **kwargs)
    
    def __getattr__(self, name):
        return getattr(_get_session_local(), name)


SessionLocal = SessionLocalProxy()


def init_db(database_url: Optional[str] = None, drop_all: bool = False):
    """
    Initialize database - create all tables if they don't exist.
    
    Args:
        database_url: Optional database URL (uses default if None)
        drop_all: If True, drop all tables before creating (dangerous!)
    """
    from . import models  # Import all models to register them with Base
    
    try:
        engine = get_engine(database_url)
        
        if drop_all:
            logger.warning("Dropping all database tables!")
            Base.metadata.drop_all(bind=engine)
        
        Base.metadata.create_all(bind=engine)
        
        # Create backup directory
        BACKUP_DIR.mkdir(exist_ok=True)
        
        # Seed default data if needed
        _seed_default_data()
        
        logger.info(f"Database initialized successfully at {_current_db_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


def _seed_default_data():
    """Seed database with default data if empty."""
    session = _get_session_local()()
    try:
        from .models import ProjectInfo
        
        # Create default project info if not exists
        if session.query(ProjectInfo).count() == 0:
            default_project = ProjectInfo(
                company_name="FARASAKOU",
                project_name="Storage Development",
                project_code="001"
            )
            session.add(default_project)
            session.commit()
            logger.info("Default project info seeded")
    except Exception as e:
        session.rollback()
        logger.warning(f"Could not seed default data: {e}")
    finally:
        session.close()


def get_db_session():
    """
    Return a new database session.
    Caller is responsible for closing the session.
    """
    return _get_session_local()()


@contextmanager
def get_session():
    """
    Context manager for database sessions.
    Usage:
        with get_session() as db:
            db.query(...)
    Automatically closes the session when exiting the block.
    """
    db = _get_session_local()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def reset_database(database_url: Optional[str] = None):
    """
    Reset database - drop all tables and recreate.
    WARNING: This deletes all data!
    """
    engine = get_engine(database_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed_default_data()
    logger.warning("Database has been reset!")


def backup_database(backup_path: Optional[str] = None) -> str:
    """
    Create a backup of the SQLite database.
    
    Args:
        backup_path: Optional path for backup file (auto-generated if None)
        
    Returns:
        Path to the backup file
    """
    if not _current_db_url or not _current_db_url.startswith('sqlite'):
        logger.warning("Backup only supported for SQLite databases")
        return ""
    
    # Extract file path from SQLite URL
    db_file = _current_db_url.replace('sqlite:///', '')
    if not os.path.exists(db_file):
        logger.error(f"Database file not found: {db_file}")
        return ""
    
    # Generate backup filename
    if backup_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = BACKUP_DIR / f"aimat_backup_{timestamp}.db"
    
    backup_path = Path(backup_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.copy2(db_file, backup_path)
        logger.info(f"Database backed up to: {backup_path}")
        
        # Cleanup old backups (keep last N)
        _cleanup_old_backups()
        
        return str(backup_path)
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return ""


def _cleanup_old_backups(max_backups: int = 30):
    """Remove old backup files keeping only the most recent ones."""
    backups = sorted(BACKUP_DIR.glob("aimat_backup_*.db"), reverse=True)
    for old_backup in backups[max_backups:]:
        try:
            old_backup.unlink()
            logger.debug(f"Removed old backup: {old_backup}")
        except Exception:
            pass


def restore_database(backup_path: str) -> bool:
    """
    Restore database from a backup file.
    
    Args:
        backup_path: Path to the backup file
        
    Returns:
        True if successful
    """
    if not os.path.exists(backup_path):
        logger.error(f"Backup file not found: {backup_path}")
        return False
    
    if not _current_db_url or not _current_db_url.startswith('sqlite'):
        logger.warning("Restore only supported for SQLite databases")
        return False
    
    db_file = _current_db_url.replace('sqlite:///', '')
    
    try:
        # Close all connections
        if _engine:
            _engine.dispose()
        
        # Copy backup over current database
        shutil.copy2(backup_path, db_file)
        logger.info(f"Database restored from: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Restore failed: {str(e)}")
        return False


def get_database_info() -> Dict[str, Any]:
    """Get information about the current database."""
    info = {
        "url": _current_db_url or "Not connected",
        "type": "SQLite" if (_current_db_url and 'sqlite' in _current_db_url) else "Unknown",
        "tables": [],
        "size_mb": 0,
    }
    
    if _current_db_url and _current_db_url.startswith('sqlite'):
        db_file = _current_db_url.replace('sqlite:///', '')
        if os.path.exists(db_file):
            info["size_mb"] = round(os.path.getsize(db_file) / (1024 * 1024), 2)
    
    if _engine:
        inspector = inspect(_engine)
        info["tables"] = inspector.get_table_names()
    
    return info


def change_database(new_path: str) -> bool:
    """
    Switch to a different database file.
    
    Args:
        new_path: Path to the new SQLite database
        
    Returns:
        True if successful
    """
    global _engine, _SessionLocal, _current_db_url
    
    if not os.path.exists(new_path):
        logger.warning(f"Database file not found: {new_path}")
        # Create new database
        new_url = f"sqlite:///{new_path}"
        _engine = None
        _SessionLocal = None
        _current_db_url = None
        init_db(new_url)
        return True
    
    try:
        # Dispose old engine
        if _engine:
            _engine.dispose()
        
        # Create new engine
        new_url = f"sqlite:///{new_path}"
        _engine = None
        _SessionLocal = None
        _current_db_url = None
        
        engine = get_engine(new_url)
        Base.metadata.create_all(bind=engine)
        
        logger.info(f"Switched to database: {new_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to switch database: {str(e)}")
        return False


# Expose engine for backward compatibility
engine = property(lambda self: get_engine())