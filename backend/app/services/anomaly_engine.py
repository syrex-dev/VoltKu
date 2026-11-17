"""
backend/app/services/anomaly_engine.py
Mesin murni deteksi anomali L2 (Robust Z-Score Baseline) dan L3 (Beban Dasar Malam).
Bebas dari efek samping database dan I/O (pure functional engine).
"""

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

TZ_WIB = timezone(timedelta(hours=7))


@dataclass
class Window5m:
    start_ts: int  # UTC epoch, kelipatan 300
    sample_count: int  # Jumlah sampel telemetri dalam jendela 5 menit (maks 30)
    p_avg: float
    p_max: float
    p_min: float
    hour_wib: int = -1
    date_wib: str = ""
    is_weekend: bool = False

    def __post_init__(self):
        if self.hour_wib < 0:
            dt = datetime.fromtimestamp(self.start_ts, tz=TZ_WIB)
            self.hour_wib = dt.hour
            self.date_wib = dt.strftime("%Y-%m-%d")
            self.is_weekend = (dt.weekday() >= 5)

    @property
    def is_complete(self) -> bool:
        """Jendela lengkap jika memiliki >= 24 dari 30 sampel telemetri (80%)."""
        return self.sample_count >= 24


@dataclass
class BucketStats:
    median: float
    mad: float
    mad_effective: float
    sample_count: int
    days_count: int
    bucket_type: str  # 'day_type_hour', 'hour_only', or 'learning'


@dataclass
class L2EvalResult:
    window: Window5m
    is_learning_mode: bool
    bucket_type: str
    baseline_median: float
    baseline_mad: float
    z_score: float
    delta_w: float
    is_candidate: bool  # z > 3.5 and delta > 100W
    consecutive_count: int
    is_anomaly_alert: bool  # True jika consecutive_count >= 3


def calculate_median_mad(values: list[float]) -> tuple[float, float, float]:
    """
    Menghitung median dan MAD (Median Absolute Deviation).
    Mengembalikan (median, mad_raw, mad_effective) dengan batas bawah:
    mad_effective = max(mad_raw, 10.0, 0.05 * median)
    """
    if not values:
        return 0.0, 0.0, 10.0
    med = statistics.median(values)
    abs_diffs = [abs(v - med) for v in values]
    mad_raw = statistics.median(abs_diffs)
    min_mad = max(10.0, 0.05 * med)
    mad_eff = max(mad_raw, min_mad)
    return med, mad_raw, mad_eff


class AnomalyEngine:
    def __init__(
        self,
        z_threshold: float = 3.5,
        delta_threshold_w: float = 100.0,
        persistence_windows: int = 3,
        min_bucket_samples: int = 24,
        min_bucket_days: int = 2,
        min_history_seconds: int = 3 * 86400,  # 3 hari penuh
    ):
        self.z_threshold = z_threshold
        self.delta_threshold_w = delta_threshold_w
        self.persistence_windows = persistence_windows
        self.min_bucket_samples = min_bucket_samples
        self.min_bucket_days = min_bucket_days
        self.min_history_seconds = min_history_seconds

    def evaluate_bucket(
        self,
        history_windows: list[Window5m],
        target_is_weekend: bool,
        target_hour: int,
    ) -> BucketStats:
        """
        Menilai kecukupan data historis (maks 14 hari) untuk suatu bucket:
        1. Cek bucket (jenis_hari, jam).
        2. Fallback ke bucket jam saja jika tidak cukup.
        3. Masuk mode belajar jika jam saja tidak cukup atau data < 3 hari penuh.
        """
        if not history_windows:
            return BucketStats(0.0, 0.0, 10.0, 0, 0, "learning")

        total_span = history_windows[-1].start_ts - history_windows[0].start_ts
        if total_span < self.min_history_seconds:
            return BucketStats(0.0, 0.0, 10.0, 0, 0, "learning")

        # Single-pass filter untuk efisiensi tinggi
        specific_vals: list[float] = []
        hour_vals: list[float] = []
        specific_days: set[str] = set()
        hour_days: set[str] = set()

        for w in history_windows:
            if not w.is_complete:
                continue
            if w.hour_wib == target_hour:
                hour_vals.append(w.p_avg)
                hour_days.add(w.date_wib)
                if w.is_weekend == target_is_weekend:
                    specific_vals.append(w.p_avg)
                    specific_days.add(w.date_wib)

        # 1. Cek bucket spesifik: (is_weekend, hour)
        if (
            len(specific_vals) >= self.min_bucket_samples
            and len(specific_days) >= self.min_bucket_days
        ):
            med, mad_raw, mad_eff = calculate_median_mad(specific_vals)
            return BucketStats(
                median=med,
                mad=mad_raw,
                mad_effective=mad_eff,
                sample_count=len(specific_vals),
                days_count=len(specific_days),
                bucket_type="day_type_hour",
            )

        # 2. Fallback ke bucket jam saja
        if (
            len(hour_vals) >= self.min_bucket_samples
            and len(hour_days) >= self.min_bucket_days
        ):
            med, mad_raw, mad_eff = calculate_median_mad(hour_vals)
            return BucketStats(
                median=med,
                mad=mad_raw,
                mad_effective=mad_eff,
                sample_count=len(hour_vals),
                days_count=len(hour_days),
                bucket_type="hour_only",
            )

        # 3. Data tidak mencukupi -> mode belajar
        return BucketStats(0.0, 0.0, 10.0, len(hour_vals), len(hour_days), "learning")

    def evaluate_window(
        self,
        current_window: Window5m,
        history_windows: list[Window5m],
        consecutive_candidates: int,
    ) -> L2EvalResult:
        """
        Mengevaluasi satu jendela 5 menit saat ini terhadap riwayat baseline.
        """
        bucket_stats = self.evaluate_bucket(
            history_windows=history_windows,
            target_is_weekend=current_window.is_weekend,
            target_hour=current_window.hour_wib,
        )

        if bucket_stats.bucket_type == "learning":
            return L2EvalResult(
                window=current_window,
                is_learning_mode=True,
                bucket_type="learning",
                baseline_median=0.0,
                baseline_mad=10.0,
                z_score=0.0,
                delta_w=0.0,
                is_candidate=False,
                consecutive_count=0,
                is_anomaly_alert=False,
            )

        delta_w = current_window.p_avg - bucket_stats.median
        z = 0.6745 * delta_w / bucket_stats.mad_effective

        is_cand = (z > self.z_threshold) and (delta_w > self.delta_threshold_w)
        new_consecutive = (consecutive_candidates + 1) if is_cand else 0
        is_alert = new_consecutive >= self.persistence_windows

        return L2EvalResult(
            window=current_window,
            is_learning_mode=False,
            bucket_type=bucket_stats.bucket_type,
            baseline_median=bucket_stats.median,
            baseline_mad=bucket_stats.mad_effective,
            z_score=z,
            delta_w=delta_w,
            is_candidate=is_cand,
            consecutive_count=new_consecutive,
            is_anomaly_alert=is_alert,
        )

    def evaluate_l3_night_baseload(
        self,
        today_night_windows: list[Window5m],
        past_7days_night_baseloads: list[float],
    ) -> tuple[bool, Optional[float], Optional[float], str]:
        """
        Evaluasi beban dasar malam (L3):
        today_night_windows: jendela telemetri antara 00.00 - 05.00 WIB hari ini.
        past_7days_night_baseloads: median beban dasar malam 7 hari sebelumnya.

        Mengembalikan (is_alert, today_base, ref_base, reason)
        """
        complete_today = [w.p_avg for w in today_night_windows if w.is_complete]
        if len(complete_today) < 12:  # Minimal 1 jam data malam lengkap (12 jendela @ 5m)
            return False, None, None, "Data malam hari ini kurang dari 1 jam lengkap"

        today_base = statistics.median(complete_today)

        if len(past_7days_night_baseloads) < 3:
            return (
                False,
                today_base,
                None,
                "Riwayat beban dasar malam kurang dari 3 hari (mode belajar)",
            )

        ref_base = statistics.median(past_7days_night_baseloads)
        delta_w = today_base - ref_base
        pct_increase = (delta_w / ref_base) if ref_base > 0 else 0.0

        # Alert jika naik > 30% DAN > 30 W
        if pct_increase > 0.30 and delta_w > 30.0:
            return (
                True,
                today_base,
                ref_base,
                f"Beban dasar naik {pct_increase*100:.1f}% (+{delta_w:.1f}W)",
            )

        return False, today_base, ref_base, "Normal"
