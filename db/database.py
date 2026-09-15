# db/database.py
"""
Database connection and session management for iMat.
Supports SQLite (default) and Microsoft SQL Server via pyodbc.
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

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "aimat.db"
BACKUP_DIR = BASE_DIR / "backups"
DEFAULT_DATABASE_URL = f"sqlite:///{DB_PATH}"

_engine = None
_SessionLocal = None
_current_db_url = None

Base = declarative_base()


def _load_db_config() -> Dict[str, Any]:
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
    driver_q = quote_plus(driver)
    query_parts = [
        f"driver={driver_q}",
        f"Encrypt={'yes' if encrypt else 'no'}",
        f"TrustServerCertificate={'yes' if trust_cert else 'no'}",
        f"Connection Timeout={timeout}",
    ]
    if trusted:
        query_parts.append("Trusted_Connection=yes")
        auth = ""
    else:
        auth = f"{quote_plus(username)}:{quote_plus(password)}@"
    host = f"{server}:{port}" if port else server
    return f"mssql+pyodbc://{auth}{host}/{database}?{'&'.join(query_parts)}"


def resolve_database_url(database_url: Optional[str] = None) -> str:
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
            logger.warning("sqlserver incomplete; falling back to SQLite.")
            return DEFAULT_DATABASE_URL
        return build_sqlserver_url(ss)
    path = cfg.get("path") or "aimat.db"
    if not os.path.isabs(path):
        path = str(BASE_DIR / path)
    return f"sqlite:///{path}"


def get_engine(database_url: Optional[str] = None, echo: bool = False):
    global _engine, _current_db_url
    database_url = resolve_database_url(database_url)
    if _engine is not None and _current_db_url == database_url:
        return _engine
    cfg = _load_db_config()
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
        ss = cfg.get("sqlserver") or {}
        pool_size = int(ss.get("pool_size") or cfg.get("pool_size") or 10)
        max_overflow = int(ss.get("max_overflow") or 20)
        _engine = create_engine(
            database_url, echo=echo, pool_size=pool_size,
            max_overflow=max_overflow, pool_pre_ping=True, pool_recycle=3600,
        )
    _current_db_url = database_url
    logger.info(f"Database engine created")
    return _engine


def _enable_sqlite_pragmas(engine) -> None:
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
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def _get_session_local():
    return get_session_factory()


class SessionLocalProxy:
    def __call__(self, *args, **kwargs):
        return _get_session_local()(*args, **kwargs)
    def __getattr__(self, name):
        return getattr(_get_session_local(), name)


SessionLocal = SessionLocalProxy()


class EngineProxy:
    def __getattr__(self, name):
        return getattr(get_engine(), name)
    def __bool__(self):
        return _engine is not None


engine = EngineProxy()


def init_db(database_url: Optional[str] = None, drop_all: bool = False):
    from . import models  # noqa: F401
    try:
        eng = get_engine(database_url)
        if drop_all:
            logger.warning("Dropping all database tables!")
            Base.metadata.drop_all(bind=eng)
        Base.metadata.create_all(bind=eng)
        BACKUP_DIR.mkdir(exist_ok=True)
        _seed_default_data()
        _ensure_sqlite_indexes()
        _ensure_document_line_columns()
        logger.info(f"Database initialized successfully at {_current_db_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


def _seed_default_data():
    session = _get_session_local()()
    try:
        from .models import ProjectInfo
        if session.query(ProjectInfo).count() == 0:
            session.add(ProjectInfo(
                company_name="FARASAKOU",
                project_name="Storage Development",
                project_code="001",
            ))
            session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"Could not seed default data: {e}")
    finally:
        session.close()


def _ensure_document_line_columns():
    """Add DocumentLine.request_no on existing SQLite DBs (idempotent)."""
    if not _engine or not (_current_db_url or "").startswith("sqlite"):
        return
    try:
        with _engine.begin() as conn:
            cols = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(document_lines)")).fetchall()
            }
            if "request_no" not in cols:
                conn.execute(text(
                    "ALTER TABLE document_lines ADD COLUMN request_no VARCHAR(50)"
                ))
                logger.info("Added document_lines.request_no column")
    except Exception as e:
        logger.debug(f"Could not ensure document_lines.request_no: {e}")


def _ensure_sqlite_indexes():
    if not _engine or not (_current_db_url or "").startswith("sqlite"):
        return
    try:
        with _engine.begin() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_doc_no ON documents (doc_no)"
            ))
    except Exception as e:
        logger.debug(f"Could not ensure document number unique index: {e}")


def get_db_session():
    return _get_session_local()()


@contextmanager
def get_session():
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
    owns_session = db is None
    session = db if db is not None else _get_session_local()()
    try:
        yield session
    finally:
        if owns_session:
            session.close()


def reset_database(database_url=None):
    eng = get_engine(database_url)
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    _seed_default_data()


def backup_database(backup_path=None):
    if not _current_db_url or not _current_db_url.startswith("sqlite"):
        return ""
    db_file = _current_db_url.replace("sqlite:///", "")
    if not os.path.exists(db_file):
        return ""
    if backup_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"aimat_backup_{timestamp}.db"
    backup_path = Path(backup_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(db_file, backup_path)
        return str(backup_path)
    except Exception:
        return ""


def get_database_info():
    info = {"url": _current_db_url or "Not connected", "type": "Unknown", "tables": [], "size_mb": 0}
    if _current_db_url:
        if _current_db_url.startswith("sqlite"):
            info["type"] = "SQLite"
            db_file = _current_db_url.replace("sqlite:///", "")
            if os.path.exists(db_file):
                info["size_mb"] = round(os.path.getsize(db_file) / (1024 * 1024), 2)
        elif "mssql" in _current_db_url:
            info["type"] = "SQL Server"
    if _engine:
        info["tables"] = inspect(_engine).get_table_names()
    return info


def change_database(new_path: str) -> bool:
    global _engine, _SessionLocal, _current_db_url
    try:
        if _engine:
            _engine.dispose()
        new_url = f"sqlite:///{new_path}"
        _engine = None
        _SessionLocal = None
        _current_db_url = None
        eng = get_engine(new_url)
        Base.metadata.create_all(bind=eng)
        return True
    except Exception:
        return False


def is_sqlserver() -> bool:
    return bool(_current_db_url and ("mssql" in _current_db_url or "sqlserver" in _current_db_url))


def is_sqlite() -> bool:
    return bool(_current_db_url and _current_db_url.startswith("sqlite"))
