import logging
import time
from unittest.mock import AsyncMock, patch

import pytest
from app.models import AlertState, Anomaly, Base, Device, Reading, Setting
from app.services.bot import (
    cmd_anomali,
    cmd_batas,
    cmd_forecast,
    cmd_laporan,
    cmd_month,
    cmd_now,
    cmd_perangkat,
    cmd_start,
    cmd_tarif,
    cmd_today,
    cmd_week,
    send_message_rate_limited,
    send_telegram_broadcast_sync,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(test_engine)
TestSessionLocal = sessionmaker(bind=test_engine)


def get_test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    monkeypatch.setattr("app.services.bot.SessionLocal", TestSessionLocal)
    with TestSessionLocal() as session:
        session.query(Anomaly).delete()
        session.query(AlertState).delete()
        session.query(Reading).delete()
        session.query(Device).delete()
        session.query(Setting).delete()

        session.add(Setting(key="tariff_sen_per_kwh", value="144470"))
        session.add(Setting(key="power_limit_w", value="2200"))
        session.add(Setting(key="report_enabled", value="true"))
        session.add(
            Device(
                id="demo-1",
                name="Warung Demo",
                mcb_watt=2200,
                status="online",
                last_seen_at=int(time.time()),
            )
        )
        session.commit()


@pytest.mark.anyio
async def test_allowlist_ignores_unknown_chat_id(caplog):
    """Chat_id yang tidak terdaftar diabaikan tanpa merespons, dan pesan tidak dibocorkan ke log."""
    caplog.set_level(logging.WARNING)
    update = AsyncMock()
    update.effective_chat.id = 999999999  # Asing
    context = AsyncMock()
    context.args = []

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345678]
        mock_settings.return_value.telegram_bot_token = "SECRET_BOT_TOKEN_12345"

        await cmd_start(update, context)

        # Bot sama sekali tidak memanggil send_message (silent drop)
        context.bot.send_message.assert_not_called()

        # Chat ID asing dan token TIDAK boleh tercatat di log sama sekali
        assert "999999999" not in caplog.text
        assert "SECRET_BOT_TOKEN_12345" not in caplog.text


@pytest.mark.anyio
async def test_no_token_leaks_in_logging(caplog):
    """Memastikan token bot tidak pernah bocor ke caplog saat operasi berjalan
    (termasuk log httpx & telegram).
    """
    caplog.set_level(logging.DEBUG)
    test_token = "BOT_SUPER_SECRET_TOKEN_XYZ_987"
    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]
        mock_settings.return_value.telegram_bot_token = test_token

        update = AsyncMock()
        update.effective_chat.id = 12345
        context = AsyncMock()
        context.args = []

        await cmd_start(update, context)

        # Simulasikan aktivitas logging httpx dan telegram
        logging.getLogger("httpx").debug("HTTP Request POST https://api.telegram.org/bot/sendMessage")
        logging.getLogger("telegram").info("Telegram polling tick processed")

        assert test_token not in caplog.text


@pytest.mark.anyio
async def test_cmd_start_authorized():
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()
    context.args = []

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]
        await cmd_start(update, context)

    context.bot.send_message.assert_called_once()
    sent_text = context.bot.send_message.call_args.kwargs["text"]
    assert "Monitor Listrik Pintar" in sent_text
    assert "/now" in sent_text
    assert "/tarif" in sent_text


@pytest.mark.anyio
async def test_cmd_perangkat():
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]
        await cmd_perangkat(update, context)

    context.bot.send_message.assert_called_once()
    sent_text = context.bot.send_message.call_args.kwargs["text"]
    assert "Warung Demo" in sent_text
    assert "demo-1" in sent_text
    assert "2200 W" in sent_text


@pytest.mark.anyio
async def test_cmd_now_and_multi_device():
    now_ts = int(time.time())
    with TestSessionLocal() as session:
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts,
                v=220.0,
                i=5.0,
                p=1100.0,
                e_kwh=10.0,
                delta_kwh=0.01,
                f=50.0,
                pf=0.98,
                rssi=-65,
            )
        )
        session.commit()

    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()
    context.args = []

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]
        mock_settings.return_value.alert_exclude_device_prefixes = "sim-"

        # 1. Tanpa argumen -> semua perangkat non-sim
        await cmd_now(update, context)
        sent_text1 = context.bot.send_message.call_args.kwargs["text"]
        assert "1.100,0 W" in sent_text1
        assert "220,0 V" in sent_text1

        # 2. Dengan argumen perangkat spesifik
        context.args = ["demo-1"]
        await cmd_now(update, context)
        sent_text2 = context.bot.send_message.call_args.kwargs["text"]
        assert "Warung Demo" in sent_text2

        # 3. Dengan argumen perangkat tidak dikenal
        context.args = ["unknown-dev"]
        await cmd_now(update, context)
        sent_text3 = context.bot.send_message.call_args.kwargs["text"]
        assert "tidak ditemukan" in sent_text3


@pytest.mark.anyio
async def test_cmd_today_week_month_forecast():
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()
    context.args = []

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]
        mock_settings.return_value.alert_exclude_device_prefixes = "sim-"

        # Today
        await cmd_today(update, context)
        assert "Ringkasan Pemakaian Hari Ini" in context.bot.send_message.call_args.kwargs["text"]

        # Week
        await cmd_week(update, context)
        assert "Ringkasan Pemakaian Minggu Ini" in context.bot.send_message.call_args.kwargs["text"]

        # Month
        await cmd_month(update, context)
        assert "Ringkasan Pemakaian Bulan Ini" in context.bot.send_message.call_args.kwargs["text"]

        # Forecast
        await cmd_forecast(update, context)
        assert "Proyeksi Tagihan Akhir Bulan" in context.bot.send_message.call_args.kwargs["text"]


@pytest.mark.anyio
async def test_cmd_anomali():
    now_ts = int(time.time())
    with TestSessionLocal() as session:
        # Tambah 25 baris anomali untuk menguji pemotongan maks 20 baris
        for i in range(25):
            session.add(
                Anomaly(
                    device_id="demo-1",
                    ts=now_ts - (1000 - i * 10),
                    type="power_limit",
                    severity="warning",
                    details_json="{}",
                    message=f"Daya melebihi 2200 W #{i}",
                    notified=1,
                )
            )
        session.commit()

    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()
    context.args = []

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]
        mock_settings.return_value.alert_exclude_device_prefixes = "sim-"

        await cmd_anomali(update, context)
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        # Harus memuat anomali terbaru (#24)
        assert "Daya melebihi 2200 W #24" in sent_text
        assert "[WARNING]" in sent_text
        # Baris anomali yang ditampilkan harus tepat 20 (maks 20)
        item_lines = [line for line in sent_text.splitlines() if line.startswith("• [WARNING]")]
        assert len(item_lines) == 20


@pytest.mark.anyio
async def test_cmd_anomali_empty():
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()
    context.args = ["dev_non_existent"]

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]
        mock_settings.return_value.alert_exclude_device_prefixes = "sim-"

        # Buat device baru tanpa anomali
        with TestSessionLocal() as session:
            if not session.get(Device, "dev_clean"):
                session.add(Device(id="dev_clean", name="Dev Clean", mcb_watt=2200))
                session.commit()

        context.args = ["dev_clean"]
        await cmd_anomali(update, context)
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        assert "tidak ada" in sent_text.lower()


@pytest.mark.anyio
async def test_cmd_tarif_validation():
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]

        # 1. Sukses: input format koma 1444,70 -> tariff_sen 144470
        context.args = ["1444,70"]
        await cmd_tarif(update, context)
        with TestSessionLocal() as session:
            val = session.scalar(select(Setting.value).where(Setting.key == "tariff_sen_per_kwh"))
            assert val == "144470"

        # 2. Tolak desimal > 2: 1444.755 ditolak (konsisten dengan API)
        context.args = ["1444.755"]
        await cmd_tarif(update, context)
        sent_text = context.bot.send_message.call_args.kwargs["text"]
        assert "tidak valid" in sent_text
        # Nilai di DB tidak berubah
        with TestSessionLocal() as session:
            val = session.scalar(select(Setting.value).where(Setting.key == "tariff_sen_per_kwh"))
            assert val == "144470"

        # 3. Tolak nilai negatif
        context.args = ["-500"]
        await cmd_tarif(update, context)
        assert "tidak valid" in context.bot.send_message.call_args.kwargs["text"]


@pytest.mark.anyio
async def test_cmd_batas_power():
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]

        # Valid
        context.args = ["3500"]
        await cmd_batas(update, context)
        with TestSessionLocal() as session:
            val = session.scalar(select(Setting.value).where(Setting.key == "power_limit_w"))
            assert val == "3500"

        # Invalid
        context.args = ["invalid_watt"]
        await cmd_batas(update, context)
        assert "tidak valid" in context.bot.send_message.call_args.kwargs["text"]


@pytest.mark.anyio
async def test_cmd_laporan_toggle():
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = [12345]

        # Matikan
        context.args = ["off"]
        await cmd_laporan(update, context)
        with TestSessionLocal() as session:
            val = session.scalar(select(Setting.value).where(Setting.key == "report_enabled"))
            assert val == "false"

        # Hidupkan kembali
        context.args = ["on"]
        await cmd_laporan(update, context)
        with TestSessionLocal() as session:
            val = session.scalar(select(Setting.value).where(Setting.key == "report_enabled"))
            assert val == "true"


@pytest.mark.anyio
async def test_message_truncation_at_4096():
    bot = AsyncMock()
    long_msg = "X" * 5000
    await send_message_rate_limited(bot, chat_id=12345, text=long_msg)

    bot.send_message.assert_called_once()
    sent_text = bot.send_message.call_args.kwargs["text"]
    assert len(sent_text) == 4096
    assert sent_text.endswith("...")


def test_send_telegram_broadcast_sync():
    mock_app = AsyncMock()
    mock_app.bot = AsyncMock()

    with patch("app.services.bot._bot_app", mock_app):
        with patch("app.services.bot.get_settings") as mock_settings:
            mock_settings.return_value.allowed_chat_id_list = [123, 456]
            success = send_telegram_broadcast_sync("Halo semua")
            assert success is True
            assert mock_app.bot.send_message.call_count == 2


def test_send_telegram_broadcast_partial_failure_returns_false():
    """Jika salah satu chat gagal, broadcast dianggap gagal (False) agar state tidak maju."""
    mock_app = AsyncMock()
    mock_bot = AsyncMock()

    async def _send_side_effect(*args, **kwargs):
        if kwargs.get("chat_id") == 456:
            raise RuntimeError("Network failure to chat 456")
        return None

    mock_bot.send_message.side_effect = _send_side_effect
    mock_app.bot = mock_bot

    with patch("app.services.bot._bot_app", mock_app):
        with patch("app.services.bot.get_settings") as mock_settings:
            mock_settings.return_value.allowed_chat_id_list = [123, 456]
            success = send_telegram_broadcast_sync("Pesan broadcast penting")
            assert success is False, "Harus mengembalikan False jika ada chat yang gagal"


@pytest.mark.anyio
async def test_empty_allowlist_drops_all_commands():
    """Allowlist kosong menolak seluruh perintah tanpa merespons."""
    update = AsyncMock()
    update.effective_chat.id = 12345
    context = AsyncMock()
    context.args = []

    with patch("app.services.bot.get_settings") as mock_settings:
        mock_settings.return_value.allowed_chat_id_list = []
        mock_settings.return_value.telegram_allowed_chat_ids = ""

        await cmd_start(update, context)
        context.bot.send_message.assert_not_called()


def test_telegram_failure_does_not_disrupt_ingest_or_scheduler():
    """Kegagalan pengiriman telegram tidak mengganggu proses ingest dan scheduler."""
    from app.mqtt_ingest import process_telemetry_payload
    from app.services.notifier import set_notification_sender
    from app.services.report_generator import check_and_send_catchup_reports

    def failing_sender(msg: str) -> bool:
        raise ConnectionResetError("Simulated Telegram API network reset")

    set_notification_sender(failing_sender)
    try:
        with TestSessionLocal() as session:
            # 1. Ingest telemetri tetap berjalan mulus tanpa terganggu kegagalan telegram
            now_ts = int(time.time())
            payload = {
                "ts": now_ts,
                "v": 220.0,
                "i": 2.0,
                "p": 440.0,
                "e": 1.0,
                "f": 50.0,
                "pf": 1.0,
            }
            reading = process_telemetry_payload(
                session, "demo-1", payload, default_mcb_watt=2200, commit=True
            )
            assert reading is not None
            assert reading.p == 440.0

            # 2. Scheduler catch-up job tidak crash bila notifikasi gagal
            actions = check_and_send_catchup_reports(session)
            assert isinstance(actions, list)
    finally:
        set_notification_sender(None)
