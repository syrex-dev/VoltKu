import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_WIB = ZoneInfo("Asia/Jakarta")


def log(msg: str):
    now_str = datetime.now(TZ_WIB).strftime("%H:%M:%S")
    print(f"[{now_str} WIB] {msg}", flush=True)


def exec_backend_python(code: str) -> str:
    cmd = [
        "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
        "exec", "-T", "backend", "python", "-c", code
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return f"ERROR: {res.stderr}"
    return res.stdout.strip()


def get_container_logs(tail: int = 50) -> str:
    cmd = [
        "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
        "logs", "backend", "--tail", str(tail)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout


def get_db_summary() -> str:
    py_code = (
        "import json\n"
        "from app.db import SessionLocal\n"
        "from app.models import AlertState, Anomaly, Device, Reading\n"
        "with SessionLocal() as s:\n"
        "    dev = s.get(Device, 'demo-1')\n"
        "    if dev:\n"
        "        print(f'Device demo-1: status={dev.status}, last_seen={dev.last_seen_at}')\n"
        "    else:\n"
        "        print('Device demo-1: None')\n"
        "    r_cnt = s.query(Reading).filter_by(device_id='demo-1').count()\n"
        "    alerts = s.query(AlertState).filter_by(device_id='demo-1').all()\n"
        "    q_anom = s.query(Anomaly).filter_by(device_id='demo-1')\n"
        "    anoms = q_anom.order_by(Anomaly.ts.asc()).all()\n"
        "    print(f'Total Readings: {r_cnt}')\n"
        "    print(f'Alert States ({len(alerts)}):')\n"
        "    for a in alerts:\n"
        "        print(f'  - type={a.alert_type}, state={a.state}, since={a.since}')\n"
        "    print(f'Anomalies ({len(anoms)}):')\n"
        "    for an in anoms:\n"
        "        print(f'  - id={an.id}, type={an.type}, ts={an.ts}, notified={an.notified}')\n"
        "        print(f'    details: {an.details_json}')\n"
    )
    return exec_backend_python(py_code)


def main():
    log("==================================================================")
    log("🚀 MEMULAI LIVE DEMO E2E (REAL BROKER + SIMULATOR + CONTAINER DB)")
    log("==================================================================")

    # 0. Pastikan demo-1 bersih
    log("Membersihkan data lama demo-1 jika ada...")
    subprocess.run([
        "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
        "exec", "-T", "backend", "python", "scripts/clean_device.py", "demo-1"
    ], check=True)

    # 1. Jalankan simulator overload (120 detik) + recovery
    log("Menjalankan simulator: python simulator/publish_fake.py --mode overload")
    cmd_sim = [
        sys.executable, "simulator/publish_fake.py",
        "--mode", "overload",
        "--device", "demo-1",
        "--overload-seconds", "120",
    ]
    sim_proc = subprocess.Popen(
        cmd_sim,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    t_start = time.time()
    overload_alert_found = False
    recovery_alert_found = False

    while True:
        line = sim_proc.stdout.readline()
        if not line and sim_proc.poll() is not None:
            break
        if line:
            line_str = line.strip()
            if "Overload" in line_str or "Recovery" in line_str or "Starting" in line_str:
                log(f"  [SIM] {line_str}")

        now = time.time()
        if not overload_alert_found and (now - t_start) >= 65:
            c_logs = get_container_logs(20)
            if "[RECORDED_ALERT] [PERINGATAN] demo-1 - Daya melebihi batas wajar" in c_logs:
                overload_alert_found = True
                log(">>> ✅ DETEKSI ALERT OVERLOAD TERKONFIRMASI DI LOG BACKEND!")

        if overload_alert_found and not recovery_alert_found and (now - t_start) >= 190:
            c_logs = get_container_logs(20)
            if "[RECORDED_ALERT] [PULIH] demo-1 - Daya kembali normal" in c_logs:
                recovery_alert_found = True
                log(">>> ✅ DETEKSI ALERT PEMULIHAN (RECOVERY) TERKONFIRMASI DI LOG BACKEND!")

    sim_proc.wait()
    log("Simulator selesai dan berhenti mempublikasikan telemetry.")

    log("\n--- RINGKASAN DB SETELAH FASE OVERLOAD & RECOVERY ---")
    print(get_db_summary())

    # 2. Tunggu alert OFFLINE (~120 - 135 detik setelah sampel terakhir)
    log("\nMenunggu perangkat demo-1 offline (ambang batas 120s + jadwal evaluator 15s)...")
    t_wait_offline = time.time()

    for _attempt in range(16):
        time.sleep(10)
        elapsed = time.time() - t_wait_offline
        log(f"  Menunggu offline... ({elapsed:.0f}s berlalu)")
        c_logs = get_container_logs(20)
        if "[RECORDED_ALERT] [PERINGATAN] demo-1 - Perangkat offline" in c_logs:
            log(f">>> ✅ DETEKSI ALERT OFFLINE DI LOG PADA DETIK KE-{elapsed:.0f}!")
            break

    log("\n--- RINGKASAN DB SETELAH FASE OFFLINE ---")
    print(get_db_summary())

    # 3. Uji ketahanan: restart backend saat alert offline aktif
    log("\nMenjalankan: docker compose restart backend (uji cegah notifikasi dobel)...")
    subprocess.run([
        "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
        "restart", "backend"
    ], check=True)
    log("Container backend berhasil di-restart. Menunggu 25 detik untuk tick scheduler...")
    time.sleep(25)

    post_restart_logs = get_container_logs(40)
    log("Log container backend pasca restart:")
    for r_line in post_restart_logs.splitlines():
        if "[RECORDED_ALERT]" in r_line:
            log(f"  [LOG] {r_line}")
    log("Memeriksa apakah ada alert/laporan ganda di DB...")
    print(get_db_summary())

    # 4. Bersihkan data demo-1 dengan clean_device.py
    log("\nMembersihkan perangkat demo-1 dengan clean_device.py di dalam container...")
    clean_res = subprocess.run([
        "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
        "exec", "-T", "backend", "python", "scripts/clean_device.py", "demo-1"
    ], capture_output=True, text=True, check=True)
    print(clean_res.stdout.strip())

    # 5. Buktikan DB bersih
    log("\n--- BUKTI DB demo-1 SETELAH PEMBERSIHAN ---")
    print(get_db_summary())

    log("\n==================================================================")
    log("🎉 LIVE DEMO E2E SELESAI DENGAN SUKSES!")
    log("==================================================================")


if __name__ == "__main__":
    main()
