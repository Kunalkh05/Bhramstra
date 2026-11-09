"""
Database engine and session management.
"""

from contextlib import contextmanager
from typing import Generator, Optional
from pathlib import Path
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from brahmastra.infrastructure.config import get_db_path
from brahmastra.infrastructure.database.models import Base

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None


def get_engine(db_path: Optional[Path] = None) -> Engine:
    """Return an active SQLAlchemy engine for SQLite."""
    global _engine, _session_factory
    target_path = db_path or get_db_path()
    db_url = f"sqlite:///{target_path}"
    
    # Check if existing engine matches target
    if _engine is not None and str(_engine.url) == db_url:
        return _engine

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    _engine = engine
    _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine


def init_db(engine: Optional[Engine] = None) -> None:
    """Initialize database tables."""
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)


@contextmanager
def get_session(engine: Optional[Engine] = None) -> Generator[Session, None, None]:
    """Context manager yielding a transactional database session."""
    eng = engine or get_engine()
    init_db(eng)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
