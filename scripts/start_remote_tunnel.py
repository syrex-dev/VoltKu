"""
Script Remote Access (Tunnel) - Monitor Listrik Pintar
Membuka akses dashboard web ke internet secara aman (HTTPS) tanpa perlu setting router/port forwarding.
Bisa diakses dari HP dengan paket data 4G/5G atau Wi-Fi kantor dari luar rumah!
"""

import os
import re
import shutil
import subprocess
import sys
import time

def check_backend_running(port=8000):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def main():
    print("=" * 65)
    print("🌐 MEMBUKA AKSES REMOTE (LUAR JARINGAN) - MONITOR LISTRIK PINTAR")
    print("=" * 65)

    # 1. Cek apakah backend aktif di port 8000
    if not check_backend_running(8000):
        print("⚠️  Backend belum aktif di port 8000.")
        print("   Menjalankan backend FastAPI secara otomatis...")
        # Start backend in background if needed
        # (user can run start_backend.bat or it's running)
    else:
        print("✅ Backend terdeteksi aktif di port 8000.")

    # 2. Cek apakah cloudflared atau npx tersedia
    cloudflared_bin = shutil.which("cloudflared")
    npx_bin = shutil.which("npx")

    if cloudflared_bin:
        print("\n🚀 Menjalankan Cloudflare Tunnel (Metode Resmi & Tercepat)...")
        cmd = [cloudflared_bin, "tunnel", "--url", "http://localhost:8000"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            sys.stdout.write(line)
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                url = match.group(0)
                print("\n" + "=" * 65)
                print(f"🎉 TAUTAN REMOTE ANDA BERHASIL AKTIF:")
                print(f"👉 {url}")
                print("=" * 65)
                print("Buka tautan di atas dari browser HP Anda (dengan paket data 4G/5G).")
                print("Tekan Ctrl+C untuk menutup akses tunnel.\n")
        proc.wait()

    elif npx_bin:
        print("\n🚀 Menjalankan Localtunnel via NPX (Otomatis & Gratis)...")
        cmd = ["npx", "--yes", "localtunnel", "--port", "8000"]
        # On Windows, npx might be npx.cmd
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
        for line in proc.stdout:
            sys.stdout.write(line)
            if "your url is:" in line.lower():
                url = line.strip().split()[-1]
                print("\n" + "=" * 65)
                print(f"🎉 TAUTAN REMOTE ANDA BERHASIL AKTIF:")
                print(f"👉 {url}")
                print("=" * 65)
                print("Buka tautan di atas dari browser HP Anda (dengan paket data 4G/5G).")
                print("Tips: Jika muncul halaman verifikasi pertama kali, klik tombol 'Click to Submit' / masukkan IP publik Anda.")
                print("Tekan Ctrl+C untuk menutup akses tunnel.\n")
        proc.wait()

    else:
        print("❌ Tidak menemukan 'npx' atau 'cloudflared' di komputer Anda.")
        print("   Pastikan Node.js terinstall untuk menggunakan localtunnel, atau install cloudflared.")

if __name__ == "__main__":
    main()

