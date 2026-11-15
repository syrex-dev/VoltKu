from decimal import ROUND_HALF_UP, Decimal

from app.models import Base, DailyStat, HourlyStat, Reading, Setting
from app.mqtt_ingest import process_telemetry_payload
from app.services.delta import reset_rejection_tracker
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def test_one_hour_simulation_matches_manual_calculation():
    """Simulasi 1 jam penuh (360 sampel, interval 10s, beban stabil P=264 W).

    Memverifikasi bahwa total kWh dan biaya di SQLite cocok 100% dengan
    perhitungan analitis manual.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Setup tarif: Rp1.444,70/kWh (144470 sen), extra_percent: 0%
    session.add(Setting(key="tariff_sen_per_kwh", value="144470"))
    session.add(Setting(key="extra_percent", value="0.0"))
    session.commit()

    reset_rejection_tracker()

    device_id = "esp32_sim_1hour"
    start_ts = 1736042400  # 2025-01-05 02:00:00 UTC (09:00 WIB)
    p_watt = 264.0
    v_volt = 220.0
    i_amp = round(p_watt / v_volt, 3)

    interval = 10
    total_samples = 360  # 360 x 10 detik = 3600 detik = 1 jam

    # Hitungan manual analitis:
    # Konsumsi energi per interval (10s) = (264 W * 10s) / (3600 * 1000) = 0.0007333... kWh
    # Setelah 360 sampel (1 jam): total energi delta = 264 W * 1 jam = 264 Wh = 0.264 kWh
    start_e = 100.000

    curr_ts = start_ts
    for step in range(total_samples):
        # e_kwh bertambah secara linear dari 100.000 ke 100.264
        e_kwh = start_e + (0.264 * (step / (total_samples - 1)))
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

    # 1. Verifikasi data di tabel readings
    readings = list(session.scalars(select(Reading).where(Reading.device_id == device_id)).all())
    assert len(readings) == total_samples

    # 2. Verifikasi agregasi per jam (hourly_stats)
    h_stat = session.scalar(
        select(HourlyStat).where(
            HourlyStat.device_id == device_id,
            HourlyStat.hour_start == (start_ts // 3600) * 3600,
        )
    )
    assert h_stat is not None
    assert h_stat.samples == total_samples
    assert h_stat.p_avg == 264.0
    assert h_stat.p_max == 264.0
    assert h_stat.p_min == 264.0
    # Akumulasi kWh harus presisi 0.264 kWh
    assert h_stat.kwh == 0.264

    # 3. Verifikasi agregasi harian (daily_stats)
    d_stat = session.scalar(select(DailyStat).where(DailyStat.device_id == device_id))
    assert d_stat is not None
    assert d_stat.kwh == 0.264
    assert d_stat.tariff_sen == 144470

    # 4. Hitung manual biaya analitis:
    # 0.264 * 1444.70 = 381.4008 -> pembulatan ROUND_HALF_UP = Rp381
    expected_cost = int(
        (Decimal("0.264") * Decimal(144470) / Decimal(100)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    assert expected_cost == 381
    assert d_stat.cost_rp == expected_cost
