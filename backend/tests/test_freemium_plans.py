import time

from app.auth import create_access_token
from app.main import app
from app.models import DailyStat, User
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)


def test_freemium_public_config_and_quota_enforcement():
    _, session = open_clean_test_session()

    cfg_res = client.get("/api/public/app-config")
    assert cfg_res.status_code == 200
    plans = cfg_res.json()["plans"]
    assert plans["freemium_enabled"] is True
    assert plans["free"]["max_devices"] == 1
    assert plans["free"]["history_days"] == 3
    assert plans["pro"]["name"] == "VoltKu Pro"
    assert plans["pro"]["price_monthly_rp"] == 30000

    # Registrasi user gratis baru
    reg = client.post(
        "/api/users/register",
        json={
            "name": "Pelanggan Gratis",
            "email": "gratis@voltku.id",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg.status_code == 201
    user_data = reg.json()["user"]
    assert user_data["plan"]["effective_tier"] == "free"
    assert user_data["plan"]["is_pro"] is False
    assert user_data["plan"]["limits"]["max_devices"] == 1
    tok = reg.json()["token"]
    headers = {"Authorization": f"Bearer {tok}"}

    # Panel ke-1 berhasil ditambahkan
    d1 = client.post(
        "/api/devices",
        headers=headers,
        json={"id": "panel_1", "name": "Panel Rumah", "mcb_watt": 2200},
    )
    assert d1.status_code == 201

    # Panel ke-2 ditolak karena batas kuota Gratis (1 panel)
    d2 = client.post(
        "/api/devices",
        headers=headers,
        json={"id": "panel_2", "name": "Panel Kos", "mcb_watt": 1300},
    )
    assert d2.status_code == 403
    err2 = d2.json()["error"]
    assert err2["reason"] == "plan_upgrade_required"
    assert err2["feature"] == "device_quota"

    # Grafik 24 jam diizinkan, tetapi 7 hari ditolak; forecast & CSV export ditolak
    now = int(time.time())
    s_24h = client.get(
        f"/api/devices/panel_1/series?from={now - 86400}&to={now}",
        headers=headers,
    )
    assert s_24h.status_code == 200

    s_7d = client.get(
        f"/api/devices/panel_1/series?from={now - 7 * 86400}&to={now}",
        headers=headers,
    )
    assert s_7d.status_code == 403
    assert s_7d.json()["error"]["feature"] == "history_days"

    fc_free = client.get("/api/devices/panel_1/forecast", headers=headers)
    assert fc_free.status_code == 403
    assert fc_free.json()["error"]["feature"] == "forecast"

    exp_free = client.get("/api/devices/panel_1/export?days=30", headers=headers)
    assert exp_free.status_code == 403
    assert exp_free.json()["error"]["feature"] == "export_csv"

    # Ajukan permintaan upgrade ke Pro
    up_res = client.post(
        "/api/users/upgrade-request",
        headers=headers,
        json={"billing_cycle": "monthly", "user_note": "Sudah transfer QRIS"},
    )
    assert up_res.status_code == 201
    up_body = up_res.json()
    assert up_body["amount_rp"] == 30000
    assert up_body["status"] == "pending"

    # Permintaan ganda saat masih pending ditolak 409
    dup = client.post(
        "/api/users/upgrade-request",
        headers=headers,
        json={"billing_cycle": "monthly"},
    )
    assert dup.status_code == 409

    # Admin melihat & menyetujui permintaan upgrade
    admin_tok = create_access_token(subject="admin", role="admin")
    adm_headers = {"Authorization": f"Bearer {admin_tok}"}

    reqs = client.get("/api/admin/upgrade-requests?status=pending", headers=adm_headers)
    assert reqs.status_code == 200
    assert len(reqs.json()) == 1
    req_id = reqs.json()[0]["id"]

    approve = client.patch(
        f"/api/admin/upgrade-requests/{req_id}",
        headers=adm_headers,
        json={"action": "approve", "duration_days": 30, "admin_note": "Lunas"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    # Setelah Pro aktif: kuota bertambah, series 7d/forecast/CSV export terbuka
    me_pro = client.get("/api/users/me", headers=headers).json()
    assert me_pro["plan"]["is_pro"] is True
    assert me_pro["plan"]["effective_tier"] == "pro"
    assert me_pro["plan"]["expires_at"] is not None

    d2_ok = client.post(
        "/api/devices",
        headers=headers,
        json={"id": "panel_2", "name": "Panel Kos", "mcb_watt": 1300},
    )
    assert d2_ok.status_code == 201

    assert (
        client.get(
            f"/api/devices/panel_1/series?from={now - 7 * 86400}&to={now}",
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get("/api/devices/panel_1/forecast", headers=headers).status_code == 200

    session.add(
        DailyStat(
            device_id="panel_1",
            day="2026-11-24",
            kwh=3.5,
            cost_rp=5056,
            tariff_sen=144470,
            p_max=1120.0,
        )
    )
    session.commit()

    exp_pro = client.get("/api/devices/panel_1/export?days=30", headers=headers)
    assert exp_pro.status_code == 200
    assert "text/csv" in exp_pro.headers["content-type"]
    assert "tanggal_wib,energi_kwh,biaya_rp" in exp_pro.text
    assert "2026-11-24,3.500,5056" in exp_pro.text
    session.close()


def test_expired_pro_reverts_and_admin_can_customize_freemium():
    _, session = open_clean_test_session()

    reg = client.post(
        "/api/users/register",
        json={
            "name": "User Kedaluwarsa",
            "email": "exp@voltku.id",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg.status_code == 201
    uid = reg.json()["user"]["id"]
    tok = reg.json()["token"]
    headers = {"Authorization": f"Bearer {tok}"}

    # Simulasikan Pro yang sudah lewat masa berlaku
    u = session.get(User, uid)
    u.plan_tier = "pro"
    u.plan_expires_at = int(time.time()) - 100
    session.commit()

    me_exp = client.get("/api/users/me", headers=headers).json()
    assert me_exp["plan"]["is_pro"] is False
    assert me_exp["plan"]["is_expired"] is True
    assert me_exp["plan"]["effective_tier"] == "free"

    # Admin dapat mengubah harga, nama paket, atau mematikan freemium dari Panel Admin
    admin_tok = create_access_token(subject="admin", role="admin")
    adm_headers = {"Authorization": f"Bearer {admin_tok}"}

    upd_cfg = client.patch(
        "/api/admin/app-settings",
        headers=adm_headers,
        json={
            "pro_plan_name": "VoltKu Sultan",
            "pro_monthly_price_rp": 45000,
            "free_max_devices": 2,
            "freemium_enabled": False,
        },
    )
    assert upd_cfg.status_code == 200
    assert upd_cfg.json()["pro_plan_name"] == "VoltKu Sultan"
    assert upd_cfg.json()["pro_monthly_price_rp"] == 45000

    # Saat freemium_enabled=False, semua user otomatis mendapat akses penuh
    me_unlocked = client.get("/api/users/me", headers=headers).json()
    assert me_unlocked["plan"]["freemium_enabled"] is False
    assert me_unlocked["plan"]["is_pro"] is True
    assert me_unlocked["plan"]["limits"]["max_devices"] == -1
    session.close()

