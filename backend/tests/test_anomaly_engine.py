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


def test_window_coverage_threshold_24_of_30():
    # Jendela dengan < 24 pembacaan (80%) diabaikan dari perhitungan bucket baseline
    engine = AnomalyEngine(min_bucket_samples=24, min_bucket_days=2)
    start_ts = 1735689600

    # Window dengan 23 sampel dinyatakan tidak lengkap
    w_incomplete = Window5m(
        start_ts=start_ts, sample_count=23, p_avg=100.0, p_max=110.0, p_min=90.0
    )
    assert w_incomplete.is_complete is False

    # Window dengan 24 sampel dinyatakan lengkap
    w_complete = Window5m(
        start_ts=start_ts + 300, sample_count=24, p_avg=100.0, p_max=110.0, p_min=90.0
    )
    assert w_complete.is_complete is True

    # Jika semua jendela dalam riwayat hanya memiliki 23 sampel (< 24),
    # bucket tidak mendapatkan sampel lengkap -> masuk mode belajar
    history = [
        Window5m(
            start_ts=start_ts + (i * 300), sample_count=23, p_avg=100.0, p_max=110.0, p_min=90.0
        )
        for i in range(7 * 288)
    ]
    stats = engine.evaluate_bucket(history, target_is_weekend=False, target_hour=10)
    assert stats.bucket_type == "learning"
    assert stats.sample_count == 0


def test_baseline_masking_robust_to_anomaly_contamination():
    # Menguji ketahanan baseline (masking) terhadap kontaminasi episode anomali
    engine = AnomalyEngine()
    start_ts = 1735664400  # 2025-01-01 00:00:00 WIB
    # Buat 14 hari normal di jam 10.00 WIB (12 jendela/hari x 14 hari = 168 jendela), nilai 100W
    history_clean = []
    for day in range(14):
        d_ts = start_ts + (day * 86400) + (10 * 3600)
        for w in range(12):
            history_clean.append(
                Window5m(
                    start_ts=d_ts + (w * 300),
                    sample_count=30,
                    p_avg=100.0,
                    p_max=110.0,
                    p_min=90.0,
                )
            )

    stats_before = engine.evaluate_bucket(history_clean, target_is_weekend=False, target_hour=10)
    assert stats_before.median == 100.0
    assert stats_before.mad_effective == 10.0

    # Suntikkan 1 episode anomali besar (+800W) selama 1 jam penuh (12 jendela bernilai 900W)
    # di hari terakhir
    history_contaminated = list(history_clean)
    d_anom_ts = start_ts + (14 * 86400) + (10 * 3600)
    for w in range(12):
        history_contaminated.append(
            Window5m(
                start_ts=d_anom_ts + (w * 300),
                sample_count=30,
                p_avg=900.0,
                p_max=950.0,
                p_min=850.0,
            )
        )

    stats_after = engine.evaluate_bucket(
        history_contaminated, target_is_weekend=False, target_hour=10
    )
    # Karena menggunakan statistik robust (median & MAD), median dan MAD baseline
    # sebelum dan sesudah episode anomali tetap identik (100W & 10W)
    assert stats_after.median == stats_before.median
    assert stats_after.mad_effective == stats_before.mad_effective


def test_persistence_across_hour_boundary_with_different_baselines():
    # Menguji akumulasi persistensi 3 jendela yang melintasi batas pergantian jam (jam 9 -> jam 10)
    # di mana jam 9 memiliki baseline 200W dan jam 10 memiliki baseline 600W
    engine = AnomalyEngine(z_threshold=3.5, delta_threshold_w=100.0, persistence_windows=3)
    start_ts = 1735689600

    # Buat 7 hari riwayat dengan jam 9 = 200W, jam 10 = 600W
    history = []
    for day in range(7):
        d_ts = start_ts + (day * 86400)
        # Jam 9 (200W)
        for w in range(12):
            history.append(
                Window5m(
                    start_ts=d_ts + (9 * 3600) + (w * 300),
                    sample_count=30,
                    p_avg=200.0,
                    p_max=220.0,
                    p_min=180.0,
                )
            )
        # Jam 10 (600W)
        for w in range(12):
            history.append(
                Window5m(
                    start_ts=d_ts + (10 * 3600) + (w * 300),
                    sample_count=30,
                    p_avg=600.0,
                    p_max=640.0,
                    p_min=560.0,
                )
            )

    eval_day_ts = start_ts + (7 * 86400)

    # Jendela 1: Jam 09:50 WIB -> P = 500W (+300W di atas baseline jam 9 sebesar 200W) -> Kandidat 1
    w1 = Window5m(
        start_ts=eval_day_ts + (9 * 3600) + (10 * 300),
        sample_count=30,
        p_avg=500.0,
        p_max=520.0,
        p_min=480.0,
    )
    res1 = engine.evaluate_window(w1, history, consecutive_candidates=0)
    assert res1.is_candidate is True
    assert res1.consecutive_count == 1
    assert res1.is_anomaly_alert is False

    # Jendela 2: Jam 09:55 WIB -> P = 500W (+300W di atas baseline jam 9) -> Kandidat 2
    w2 = Window5m(
        start_ts=eval_day_ts + (9 * 3600) + (11 * 300),
        sample_count=30,
        p_avg=500.0,
        p_max=520.0,
        p_min=480.0,
    )
    res2 = engine.evaluate_window(w2, history, consecutive_candidates=res1.consecutive_count)
    assert res2.is_candidate is True
    assert res2.consecutive_count == 2
    assert res2.is_anomaly_alert is False

    # Jendela 3: Jam 10:00 WIB (melintasi batas jam!)
    # Baseline jam 10 adalah 600W. P = 1000W (+400W di atas baseline jam 10) -> Kandidat 3 -> Alert!
    w3 = Window5m(
        start_ts=eval_day_ts + (10 * 3600),
        sample_count=30,
        p_avg=1000.0,
        p_max=1050.0,
        p_min=950.0,
    )
    res3 = engine.evaluate_window(w3, history, consecutive_candidates=res2.consecutive_count)
    assert res3.is_candidate is True
    assert res3.consecutive_count == 3
    assert res3.is_anomaly_alert is True
    # Pastikan jendela 3 dinilai terhadap baseline jam 10 (600W), bukan jam 9
    assert res3.baseline_median == 600.0


def test_eval_lightweight_dev_seed_normal_and_transients():
    # Tes evaluasi ringan 1 seed pengembangan (seed 42, 3 hari evaluasi)
    # Memastikan 0 alarm palsu pada data normal dan transien (kettle/kompresor < 10m)
    from scripts.synthetic_data import generate_synthetic_dataset

    engine = AnomalyEngine()
    # 14 hari training + 3 hari evaluasi = total 17 hari
    dataset = generate_synthetic_dataset(seed=42, total_days=17)

    triggered_alerts = []
    consecutive_cand = 0
    cooldown_seconds = 1800
    last_alert_ts = -cooldown_seconds

    eval_start_idx = 14 * 288
    for i in range(eval_start_idx, len(dataset.windows)):
        curr_w = dataset.windows[i]
        history = dataset.windows[max(0, i - 4032) : i]
        res = engine.evaluate_window(curr_w, history, consecutive_cand)
        consecutive_cand = res.consecutive_count

        if res.is_anomaly_alert:
            if curr_w.start_ts - last_alert_ts >= cooldown_seconds:
                triggered_alerts.append(curr_w.start_ts)
                last_alert_ts = curr_w.start_ts

    # Semua alert yang terpicu harus jatuh di dalam anomali berlabel nyata,
    # dan transien (<10m) tidak boleh memicu alert
    for tr in dataset.transients:
        # Tidak boleh ada alert yang terpicu akibat transien murni
        tr_end = tr.start_ts + (tr.duration_minutes * 60)
        # Jika transien berada di luar anomali L2, tidak boleh ada alert di rentang itu
        is_overlapping_l2 = any(
            (an.start_ts <= tr.start_ts <= an.end_ts) for an in dataset.ground_truth_l2
        )
        if not is_overlapping_l2:
            tr_alerts = [ts for ts in triggered_alerts if tr.start_ts <= ts <= tr_end + 300]
            assert len(tr_alerts) == 0

    # Cek false positive di luar anomali berlabel L2
    fp_alerts = [
        ts for ts in triggered_alerts
        if not any((an.start_ts <= ts <= an.end_ts + 300) for an in dataset.ground_truth_l2)
    ]
    assert len(fp_alerts) == 0
