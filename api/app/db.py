from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        future=True,
    )

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_sqlite_columns() -> None:
    """Add columns create_all will not attach to an existing demo file."""
    if not str(engine.url).startswith("sqlite"):
        return
    patches = {
        "cases": [("worklist", "BOOLEAN NOT NULL DEFAULT 1")],
        "events": [("outcome", "VARCHAR(64)")],
    }
    with engine.begin() as conn:
        for table, columns in patches.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if not existing:
                continue
            for name, ddl in columns:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    from app import models  # noqa: F401

    # Disposable synthetic demo: create missing tables and additive columns.
    # Destructive reshapes still need a new SQLite file or a guest reset.
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()