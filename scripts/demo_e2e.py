import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# Setup path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
backend_dir = os.path.join(BASE_DIR, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import AlertState, Anomaly, Device, Reading, Setting  # noqa: E402
from app.services.alert import evaluate_all_alerts  # noqa: E402
from app.services.notifier import set_notification_sender  # noqa: E402
from app.services.report_generator import check_and_send_catchup_reports  # noqa: E402
from sqlalchemy import select  # noqa: E402

from scripts.clean_device import clean_device  # noqa: E402

TZ_WIB = ZoneInfo("Asia/Jakarta")


def run_e2e_demo():
    print("=" * 70)
    print("🚀 MEMULAI END-TO-END DEMO MILESTONE 3 (CONTAINER RECORDING LOGGER)")
    print("=" * 70)

    # 1. Pasang Recording Logger (tanpa real Telegram)
    recorded_alerts: list[str] = []

    def recording_logger(message: str) -> bool:
        recorded_alerts.append(message)
        print(f"  🔔 [RECORDED_LOGGER] {message}")
        return True

    set_notification_sender(recording_logger)

    init_db()
    session = SessionLocal()

    # Pastikan settings default terpasang
    if not session.scalar(select(Setting).where(Setting.key == "power_limit_w")):
        session.add(Setting(key="power_limit_w", value="2200"))
    if not session.scalar(select(Setting).where(Setting.key == "alert_cooldown_min")):
        session.add(Setting(key="alert_cooldown_min", value="15"))
    if not session.scalar(select(Setting).where(Setting.key == "report_hour")):
        session.add(Setting(key="report_hour", value="21"))
    if not session.scalar(select(Setting).where(Setting.key == "report_enabled")):
        session.add(Setting(key="report_enabled", value="true"))
    session.commit()

    # Bersihkan demo-1 jika ada data lama
    clean_device("demo-1", session=session)

    # Daftarkan perangkat demo-1
    base_ts = int(time.time())
    startup_ts = base_ts - 300  # Melewati startup grace period (120s)

    dev = Device(
        id="demo-1",
        name="Demo Warung",
        mcb_watt=2200,
        status="online",
        last_seen_at=base_ts,
        last_data_ts=base_ts,
    )
    session.add(dev)
    session.commit()
    print(f"\n[STEP 1] Perangkat 'demo-1' didaftarkan (MCB: {dev.mcb_watt} W, Status: ONLINE).")

    # -------------------------------------------------------------------------
    # 2. OVERLOAD SCENARIO: P > 2200 W selama 70 detik
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Simulasi OVERLOAD 70 detik (8 sampel @ 10 detik, P = 2640 W)...")
    curr_e = 50.0
    for i in range(8):
        sample_ts = base_ts + (i * 10)
        p = 2640.0
        v = 220.0
        i_val = p / v
        curr_e += (p * 10) / (3600.0 * 1000.0)
        dev.last_seen_at = sample_ts
        dev.last_data_ts = sample_ts
        session.add(
            Reading(
                device_id="demo-1",
                ts=sample_ts,
                v=v,
                i=round(i_val, 2),
                p=p,
                e_kwh=round(curr_e, 3),
                delta_kwh=0.007,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    ts_overload = base_ts + 70
    msgs_overload = evaluate_all_alerts(session, now_ts=ts_overload, startup_ts=startup_ts)
    print(f"-> Hasil Evaluasi Overload: {len(msgs_overload)} alert terkirim.")
    assert len(msgs_overload) == 1
    assert "Daya melebihi batas" in msgs_overload[0]

    # Cek Anomaly di DB
    anom_overload = session.scalar(
        select(Anomaly).where(Anomaly.device_id == "demo-1", Anomaly.type == "power_limit")
    )
    assert anom_overload is not None
    print(
        f"-> DB Verification: Anomaly recorded "
        f"(ID={anom_overload.id}, Type={anom_overload.type}, Severity={anom_overload.severity})."
    )

    # -------------------------------------------------------------------------
    # 3. RECOVERY SCENARIO: P turun kembali ke beban normal (350 W)
    # -------------------------------------------------------------------------
    print("\n[STEP 3] Simulasi PEMULIHAN / NORMAL (8 sampel @ 10 detik, P = 350 W)...")
    rec_start_ts = ts_overload + 10
    for i in range(8):
        sample_ts = rec_start_ts + (i * 10)
        p = 350.0
        v = 220.0
        i_val = p / v
        curr_e += (p * 10) / (3600.0 * 1000.0)
        dev.last_seen_at = sample_ts
        dev.last_data_ts = sample_ts
        session.add(
            Reading(
                device_id="demo-1",
                ts=sample_ts,
                v=v,
                i=round(i_val, 2),
                p=p,
                e_kwh=round(curr_e, 3),
                delta_kwh=0.001,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    ts_recovery = rec_start_ts + 70
    msgs_rec = evaluate_all_alerts(session, now_ts=ts_recovery, startup_ts=startup_ts)
    print(f"-> Hasil Evaluasi Pemulihan: {len(msgs_rec)} alert terkirim.")
    assert len(msgs_rec) == 1
    assert "PULIH" in msgs_rec[0]

    # -------------------------------------------------------------------------
    # 4. SIMULATOR BERHENTI -> OFFLINE ALERT ~120s KEMUDIAN
    # -------------------------------------------------------------------------
    print("\n[STEP 4] Simulator dimatikan (tidak ada data masuk). Menunggu timeout offline 120s...")
    ts_offline = ts_recovery + 125  # 125 detik tanpa pembacaan baru
    msgs_offline = evaluate_all_alerts(session, now_ts=ts_offline, startup_ts=startup_ts)
    print(f"-> Hasil Evaluasi Offline: {len(msgs_offline)} alert terkirim.")
    assert len(msgs_offline) == 1
    assert "Perangkat offline" in msgs_offline[0]

    # -------------------------------------------------------------------------
    # 5. RESTART BACKEND -> TIDAK ADA DUPLIKASI ALERT ATAU LAPORAN
    # -------------------------------------------------------------------------
    print("\n[STEP 5] Simulasi RESTART BACKEND (memastikan idempoten & tidak ada duplikat)...")
    restart_ts = ts_offline + 30
    new_startup_ts = restart_ts

    # A. Selama startup grace period (120s pertama setelah restart) -> alert tertahan
    msgs_grace = evaluate_all_alerts(session, now_ts=restart_ts + 30, startup_ts=new_startup_ts)
    print(f"-> Alert saat grace period (30s pasca restart): {len(msgs_grace)} (Harus 0 - ditekan).")
    assert len(msgs_grace) == 0

    # B. Setelah grace period -> cooldown aktif -> tidak ada duplikat alert offline
    msgs_after_grace = evaluate_all_alerts(
        session, now_ts=restart_ts + 150, startup_ts=new_startup_ts
    )
    print(f"-> Alert setelah grace period: {len(msgs_after_grace)} (Harus 0 - cooldown aktif).")
    assert len(msgs_after_grace) == 0

    # C. Pengecekan catch-up laporan terjadwal pasca restart
    dt_restart = datetime.fromtimestamp(restart_ts, tz=TZ_WIB)
    check_and_send_catchup_reports(session, now_dt=dt_restart)
    # Jalankan kedua kali untuk memastikan tidak ada duplikat
    report_actions_2 = check_and_send_catchup_reports(session, now_dt=dt_restart)
    print(f"-> Pengecekan ulang laporan pasca restart: {report_actions_2} (tidak ada duplikat).")
    assert report_actions_2 == []

    # -------------------------------------------------------------------------
    # 6. TAMPILKAN STATUS TABEL DB (alert_state dan anomalies)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("📊 DATA REAL DALAM TABEL DATABASE:")
    print("=" * 70)

    print("\n--- TABEL alert_state (demo-1) ---")
    states = session.scalars(
        select(AlertState).where(AlertState.device_id == "demo-1")
    ).all()
    for s in states:
        last_dt = datetime.fromtimestamp(s.last_notified_at, tz=TZ_WIB).strftime("%H:%M:%S")
        print(f"  • Alert: {s.alert_type:<15} | State: {s.state:<8} | Notified: {last_dt} WIB")

    print("\n--- TABEL anomalies (demo-1, 7 Hari Terakhir) ---")
    anomalies = session.scalars(
        select(Anomaly)
        .where(Anomaly.device_id == "demo-1")
        .order_by(Anomaly.ts.asc())
    ).all()
    for a in anomalies:
        a_dt = datetime.fromtimestamp(a.ts, tz=TZ_WIB).strftime("%H:%M:%S")
        print(f"  • [{a.severity.upper():<8}] {a_dt} WIB | Type: {a.type:<20} | Msg: {a.message}")

    # -------------------------------------------------------------------------
    # 7. PEMBERSIHAN DENGAN SKRIP clean_device.py
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("[STEP 7] Membersihkan perangkat demo-1 dengan scripts/clean_device.py...")
    print("=" * 70)
    res_clean = clean_device("demo-1", session=session)
    print(f"Pembersihan sukses: {res_clean}")

    # Verifikasi DB bersih
    dev_check = session.get(Device, "demo-1")
    assert dev_check is None
    readings_check = session.scalars(
        select(Reading).where(Reading.device_id == "demo-1")
    ).all()
    assert len(readings_check) == 0
    print("✅ Seluruh data 'demo-1' terverifikasi telah bersih 100% dari database.")
    print("=" * 70)
    print("🎉 END-TO-END DEMO SUKSES LENGKAP!")
    print("=" * 70)

    session.close()


if __name__ == "__main__":
    run_e2e_demo()
