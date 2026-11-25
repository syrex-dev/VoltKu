from decimal import ROUND_HALF_UP, Decimal

from app.models import DailyStat, HourlyStat, Reading, Setting
from app.mqtt_ingest import process_telemetry_payload
from app.services.delta import reset_rejection_tracker
from mysql_test_helper import open_clean_test_session
from sqlalchemy import select


def test_simulation_360_samples_359_intervals():
    """360 sampel berjarak 10 detik mencakup 359 interval (3.590 detik).

    Sesuai kontrak data, sampel pertama adalah baseline (delta = 0).
    Maka energi yang terakumulasi adalah:
    359 interval * (264 W * 10s / 3.600.000) = 0.263266... kWh -> 0.263 kWh (263.3 Wh).
    Biaya: 0.263 * 1444.70 = 379.9561 -> Rp380.
    """
    _, session = open_clean_test_session()

    session.add(Setting(key="tariff_sen_per_kwh", value="144470"))
    session.add(Setting(key="extra_percent", value="0.0"))
    session.commit()

    reset_rejection_tracker()

    device_id = "esp32_sim_359_intervals"
    start_ts = 1736042400
    p_watt = 264.0
    v_volt = 220.0
    i_amp = round(p_watt / v_volt, 3)
    interval = 10
    total_samples = 360  # 359 interval
    start_e = 100.000

    curr_ts = start_ts
    for step in range(total_samples):
        # Akumulasi fisik meter PZEM seiring waktu:
        # e = start_e + (step * delta_per_interval)
        e_kwh = start_e + (step * (p_watt * interval / 3600000.0))
        payload = {
            "ts": curr_ts,
            "v": v_volt,
            "i": i_amp,
            "p": p_watt,
            "e": round(e_kwh, 3),
            "f": 50.0,
            "pf": 0.98,
            "rssi": -65,
        }
        process_telemetry_payload(session, device_id, payload, default_mcb_watt=2200)
        curr_ts += interval

    readings = list(session.scalars(select(Reading).where(Reading.device_id == device_id)).all())
    assert len(readings) == total_samples

    h_stat = session.scalar(
        select(HourlyStat).where(
            HourlyStat.device_id == device_id,
            HourlyStat.hour_start == (start_ts // 3600) * 3600,
        )
    )
    assert h_stat is not None
    assert h_stat.samples == total_samples
    # 359 interval x 0.0007333... kWh = 0.263 kWh
    assert h_stat.kwh == 0.263

    d_stat = session.scalar(select(DailyStat).where(DailyStat.device_id == device_id))
    assert d_stat is not None
    assert d_stat.kwh == 0.263
    # 0.263 * 1444.70 = 379.9561 -> Rp380
    expected_cost = int(
        (Decimal("0.263") * Decimal(144470) / Decimal(100)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    assert expected_cost == 380
    assert d_stat.cost_rp == expected_cost


def test_simulation_361_samples_exact_1_hour():
    """361 sampel mencakup tepat 360 interval x 10 detik = 3.600 detik (1 jam penuh).

    Sampel 0: baseline (delta = 0).
    Sampel 1..360: 360 interval * (264 W * 10s / 3.600.000) = 0.264 kWh (264 Wh).
    Biaya: 0.264 * 1444.70 = 381.4008 -> Rp381.
    """
    _, session = open_clean_test_session()

    session.add(Setting(key="tariff_sen_per_kwh", value="144470"))
    session.add(Setting(key="extra_percent", value="0.0"))
    session.commit()

    reset_rejection_tracker()

    device_id = "esp32_sim_1hour_exact"
    start_ts = 1736042400
    p_watt = 264.0
    v_volt = 220.0
    i_amp = round(p_watt / v_volt, 3)
    interval = 10
    total_samples = 361  # 360 interval = 3600 detik = 1 jam
    start_e = 100.000

    curr_ts = start_ts
    for step in range(total_samples):
        e_kwh = start_e + (step * (p_watt * interval / 3600000.0))
        payload = {
            "ts": curr_ts,
            "v": v_volt,
            "i": i_amp,
            "p": p_watt,
            "e": round(e_kwh, 3),
            "f": 50.0,
            "pf": 0.98,
            "rssi": -65,
        }
        process_telemetry_payload(session, device_id, payload, default_mcb_watt=2200)
        curr_ts += interval

    readings = list(session.scalars(select(Reading).where(Reading.device_id == device_id)).all())
    assert len(readings) == 361

    # Jam pertama [start_ts, start_ts + 3600) memuat tepat 360 sampel (0 s.d. 3590s)
    h_stat = session.scalar(
        select(HourlyStat).where(
            HourlyStat.device_id == device_id,
            HourlyStat.hour_start == (start_ts // 3600) * 3600,
        )
    )
    assert h_stat is not None
    assert h_stat.samples == 360
    assert h_stat.kwh == 0.263

    # Sampel ke-361 (pada detik ke-3600) masuk ke jam berikutnya
    h_stat_next = session.scalar(
        select(HourlyStat).where(
            HourlyStat.device_id == device_id,
            HourlyStat.hour_start == ((start_ts // 3600) * 3600) + 3600,
        )
    )
    assert h_stat_next is not None
    assert h_stat_next.samples == 1
    assert h_stat_next.kwh == 0.001

    # Total harian mengakumulasi 360 interval penuh = 0.264 kWh
    d_stat = session.scalar(select(DailyStat).where(DailyStat.device_id == device_id))
    assert d_stat is not None
    assert d_stat.kwh == 0.264
    expected_cost = int(
        (Decimal("0.264") * Decimal(144470) / Decimal(100)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    assert expected_cost == 381
    assert d_stat.cost_rp == expected_cost
