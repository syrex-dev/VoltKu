from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.models import Base, Setting

settings = get_settings()

db_url = settings.database_url
is_sqlite = db_url.startswith("sqlite")

if is_sqlite and db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
    raw_path = db_url[len("sqlite:///"):]
    db_file = Path(raw_path)
    if not db_file.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent
        db_file = (project_root / raw_path).resolve()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{db_file.as_posix()}"

engine_kwargs: dict = {
    "pool_pre_ping": True,
}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    if db_url == "sqlite:///:memory:":
        engine_kwargs["poolclass"] = StaticPool
else:
    engine_kwargs["pool_recycle"] = 1800

engine = create_engine(db_url, **engine_kwargs)

if is_sqlite:

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_multi_tenant_columns(target_engine: Engine) -> None:
    """Pastikan kolom multi-tenant & OAuth ada pada DB lama (lintas MySQL & SQLite)."""
    with target_engine.begin() as conn:
        user_cols = {c["name"] for c in inspect(conn).get_columns("users")}
        if "auth_provider" not in user_cols:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN auth_provider "
                    "VARCHAR(32) NOT NULL DEFAULT 'local'"
                )
            )
        if "google_sub" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(128) NULL"))
        if "avatar_url" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512) NULL"))
        if "terms_version_accepted" not in user_cols:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN terms_version_accepted VARCHAR(32) NULL")
            )
        if "terms_accepted_at" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN terms_accepted_at INTEGER NULL"))
        if "plan_tier" not in user_cols:
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN plan_tier VARCHAR(16) NOT NULL DEFAULT 'free'"
                )
            )
        if "plan_expires_at" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN plan_expires_at INTEGER NULL"))
        if "plan_updated_at" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN plan_updated_at INTEGER NULL"))
        user_indexes = {idx["name"] for idx in inspect(conn).get_indexes("users")}
        if "uq_users_google_sub" not in user_indexes:
            conn.execute(
                text("CREATE UNIQUE INDEX uq_users_google_sub ON users (google_sub)")
            )

        cols = {c["name"] for c in inspect(conn).get_columns("devices")}
        if "owner_user_id" not in cols:
            conn.execute(text("ALTER TABLE devices ADD COLUMN owner_user_id INTEGER NULL"))
        if "is_public_demo" not in cols:
            conn.execute(
                text("ALTER TABLE devices ADD COLUMN is_public_demo INTEGER NOT NULL DEFAULT 0")
            )
            conn.execute(
                text(
                    "UPDATE devices SET is_public_demo = 1 "
                    "WHERE owner_user_id IS NULL AND id LIKE 'sim-%'"
                )
            )
        idx_names = {idx["name"] for idx in inspect(conn).get_indexes("readings")}
        if "idx_readings_device_ts_pv" not in idx_names:
            conn.execute(
                text("CREATE INDEX idx_readings_device_ts_pv ON readings (device_id, ts, p, v)")
            )


def init_db(target_engine: Engine = engine) -> None:
    Base.metadata.create_all(bind=target_engine)
    ensure_multi_tenant_columns(target_engine)

    # Seed default settings if missing
    defaults = {
        "tariff_sen_per_kwh": "144470",
        "extra_percent": "0.0",
        "power_limit_w": "2200",
        "alert_cooldown_min": "30",
        "report_hour": "21",
        "report_enabled": "true",
    }
    local_session = sessionmaker(autocommit=False, autoflush=False, bind=target_engine)
    with local_session() as session:
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
