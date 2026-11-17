"""
scripts/synthetic_data.py
Generator data telemetri sintetis deterministik untuk evaluasi deteksi anomali.
Memodelkan siklus kulkas, jam operasional warung, derau, hari kerja vs akhir pekan,
transien non-anomali (kettle/kompresor < 10m), dan anomali berlabel L2 & L3.
"""

import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

# Tambahkan backend ke sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.anomaly_engine import TZ_WIB, Window5m


@dataclass
class AnomalyLabel:
    anomaly_id: str
    layer: Literal["L2", "L3"]
    difficulty: Literal["mudah", "sulit"]
    start_ts: int
    duration_minutes: int
    magnitude_w: float
    description: str

    @property
    def end_ts(self) -> int:
        return self.start_ts + (self.duration_minutes * 60)


@dataclass
class TransientLabel:
    transient_id: str
    start_ts: int
    duration_minutes: int  # 5-10 menit
    magnitude_w: float
    description: str


@dataclass
class SyntheticDataset:
    seed: int
    windows: list[Window5m]
    ground_truth_l2: list[AnomalyLabel]
    ground_truth_l3: list[AnomalyLabel]
    transients: list[TransientLabel]


def get_base_pattern_power(hour_float: float, is_weekend: bool) -> float:
    """
    Profil daya tipikal warung kelontong berdasarkan jam (WIB):
    - 00.00 - 05.00: Jam tidur/malam (standby ~40W + siklus kulkas ~80W) -> ~70W rata-rata
    - 05.00 - 08.00: Persiapan pagi / buka warung -> 150 - 250W
    - 08.00 - 12.00: Jam ramai pagi (chiller minuman nyala, kasir, lampu) -> 450 - 650W
    - 12.00 - 14.00: Jam istirahat siang (relatif sepi) -> 300 - 400W
    - 14.00 - 17.00: Jam sibuk sore -> 500 - 700W
    - 17.00 - 21.00: Jam puncak malam (semua lampu, TV, pendingin) -> 600 - 850W
    - 21.00 - 24.00: Tutup warung, meredup -> 120 - 200W
    Akhir pekan memiliki aktivitas malam lebih ramai (+20%).
    """
    if 0.0 <= hour_float < 5.0:
        base = 70.0
    elif 5.0 <= hour_float < 8.0:
        base = 150.0 + (hour_float - 5.0) * 40.0
    elif 8.0 <= hour_float < 12.0:
        base = 500.0 + math.sin((hour_float - 8.0) / 4.0 * math.pi) * 120.0
    elif 12.0 <= hour_float < 14.0:
        base = 360.0
    elif 14.0 <= hour_float < 17.0:
        base = 550.0 + (hour_float - 14.0) * 30.0
    elif 17.0 <= hour_float < 21.0:
        base = 650.0 + (100.0 if is_weekend else 40.0)
    else:  # 21.00 - 24.00
        base = 180.0 - (hour_float - 21.0) * 35.0

    if is_weekend and hour_float >= 10.0:
        base *= 1.15

    return base


def generate_synthetic_dataset(
    seed: int = 42,
    total_days: int = 21,  # 14 hari training baseline + 7 hari evaluasi
    start_epoch_wib: int = 1735689600,  # 2025-01-01 00:00:00 WIB (1735664400 UTC)
) -> SyntheticDataset:
    rng = random.Random(seed)

    # 1. Tentukan jadwal anomali L2 berlabel (minimal 10 per seed: 5 mudah, 5 sulit)
    eval_start_day = 14
    l2_labels: list[AnomalyLabel] = []
    # 5 Skenario Mudah: Lonjakan besar (300-600W), durasi 30-60 menit
    for i in range(1, 6):
        # Pilih hari acak di masa evaluasi
        day_offset = rng.randint(eval_start_day, total_days - 1)
        # Pilih jam di luar jam puncak (mis. dini hari atau jam sepi siang)
        hour = rng.choice([1, 2, 3, 13, 14, 22, 23])
        minute = rng.choice([0, 15, 30])
        dur = rng.choice([30, 45, 60])
        mag = rng.uniform(320.0, 580.0)
        start_ts = start_epoch_wib + (day_offset * 86400) + (hour * 3600) + (minute * 60)
        l2_labels.append(AnomalyLabel(
            anomaly_id=f"L2-M-{seed}-{i:02d}",
            layer="L2",
            difficulty="mudah",
            start_ts=start_ts,
            duration_minutes=dur,
            magnitude_w=round(mag, 1),
            description=f"Lonjakan mudah +{mag:.0f}W durasi {dur}m jam {hour:02d}:{minute:02d}",
        ))

    # 5 Skenario Sulit: Lonjakan mendekati ambang (150-250W) atau durasi pas 15 menit
    for i in range(1, 6):
        day_offset = rng.randint(eval_start_day, total_days - 1)
        hour = rng.choice([9, 11, 15, 17, 19, 20])  # Di jam ramai/berfluktuasi
        minute = rng.choice([5, 20, 35])
        dur = rng.choice([15, 20, 25])  # Durasi pas-pasan (3-5 jendela)
        mag = rng.uniform(160.0, 240.0)  # Menantang di jam sibuk
        start_ts = start_epoch_wib + (day_offset * 86400) + (hour * 3600) + (minute * 60)
        l2_labels.append(AnomalyLabel(
            anomaly_id=f"L2-S-{seed}-{i:02d}",
            layer="L2",
            difficulty="sulit",
            start_ts=start_ts,
            duration_minutes=dur,
            magnitude_w=round(mag, 1),
            description=f"Lonjakan sulit +{mag:.0f}W durasi {dur}m jam {hour:02d}:{minute:02d}",
        ))

    # Pastikan jadwal tidak saling tumpang-tindih
    l2_labels.sort(key=lambda a: a.start_ts)

    # 2. Tentukan transien non-anomali (kettle, kompresor start: 5 - 10 menit)
    # Transien ini memiliki magnitude besar (300-800W) tetapi TIDAK boleh memicu alert
    # karena durasinya < 3 jendela 5m (hanya 1 atau 2 jendela)
    transients: list[TransientLabel] = []
    for i in range(1, 15):
        day_offset = rng.randint(eval_start_day, total_days - 1)
        hour = rng.randint(6, 22)
        minute = rng.choice([0, 10, 20, 30, 40, 50])
        dur = rng.choice([5, 8, 10])  # Maks 10 menit (1-2 jendela)
        mag = rng.uniform(350.0, 750.0)
        t_start = start_epoch_wib + (day_offset * 86400) + (hour * 3600) + (minute * 60)
        transients.append(TransientLabel(
            transient_id=f"TR-{seed}-{i:02d}",
            start_ts=t_start,
            duration_minutes=dur,
            magnitude_w=round(mag, 1),
            description=f"Transien non-anomali {mag:.0f}W durasi {dur}m",
        ))

    # 3. Anomali L3: Injeksi peningkatan beban dasar malam pada satu hari tertentu
    l3_labels: list[AnomalyLabel] = []
    l3_day = eval_start_day + 3  # Hari ke-17
    l3_start_ts = start_epoch_wib + (l3_day * 86400)  # 00.00 WIB
    l3_labels.append(AnomalyLabel(
        anomaly_id=f"L3-{seed}-01",
        layer="L3",
        difficulty="mudah",
        start_ts=l3_start_ts,
        duration_minutes=300,  # 5 jam penuh (00.00 - 05.00 WIB)
        magnitude_w=45.0,  # Naik 45W (dari ~70W -> ~115W, >30% dan >30W)
        description="Beban dasar malam naik +45W (kulkas bocor / alat lupa mati)",
    ))

    # 4. Generate jendela 5 menit
    windows: list[Window5m] = []
    total_windows = total_days * 288  # 288 jendela per hari

    # Faktor variasi cuaca / operasional per hari (+/- 15%)
    daily_factors = [1.0 + rng.uniform(-0.15, 0.15) for _ in range(total_days)]
    # Satu hari tak biasa (mis. hari ke-10 toko tutup awal / hujan deras -30%)
    daily_factors[10] = 0.70

    for w_idx in range(total_windows):
        ts = start_epoch_wib + (w_idx * 300)
        day_num = w_idx // 288
        minute_in_day = (w_idx % 288) * 5
        hour_float = minute_in_day / 60.0

        dt = datetime.fromtimestamp(ts, tz=TZ_WIB)
        is_weekend = dt.weekday() >= 5

        # Nilai dasar
        base_p = get_base_pattern_power(hour_float, is_weekend) * daily_factors[day_num]

        # Siklus kulkas (periode ~30m: 15m on +80W, 15m off)
        fridge_cycle = 80.0 if ((minute_in_day % 30) < 15) else 0.0

        # Derau acak deterministik (+/- 5%)
        noise = rng.gauss(0.0, 15.0)

        p_total = base_p + fridge_cycle + noise

        # Suntikkan anomali L2 jika waktu berada di dalam rentang
        for anom in l2_labels:
            if anom.start_ts <= ts < anom.end_ts:
                p_total += anom.magnitude_w

        # Suntikkan transien
        for tr in transients:
            if tr.start_ts <= ts < (tr.start_ts + tr.duration_minutes * 60):
                p_total += tr.magnitude_w

        # Suntikkan anomali L3 malam
        for anom3 in l3_labels:
            if anom3.start_ts <= ts < anom3.end_ts:
                p_total += anom3.magnitude_w

        # Jendela lengkap (30 sampel), kecuali sedikit gap acak (mis. 2% kemungkinan gap kecil)
        sample_count = 30
        if rng.random() < 0.01:
            sample_count = rng.randint(20, 23)  # Jendela tidak lengkap (<24)

        p_val = max(15.0, round(p_total, 1))
        windows.append(Window5m(
            start_ts=ts,
            sample_count=sample_count,
            p_avg=p_val,
            p_max=round(p_val * 1.1, 1),
            p_min=round(p_val * 0.9, 1),
        ))

    return SyntheticDataset(
        seed=seed,
        windows=windows,
        ground_truth_l2=l2_labels,
        ground_truth_l3=l3_labels,
        transients=transients,
    )
