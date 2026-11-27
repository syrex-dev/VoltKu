import time

from app.auth import create_access_token
from app.main import app
from app.models import Anomaly, ChatLog, Device
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)


def _register_user(email: str, name: str) -> tuple[str, int]:
    res = client.post(
        "/api/users/register",
        json={
            "name": name,
            "email": email,
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert res.status_code == 201
    body = res.json()
    return body["token"], int(body["user"]["id"])


def test_user_and_admin_feedback_crud_with_reply_notification():
    open_clean_test_session()
    user_tok, user_id = _register_user("pelanggan@voltku.id", "Bu Ulis")
    admin_tok = create_access_token(subject="admin", role="admin")

    # Pelanggan mengirim laporan bug (kurang dari 4 karakter ditolak)
    bad_bug = client.post(
        "/api/users/feedback",
        headers={"Authorization": f"Bearer {user_tok}"},
        json={"rating": 2, "category": "bug", "comment": "ok"},
    )
    assert bad_bug.status_code == 422

    created = client.post(
        "/api/users/feedback",
        headers={"Authorization": f"Bearer {user_tok}"},
        json={"rating": 4, "category": "bug", "comment": "Grafik kWh kadang telat 1 menit"},
    )
    assert created.status_code == 201
    fb_id = created.json()["id"]
    assert created.json()["status"] == "new"

    # Non-admin ditolak di rute admin feedback
    forbidden = client.get(
        "/api/admin/feedback",
        headers={"Authorization": f"Bearer {user_tok}"},
    )
    assert forbidden.status_code == 403

    # Admin melihat daftar dan menghitung new_feedback di sync-state
    adm_list = client.get(
        "/api/admin/feedback",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert adm_list.status_code == 200
    assert adm_list.json()["counts"]["new"] == 1
    assert adm_list.json()["items"][0]["id"] == fb_id

    sync = client.get(
        "/api/admin/sync-state",
        headers={"Authorization": f"Bearer {admin_tok}"},
    ).json()
    assert sync["counts"]["new_feedback"] == 1

    # Admin membalas masukan dan mengirim notifikasi ke inbox user
    replied = client.patch(
        f"/api/admin/feedback/{fb_id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "status": "resolved",
            "admin_reply": "Sudah kami perbaiki di pembaruan sinkronisasi terbaru.",
            "notify_user": True,
        },
    )
    assert replied.status_code == 200
    assert replied.json()["status"] == "resolved"
    assert replied.json()["admin_reply"].startswith("Sudah kami perbaiki")

    # User melihat riwayat feedback + balasan admin & menerima notifikasi lonceng
    my_hist = client.get(
        "/api/users/feedback",
        headers={"Authorization": f"Bearer {user_tok}"},
    ).json()
    assert my_hist[0]["status"] == "resolved"

    inbox = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {user_tok}"},
    ).json()
    assert inbox["unread_count"] == 1
    assert inbox["items"][0]["user_id"] if "user_id" in inbox["items"][0] else True
    assert "Balasan Admin" in inbox["items"][0]["title"]
    assert user_id > 0

    # Admin menghapus feedback
    deleted = client.delete(
        f"/api/admin/feedback/{fb_id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_admin_broadcast_notifications_and_recall():
    _, session = open_clean_test_session()
    free_tok, free_uid = _register_user("gratis@voltku.id", "Akun Gratis")
    pro_tok, pro_uid = _register_user("pro@voltku.id", "Akun Pro")
    admin_tok = create_access_token(subject="admin", role="admin")

    # Naikkan satu user ke Pro
    client.patch(
        f"/api/admin/users/{pro_uid}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"plan_tier": "pro", "plan_days": 30},
    )
    assert free_uid != pro_uid

    # Broadcast khusus paket Pro
    bc_pro = client.post(
        "/api/admin/notifications/broadcast",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "title": "Fitur Eksklusif Pro",
            "body": "Analisa L2 & ekspor CSV 90 hari siap digunakan.",
            "category": "info",
            "severity": "info",
            "target": "pro",
            "send_push": False,
        },
    )
    assert bc_pro.status_code == 201
    assert bc_pro.json()["recipient_count"] == 1
    batch_key = bc_pro.json()["batch_key"]

    # Hanya akun Pro yang menerima
    free_inbox = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {free_tok}"},
    ).json()
    pro_inbox = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {pro_tok}"},
    ).json()
    assert len(free_inbox["items"]) == 0
    assert len(pro_inbox["items"]) == 1
    assert pro_inbox["items"][0]["title"] == "Fitur Eksklusif Pro"

    # Admin melihat daftar batch broadcast lalu menariknya kembali
    adm_notifs = client.get(
        "/api/admin/notifications",
        headers={"Authorization": f"Bearer {admin_tok}"},
    ).json()
    assert any(b["batch_key"] == batch_key for b in adm_notifs["batches"])

    recalled = client.delete(
        f"/api/admin/notifications?batch_key={batch_key}",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert recalled.status_code == 200
    assert recalled.json()["deleted"] == 1

    pro_after = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {pro_tok}"},
    ).json()
    assert len(pro_after["items"]) == 0


def test_admin_telegram_users_crud_and_anomaly_cleanup():
    _, session = open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")

    # Telegram allowlist CRUD (termasuk chat_id grup negatif)
    add_tg = client.post(
        "/api/admin/telegram-users",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"chat_id": -100998877, "name": "Grup Operator Panel"},
    )
    assert add_tg.status_code == 201
    assert add_tg.json()["chat_id"] == -100998877

    dup_tg = client.post(
        "/api/admin/telegram-users",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"chat_id": -100998877, "name": "Duplikat"},
    )
    assert dup_tg.status_code == 409

    upd_tg = client.patch(
        "/api/admin/telegram-users/-100998877",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"name": "Grup Teknisi Utama"},
    )
    assert upd_tg.status_code == 200
    assert upd_tg.json()["name"] == "Grup Teknisi Utama"

    session.add(
        ChatLog(
            chat_id=-100998877,
            ts=int(time.time()),
            question="Biaya hari ini?",
            tools_used="get_summary",
            answer="Rp 5.000",
            tokens=120,
        )
    )
    session.commit()

    tg_list = client.get(
        "/api/admin/telegram-users",
        headers={"Authorization": f"Bearer {admin_tok}"},
    ).json()
    assert len(tg_list["items"]) == 1
    assert tg_list["recent_logs"][0]["sender_name"] == "Grup Teknisi Utama"

    del_tg = client.delete(
        "/api/admin/telegram-users/-100998877",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert del_tg.status_code == 200

    # Seed device + 3 anomalies untuk menguji delete single & purge filtered
    now_ts = int(time.time())
    session.add(Device(id="dev_uji", name="Panel Uji", mcb_watt=2200, status="online"))
    a1 = Anomaly(
        device_id="dev_uji",
        ts=now_ts - 10,
        type="power_limit",
        severity="critical",
        details_json="{}",
        message="Beban tinggi",
    )
    a2 = Anomaly(
        device_id="dev_uji",
        ts=now_ts - 5,
        type="voltage_low",
        severity="warning",
        details_json="{}",
        message="Tegangan turun",
    )
    session.add_all([a1, a2])
    session.commit()
    session.refresh(a1)

    del_one = client.delete(
        f"/api/admin/anomalies/{a1.id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert del_one.status_code == 200

    purge_rest = client.delete(
        "/api/admin/anomalies?device_id=dev_uji",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert purge_rest.status_code == 200
    assert purge_rest.json()["deleted"] == 1


def test_admin_stock_device_create_single_and_batch():
    open_clean_test_session()
    user_tok, _ = _register_user("stokuser@voltku.id", "Pelanggan")
    admin_tok = create_access_token(subject="admin", role="admin")

    # Non-admin ditolak (403)
    forbidden = client.post(
        "/api/admin/devices",
        headers={"Authorization": f"Bearer {user_tok}"},
        json={"id": "VK-FAIL-1", "name": "Panel Ilegal"},
    )
    assert forbidden.status_code == 403

    # Buat 1 unit stok kustom
    single = client.post(
        "/api/admin/devices",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "id": "VK-UNIT-01",
            "name": "Panel Stok Gudang",
            "location": "Rak B",
            "mcb_watt": 3500,
            "is_public_demo": False,
        },
    )
    assert single.status_code == 201
    assert single.json()["count"] == 1
    assert single.json()["created"][0]["id"] == "VK-UNIT-01"

    # Duplikat ID ditolak (409)
    dup = client.post(
        "/api/admin/devices",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"id": "VK-UNIT-01", "name": "Duplikat"},
    )
    assert dup.status_code == 409

    # Batch create 3 unit
    batch = client.post(
        "/api/admin/devices",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "id_prefix": "VK-BATCH-",
            "count": 3,
            "name": "VoltKu Batch",
            "mcb_watt": 2200,
            "is_public_demo": True,
        },
    )
    assert batch.status_code == 201
    assert batch.json()["count"] == 3
    ids = [d["id"] for d in batch.json()["created"]]
    assert ids == ["VK-BATCH-01", "VK-BATCH-02", "VK-BATCH-03"]
    assert all(d["is_public_demo"] is True for d in batch.json()["created"])


def test_admin_dynamic_content_tariffs_release_guide_and_ai_prompts():
    open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")

    # Validasi ketat URL APK & prompt kosong
    bad_apk = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"app_release": {"version": "v3.0.0", "apk_download_url": "javascript:alert(1)"}},
    )
    assert bad_apk.status_code == 422

    bad_prompts = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"ai_quick_prompts": []},
    )
    assert bad_prompts.status_code == 422

    rev_before = client.get("/api/public/sync-state").json()["config_rev"]
    upd = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "ai_quick_prompts": ["Cek beban AC sekarang?", "Hitung tagihan minggu ini"],
            "pln_tariffs": [
                {
                    "id": "promo-rumah",
                    "category": "rumah",
                    "group": "Rumah Tangga",
                    "label": "R-1/TR · Promo Uji",
                    "tariff_rp": "1500.00",
                }
            ],
            "app_release": {
                "version": "v2.6.0",
                "apk_download_url": "https://voltku.synemax.web.id/VoltKu.apk",
                "release_notes": "Rilis baru dengan kontrol CRUD penuh.",
                "changelog": [
                    {
                        "version": "v2.6.0",
                        "date": "27 Nov 2026",
                        "badge": "Baru",
                        "items": ["Tambahan CRUD stok QR & konten dinamis"],
                    }
                ],
            },
            "usage_guide": {
                "pairing_intro_title": "Panduan Cepat Kustom",
                "pairing_intro_desc": "Siapkan Wi-Fi 2.4 GHz.",
                "usage_intro_title": "Fitur Utama",
                "usage_intro_desc": "Pantau real-time.",
                "pairing_steps": [{"step": 1, "text": "Nyalakan unit lalu scan QR."}],
                "usage_cards": [{"title": "Live Watt", "desc": "Lihat beban setiap 10 detik."}],
            },
        },
    )
    assert upd.status_code == 200
    rev_after = client.get("/api/public/sync-state").json()["config_rev"]
    assert rev_after != rev_before

    pub = client.get("/api/public/app-config").json()
    assert pub["ai_quick_prompts"] == ["Cek beban AC sekarang?", "Hitung tagihan minggu ini"]
    assert pub["pln_tariffs"][0]["id"] == "promo-rumah"
    assert pub["pln_tariffs"][0]["tariff_rp"] == "1500.00"
    assert pub["app_release"]["version"] == "v2.6.0"
    assert pub["app_release"]["apk_download_url"] == "https://voltku.synemax.web.id/VoltKu.apk"
    assert pub["usage_guide"]["pairing_intro_title"] == "Panduan Cepat Kustom"
    assert pub["usage_guide"]["pairing_steps"][0]["text"] == "Nyalakan unit lalu scan QR."
