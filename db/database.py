# db/database.py
"""
Database connection and session management for iMat.

Supports:
- SQLite (default, single-user / offline)
- Microsoft SQL Server (network / multi-user) via pyodbc

Switch by setting database.engine = "sqlserver" in app_config.json
and filling the database.sqlserver section.
"""

import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote_plus
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager

# Setup logger
logger = logging.getLogger(__name__)

# Determine database path
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "aimat.db"
BACKUP_DIR = BASE_DIR / "backups"

# Default database URL (SQLite)
DEFAULT_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Global variables
_engine = None
_SessionLocal = None
_current_db_url = None

# Base class for ORM models
Base = declarative_base()


def _load_db_config() -> Dict[str, Any]:
    """Read database section from ConfigManager (safe fallback)."""
    try:
        from config.config_manager import config
        return {
            "engine": (config.get("database.engine") or "sqlite").lower(),
            "path": config.get("database.path", "aimat.db"),
            "pool_size": config.get("database.pool_size", 5),
            "timeout": config.get("database.timeout", 30),
            "sqlserver": config.get("database.sqlserver") or {},
        }
    except Exception:
        return {
            "engine": "sqlite",
            "path": "aimat.db",
            "pool_size": 5,
            "timeout": 30,
            "sqlserver": {},
        }


def build_sqlserver_url(cfg: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a SQLAlchemy connection URL for Microsoft SQL Server (pyodbc).

    Example result:
    mssql+pyodbc://user:pass@server:1433/iMat?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
    """
    ss = cfg or {}
    driver = ss.get("driver") or "ODBC Driver 17 for SQL Server"
    server = ss.get("server") or "localhost"
    port = ss.get("port") or 1433
    database = ss.get("database") or "iMat"
    username = ss.get("username") or ""
    password = ss.get("password") or ""
    trusted = bool(ss.get("trusted_connection", False))
    encrypt = bool(ss.get("encrypt", True))
    trust_cert = bool(ss.get("trust_server_certificate", True))
    timeout = int(ss.get("connection_timeout") or 30)

    # Driver name must be URL-encoded
    driver_q = quote_plus(driver)

    query_parts = [
        f"driver={driver_q}",
        f"Encrypt={'yes' if encrypt else 'no'}",
        f"TrustServerCertificate={'yes' if trust_cert else 'no'}",
        f"Connection Timeout={timeout}",
    ]

    if trusted:
        # Windows Authentication
        query_parts.append("Trusted_Connection=yes")
        auth = ""
    else:
        # SQL Authentication
        user_q = quote_plus(username)
        pass_q = quote_plus(password)
        auth = f"{user_q}:{pass_q}@"

    host = f"{server}:{port}" if port else server
    return f"mssql+pyodbc://{auth}{host}/{database}?{'&'.join(query_parts)}"


def resolve_database_url(database_url: Optional[str] = None) -> str:
    """
    Decide the final connection URL.

    Priority:
    1. Explicit database_url argument
    2. Environment variable DATABASE_URL
    3. Config (database.engine + sqlserver / sqlite path)
    """
    if database_url:
        return database_url

    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url

    cfg = _load_db_config()
    engine_name = cfg.get("engine", "sqlite")

    if engine_name in ("sqlserver", "mssql", "mssql+pyodbc"):
        ss = cfg.get("sqlserver") or {}
        if not ss.get("enabled", False) and not ss.get("server"):
            logger.warning(
                "database.engine is sqlserver but sqlserver settings are incomplete; "
                "falling back to SQLite."
            )
            return DEFAULT_DATABASE_URL
        return build_sqlserver_url(ss)

    # Default: SQLite
    path = cfg.get("path") or "aimat.db"
    if not os.path.isabs(path):
        path = str(BASE_DIR / path)
    return f"sqlite:///{path}"


def get_engine(database_url: Optional[str] = None, echo: bool = False):
    """
    Get or create SQLAlchemy engine.

    Args:
        database_url: Database connection URL (default: from config / env)
        echo: Print SQL statements for debugging

    Returns:
        SQLAlchemy engine instance
    """
    global _engine, _current_db_url

    database_url = resolve_database_url(database_url)

    # If engine exists and URL hasn't changed, return cached
    if _engine is not None and _current_db_url == database_url:
        return _engine

    cfg = _load_db_config()

    # Create new engine
    if database_url.startswith("sqlite"):
        _engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False, "timeout": cfg.get("timeout", 30)},
            echo=echo,
            poolclass=StaticPool,
            pool_pre_ping=True,
        )
        _enable_sqlite_pragmas(_engine)
    else:
        # SQL Server / PostgreSQL / MySQL / etc.
        ss = cfg.get("sqlserver") or {}
        pool_size = int(ss.get("pool_size") or cfg.get("pool_size") or 10)
        max_overflow = int(ss.get("max_overflow") or 20)

        _engine = create_engine(
            database_url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    _current_db_url = database_url
    # Avoid logging password
    safe_url = database_url
    if "@" in safe_url and ":" in safe_url.split("@")[0]:
        # mask password
        try:
            prefix, rest = safe_url.split("//", 1)
            creds, hostpart = rest.split("@", 1)
            user = creds.split(":")[0]
            safe_url = f"{prefix}//{user}:****@{hostpart}"
        except Exception:
            pass
    logger.info(f"Database engine created: {safe_url}")
    return _engine


def _enable_sqlite_pragmas(engine) -> None:
    """Enable WAL, foreign keys, and a busy timeout on every SQLite connection."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


def get_session_factory():
    """Get or create session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
    return _SessionLocal


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

        # Create backup directory (mainly for SQLite)
        BACKUP_DIR.mkdir(exist_ok=True)

        # Seed default data if needed
        _seed_default_data()
        _ensure_sqlite_indexes()

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
                project_code="001",
            )
            session.add(default_project)
            session.commit()
            logger.info("Default project info seeded")
    except Exception as e:
        session.rollback()
        logger.warning(f"Could not seed default data: {e}")
    finally:
        session.close()


def _ensure_sqlite_indexes():
    """Add uniqueness indexes that create_all will not retrofit on existing files."""
    if not _engine or not (_current_db_url or "").startswith("sqlite"):
        return
    try:
        with _engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_doc_no "
                    "ON documents (doc_no)"
                )
            )
    except Exception as e:
        logger.debug(f"Could not ensure document number unique index: {e}")


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


@contextmanager
def session_scope(db=None):
    """
    Yield an existing session, or open a short-lived one that is closed on exit.

    Used by inventory/report helpers so tests can inject an in-memory session
    while production code still works without passing a session.
    """
    owns_session = db is None
    session = db if db is not None else _get_session_local()()
    try:
        yield session
    finally:
        if owns_session:
            session.close()


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
    if not _current_db_url or not _current_db_url.startswith("sqlite"):
        logger.warning("Backup only supported for SQLite databases")
        return ""

    # Extract file path from SQLite URL
    db_file = _current_db_url.replace("sqlite:///", "")
    if not os.path.exists(db_file):
        logger.error(f"Database file not found: {db_file}")
        return ""

    # Generate backup filename
    if backup_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

    if not _current_db_url or not _current_db_url.startswith("sqlite"):
        logger.warning("Restore only supported for SQLite databases")
        return False

    db_file = _current_db_url.replace("sqlite:///", "")

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
        "type": "Unknown",
        "tables": [],
        "size_mb": 0,
    }

    if _current_db_url:
        if _current_db_url.startswith("sqlite"):
            info["type"] = "SQLite"
            db_file = _current_db_url.replace("sqlite:///", "")
            if os.path.exists(db_file):
                info["size_mb"] = round(os.path.getsize(db_file) / (1024 * 1024), 2)
        elif "mssql" in _current_db_url or "sqlserver" in _current_db_url:
            info["type"] = "SQL Server"
        elif "postgresql" in _current_db_url or "postgres" in _current_db_url:
            info["type"] = "PostgreSQL"
        elif "mysql" in _current_db_url:
            info["type"] = "MySQL"

    if _engine:
        inspector = inspect(_engine)
        info["tables"] = inspector.get_table_names()

    return info


def change_database(new_path: str) -> bool:
    """
    Switch to a different SQLite database file.

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


def is_sqlserver() -> bool:
    """Return True if the current engine is Microsoft SQL Server."""
    return bool(_current_db_url and ("mssql" in _current_db_url or "sqlserver" in _current_db_url))


def is_sqlite() -> bool:
    """Return True if the current engine is SQLite."""
    return bool(_current_db_url and _current_db_url.startswith("sqlite"))
