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
    assert 'filename="voltku-panel_1-30d.csv"' in exp_pro.headers.get("content-disposition", "")
    assert "tanggal_wib,energi_kwh,biaya_rp" in exp_pro.text
    assert "2026-11-24,3.500,5056" in exp_pro.text

    # Isolasi multi-tenant pada CSV export: user lain ditolak 403
    reg_other = client.post(
        "/api/users/register",
        json={
            "name": "User Lain",
            "email": "other-pro@voltku.id",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg_other.status_code == 201
    other_uid = reg_other.json()["user"]["id"]
    other_user = session.get(User, other_uid)
    other_user.plan_tier = "pro"
    other_user.plan_expires_at = int(time.time()) + 86400 * 30
    session.commit()
    other_headers = {"Authorization": f"Bearer {reg_other.json()['token']}"}
    other_exp = client.get("/api/devices/panel_1/export?days=30", headers=other_headers)
    assert other_exp.status_code == 403

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


def _sample_png_data_url() -> str:
    """PNG 1x1 transparan valid untuk simulasi upload bukti transfer / QRIS."""
    import base64

    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\x0bIDATx\x9cc`\x00\x02\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def test_manual_payment_methods_and_proof_verification_flow():
    _, session = open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")
    adm_headers = {"Authorization": f"Bearer {admin_tok}"}

    # 1. Admin membuat metode pembayaran QRIS + Bank + nonaktif
    qris_res = client.post(
        "/api/admin/payment-methods",
        headers=adm_headers,
        json={
            "type": "qris",
            "label": "QRIS VoltKu",
            "account_holder": "VoltKu Indonesia",
            "instructions": "Scan QRIS lalu unggah bukti bayar",
            "qris_image_base64": _sample_png_data_url(),
            "is_active": True,
            "sort_order": 1,
        },
    )
    assert qris_res.status_code == 201
    qris_pm = qris_res.json()
    assert qris_pm["has_qris_image"] is True
    assert qris_pm["qris_image_url"].startswith(f"/api/payment-methods/{qris_pm['id']}/qris")

    bank_res = client.post(
        "/api/admin/payment-methods",
        headers=adm_headers,
        json={
            "type": "bank",
            "label": "Transfer BCA",
            "account_number": "1234567890",
            "account_holder": "PT VoltKu Mandiri",
            "is_active": True,
            "sort_order": 2,
        },
    )
    assert bank_res.status_code == 201
    bank_pm = bank_res.json()

    hidden_res = client.post(
        "/api/admin/payment-methods",
        headers=adm_headers,
        json={
            "type": "ewallet",
            "label": "OVO Nonaktif",
            "account_number": "0811111111",
            "is_active": False,
        },
    )
    assert hidden_res.status_code == 201

    # 2. Public hanya melihat metode yang aktif dan bisa mengunduh gambar QRIS
    pub_res = client.get("/api/public/payment-methods")
    assert pub_res.status_code == 200
    pub_list = pub_res.json()
    assert [m["id"] for m in pub_list] == [qris_pm["id"], bank_pm["id"]]

    qris_img = client.get(qris_pm["qris_image_url"])
    assert qris_img.status_code == 200
    assert qris_img.headers["content-type"] == "image/png"

    # Nonaktifkan QRIS via PATCH + unggah ulang QRIS via endpoint khusus
    upd_qris = client.post(
        f"/api/admin/payment-methods/{qris_pm['id']}/qris",
        headers=adm_headers,
        json={"image_base64": _sample_png_data_url()},
    )
    assert upd_qris.status_code == 200

    # 3. Pelanggan A & B daftar
    reg_a = client.post(
        "/api/users/register",
        json={
            "name": "Pembeli Satu",
            "email": "buyer1@example.com",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg_a.status_code == 201
    a_headers = {"Authorization": f"Bearer {reg_a.json()['token']}"}

    reg_b = client.post(
        "/api/users/register",
        json={
            "name": "Orang Lain",
            "email": "other2@example.com",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg_b.status_code == 201
    b_headers = {"Authorization": f"Bearer {reg_b.json()['token']}"}

    # Pelanggan A membuat tagihan pakai Bank -> status awaiting_payment + order_code
    inv_res = client.post(
        "/api/users/upgrade-request",
        headers=a_headers,
        json={
            "billing_cycle": "monthly",
            "payment_method_id": bank_pm["id"],
            "user_note": "Order pertama",
        },
    )
    assert inv_res.status_code == 201
    inv = inv_res.json()
    assert inv["status"] == "awaiting_payment"
    assert inv["order_code"].startswith("VK-")
    assert inv["payment_method_label"] == "Transfer BCA"
    assert inv["payment_account_number"] == "1234567890"
    assert inv["amount_rp"] == 30000
    assert inv["expires_at"] is not None
    assert inv["expires_at"] - inv["created_at"] == 1800

    # Tidak boleh unggah payload non-gambar (harus ditolak 422)
    bad_proof = client.post(
        f"/api/users/upgrade-requests/{inv['id']}/confirm-payment",
        headers=a_headers,
        json={"proof_base64": "data:text/plain;base64,SGVsbG8td29ybGQ="},
    )
    assert bad_proof.status_code == 422

    # Batalkan tagihan pertama, lalu buat tagihan kedua pakai QRIS
    cancel_res = client.post(
        f"/api/users/upgrade-requests/{inv['id']}/cancel",
        headers=a_headers,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    inv2_res = client.post(
        "/api/users/upgrade-request",
        headers=a_headers,
        json={"billing_cycle": "yearly", "payment_method_id": qris_pm["id"]},
    )
    assert inv2_res.status_code == 201
    inv2 = inv2_res.json()
    assert inv2["status"] == "awaiting_payment"
    assert inv2["amount_rp"] == 300000

    # Pelanggan A mengunggah bukti pembayaran PNG valid -> status verifying
    conf_res = client.post(
        f"/api/users/upgrade-requests/{inv2['id']}/confirm-payment",
        headers=a_headers,
        json={"proof_base64": _sample_png_data_url(), "user_note": "Sudah transfer QRIS"},
    )
    assert conf_res.status_code == 200
    conf = conf_res.json()
    assert conf["status"] == "verifying"
    assert conf["has_payment_proof"] is True
    assert conf["submitted_at"] is not None

    # Isolasi akses foto bukti pembayaran: user lain ditolak (403), pemilik & admin diizinkan
    other_proof = client.get(
        f"/api/users/upgrade-requests/{inv2['id']}/proof",
        headers=b_headers,
    )
    assert other_proof.status_code == 403

    owner_proof = client.get(
        f"/api/users/upgrade-requests/{inv2['id']}/proof",
        headers=a_headers,
    )
    assert owner_proof.status_code == 200
    assert owner_proof.headers["content-type"] == "image/png"

    admin_proof = client.get(
        f"/api/admin/upgrade-requests/{inv2['id']}/proof",
        headers=adm_headers,
    )
    assert admin_proof.status_code == 200
    assert admin_proof.headers["content-type"] == "image/png"

    # Admin memfilter status=active, lalu menyetujui & mengaktifkan VoltKu Pro
    active_list = client.get("/api/admin/upgrade-requests?status=active", headers=adm_headers)
    assert active_list.status_code == 200
    assert any(
        item["id"] == inv2["id"] and item["status"] == "verifying"
        for item in active_list.json()
    )

    appr_res = client.patch(
        f"/api/admin/upgrade-requests/{inv2['id']}",
        headers=adm_headers,
        json={"action": "approve", "admin_note": "Dana masuk via QRIS"},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"

    me_pro = client.get("/api/users/me", headers=a_headers).json()
    assert me_pro["plan"]["is_pro"] is True
    assert me_pro["plan"]["effective_tier"] == "pro"
    assert me_pro["plan"]["latest_upgrade"]["status"] == "approved"

    # Hapus metode pembayaran saat tidak dipakai
    del_res = client.delete(
        f"/api/admin/payment-methods/{hidden_res.json()['id']}",
        headers=adm_headers,
    )
    assert del_res.status_code == 200
    session.close()

