from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Base, DailyStat, Device, HourlyStat, Setting
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}
TZ_WIB = ZoneInfo("Asia/Jakarta")


def setup_forecast_db():
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
            Device(id="esp_fc", name="Forecast Test Device", mcb_watt=2200, status="online"),
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


def test_forecast_no_data():
    setup_forecast_db()
    res = client.get("/api/devices/esp_fc/forecast", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is False
    assert data["basis_days"] == 0
    assert data["projected_kwh"] is None
    assert data["projected_cost_rp"] is None
    app.dependency_overrides.clear()


def test_forecast_excludes_partial_day_and_calculates_exact():
    session = setup_forecast_db()
    now_wib = datetime.now(tz=TZ_WIB)
    today_date = now_wib.date()

    # Buat data 8 hari lampau:
    # Hari ke-8 lampau: hari parsial (hanya 4000 sampel < 7776) -> HARUS DIKECUALIKAN
    # Hari ke-7 s.d. hari ke-2 lampau (6 hari penuh berturut-turut):
    # masing-masing 8640 sampel dan 10.92 kWh
    # Hari ini: parsial (4.74 kWh)

    # 1. Hari parsial lampau (8 hari lalu)
    day_partial = today_date - timedelta(days=8)
    d_partial_str = day_partial.strftime("%Y-%m-%d")
    d_part_start = datetime.combine(day_partial, time(0, 0, 0), tzinfo=TZ_WIB)
    session.add(
        HourlyStat(
            device_id="esp_fc",
            hour_start=int(d_part_start.timestamp()),
            kwh=6.162,
            p_avg=200.0,
            p_max=500.0,
            p_min=100.0,
            samples=4000,  # < 7776!
        )
    )
    session.add(
        DailyStat(
            device_id="esp_fc",
            day=d_partial_str,
            kwh=6.162,
            cost_rp=8902,
            tariff_sen=144470,
            p_max=500.0,
            p_base=140.0,
        )
    )

    # 2. Enam hari penuh lampau (7 hari lalu s.d. kemarin)
    full_day_kwhs = [10.933, 10.916, 10.924, 10.934, 10.902, 10.911]  # avg ~10.92
    for idx, kwh_val in enumerate(full_day_kwhs):
        day_d = today_date - timedelta(days=7 - idx)
        d_str = day_d.strftime("%Y-%m-%d")
        d_start = datetime.combine(day_d, time(0, 0, 0), tzinfo=TZ_WIB)
        session.add(
            HourlyStat(
                device_id="esp_fc",
                hour_start=int(d_start.timestamp()),
                kwh=kwh_val,
                p_avg=450.0,
                p_max=1070.0,
                p_min=140.0,
                samples=8640,  # Penuh (>= 7776)
            )
        )
        session.add(
            DailyStat(
                device_id="esp_fc",
                day=d_str,
                kwh=kwh_val,
                cost_rp=int(kwh_val * 1444.70),
                tariff_sen=144470,
                p_max=1070.0,
                p_base=142.5,
            )
        )

    # 3. Hari berjalan (hari ini)
    session.add(
        DailyStat(
            device_id="esp_fc",
            day=today_date.strftime("%Y-%m-%d"),
            kwh=4.744,
            cost_rp=6854,
            tariff_sen=144470,
            p_max=630.0,
            p_base=142.0,
        )
    )
    session.commit()

    res = client.get("/api/devices/esp_fc/forecast", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["available"] is True
    assert data["basis_days"] == 6  # Hari parsial 8 hari lalu berhasil dikecualikan!
    assert data["low_confidence"] is False  # 6 >= 3
    assert abs(data["avg_daily_kwh"] - 10.920) < 0.05
    assert data["month_so_far_kwh"] > 70.0
    assert data["projected_kwh"] > 70.0
    assert data["projected_cost_rp"] > 100000

    app.dependency_overrides.clear()
