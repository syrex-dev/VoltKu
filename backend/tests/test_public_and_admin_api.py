import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.auth import create_access_token, user_login_limiter
from app.db import get_db
from app.main import app
from app.models import Anomaly, DailyStat, Device, Reading, Setting
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)


def _setup_mem_db():
    _, session = open_clean_test_session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return session


def _admin_headers():
    return {"Authorization": f"Bearer {create_access_token(subject='admin', role='admin')}"}


def test_public_demo_endpoints_isolate_private_devices():
    session = _setup_mem_db()
    now = int(time.time())
    session.add_all(
        [
            Device(
                id="demo_unit",
                name="Unit Demo",
                location="Showroom",
                mcb_watt=2200,
                is_public_demo=1,
                last_seen_at=now - 10,
                last_data_ts=now - 10,
                status="online",
            ),
            Device(
                id="private_unit",
                name="Rumah Pembeli",
                location="Tangerang",
                mcb_watt=2200,
                is_public_demo=0,
                last_seen_at=now - 10,
                last_data_ts=now - 10,
                status="online",
            ),
        ]
    )
    session.add_all(
        [
            Reading(
                device_id="demo_unit",
                ts=now - 10,
                v=221.0,
                i=1.5,
                p=330.0,
                e_kwh=10.0,
                delta_kwh=0.01,
                f=50.0,
                pf=0.98,
                rssi=-60,
            ),
            Reading(
                device_id="private_unit",
                ts=now - 10,
                v=220.0,
                i=3.0,
                p=660.0,
                e_kwh=20.0,
                delta_kwh=0.02,
                f=50.0,
                pf=0.99,
                rssi=-55,
            ),
        ]
    )
    today_wib = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d")
    session.add(
        DailyStat(
            device_id="demo_unit",
            day=today_wib,
            kwh=2.5,
            cost_rp=3612,
            tariff_sen=144470,
            p_max=980.0,
        )
    )
    session.add_all(
        [
            Anomaly(
                device_id="demo_unit",
                ts=now - 30,
                type="power_limit",
                severity="warning",
                details_json=json.dumps({"power_w": 2300}),
                message="Alert demo",
                notified=0,
            ),
            Anomaly(
                device_id="private_unit",
                ts=now - 30,
                type="power_limit",
                severity="critical",
                details_json=json.dumps({"power_w": 2500}),
                message="Alert private",
                notified=0,
            ),
        ]
    )
    session.commit()

    # Hanya unit demo yang tampil di mode Tanpa Login
    devs = client.get("/api/public/devices?include_latest=true")
    assert devs.status_code == 200
    assert [d["id"] for d in devs.json()] == ["demo_unit"]

    assert client.get("/api/public/devices/demo_unit/latest").status_code == 200
    assert client.get("/api/public/devices/private_unit/latest").status_code == 404
    assert client.get("/api/public/devices/private_unit/summary?range=today").status_code == 404

    pub_csv = client.get("/api/public/devices/demo_unit/export?days=14")
    assert pub_csv.status_code == 200
    assert "text/csv" in pub_csv.headers["content-type"]
    assert pub_csv.text.startswith("\ufefftanggal_wib,energi_kwh,biaya_rp")
    assert f"{today_wib},2.500,3612" in pub_csv.text
    assert 'filename="voltku-demo_unit-14d.csv"' in pub_csv.headers.get("content-disposition", "")
    assert client.get("/api/public/devices/private_unit/export?days=14").status_code == 404

    public_anoms = client.get("/api/public/anomalies").json()
    assert [a["device_id"] for a in public_anoms] == ["demo_unit"]

    # Toggle off oleh admin menutup seluruh /api/public/*
    assert (
        client.patch(
            "/api/admin/access",
            json={"public_read_enabled": False},
            headers=_admin_headers(),
        ).status_code
        == 200
    )
    assert client.get("/api/public/devices").status_code == 401
    assert client.get("/api/public/devices/demo_unit/export?days=14").status_code == 401
    assert client.get("/api/public/anomalies").status_code == 401

    app.dependency_overrides.clear()


def test_multi_tenant_user_isolation_and_admin_separation():
    session = _setup_mem_db()
    user_login_limiter.reset()
    now = int(time.time())

    # Pre-register / MQTT auto-created unclaimed hardware unit
    session.add(
        Device(
            id="ML-UNIT01",
            name="ML-UNIT01",
            mcb_watt=2200,
            owner_user_id=None,
            is_public_demo=0,
            last_seen_at=now - 10,
            status="online",
        )
    )
    session.add(Setting(key="tariff_sen_per_kwh", value="144470"))
    session.commit()

    # 1. Dua tenant daftar akun terpisah
    reg_a = client.post(
        "/api/users/register",
        json={"name": "Budi", "email": "budi@contoh.id", "password": "secretuser1"},
    )
    assert reg_a.status_code == 201
    token_a = reg_a.json()["token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    reg_b = client.post(
        "/api/users/register",
        json={"name": "Sari", "email": "sari@contoh.id", "password": "secretuser2"},
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. User A mengklaim ML-UNIT01; User B tidak boleh mengklaim atau mengaksesnya
    claim_a = client.post(
        "/api/devices",
        headers=headers_a,
        json={"id": "ML-UNIT01", "name": "Rumah Budi", "mcb_watt": 2200, "claim": True},
    )
    assert claim_a.status_code == 200
    assert claim_a.json()["owner_user_id"] == reg_a.json()["user"]["id"]

    assert [d["id"] for d in client.get("/api/devices", headers=headers_a).json()] == ["ML-UNIT01"]
    assert client.get("/api/devices", headers=headers_b).json() == []

    # User B mencoba klaim / edit / baca / hapus unit Budi -> ditolak 409 / 403
    hijack = client.post(
        "/api/devices",
        headers=headers_b,
        json={"id": "ML-UNIT01", "name": "Bajakan", "mcb_watt": 2200, "claim": True},
    )
    assert hijack.status_code == 409
    assert (
        client.patch("/api/devices/ML-UNIT01", headers=headers_b, json={"name": "X"}).status_code
        == 403
    )
    assert client.delete("/api/devices/ML-UNIT01", headers=headers_b).status_code == 403

    # 3. Pengaturan tarif per tenant terisolasi
    patch_set_a = client.patch("/api/settings", headers=headers_a, json={"tariff_rp": "1699.50"})
    assert patch_set_a.status_code == 200
    assert patch_set_a.json()["tariff_rp"] == "1699.50"
    assert client.get("/api/settings", headers=headers_b).json()["tariff_rp"] == "1444.70"

    # 4. Token User biasa DITOLAK 403 pada semua rute /api/admin/*
    for admin_path in ("/api/admin/overview", "/api/admin/users", "/api/admin/devices"):
        assert client.get(admin_path, headers=headers_a).status_code == 403

    # 5. Admin login & manajemen multi-tenant penuh
    adm_login = client.post("/api/admin/login", json={"password": "test_password_12chars"})
    assert adm_login.status_code == 200
    adm_headers = {"Authorization": f"Bearer {adm_login.json()['token']}"}

    ov = client.get("/api/admin/overview", headers=adm_headers).json()
    assert ov["users_total"] == 2
    assert ov["devices_claimed"] == 1
    assert "dashboard_password" not in json.dumps(ov)

    # Admin bisa melihat pemilik dan memindahkan kepemilikan / flag demo publik
    adm_devs = client.get("/api/admin/devices", headers=adm_headers).json()
    assert adm_devs[0]["owner_name"] == "Budi"

    reassign = client.patch(
        "/api/admin/devices/ML-UNIT01",
        headers=adm_headers,
        json={"owner_user_id": reg_b.json()["user"]["id"], "is_public_demo": True},
    )
    assert reassign.status_code == 200
    assert [d["id"] for d in client.get("/api/devices", headers=headers_b).json()] == ["ML-UNIT01"]

    # Nonaktifkan user B -> token user B tertolak 401 & tidak bisa login ulang
    deact = client.patch(
        f"/api/admin/users/{reg_b.json()['user']['id']}",
        headers=adm_headers,
        json={"is_active": False},
    )
    assert deact.status_code == 200
    assert client.get("/api/devices", headers=headers_b).status_code == 401
    assert (
        client.post(
            "/api/users/login", json={"email": "sari@contoh.id", "password": "secretuser2"}
        ).status_code
        == 403
    )

    app.dependency_overrides.clear()
