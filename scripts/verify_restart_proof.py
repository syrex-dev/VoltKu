import subprocess
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ_WIB = ZoneInfo("Asia/Jakarta")


def log(msg: str):
    now_str = datetime.now(TZ_WIB).strftime("%H:%M:%S")
    print(f"[{now_str} WIB] {msg}", flush=True)


def ensure_docker_running():
    check = subprocess.run(["wsl", "docker", "info"], capture_output=True, text=True)
    if check.returncode != 0:
        log("Memulai Docker service di WSL...")
        subprocess.run(["wsl", "-u", "root", "service", "docker", "start"], check=True)
        time.sleep(2)


def exec_backend_python(code: str) -> str:
    ensure_docker_running()
    cmd = [
        "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
        "exec", "-T", "backend", "python", "-c", code
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return f"ERROR: {res.stderr}"
    return res.stdout.strip()


def main():
    log("==================================================================")
    log("🔁 PENGUJIAN RESTART CONTAINER DENGAN ALERT OFFLINE AKTIF")
    log("==================================================================")

    # Jaga agar distro WSL tidak masuk status idle/terminate selama pengujian
    keepalive_proc = subprocess.Popen(["wsl", "sleep", "300"])
    try:
        ensure_docker_running()

        # 1. Bersihkan demo-1 lebih dulu
        log("Membersihkan data demo-1...")
        subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "exec", "-T", "backend", "python", "scripts/clean_device.py", "demo-1"
        ], check=True)

        # 2. Buat kondisi alert offline aktif
        now_ts = int(time.time())
        active_ts = now_ts - 100
        setup_code = (
            "from app.db import SessionLocal\n"
            "from app.models import Device, AlertState, Anomaly\n"
            "with SessionLocal() as s:\n"
            "    dev = Device(id='demo-1', name='demo-1', mcb_watt=2200, status='offline',\n"
            f"                 last_seen_at={now_ts - 200}, last_data_ts={now_ts - 200})\n"
            "    s.add(dev)\n"
            "    s.commit()\n"
            f"    alert = AlertState(device_id='demo-1', alert_type='offline', state='active',\n"
            f"                       since={active_ts}, last_notified_at={active_ts},\n"
            f"                       details_json='{{\"last_seen_at\": {now_ts - 200}}}')\n"
            "    s.add(alert)\n"
            f"    anom = Anomaly(device_id='demo-1', ts={active_ts}, type='offline',\n"
            "                   severity='warning',\n"
            f"                   details_json='{{\"last_seen_at\": {now_ts - 200}}}',\n"
            "                   message='[PERINGATAN] demo-1 - Perangkat offline', notified=1)\n"
            "    s.add(anom)\n"
            "    s.commit()\n"
            "    print('SETUP_OK')\n"
        )
        res = exec_backend_python(setup_code)
        log(f"Setup alert offline aktif di DB: {res}")

        # 3. Catat last_notified_at sebelum restart
        query_ts_code = (
            "from app.db import SessionLocal\n"
            "from app.models import AlertState\n"
            "with SessionLocal() as s:\n"
            "    q = s.query(AlertState).filter_by(device_id='demo-1', alert_type='offline')\n"
            "    a = q.first()\n"
            "    print(a.last_notified_at if a else 'NONE')\n"
        )
        before_ts = exec_backend_python(query_ts_code)
        log(f"Nilai last_notified_at SEBELUM restart: {before_ts}")

        # 4. Catat waktu restart dan restart container
        restart_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log(f"Waktu restart UTC: {restart_iso}")
        log("Menjalankan: docker compose restart backend...")
        subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "restart", "backend"
        ], check=True)
        log("Container backend berhasil di-restart.")

        # 5. Tunggu >= 150 detik (melewati grace period 120s + tick scheduler)
        wait_seconds = 155
        log(f"Menunggu {wait_seconds} detik (melewati grace period 120s dan tick scheduler)...")
        for sec in range(0, wait_seconds, 15):
            time.sleep(15)
            ensure_docker_running()
            log(f"  ... {sec + 15}s berlalu")

        # 6. Ambil last_notified_at setelah restart
        after_ts = exec_backend_python(query_ts_code)
        log(f"Nilai last_notified_at SESUDAH restart: {after_ts}")

        # 7. Ambil logs sejak restart
        ensure_docker_running()
        log(f"\nMengambil docker logs --since {restart_iso}:")
        cmd_logs = [
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "logs", "backend", "--since", restart_iso
        ]
        logs_res = subprocess.run(cmd_logs, capture_output=True, text=True)
        print("--- DOCKER LOGS OUTPUT ---")
        print(logs_res.stdout)
        print("--------------------------")

        # 8. Verifikasi kesamaan timestamp & tidak adanya notifikasi baru
        assert before_ts == after_ts, (
            f"Timestamp berubah! Sebelum: {before_ts}, Sesudah: {after_ts}"
        )
        assert "[RECORDED_ALERT]" not in logs_res.stdout, "Ditemukan alert baru pasca restart!"
        log(">>> ✅ VERIFIKASI BERHASIL: last_notified_at identik dan tidak ada alert baru!")

        # 9. Bersihkan demo-1
        log("\nMembersihkan demo-1...")
        subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "exec", "-T", "backend", "python", "scripts/clean_device.py", "demo-1"
        ], check=True)
        log("Pembersihan selesai.")
    finally:
        keepalive_proc.terminate()
        try:
            keepalive_proc.wait(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    main()
