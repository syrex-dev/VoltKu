from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Base, DailyStat, Device, Reading, Setting
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}
TZ_WIB = ZoneInfo("Asia/Jakarta")


def setup_summary_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    session.add_all(
        [
            Setting(key="tariff_sen_per_kwh", value="144470"),
            Setting(key="extra_percent", value="0.0"),
            Device(id="esp_sum", name="Sum Test Device", mcb_watt=2200, status="online"),
        ]
    )
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return session


def test_summary_range_today_and_wib_boundaries():
    session = setup_summary_db()
    now_wib = datetime.now(tz=TZ_WIB)
    start_today = datetime.combine(now_wib.date(), time(0, 0, 0), tzinfo=TZ_WIB)
    ts_start = int(start_today.timestamp())

    # Masukkan beberapa reading hari ini
    r1 = Reading(
        device_id="esp_sum",
        ts=ts_start + 3600,
        v=220.0,
        i=1.0,
        p=220.0,
        e_kwh=10.0,
        delta_kwh=0.5,
        f=50.0,
        pf=1.0,
        rssi=-60,
    )
    r2 = Reading(
        device_id="esp_sum",
        ts=ts_start + 7200,
        v=220.0,
        i=2.0,
        p=440.0,
        e_kwh=10.5,
        delta_kwh=0.5,
        f=50.0,
        pf=1.0,
        rssi=-60,
    )
    session.add_all([r1, r2])
    session.commit()

    res = client.get("/api/devices/esp_sum/summary?range=today", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["kwh"] == 1.0
    assert data["avg_power_w"] == 330.0
    assert data["peak_w"] == 440.0
    assert data["peak_ts"] == ts_start + 7200
    assert data["cost_estimated"] is True  # Hari berjalan adalah estimasi
    assert data["cost_rp"] > 0

    app.dependency_overrides.clear()


def test_summary_exact_past_day_boundaries_frozen_tariff():
    session = setup_summary_db()

    # Buat 2 hari lampau penuh
    day1_str = "2026-11-01"
    day2_str = "2026-11-02"

    d1 = DailyStat(
        device_id="esp_sum",
        day=day1_str,
        kwh=10.0,
        cost_rp=14447,
        tariff_sen=144470,
        p_max=1000.0,
        p_base=150.0,
    )
    d2 = DailyStat(
        device_id="esp_sum",
        day=day2_str,
        kwh=10.0,
        cost_rp=14447,
        tariff_sen=144470,
        p_max=1000.0,
        p_base=150.0,
    )
    session.add_all([d1, d2])

    # Masukkan readings pendukung
    dt1 = datetime.strptime(day1_str, "%Y-%m-%d").replace(tzinfo=TZ_WIB)
    dt2 = datetime.strptime(day2_str, "%Y-%m-%d").replace(tzinfo=TZ_WIB)
    ts1 = int(dt1.timestamp())
    ts2 = int(datetime.combine(dt2.date(), time(23, 59, 59), tzinfo=TZ_WIB).timestamp())

    r1 = Reading(
        device_id="esp_sum",
        ts=ts1 + 3600,
        v=220.0,
        i=1.0,
        p=220.0,
        e_kwh=10.0,
        delta_kwh=20.0,
        f=50.0,
        pf=1.0,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    # Kueri rentang pas batas hari lampau
    res = client.get(f"/api/devices/esp_sum/summary?from={ts1}&to={ts2}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["cost_estimated"] is False  # Rentang pas hari lampau bukan estimasi
    assert data["cost_rp"] == 14447 + 14447  # Jumlah tepat cost_rp harian dari daily_stats

    app.dependency_overrides.clear()
