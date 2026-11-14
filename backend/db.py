import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

if os.getenv("VERCEL") and not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL must be configured for Vercel deployment")
DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./compensation.db"))
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


def initialize_database(target_engine=engine):
    """Apply versioned, non-destructive upgrades using one transaction."""
    from pathlib import Path
    from alembic import command
    from alembic.config import Config

    config = Config(str(Path(__file__).with_name("alembic.ini")))
    with target_engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            # Serialize startup migrations across concurrently starting workers.
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(7340911)")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
