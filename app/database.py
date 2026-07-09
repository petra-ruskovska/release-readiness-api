"""
Database engine + session handling.

Using SQLite for local dev — zero setup.
Swap DATABASE_URL for a Postgres URL later if you want deployment practice.
"""
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///./release_readiness.db"

# check_same_thread=False is needed because FastAPI can use the connection
# across different threads within a single request lifecycle.
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create all tables. Call once on startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a DB session per request."""
    with Session(engine) as session:
        yield session
