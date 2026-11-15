import json
import os
import subprocess
import urllib.request

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = r"C:\Users\deder\Music\energy-monitor"

# 1. Baca password dari .env
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
password = ""
with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        if line.startswith("DASHBOARD_PASSWORD="):
            password = line.strip().split("=", 1)[1].strip('"').strip("'")

# 2. Login untuk dapatkan token
login_req = urllib.request.Request(
    "http://localhost:8000/api/login",
    data=json.dumps({"password": password}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(login_req) as resp:
    token = json.loads(resp.read().decode("utf-8"))["token"]

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def take_screenshot(url, filename, width=1280, height=800):
    filepath = os.path.join(OUTPUT_DIR, filename)
    cmd = [
        CHROME_PATH,
        "--headless=new",
        f"--screenshot={filepath}",
        f"--window-size={width},{height}",
        "--virtual-time-budget=6000",
        "--hide-scrollbars",
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(filepath):
        print(f"Captured {filename}: {os.path.getsize(filepath)} bytes")
    else:
        print(f"Failed to capture {filename}: {res.stderr}")
    return filepath

# A. Screenshot Login
take_screenshot("http://localhost:8000", "screenshot_login.png", 1280, 800)

# B. Screenshot Dashboard Normal (Desktop)
url_dash = f"http://localhost:8000/?token={token}"
take_screenshot(url_dash, "screenshot_dashboard_desktop.png", 1280, 950)

# C. Screenshot Warning Banner (power_limit_w 2500 > mcb_watt 2200)
# Update settings power_limit_w to 2500
patch_req = urllib.request.Request(
    "http://localhost:8000/api/settings",
    data=json.dumps({"power_limit_w": 2500}).encode("utf-8"),
    headers=headers,
    method="PATCH",
)
with urllib.request.urlopen(patch_req) as resp:
    print("Updated power_limit_w to 2500 (triggers warning banner)")

take_screenshot(url_dash, "screenshot_warning_banner.png", 1280, 950)

# Revert power_limit_w back to 2200
revert_req = urllib.request.Request(
    "http://localhost:8000/api/settings",
    data=json.dumps({"power_limit_w": 2200}).encode("utf-8"),
    headers=headers,
    method="PATCH",
)
with urllib.request.urlopen(revert_req) as resp:
    print("Reverted power_limit_w back to 2200")

# D. Screenshot Mobile (390 x 844 - iPhone / Smartphone)
take_screenshot(url_dash, "screenshot_dashboard_mobile.png", 390, 844)

