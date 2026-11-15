from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    mcb_watt: Mapped[int] = mapped_column(Integer, default=2200, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )
    last_seen_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_data_ts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="offline", nullable=False)


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    v: Mapped[float] = mapped_column(Float, nullable=False)
    i: Mapped[float] = mapped_column(Float, nullable=False)
    p: Mapped[float] = mapped_column(Float, nullable=False)
    e_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    delta_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    f: Mapped[float] = mapped_column(Float, nullable=False)
    pf: Mapped[float] = mapped_column(Float, nullable=False)
    rssi: Mapped[int] = mapped_column(Integer, nullable=False)
    is_gap: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("device_id", "ts", name="uq_device_ts"),
        Index("idx_readings_device_ts", "device_id", "ts"),
    )


class HourlyStat(Base):
    __tablename__ = "hourly_stats"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    hour_start: Mapped[int] = mapped_column(Integer, primary_key=True)  # UTC epoch
    kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DailyStat(Base):
    __tablename__ = "daily_stats"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD (WIB)
    kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_rp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tariff_sen: Mapped[int] = mapped_column(Integer, nullable=False)
    p_max: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    p_base: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    details_json: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String(256), nullable=False)
    notified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class ChatLog(Base):
    __tablename__ = "chat_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    tools_used: Mapped[str] = mapped_column(String, nullable=False)
    answer: Mapped[str] = mapped_column(String, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
