from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    auth_provider: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    google_sub: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    terms_version_accepted: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    terms_accepted_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plan_tier: Mapped[str] = mapped_column(String(16), default="free", nullable=False)
    plan_expires_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plan_updated_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )
    last_login_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # qris | bank | ewallet
    type: Mapped[str] = mapped_column(String(16), default="bank", nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    account_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    account_holder: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    qris_image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )


class UpgradeRequest(Base):
    __tablename__ = "upgrade_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, nullable=True)
    requested_tier: Mapped[str] = mapped_column(String(16), default="pro", nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(16), default="monthly", nullable=False)
    amount_rp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_method_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_method_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    payment_method_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payment_account_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payment_account_holder: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payment_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payment_proof_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    user_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )
    resolved_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class TermsConsent(Base):
    __tablename__ = "terms_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    email_snapshot: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    terms_version: Mapped[str] = mapped_column(String(32), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    accepted_via: Mapped[str] = mapped_column(String(32), default="web", nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    accepted_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )


class UserSetting(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)
    used_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    mcb_watt: Mapped[int] = mapped_column(Integer, default=2200, nullable=False)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    is_public_demo: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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
        Index("idx_readings_device_ts_pv", "device_id", "ts", "p", "v"),
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


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(String(256), nullable=False)
    notified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AlertState(Base):
    __tablename__ = "alert_state"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)  # active, cleared
    since: Mapped[int] = mapped_column(Integer, nullable=False)
    last_notified_at: Mapped[int] = mapped_column(Integer, nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ScheduledReportsLog(Base):
    __tablename__ = "scheduled_reports_log"

    report_type: Mapped[str] = mapped_column(String(16), primary_key=True)  # daily, weekly
    report_date: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD (WIB)
    sent_at: Mapped[int] = mapped_column(Integer, nullable=False)


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class ChatLog(Base):
    __tablename__ = "chat_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ts: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    tools_used: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PushToken(Base):
    __tablename__ = "push_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(16), default="android", nullable=False)
    device_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )
    updated_at: Mapped[int] = mapped_column(
        Integer, default=lambda: int(datetime.now(timezone.utc).timestamp()), nullable=False
    )


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="alert", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="warning", nullable=False)
    data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    is_read: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    pushed_fcm: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[int] = mapped_column(
        Integer,
        default=lambda: int(datetime.now(timezone.utc).timestamp()),
        nullable=False,
        index=True,
    )

