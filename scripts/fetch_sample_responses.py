import json
import os
import urllib.request


def get_dashboard_password():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("DASHBOARD_PASSWORD="):
                return line.strip().split("=", 1)[1].strip('"').strip("'")
    return ""


password = get_dashboard_password()

# 1. Login
login_req = urllib.request.Request(
    "http://localhost:8000/api/login",
    data=json.dumps({"password": password}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(login_req) as resp:
    token_data = json.loads(resp.read().decode("utf-8"))
token = token_data["token"]
headers = {"Authorization": f"Bearer {token}"}


def get_json(path):
    req = urllib.request.Request(f"http://localhost:8000{path}", headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


print("=== /api/devices/sim-warung/summary?range=today ===")
summary = get_json("/api/devices/sim-warung/summary?range=today")
print(json.dumps(summary, indent=2))

print("\n=== /api/devices/sim-warung/forecast ===")
forecast = get_json("/api/devices/sim-warung/forecast")
print(json.dumps(forecast, indent=2))

print(
    "\n=== /api/devices/sim-warung/series?from="
    + str(summary["from"])
    + "&to="
    + str(summary["from"] + 3600)
    + " ==="
)
series = get_json(
    f"/api/devices/sim-warung/series?from={summary['from']}&to={summary['from'] + 3600}"
)
# Tampilkan metadata dan 3 titik pertama + 1 titik terakhir
print(
    json.dumps(
        {
            "device_id": series["device_id"],
            "interval_seconds": series["interval_seconds"],
            "truncated": series["truncated"],
            "points_count": len(series["points"]),
            "first_3_points": series["points"][:3],
            "last_point": series["points"][-1] if series["points"] else None,
        },
        indent=2,
    )
)
