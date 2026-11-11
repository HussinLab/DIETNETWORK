"""
Lightweight synchronous mirror of the tables the API defines with async
SQLAlchemy (backend/app/models.py). Celery tasks run outside the asyncio
event loop, so the worker talks to Postgres with a plain sync driver
(psycopg2) against the *same* tables -- table/column names must stay in
sync with the backend models. The backend (or Alembic) owns schema
creation; the worker only reads/writes rows.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from worker.config import settings

engine = create_engine(settings.database_url_sync, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, future=True)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    # Postgres column type is `uuid` (see backend/app/models.py, UUID(as_uuid=False)).
    # psycopg2 auto-adapts `uuid` columns to Python uuid.UUID unless SQLAlchemy is
    # told the real column type -- a plain String mapping here silently gets back
    # UUID objects instead of str, which breaks anything doing os.path.join(id, ...).
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    email: Mapped[str] = mapped_column(String)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    status: Mapped[str] = mapped_column(String)
    input_type: Mapped[str] = mapped_column(String)
    raw_path: Mapped[str | None] = mapped_column(String)
    results_path: Mapped[str | None] = mapped_column(String)
    raw_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snp_overlap_count: Mapped[int | None] = mapped_column(Integer)
    snp_overlap_total: Mapped[int | None] = mapped_column(Integer)
    is_reliable: Mapped[bool | None] = mapped_column(Boolean)
    predictions: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def get_session() -> Session:
    return SessionLocal()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
