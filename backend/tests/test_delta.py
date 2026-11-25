import random

from app.models import Reading
from app.mqtt_ingest import process_telemetry_payload
from app.services.delta import calculate_delta_kwh, reset_rejection_tracker
from mysql_test_helper import open_clean_test_session
from sqlalchemy import select


def get_test_session():
    _, session = open_clean_test_session()
    return session


def test_delta_first_sample_from_db():
    session = get_test_session()
    reset_rejection_tracker()

    # Sampel pertama pada DB kosong -> delta = 0.0
    delta, is_gap, baseline_id = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000000,
        e_kwh=10.0,
        mcb_watt=2200,
    )
    assert delta == 0.0
    assert is_gap == 0
    assert baseline_id is None


def test_delta_restart_verified_from_db():
    session = get_test_session()
    reset_rejection_tracker()

    # Simulasikan ada record di DB sebelum backend restart
    prev = Reading(
        device_id="esp_1",
        ts=1736000000,
        v=220,
        i=1,
        p=220,
        e_kwh=10.0,
        delta_kwh=0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(prev)
    session.commit()

    # Backend restart: memori tracker direset
    reset_rejection_tracker()

    # Sampel pertama setelah restart mengambil baseline langsung dari DB
    delta, is_gap, baseline_id = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000010,
        e_kwh=10.005,
        mcb_watt=2200,
    )
    assert delta == 0.005
    assert baseline_id == prev.id


def test_delta_normal_sequence():
    session = get_test_session()
    reset_rejection_tracker()

    r1 = Reading(
        device_id="esp_1",
        ts=1736000000,
        v=220,
        i=1,
        p=220,
        e_kwh=50.0,
        delta_kwh=0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    delta, is_gap, baseline_id = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000010,
        e_kwh=50.008,
        mcb_watt=2200,
    )
    assert delta == 0.008
    assert is_gap == 0
    assert baseline_id == r1.id


def test_delta_glitch_then_normal_sample():
    session = get_test_session()
    reset_rejection_tracker()

    # Sampel awal: 50.0 kWh
    r1 = Reading(
        device_id="esp_1",
        ts=1736000000,
        v=220,
        i=1,
        p=220,
        e_kwh=50.0,
        delta_kwh=0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    # Glitch tinggi tak wajar: tiba-tiba 150.0 kWh dalam 10 detik
    delta_glitch, _, _ = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000010,
        e_kwh=150.0,
        mcb_watt=2200,
    )
    assert delta_glitch == 0.0  # Ditolak

    # Sampel berikutnya normal: 50.008 kWh (terhadap baseline r1 yang belum maju)
    delta_normal, _, baseline_id = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000020,
        e_kwh=50.008,
        mcb_watt=2200,
    )
    assert delta_normal == 0.008
    assert baseline_id == r1.id


def test_delta_counter_reset_normal():
    session = get_test_session()
    reset_rejection_tracker()

    r1 = Reading(
        device_id="esp_1",
        ts=1736000000,
        v=220,
        i=1,
        p=220,
        e_kwh=100.0,
        delta_kwh=0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    # Reset tombol PZEM: e_baru = 0.005 kWh (dalam batas wajar dt=10s)
    delta, is_gap, baseline_id = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000010,
        e_kwh=0.005,
        mcb_watt=2200,
    )
    assert delta == 0.005
    assert baseline_id == r1.id


def test_delta_counter_reset_too_large():
    session = get_test_session()
    reset_rejection_tracker()

    r1 = Reading(
        device_id="esp_1",
        ts=1736000000,
        v=220,
        i=1,
        p=220,
        e_kwh=100.0,
        delta_kwh=0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    # Reset tapi e_baru langsung 50.0 kWh (melebihi batas wajar untuk dt=10s)
    delta, _, _ = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000010,
        e_kwh=50.0,
        mcb_watt=2200,
    )
    assert delta == 0.0  # Ditolak


def test_delta_three_consecutive_rejections_baseline():
    session = get_test_session()
    reset_rejection_tracker()

    r1 = Reading(
        device_id="esp_1",
        ts=1736000000,
        v=220,
        i=1,
        p=220,
        e_kwh=10.0,
        delta_kwh=0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    # Penolakan 1
    d1, _, _ = calculate_delta_kwh(
        session=session, device_id="esp_1", ts=1736000010, e_kwh=200.0, mcb_watt=2200
    )
    assert d1 == 0.0

    # Penolakan 2
    d2, _, _ = calculate_delta_kwh(
        session=session, device_id="esp_1", ts=1736000020, e_kwh=200.005, mcb_watt=2200
    )
    assert d2 == 0.0

    # Penolakan 3 -> Memicu penetapan baseline baru
    d3, _, baseline = calculate_delta_kwh(
        session=session, device_id="esp_1", ts=1736000030, e_kwh=200.010, mcb_watt=2200
    )
    assert d3 == 0.0
    assert baseline is None


def test_delta_gap_detection():
    session = get_test_session()
    reset_rejection_tracker()

    r1 = Reading(
        device_id="esp_1",
        ts=1736000000,
        v=220,
        i=1,
        p=220,
        e_kwh=50.0,
        delta_kwh=0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r1)
    session.commit()

    # Interval normal (10s) -> bukan gap
    _, is_gap_normal, _ = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000010,
        e_kwh=50.005,
        publish_interval=10,
    )
    assert is_gap_normal == 0

    # Gap panjang: dt = 300s (> 3 * 10s) -> is_gap = 1, delta tetap dihitung (energi riil)
    delta_gap, is_gap_long, _ = calculate_delta_kwh(
        session=session,
        device_id="esp_1",
        ts=1736000300,
        e_kwh=50.100,
        publish_interval=10,
    )
    assert is_gap_long == 1
    assert delta_gap == 0.100


def test_property_random_arrival_delta_conservation():
    """Tes Properti: Tanpa reset dan tanpa penolakan, sum(delta_kwh) == e_terakhir - e_pertama

    untuk 200 permutasi kedatangan data yang diacak, mencetak seed bila gagal.
    """
    p_watt = 360.0
    interval = 10
    n_points = 15

    session = get_test_session()
    try:
        for seed in range(200):
            reset_rejection_tracker()
            device_id = f"esp_prop_{seed}"
            start_ts = 1736000000
            start_e = 50.000

            payloads = []
            for step in range(n_points):
                ts = start_ts + (step * interval)
                e = start_e + (step * 0.001)
                payloads.append(
                    {
                        "ts": ts,
                        "v": 220.0,
                        "i": 1.636,
                        "p": p_watt,
                        "e": round(e, 3),
                        "f": 50.0,
                        "pf": 0.98,
                        "rssi": -60,
                    }
                )

            e_first = payloads[0]["e"]
            e_last = payloads[-1]["e"]
            expected_total_delta = round(e_last - e_first, 3)

            rng = random.Random(seed)
            shuffled = list(payloads)
            rng.shuffle(shuffled)

            try:
                for p in shuffled:
                    process_telemetry_payload(
                        session,
                        device_id,
                        p,
                        default_mcb_watt=2200,
                        commit=False,
                        update_stats=False,
                    )
                session.commit()

                stmt = (
                    select(Reading).where(Reading.device_id == device_id).order_by(Reading.ts.asc())
                )
                saved_readings = list(session.scalars(stmt).all())
                assert len(saved_readings) == n_points, f"Seed {seed}: row count mismatch"

                actual_sum_delta = round(sum(r.delta_kwh for r in saved_readings), 3)
                assert actual_sum_delta == expected_total_delta, (
                    f"Seed {seed}: actual sum {actual_sum_delta} != expected {expected_total_delta}"
                )
            except Exception as err:
                print(f"FAILED PROPERTY TEST ON SEED: {seed}")
                raise err
    finally:
        session.close()
