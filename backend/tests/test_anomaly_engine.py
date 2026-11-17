from app.services.anomaly_engine import (
    AnomalyEngine,
    Window5m,
    calculate_median_mad,
)


def test_calculate_median_mad():
    values = [100.0, 102.0, 98.0, 101.0, 99.0]
    med, mad_raw, mad_eff = calculate_median_mad(values)
    assert med == 100.0
    # Selisih absolut: [0, 2, 2, 1, 1] -> median = 1.0
    assert mad_raw == 1.0
    # Floor: max(1.0, 10.0, 0.05 * 100 = 5.0) -> 10.0
    assert mad_eff == 10.0


def test_mad_minimum_floor_prevents_division_by_zero():
    # Semua nilai sama persis
    values = [200.0] * 30
    med, mad_raw, mad_eff = calculate_median_mad(values)
    assert med == 200.0
    assert mad_raw == 0.0
    # 5% dari 200 = 10.0; max(0.0, 10.0, 10.0) = 10.0
    assert mad_eff == 10.0


def test_learning_mode_when_history_under_3_days():
    engine = AnomalyEngine()
    start_ts = 1735689600  # Hari 1 00.00 WIB
    # Buat hanya 1 hari riwayat (288 jendela)
    history = [
        Window5m(
            start_ts=start_ts + (i * 300), sample_count=30, p_avg=100.0, p_max=110.0, p_min=90.0
        )
        for i in range(288)
    ]
    curr_w = Window5m(
        start_ts=start_ts + (288 * 300), sample_count=30, p_avg=300.0, p_max=320.0, p_min=280.0
    )

    res = engine.evaluate_window(curr_w, history, consecutive_candidates=0)
    assert res.is_learning_mode is True
    assert res.bucket_type == "learning"
    assert res.is_anomaly_alert is False


def test_bucket_fallback_from_daytype_to_hour_only():
    engine = AnomalyEngine(min_bucket_samples=24, min_bucket_days=2)
    start_ts = 1735689600  # 2025-01-01 (Rabu = Hari Kerja)
    history = []
    # Buat 4 hari (span > 3 hari): Rabu, Kamis, Jumat, Sabtu
    for day in range(4):
        d_ts = start_ts + (day * 86400)
        for w_idx in range(288):
            ts = d_ts + (w_idx * 300)
            history.append(
                Window5m(start_ts=ts, sample_count=30, p_avg=200.0, p_max=220.0, p_min=180.0)
            )

    # Evaluasi jendela hari Minggu (akhir pekan) jam 10.00 WIB
    # Karena akhir pekan di riwayat hanya ada Sabtu (1 hari), harus fallback ke bucket hour_only
    sunday_10am_ts = start_ts + (4 * 86400) + (10 * 3600)
    curr_w = Window5m(
        start_ts=sunday_10am_ts, sample_count=30, p_avg=205.0, p_max=220.0, p_min=190.0
    )

    stats = engine.evaluate_bucket(
        history, target_is_weekend=curr_w.is_weekend, target_hour=curr_w.hour_wib
    )
    assert stats.bucket_type == "hour_only"
    assert stats.sample_count >= 24


def test_persistence_requires_3_consecutive_windows():
    engine = AnomalyEngine(z_threshold=3.5, delta_threshold_w=100.0, persistence_windows=3)
    start_ts = 1735689600
    # Buat 7 hari data stabil 100W
    history = [
        Window5m(
            start_ts=start_ts + (i * 300), sample_count=30, p_avg=100.0, p_max=110.0, p_min=90.0
        )
        for i in range(7 * 288)
    ]
    eval_ts = start_ts + (7 * 86400) + (10 * 3600)

    # Jendela 1: lonjakan 300W (+200W di atas baseline)
    w1 = Window5m(start_ts=eval_ts, sample_count=30, p_avg=300.0, p_max=320.0, p_min=280.0)
    res1 = engine.evaluate_window(w1, history, consecutive_candidates=0)
    assert res1.is_candidate is True
    assert res1.consecutive_count == 1
    assert res1.is_anomaly_alert is False  # Belum 3 jendela

    # Jendela 2: masih lonjakan 300W
    w2 = Window5m(start_ts=eval_ts + 300, sample_count=30, p_avg=300.0, p_max=320.0, p_min=280.0)
    res2 = engine.evaluate_window(w2, history, consecutive_candidates=res1.consecutive_count)
    assert res2.is_candidate is True
    assert res2.consecutive_count == 2
    assert res2.is_anomaly_alert is False  # Belum 3 jendela

    # Jendela 3: masih lonjakan 300W -> Pemicu alert!
    w3 = Window5m(start_ts=eval_ts + 600, sample_count=30, p_avg=300.0, p_max=320.0, p_min=280.0)
    res3 = engine.evaluate_window(w3, history, consecutive_candidates=res2.consecutive_count)
    assert res3.is_candidate is True
    assert res3.consecutive_count == 3
    assert res3.is_anomaly_alert is True  # Alert terpicu pada jendela ke-3!

    # Jendela 4: kembali normal 100W -> Consecutive reset ke 0
    w4 = Window5m(start_ts=eval_ts + 900, sample_count=30, p_avg=100.0, p_max=110.0, p_min=90.0)
    res4 = engine.evaluate_window(w4, history, consecutive_candidates=res3.consecutive_count)
    assert res4.is_candidate is False
    assert res4.consecutive_count == 0
    assert res4.is_anomaly_alert is False


def test_transient_10_minutes_does_not_trigger_alert():
    # Transien 10 menit hanya mengisi 2 jendela 5m, tidak boleh memicu alert
    engine = AnomalyEngine(persistence_windows=3)
    start_ts = 1735689600
    history = [
        Window5m(
            start_ts=start_ts + (i * 300), sample_count=30, p_avg=100.0, p_max=110.0, p_min=90.0
        )
        for i in range(7 * 288)
    ]
    eval_ts = start_ts + (7 * 86400) + (12 * 3600)

    # Jendela 1 (lonjakan kettle 1000W)
    w1 = Window5m(start_ts=eval_ts, sample_count=30, p_avg=1000.0, p_max=1100.0, p_min=900.0)
    res1 = engine.evaluate_window(w1, history, consecutive_candidates=0)
    assert res1.is_anomaly_alert is False

    # Jendela 2 (masih 1000W)
    w2 = Window5m(start_ts=eval_ts + 300, sample_count=30, p_avg=1000.0, p_max=1100.0, p_min=900.0)
    res2 = engine.evaluate_window(w2, history, consecutive_candidates=res1.consecutive_count)
    assert res2.is_anomaly_alert is False

    # Jendela 3 (kettle mati, kembali normal 100W)
    w3 = Window5m(start_ts=eval_ts + 600, sample_count=30, p_avg=100.0, p_max=110.0, p_min=90.0)
    res3 = engine.evaluate_window(w3, history, consecutive_candidates=res2.consecutive_count)
    assert res3.is_anomaly_alert is False
    assert res3.consecutive_count == 0


def test_l3_night_baseload_evaluation():
    engine = AnomalyEngine()
    # 7 hari sebelumnya stabil 70W
    past_7d = [70.0, 72.0, 68.0, 71.0, 69.0, 70.0, 71.0]

    # Kasus 1: Malam ini naik 45W (+64%, >30% dan >30W) -> Alert!
    night_high = [
        Window5m(
            start_ts=1735689600 + (i * 300), sample_count=30, p_avg=115.0, p_max=130.0, p_min=100.0
        )
        for i in range(60)  # 5 jam
    ]
    alert, today_base, ref_base, _ = engine.evaluate_l3_night_baseload(night_high, past_7d)
    assert alert is True
    assert today_base == 115.0
    assert ref_base == 70.0

    # Kasus 2: Malam ini hanya naik 15W (+21%, <30W dan <30%) -> Tidak alert
    night_slight = [
        Window5m(
            start_ts=1735689600 + (i * 300), sample_count=30, p_avg=85.0, p_max=100.0, p_min=70.0
        )
        for i in range(60)
    ]
    alert2, _, _, _ = engine.evaluate_l3_night_baseload(night_slight, past_7d)
    assert alert2 is False
