import os

from app.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

TEST_MYSQL_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://root@127.0.0.1:3306/energy_monitor_test?charset=utf8mb4",
)

test_engine = create_engine(
    TEST_MYSQL_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

_SCHEMA_CREATED = False
_ACTIVE_SESSIONS: list[Session] = []


def close_active_test_sessions() -> None:
    while _ACTIVE_SESSIONS:
        sess = _ACTIVE_SESSIONS.pop()
        try:
            sess.close()
        except Exception:
            pass


def get_clean_mysql_engine() -> Engine:
    """Siapkan skema MySQL uji sekali dan kosongkan baris tabel secara aman."""
    global _SCHEMA_CREATED
    close_active_test_sessions()
    if not _SCHEMA_CREATED:
        Base.metadata.create_all(bind=test_engine)
        _SCHEMA_CREATED = True

    with test_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for tbl in reversed(Base.metadata.sorted_tables):
            conn.execute(tbl.delete())
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    return test_engine


def open_clean_test_session() -> tuple[Engine, Session]:
    """Mengembalikan (engine, session) bersih pada database MySQL pengujian."""
    eng = get_clean_mysql_engine()
    sess = TestSessionLocal()
    _ACTIVE_SESSIONS.append(sess)
    return eng, sess

