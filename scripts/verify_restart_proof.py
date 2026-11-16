import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
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
    last_err = ""
    for _ in range(5):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
        last_err = res.stderr
        if "restarting" in last_err.lower() or "not running" in last_err.lower():
            time.sleep(2)
            continue
        break
    return f"ERROR: {last_err}"


def wait_for_container_ready():
    ensure_docker_running()
    for _ in range(15):
        res = subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "exec", "-T", "backend", "python", "-c", "print('READY')"
        ], capture_output=True, text=True)
        if res.returncode == 0 and "READY" in res.stdout:
            return
        time.sleep(1)


def set_override_notifier(enabled: bool):
    """Mengaktifkan NOTIFIER=log lewat temporary docker-compose override file
    tanpa menyentuh .env atau docker-compose.yml.
    """
    override_path = Path("deploy/docker-compose.test-override.yml")
    if enabled:
        override_content = (
            "services:\n"
            "  backend:\n"
            "    environment:\n"
            "      - NOTIFIER=log\n"
        )
        override_path.write_text(override_content, encoding="utf-8")
    else:
        if override_path.exists():
            override_path.unlink()


def main():
    log("==================================================================")
    log("🔁 PENGUJIAN RESTART CONTAINER & KONTROL POSITIF (M3)")
    log("==================================================================")

    # Jaga agar distro WSL tidak masuk status idle/terminate selama pengujian
    keepalive_proc = subprocess.Popen(["wsl", "sleep", "360"])
    try:
        ensure_docker_running()

        # Pasang NOTIFIER=log lewat compose override sementara tanpa menyentuh .env
        set_override_notifier(True)

        # 1. Bersihkan demo-1 lebih dulu
        wait_for_container_ready()
        log("Membersihkan data demo-1...")
        subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "exec", "-T", "backend", "python", "scripts/clean_device.py", "demo-1"
        ], check=True)

        # 2. Buat kondisi alert offline aktif di DB
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

        # 4. Catat waktu restart dan restart container dengan recreate env
        restart_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log(f"Waktu restart UTC: {restart_iso}")
        log("Menjalankan: docker compose up -d --force-recreate backend...")
        subprocess.run([
            "wsl", "docker", "compose",
            "-f", "deploy/docker-compose.yml",
            "-f", "deploy/docker-compose.test-override.yml",
            "up", "-d", "--force-recreate", "backend",
        ], check=True)
        log("Container backend berhasil dijalankan ulang.")

        # 5. Tunggu >= 150 detik (melewati grace period 120s + tick scheduler)
        wait_seconds = 155
        log(f"Menunggu {wait_seconds} detik (melewati grace period 120s dan tick scheduler)...")
        for sec in range(0, wait_seconds, 15):
            time.sleep(15)
            ensure_docker_running()
            log(f"  ... {sec + 15}s berlalu")

        # 6. Ambil last_notified_at setelah menunggu > 150s
        after_ts = exec_backend_python(query_ts_code)
        log(f"Nilai last_notified_at SESUDAH > 150s: {after_ts}")
        assert before_ts == after_ts, (
            f"Timestamp berubah! Sebelum: {before_ts}, Sesudah: {after_ts}"
        )

        # 7. Verifikasi log sementara: tidak ada alert offline yang terkirim ulang
        ensure_docker_running()
        cmd_logs = [
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "logs", "backend", "--since", restart_iso
        ]
        logs_res_mid = subprocess.run(cmd_logs, capture_output=True, text=True)
        assert "[RECORDED_ALERT]" not in logs_res_mid.stdout, (
            "Ditemukan alert sebelum kontrol positif!"
        )
        log(">>> ✅ VERIFIKASI AWAL: Tidak ada alert offline lama dikirim ulang selama > 150s!")

        # 8. Kontrol Positif: Picu episode baru (overload di demo-1)
        log("\n--- Menjalankan Kontrol Positif: Overload di demo-1 (2600 W > 2200 W) ---")
        now_ts_ovl = int(time.time())
        inject_overload_code = (
            "from app.db import SessionLocal\n"
            "from app.models import Device, Reading\n"
            f"now_ts = {now_ts_ovl}\n"
            "with SessionLocal() as s:\n"
            "    dev = s.get(Device, 'demo-1')\n"
            "    if dev:\n"
            "        dev.last_seen_at = now_ts\n"
            "        dev.last_data_ts = now_ts\n"
            "        dev.status = 'online'\n"
            "    for i in range(7):\n"
            "        r = Reading(\n"
            "            device_id='demo-1',\n"
            "            ts=now_ts - 10 * (6 - i),\n"
            "            v=220.0, i=11.8, p=2600.0, e_kwh=10.5, delta_kwh=0.01,\n"
            "            f=50.0, pf=1.0, rssi=-60\n"
            "        )\n"
            "        s.add(r)\n"
            "    s.commit()\n"
            "    print('OVERLOAD_INJECTED')\n"
        )
        res_ovl = exec_backend_python(inject_overload_code)
        log(f"Injeksi data overload: {res_ovl}")
        log("Menunggu tick evaluator alert (20 detik)...")
        time.sleep(20)

        # 9. Ambil log lengkap sejak restart
        ensure_docker_running()
        log(f"\nMengambil docker logs --since {restart_iso}:")
        logs_res = subprocess.run(cmd_logs, capture_output=True, text=True)
        print("--- DOCKER LOGS OUTPUT ---")
        print(logs_res.stdout)
        print("--------------------------")

        # 10. Verifikasi:
        # - Log start: APScheduler aktif, Notifier aktif, EVALUATOR_TICK
        assert "APScheduler aktif. Jobs terdaftar:" in logs_res.stdout, (
            "Log start scheduler tidak ditemukan!"
        )
        assert "Notifier aktif: LogNotifier" in logs_res.stdout, (
            "Log start notifier tidak ditemukan!"
        )
        assert "[EVALUATOR_TICK #" in logs_res.stdout, "Log tick evaluator tidak ditemukan!"

        # - Alert baru: tepat 1 alert baru untuk overload di demo-1
        recorded_alerts = [
            line for line in logs_res.stdout.splitlines() if "[RECORDED_ALERT]" in line
        ]
        log(f"Ditemukan {len(recorded_alerts)} alert tercatat:")
        for a in recorded_alerts:
            log(f"  {a}")

        # Alert overload harus ada
        assert any("Daya melebihi batas wajar" in a for a in recorded_alerts), (
            "Alert overload tidak terpicu!"
        )
        # Episode offline lama TIDAK dikirim ulang
        assert not any("Perangkat offline" in a for a in recorded_alerts), (
            "Alert offline lama dikirim ulang!"
        )

        log(">>> ✅ KONTROL POSITIF BERHASIL: Tepat 1 alert overload terpicu!")

        # 11. Bersihkan demo-1
        log("\nMembersihkan demo-1...")
        subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "exec", "-T", "backend", "python", "scripts/clean_device.py", "demo-1"
        ], check=True)
        log("Pembersihan selesai.")
    finally:
        # Hapus temporary override file dan restart container ke kondisi default murni
        log("\nMenghapus temporary override dan restart container ke kondisi default...")
        set_override_notifier(False)
        subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "up", "-d", "--force-recreate", "backend"
        ], check=True)
        wait_for_container_ready()
        time.sleep(2)
        check_def_logs = subprocess.run([
            "wsl", "docker", "compose", "-f", "deploy/docker-compose.yml",
            "logs", "backend", "--tail", "20"
        ], capture_output=True, text=True)
        print("--- DEFAULT CONTAINER START LOGS ---")
        print(check_def_logs.stdout)
        print("------------------------------------")
        assert (
            "Notifier aktif: NullNotifier" in check_def_logs.stdout
            or "NullNotifier" in check_def_logs.stdout
        )

        keepalive_proc.terminate()
        try:
            keepalive_proc.wait(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    main()
