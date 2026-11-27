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
                    "ALTER TABLE users ADD COLUMN plan_tier VARCHAR(32) NOT NULL DEFAULT 'free'"
                )
            )
        elif conn.dialect.name == "mysql":
            conn.execute(
                text(
                    "ALTER TABLE users MODIFY COLUMN plan_tier VARCHAR(32) NOT NULL DEFAULT 'free'"
                )
            )
        if "plan_id" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN plan_id INTEGER NULL"))
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

        upg_cols = {c["name"] for c in inspect(conn).get_columns("upgrade_requests")}
        upg_additions = [
            ("order_code", "VARCHAR(32) NULL"),
            ("plan_id", "INTEGER NULL"),
            ("plan_name_snapshot", "VARCHAR(64) NULL"),
            ("base_amount_rp", "INTEGER NOT NULL DEFAULT 0"),
            ("promo_discount_rp", "INTEGER NOT NULL DEFAULT 0"),
            ("discount_code_id", "INTEGER NULL"),
            ("discount_code", "VARCHAR(32) NULL"),
            ("voucher_discount_rp", "INTEGER NOT NULL DEFAULT 0"),
            ("payment_method_id", "INTEGER NULL"),
            ("payment_method_type", "VARCHAR(16) NULL"),
            ("payment_method_label", "VARCHAR(64) NULL"),
            ("payment_account_number", "VARCHAR(64) NULL"),
            ("payment_account_holder", "VARCHAR(128) NULL"),
            ("payment_instructions", "TEXT NULL"),
            ("payment_proof_path", "VARCHAR(255) NULL"),
            ("expires_at", "INTEGER NULL"),
            ("submitted_at", "INTEGER NULL"),
        ]
        if conn.dialect.name == "mysql" and "requested_tier" in upg_cols:
            conn.execute(
                text(
                    "ALTER TABLE upgrade_requests MODIFY COLUMN "
                    "requested_tier VARCHAR(32) NOT NULL DEFAULT 'pro'"
                )
            )
        for col_name, col_def in upg_additions:
            if col_name not in upg_cols:
                conn.execute(text(f"ALTER TABLE upgrade_requests ADD COLUMN {col_name} {col_def}"))
        upg_indexes = {idx["name"] for idx in inspect(conn).get_indexes("upgrade_requests")}
        if "uq_upgrade_requests_order_code" not in upg_indexes:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX uq_upgrade_requests_order_code "
                    "ON upgrade_requests (order_code)"
                )
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
        "report_timezone": "Asia/Jakarta",
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
