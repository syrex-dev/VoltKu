from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.models import Base, Setting

settings = get_settings()

engine_kwargs = {
    "connect_args": {"check_same_thread": False} if "sqlite" in settings.database_url else {},
    "pool_pre_ping": True,
}
if settings.database_url == "sqlite:///:memory:":
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    # Seed default settings if missing
    defaults = {
        "tariff_sen_per_kwh": "144470",
        "extra_percent": "0.0",
        "power_limit_w": "2200",
        "alert_cooldown_min": "30",
        "report_hour": "21",
    }
    with SessionLocal() as session:
        for k, v in defaults.items():
            existing = session.scalar(select(Setting).where(Setting.key == k))
            if not existing:
                session.add(Setting(key=k, value=v))
        session.commit()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
