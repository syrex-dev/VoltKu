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


def test_admin_plans_crud_promo_pricing_and_custom_tier():
    _, session = open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")
    adm_headers = {"Authorization": f"Bearer {admin_tok}"}

    # 1. Admin list melihat paket bawaan free & pro
    list_res = client.get("/api/admin/plans", headers=adm_headers)
    assert list_res.status_code == 200
    slugs = {p["slug"]: p for p in list_res.json()}
    assert "free" in slugs and "pro" in slugs
    assert slugs["free"]["is_default_free"] is True

    # Paket gratis bawaan tidak bisa dinonaktifkan maupun dihapus
    bad_deact = client.patch(
        f"/api/admin/plans/{slugs['free']['id']}",
        headers=adm_headers,
        json={"is_active": False},
    )
    assert bad_deact.status_code == 422

    bad_del = client.delete(
        f"/api/admin/plans/{slugs['free']['id']}",
        headers=adm_headers,
    )
    assert bad_del.status_code == 422

    # 2. Admin membuat paket kustom 'bisnis' dengan promo harga coret 20% aktif
    now_utc = int(time.time())
    create_res = client.post(
        "/api/admin/plans",
        headers=adm_headers,
        json={
            "slug": "bisnis",
            "name": "VoltKu Bisnis",
            "description": "Untuk toko & kantor banyak cabang",
            "badge_text": "Paling Laris",
            "price_monthly_rp": 100000,
            "price_yearly_rp": 1000000,
            "promo_discount_type": "percent",
            "promo_discount_value": 20,
            "promo_label": "Diskon Pembukaan",
            "promo_starts_at": now_utc - 60,
            "promo_expires_at": now_utc + 3600,
            "max_devices": 25,
            "history_days": 180,
            "forecast_enabled": True,
            "export_enabled": True,
            "anomaly_advanced": True,
            "features": ["25 panel aktif", "Riwayat 180 hari", "Prioritas dukungan"],
            "is_recommended": True,
            "is_active": True,
            "sort_order": 30,
        },
    )
    assert create_res.status_code == 201
    bisnis = create_res.json()
    assert bisnis["slug"] == "bisnis"
    assert bisnis["promo_active"] is True
    assert bisnis["monthly_promo_discount_rp"] == 20000
    assert bisnis["effective_monthly_price_rp"] == 80000
    assert bisnis["yearly_promo_discount_rp"] == 200000
    assert bisnis["effective_yearly_price_rp"] == 800000

    # 3. Public endpoint menampilkan paket kustom beserta harga promo
    pub_plans = client.get("/api/public/plans")
    assert pub_plans.status_code == 200
    pub_items = {p["slug"]: p for p in pub_plans.json()["items"]}
    assert "bisnis" in pub_items
    assert pub_items["bisnis"]["effective_monthly_price_rp"] == 80000
    assert pub_items["bisnis"]["promo_label"] == "Diskon Pembukaan"

    # Promo fixed_rp melebihi harga dasar tidak pernah menghasilkan angka negatif
    patch_fixed = client.patch(
        f"/api/admin/plans/{bisnis['id']}",
        headers=adm_headers,
        json={
            "promo_discount_type": "fixed_rp",
            "promo_discount_value": 150000,
        },
    )
    assert patch_fixed.status_code == 200
    assert patch_fixed.json()["effective_monthly_price_rp"] == 0
    assert patch_fixed.json()["effective_yearly_price_rp"] == 850000

    # Promo yang sudah melewati promo_expires_at otomatis tidak aktif lagi
    patch_exp = client.patch(
        f"/api/admin/plans/{bisnis['id']}",
        headers=adm_headers,
        json={
            "promo_starts_at": now_utc - 7200,
            "promo_expires_at": now_utc - 60,
        },
    )
    assert patch_exp.status_code == 200
    assert patch_exp.json()["promo_active"] is False
    assert patch_exp.json()["effective_monthly_price_rp"] == 100000

    # Hapus paket yang belum memiliki pelanggan berhasil
    del_bisnis = client.delete(
        f"/api/admin/plans/{bisnis['id']}",
        headers=adm_headers,
    )
    assert del_bisnis.status_code == 200
    session.close()


def test_discount_codes_checkout_caps_and_quota_release():
    _, session = open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")
    adm_headers = {"Authorization": f"Bearer {admin_tok}"}

    # 1. Buat metode bayar aktif + paket 'bisnis' (100rb/bln, promo 20% -> 80rb)
    pm_res = client.post(
        "/api/admin/payment-methods",
        headers=adm_headers,
        json={
            "type": "bank",
            "label": "Mandiri VoltKu",
            "account_number": "99887766",
            "is_active": True,
        },
    )
    assert pm_res.status_code == 201
    pm_id = pm_res.json()["id"]

    bisnis_res = client.post(
        "/api/admin/plans",
        headers=adm_headers,
        json={
            "slug": "bisnis",
            "name": "VoltKu Bisnis",
            "price_monthly_rp": 100000,
            "price_yearly_rp": 1000000,
            "promo_discount_type": "percent",
            "promo_discount_value": 20,
            "promo_label": "Promo Bisnis",
            "max_devices": 25,
            "history_days": 180,
            "forecast_enabled": True,
            "export_enabled": True,
            "anomaly_advanced": True,
            "is_active": True,
        },
    )
    assert bisnis_res.status_code == 201
    bisnis_id = bisnis_res.json()["id"]

    # 2. Kupon HEMAT50: 50% maks 25rb, min 50rb, bisnis monthly, maks 1x pakai
    dc_res = client.post(
        "/api/admin/discounts",
        headers=adm_headers,
        json={
            "code": "hemat50",
            "label": "Voucher Hemat 50%",
            "discount_type": "percent",
            "discount_value": 50,
            "max_discount_rp": 25000,
            "min_purchase_rp": 50000,
            "target_plan_slug": "bisnis",
            "target_cycle": "monthly",
            "max_uses": 1,
            "is_active": True,
        },
    )
    assert dc_res.status_code == 201
    dc_obj = dc_res.json()
    assert dc_obj["code"] == "HEMAT50"

    # 3. Registrasi 2 pelanggan
    reg_a = client.post(
        "/api/users/register",
        json={
            "name": "Bisnis A",
            "email": "bisnis-a@example.com",
            "password": "password123",
            "accept_terms": True,
        },
    )
    reg_b = client.post(
        "/api/users/register",
        json={
            "name": "Bisnis B",
            "email": "bisnis-b@example.com",
            "password": "password123",
            "accept_terms": True,
        },
    )
    a_headers = {"Authorization": f"Bearer {reg_a.json()['token']}"}
    b_headers = {"Authorization": f"Bearer {reg_b.json()['token']}"}

    # Validasi apply-discount gagal jika salah paket / salah siklus / kode palsu
    assert (
        client.post(
            "/api/users/apply-discount",
            headers=a_headers,
            json={"plan_slug": "bisnis", "billing_cycle": "monthly", "discount_code": "NGASAL"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/users/apply-discount",
            headers=a_headers,
            json={"plan_slug": "pro", "billing_cycle": "monthly", "discount_code": "HEMAT50"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/users/apply-discount",
            headers=a_headers,
            json={"plan_slug": "bisnis", "billing_cycle": "yearly", "discount_code": "HEMAT50"},
        ).status_code
        == 422
    )

    # Preview valid pada bisnis monthly:
    # 100.000 - promo 20.000 = 80.000 -> voucher 50% cap 25.000 = 55.000
    prev = client.post(
        "/api/users/apply-discount",
        headers=a_headers,
        json={"plan_slug": "bisnis", "billing_cycle": "monthly", "discount_code": "HEMAT50"},
    )
    assert prev.status_code == 200
    pq = prev.json()
    assert pq["base_amount_rp"] == 100000
    assert pq["promo_discount_rp"] == 20000
    assert pq["voucher_discount_rp"] == 25000
    assert pq["final_amount_rp"] == 55000

    # 4. Pelanggan A buat invoice lalu BATALKAN -> kuota dipakai 1 lalu kembali 0
    inv1 = client.post(
        "/api/users/upgrade-request",
        headers=a_headers,
        json={
            "plan_slug": "bisnis",
            "billing_cycle": "monthly",
            "discount_code": "HEMAT50",
            "payment_method_id": pm_id,
        },
    )
    assert inv1.status_code == 201
    inv1_data = inv1.json()
    assert inv1_data["plan_name_snapshot"] == "VoltKu Bisnis"
    assert inv1_data["amount_rp"] == 55000
    assert inv1_data["discount_code"] == "HEMAT50"

    # Saat dipakai oleh inv1 (max_uses=1), pelanggan B tidak bisa apply kode yang sama
    b_full = client.post(
        "/api/users/apply-discount",
        headers=b_headers,
        json={"plan_slug": "bisnis", "billing_cycle": "monthly", "discount_code": "HEMAT50"},
    )
    assert b_full.status_code == 409

    # Setelah inv1 dibatalkan, kuota HEMAT50 kembali 0 & bisa dipakai lagi
    can1 = client.post(
        f"/api/users/upgrade-requests/{inv1_data['id']}/cancel",
        headers=a_headers,
    )
    assert can1.status_code == 200
    d_cancel_rows = client.get("/api/admin/discounts", headers=adm_headers).json()
    d_list_after_cancel = {d["code"]: d for d in d_cancel_rows}
    assert d_list_after_cancel["HEMAT50"]["used_count"] == 0

    # 5. Pelanggan A buat invoice lagi & unggah bukti, Admin TOLAK -> kuota kembali 0
    inv2 = client.post(
        "/api/users/upgrade-request",
        headers=a_headers,
        json={
            "plan_slug": "bisnis",
            "billing_cycle": "monthly",
            "discount_code": "HEMAT50",
            "payment_method_id": pm_id,
        },
    ).json()
    assert (
        client.post(
            f"/api/users/upgrade-requests/{inv2['id']}/confirm-payment",
            headers=a_headers,
            json={"proof_base64": _sample_png_data_url()},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/admin/upgrade-requests/{inv2['id']}",
            headers=adm_headers,
            json={"action": "reject", "admin_note": "Nominal kurang"},
        ).status_code
        == 200
    )
    d_reject_rows = client.get("/api/admin/discounts", headers=adm_headers).json()
    d_list_after_reject = {d["code"]: d for d in d_reject_rows}
    assert d_list_after_reject["HEMAT50"]["used_count"] == 0

    # 6. Pelanggan A buat invoice ke-3 & Admin SETUJUI -> naik ke tier 'bisnis'
    inv3 = client.post(
        "/api/users/upgrade-request",
        headers=a_headers,
        json={
            "plan_slug": "bisnis",
            "billing_cycle": "monthly",
            "discount_code": "HEMAT50",
            "payment_method_id": pm_id,
        },
    ).json()
    assert (
        client.post(
            f"/api/users/upgrade-requests/{inv3['id']}/confirm-payment",
            headers=a_headers,
            json={"proof_base64": _sample_png_data_url()},
        ).status_code
        == 200
    )
    appr3 = client.patch(
        f"/api/admin/upgrade-requests/{inv3['id']}",
        headers=adm_headers,
        json={"action": "approve"},
    )
    assert appr3.status_code == 200
    me_bisnis = client.get("/api/users/me", headers=a_headers).json()
    assert me_bisnis["plan"]["effective_tier"] == "bisnis"
    assert me_bisnis["plan"]["plan_name"] == "VoltKu Bisnis"
    assert me_bisnis["plan"]["is_pro"] is True
    assert me_bisnis["plan"]["limits"]["max_devices"] == 25
    assert me_bisnis["plan"]["limits"]["history_days"] == 180

    # Paket 'bisnis' yang masih memiliki pelanggan aktif tidak boleh dihapus (409)
    del_in_use = client.delete(f"/api/admin/plans/{bisnis_id}", headers=adm_headers)
    assert del_in_use.status_code == 409

    # Nonaktifkan paket 'bisnis' -> pelanggan B tidak bisa checkout paket nonaktif (404)
    deact_bisnis = client.patch(
        f"/api/admin/plans/{bisnis_id}",
        headers=adm_headers,
        json={"is_active": False},
    )
    assert deact_bisnis.status_code == 200
    b_try = client.post(
        "/api/users/upgrade-request",
        headers=b_headers,
        json={"plan_slug": "bisnis", "billing_cycle": "monthly", "payment_method_id": pm_id},
    )
    assert b_try.status_code == 404

    # Hapus kode promo yang tidak lagi dipakai berhasil
    del_dc = client.delete(f"/api/admin/discounts/{dc_obj['id']}", headers=adm_headers)
    assert del_dc.status_code == 200
    session.close()

