import json
import os
import subprocess
import time
import urllib.request

import paho.mqtt.client as mqtt

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
REPO_DIR = r"c:\Users\deder\Music\energy-monitor"
DOCS_SCREENSHOTS_DIR = os.path.join(REPO_DIR, "docs", "screenshots")
BRAIN_DIR = r"C:\Users\deder\.gemini\antigravity\brain\bf4a056b-c98f-4e55-9a89-c9b5cec3508f"
os.makedirs(DOCS_SCREENSHOTS_DIR, exist_ok=True)

# 1. Baca kredensial dari .env
env_path = os.path.join(REPO_DIR, ".env")
password = os.environ.get("DASHBOARD_PASSWORD", "")
mqtt_user = os.environ.get("MQTT_USER", "")
mqtt_pass = os.environ.get("MQTT_PASSWORD", "")

if not password or not mqtt_user:
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DASHBOARD_PASSWORD="):
                password = line.split("=", 1)[1].strip('"').strip("'")
            elif line.startswith("MQTT_USER="):
                mqtt_user = line.split("=", 1)[1].strip('"').strip("'")
            elif line.startswith("MQTT_PASSWORD="):
                mqtt_pass = line.split("=", 1)[1].strip('"').strip("'")

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


def publish_fresh_telemetry():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="screenshot_pub")
    client.username_pw_set(mqtt_user, mqtt_pass)
    client.connect("127.0.0.1", 1883, 60)
    client.loop_start()

    now_ts = int(time.time())
    payload = {
        "v": 221.8,
        "i": 2.14,
        "p": 474.7,
        "e_kwh": 26.500,
        "f": 50.0,
        "pf": 0.97,
        "rssi": -63,
        "ts": now_ts,
    }
    msg_info = client.publish("energy/sim-warung/telemetry", json.dumps(payload), qos=1)
    msg_info.wait_for_publish(timeout=5)
    client.loop_stop()
    client.disconnect()
    print("Published live telemetry at:", now_ts)


def take_screenshot(url, filename, width=1280, height=800):
    filepath = os.path.join(DOCS_SCREENSHOTS_DIR, filename)
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
        brain_path = os.path.join(BRAIN_DIR, filename)
        with open(filepath, "rb") as sf, open(brain_path, "wb") as df:
            df.write(sf.read())
    else:
        print(f"Failed to capture {filename}: {res.stderr}")
    return filepath


# A. Screenshot Login
take_screenshot("http://localhost:8000", "screenshot_login.png", 1280, 800)

url_dash = f"http://localhost:8000/?token={token}"

# B. Screenshot Online (publish fresh telemetry)
publish_fresh_telemetry()
time.sleep(2)
take_screenshot(url_dash, "screenshot_dashboard_online.png", 1280, 950)

# C. Screenshot Offline (tunggu sampai timeout > 30 detik agar offline secara natural)
print("Waiting 32 seconds for device to transition to offline status...")
time.sleep(32)
take_screenshot(url_dash, "screenshot_dashboard_offline.png", 1280, 950)

# D. Screenshot Warning Banner (power_limit_w 2500 > mcb_watt 2200)
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

# E. Screenshot Mobile (390 x 844 - Smartphone)
take_screenshot(url_dash, "screenshot_dashboard_mobile.png", 390, 844)
print("All screenshots successfully captured and saved.")
