from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import DailyStat, Device, Reading, Setting
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}
TZ_WIB = ZoneInfo("Asia/Jakarta")


def setup_summary_db():
    _, session = open_clean_test_session()

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


def test_summary_range_today_equals_daily_stat():
    session = setup_summary_db()
    from app.services.aggregation import update_daily_stat
    from app.services.cost import calculate_cost_rp

    now_wib = datetime.now(tz=TZ_WIB)
    start_today = datetime.combine(now_wib.date(), time(0, 0, 0), tzinfo=TZ_WIB)
    ts_start = int(start_today.timestamp())

    # Masukkan data 8.434 kWh hari ini
    r1 = Reading(
        device_id="esp_sum",
        ts=ts_start + 1800,
        v=220.0,
        i=2.0,
        p=440.0,
        e_kwh=10.0,
        delta_kwh=8.434,
        f=50.0,
        pf=1.0,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    # Hitung daily_stat hari ini
    d_stat = update_daily_stat(session, "esp_sum", ts_start + 1800)
    session.commit()

    res = client.get("/api/devices/esp_sum/summary?range=today", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    expected_cost = calculate_cost_rp(8.434, 144470, 0.0)
    assert expected_cost == 12185
    assert abs(data["cost_rp"] - d_stat.cost_rp) <= 1
    assert data["cost_rp"] == 12185

    app.dependency_overrides.clear()


def test_summary_sub_day_decimal_cost():
    session = setup_summary_db()
    from app.services.cost import calculate_cost_rp

    now_wib = datetime.now(tz=TZ_WIB)
    start_today = datetime.combine(now_wib.date(), time(0, 0, 0), tzinfo=TZ_WIB)
    ts_start = int(start_today.timestamp())

    # Jendela sub-hari: 10:00 s.d. 12:00 WIB (2 jam)
    sub_from = ts_start + (10 * 3600)
    sub_to = ts_start + (12 * 3600)

    # Masukkan reading 3.2 kWh di dalam jendela
    r = Reading(
        device_id="esp_sum",
        ts=sub_from + 1800,
        v=220.0,
        i=1.5,
        p=330.0,
        e_kwh=13.2,
        delta_kwh=3.2,
        f=50.0,
        pf=1.0,
        rssi=-60,
    )
    session.add(r)
    session.commit()

    res = client.get(
        f"/api/devices/esp_sum/summary?from={sub_from}&to={sub_to}", headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["kwh"] == 3.2
    # 3.2 kWh pada tarif 144470 sen -> Rp 4623
    expected_cost = calculate_cost_rp(3.2, 144470, 0.0)
    assert data["cost_rp"] == expected_cost == 4623
    assert data["cost_estimated"] is True

    app.dependency_overrides.clear()


def test_summary_week_and_month_equals_sum_of_daily_costs():
    session = setup_summary_db()
    from app.services.cost import calculate_cost_rp

    now_wib = datetime.now(tz=TZ_WIB)
    today_date = now_wib.date()

    # Pastikan ada 2 hari lampau di daily_stats
    past1 = (today_date - timedelta(days=2)).strftime("%Y-%m-%d")
    past2 = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")

    d1 = DailyStat(
        device_id="esp_sum",
        day=past1,
        kwh=10.0,
        cost_rp=14447,
        tariff_sen=144470,
        p_max=1000.0,
        p_base=150.0,
    )
    d2 = DailyStat(
        device_id="esp_sum",
        day=past2,
        kwh=10.0,
        cost_rp=14447,
        tariff_sen=144470,
        p_max=1000.0,
        p_base=150.0,
    )
    session.add_all([d1, d2])

    # Masukkan data hari ini 2.0 kWh
    start_today = datetime.combine(today_date, time(0, 0, 0), tzinfo=TZ_WIB)
    ts_today = int(start_today.timestamp()) + 3600
    session.add(
        Reading(
            device_id="esp_sum",
            ts=ts_today,
            v=220.0,
            i=1.0,
            p=220.0,
            e_kwh=22.0,
            delta_kwh=2.0,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
    )
    session.commit()

    today_cost = calculate_cost_rp(2.0, 144470, 0.0)
    res_month = client.get("/api/devices/esp_sum/summary?range=month", headers=auth_headers)
    assert res_month.status_code == 200
    data_month = res_month.json()
    # Harus sama dengan jumlah cost_rp harian (hari lampau + hari ini)
    expected_month_cost = d1.cost_rp + d2.cost_rp + today_cost
    assert data_month["cost_rp"] == expected_month_cost

    app.dependency_overrides.clear()


def test_summary_validation_errors():
    setup_summary_db()

    # 1. range bersama from/to -> 422
    res1 = client.get(
        "/api/devices/esp_sum/summary?range=today&from=1700000000", headers=auth_headers
    )
    assert res1.status_code == 422

    # 2. from > to -> 422
    res2 = client.get(
        "/api/devices/esp_sum/summary?from=1700002000&to=1700001000", headers=auth_headers
    )
    assert res2.status_code == 422

    # 3. Rentang > 366 hari -> 422
    res3 = client.get(
        f"/api/devices/esp_sum/summary?from=1700000000&to={1700000000 + (367 * 86400)}",
        headers=auth_headers,
    )
    assert res3.status_code == 422

    app.dependency_overrides.clear()
