import time

from app.auth import create_access_token
from app.config import get_settings
from app.main import app
from app.models import TermsConsent
from app.services import google_oauth
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session
from test_google_auth import _generate_rsa_jwk_pair, _sign_google_token

client = TestClient(app)


def test_public_app_config_and_guest_terms_consent():
    _, session = open_clean_test_session()

    cfg_res = client.get("/api/public/app-config")
    assert cfg_res.status_code == 200
    cfg = cfg_res.json()
    assert cfg["app_name"] == "VoltKu"
    assert cfg["navbar_brand_display"] == "logo_only"
    assert len(cfg["onboarding_steps"]) == 3
    assert cfg["terms_title"]
    assert cfg["terms_content"]
    assert cfg["privacy_title"]
    assert cfg["privacy_content"]
    assert "jwt_secret" not in cfg
    assert "dashboard_password" not in cfg

    bad_res = client.post(
        "/api/public/terms-consent",
        json={"accepted": False, "client_id": "client-abc-12345"},
    )
    assert bad_res.status_code == 422

    ok_res = client.post(
        "/api/public/terms-consent",
        json={
            "accepted": True,
            "client_id": "client-apk-987654",
            "terms_version": cfg["terms_version"],
        },
        headers={"User-Agent": "VoltKuTestAgent/1.0"},
    )
    assert ok_res.status_code == 201
    body = ok_res.json()
    assert body["recorded"] is True
    assert body["terms_version"] == cfg["terms_version"]

    logged = session.query(TermsConsent).filter_by(client_id="client-apk-987654").first()
    assert logged is not None
    assert logged.accepted_via == "guest"
    assert logged.user_agent == "VoltKuTestAgent/1.0"
    session.close()


def test_register_login_google_and_reconsent_persists_terms_in_db(monkeypatch):
    _, session = open_clean_test_session()

    # Registrasi ditolak bila accept_terms=False
    declined = client.post(
        "/api/users/register",
        json={
            "name": "Budi Santoso",
            "email": "budi@contoh.id",
            "password": "password123",
            "accept_terms": False,
        },
    )
    assert declined.status_code == 422

    # Registrasi dengan accept_terms=True tercatat di users & terms_consents
    reg = client.post(
        "/api/users/register",
        json={
            "name": "Budi Santoso",
            "email": "budi@contoh.id",
            "password": "password123",
            "accept_terms": True,
            "client_id": "web-client-001",
        },
    )
    assert reg.status_code == 201
    reg_body = reg.json()
    assert reg_body["user"]["terms_version_accepted"]
    assert reg_body["user"]["needs_terms_reconsent"] is False
    tok = reg_body["token"]

    # Admin menaikkan versi S&K -> user wajib menyetujui ulang
    admin_tok = create_access_token(subject="admin", role="admin")
    bump = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"terms_version": "2026-12-v2", "terms_content": "Ketentuan versi terbaru."},
    )
    assert bump.status_code == 200
    assert bump.json()["terms_version"] == "2026-12-v2"

    me_stale = client.get("/api/users/me", headers={"Authorization": f"Bearer {tok}"})
    assert me_stale.status_code == 200
    assert me_stale.json()["needs_terms_reconsent"] is True

    reconsent = client.post(
        "/api/users/terms-consent",
        headers={"Authorization": f"Bearer {tok}"},
        json={"accepted": True, "terms_version": "2026-12-v2", "client_id": "web-client-001"},
    )
    assert reconsent.status_code == 200
    assert reconsent.json()["terms_version_accepted"] == "2026-12-v2"
    assert reconsent.json()["needs_terms_reconsent"] is False

    # Google Sign-In juga menyimpan consent dengan accept_terms=True
    priv, jwks = _generate_rsa_jwk_pair()
    cid = "admin-override-google-cid.apps.googleusercontent.com"
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    get_settings.cache_clear()
    monkeypatch.setattr(google_oauth, "_fetch_google_jwks", lambda force_refresh=False: jwks)

    set_cid = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"google_auth_enabled": True, "google_client_id": cid},
    )
    assert set_cid.status_code == 200
    assert set_cid.json()["google_enabled"] is True

    id_token = _sign_google_token(
        priv,
        aud=cid,
        sub="g-sub-consent-1",
        email="sari.google@contoh.id",
        name="Sari Google",
    )
    gres = client.post(
        "/api/users/google",
        json={"id_token": id_token, "accept_terms": True, "client_id": "apk-client-99"},
    )
    assert gres.status_code == 200
    assert gres.json()["user"]["terms_version_accepted"] == "2026-12-v2"

    # Audit log admin memuat semua riwayat
    audit = client.get("/api/admin/consents", headers={"Authorization": f"Bearer {admin_tok}"})
    assert audit.status_code == 200
    audit_body = audit.json()
    assert audit_body["users_agreed_current"] == 2
    assert audit_body["users_pending_or_outdated"] == 0
    vias = {item["accepted_via"] for item in audit_body["items"]}
    assert {"register", "reconsent", "google"}.issubset(vias)
    session.close()


def test_admin_app_settings_controls_registration_google_and_operational():
    open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")
    reg_u = client.post(
        "/api/users/register",
        json={
            "name": "User Biasa",
            "email": "u@contoh.id",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg_u.status_code == 201
    user_tok = reg_u.json()["token"]

    # User biasa ditolak (403)
    assert (
        client.get(
            "/api/admin/app-settings", headers={"Authorization": f"Bearer {user_tok}"}
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/admin/consents", headers={"Authorization": f"Bearer {user_tok}"}
        ).status_code
        == 403
    )

    # Admin update branding, auth policy, dukungan & operasional
    patch_res = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "app_name": "VoltKu Pro",
            "navbar_brand_display": "logo_text",
            "announcement_active": True,
            "announcement_text": "Pemeliharaan sensor jam 23:00 WIB",
            "default_theme": "dark",
            "onboarding_enabled": False,
            "registration_enabled": False,
            "google_auth_enabled": False,
            "public_read_enabled": False,
            "support_whatsapp": "6281234567890",
            "tariff_rp": "1699.53",
            "power_limit_w": 3500,
        },
    )
    assert patch_res.status_code == 200
    saved = patch_res.json()
    assert saved["app_name"] == "VoltKu Pro"
    assert saved["navbar_brand_display"] == "logo_text"
    assert saved["default_theme"] == "dark"
    assert saved["onboarding_enabled"] is False
    assert saved["registration_enabled"] is False
    assert saved["google_auth_enabled"] is False
    assert saved["google_enabled"] is False
    assert saved["public_read_enabled"] is False
    assert saved["support_whatsapp"] == "6281234567890"
    assert saved["tariff_rp"] == "1699.53"
    assert saved["power_limit_w"] == 3500

    # Publik app-config langsung merefleksikan perubahan
    pub = client.get("/api/public/app-config").json()
    assert pub["app_name"] == "VoltKu Pro"
    assert pub["announcement_active"] is True
    assert pub["registration_enabled"] is False
    assert pub["google_enabled"] is False
    assert pub["public_read_enabled"] is False

    # Registrasi & Google Login ditolak ketika dinonaktifkan Admin
    reg_blocked = client.post(
        "/api/users/register",
        json={
            "name": "Tamu Ditolak",
            "email": f"blocked{int(time.time())}@contoh.id",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg_blocked.status_code == 403

    google_blocked = client.post(
        "/api/users/google",
        json={"id_token": "x" * 40, "accept_terms": True},
    )
    assert google_blocked.status_code == 503


def test_admin_hero_banners_crud_validation_and_empty_delete():
    open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")

    init_pub = client.get("/api/public/app-config").json()
    assert len(init_pub["hero_banners"]) == 6
    rev_before = client.get("/api/public/sync-state").json()["config_rev"]

    # Validasi ketat URL & judul wajib diisi
    bad_url = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "hero_banners": [
                {
                    "id": "xss-test",
                    "title": "Klik Bahaya",
                    "action_type": "open_url",
                    "action_url": "javascript:alert(1)",
                }
            ]
        },
    )
    assert bad_url.status_code == 422

    bad_title = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"hero_banners": [{"id": "no-title", "title": "   "}]},
    )
    assert bad_title.status_code == 422

    # Admin mengubah & menonaktifkan salah satu banner
    custom_banners = [
        {
            "id": "promo-november",
            "badge": "PROMO AKHIR BULAN",
            "title": "Diskon Pro 50% Hari Ini",
            "subtitle": "Khusus pelanggan aktif hingga pukul 23:59 WIB",
            "cta": "Klaim Promo",
            "tone": "is-announcement",
            "icon": "sparkles",
            "action_type": "upgrade_plan",
            "audience": "free_only",
            "enabled": True,
        },
        {
            "id": "hidden-slide",
            "badge": "ARSIP",
            "title": "Banner Nonaktif",
            "subtitle": "Disembunyikan sementara",
            "cta": "Lihat",
            "tone": "is-cobalt",
            "icon": "zap",
            "action_type": "none",
            "audience": "all",
            "enabled": False,
        },
    ]
    upd = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"hero_banners": custom_banners},
    )
    assert upd.status_code == 200
    upd_body = upd.json()
    assert len(upd_body["hero_banners"]) == 2
    assert len(upd_body["default_hero_banners"]) == 6

    pub_after = client.get("/api/public/app-config").json()
    assert [b["id"] for b in pub_after["hero_banners"]] == ["promo-november", "hidden-slide"]
    assert pub_after["hero_banners"][0]["tone"] == "is-announcement"
    rev_after = client.get("/api/public/sync-state").json()["config_rev"]
    assert rev_after != rev_before

    # Menghapus seluruh banner ([]) tetap bertahan [] dan tidak balik ke 6 default
    cleared = client.patch(
        "/api/admin/app-settings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"hero_banners": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["hero_banners"] == []
    assert client.get("/api/public/app-config").json()["hero_banners"] == []


def test_admin_visual_assets_crud_upload_toggle_reset_and_disable():
    open_clean_test_session()
    admin_tok = create_access_token(subject="admin", role="admin")
    reg = client.post(
        "/api/users/register",
        json={
            "name": "Bukan Admin",
            "email": "bukanadmin@voltku.id",
            "password": "password123",
            "accept_terms": True,
        },
    )
    assert reg.status_code == 201
    user_tok = reg.json()["token"]

    tiny_png_b64 = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    # Non-admin ditolak (403)
    forbidden = client.put(
        "/api/admin/visual-assets/pro_banner",
        headers={"Authorization": f"Bearer {user_tok}"},
        json={"image_base64": tiny_png_b64},
    )
    assert forbidden.status_code == 403

    # Slot tidak dikenal ditolak (404), payload rusak ditolak (422)
    unknown = client.put(
        "/api/admin/visual-assets/slot_palsu",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"enabled": False},
    )
    assert unknown.status_code == 404

    invalid_img = client.put(
        "/api/admin/visual-assets/pro_banner",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"image_base64": "bukan-gambar-base64"},
    )
    assert invalid_img.status_code == 422

    rev_before = client.get("/api/public/sync-state").json()["config_rev"]

    # Admin upload gambar kustom untuk pro_banner
    uploaded = client.put(
        "/api/admin/visual-assets/pro_banner",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"image_base64": tiny_png_b64, "enabled": True},
    )
    assert uploaded.status_code == 200
    pro_meta = uploaded.json()["visual_assets"]["pro_banner"]
    assert pro_meta["is_custom"] is True
    assert pro_meta["enabled"] is True
    assert pro_meta["url"].startswith("/api/public/visual-assets/pro_banner?v=")

    # Public config & file endpoint menyajikan gambar kustom dan sync-state berubah
    pub = client.get("/api/public/app-config").json()
    assert pub["visual_assets"]["pro_banner"]["url"] == pro_meta["url"]
    rev_after = client.get("/api/public/sync-state").json()["config_rev"]
    assert rev_after != rev_before

    img_res = client.get("/api/public/visual-assets/pro_banner")
    assert img_res.status_code == 200
    assert img_res.headers["content-type"].startswith("image/png")
    assert img_res.content.startswith(b"\x89PNG")

    # Toggle hide sementara mempertahankan custom flag tetapi enabled=False
    toggled = client.put(
        "/api/admin/visual-assets/pro_banner",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"enabled": False},
    )
    assert toggled.status_code == 200
    assert toggled.json()["visual_assets"]["pro_banner"]["enabled"] is False
    assert toggled.json()["visual_assets"]["pro_banner"]["is_custom"] is True

    # Delete action=disable menyembunyikan slot bawaan dan menghapus file kustom
    disabled = client.delete(
        "/api/admin/visual-assets/chatbot_avatar?action=disable",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["visual_assets"]["chatbot_avatar"]["enabled"] is False
    assert disabled.json()["visual_assets"]["chatbot_avatar"]["is_custom"] is False

    # Delete action=reset memulihkan pro_banner ke maskot bawaan & menghapus berkas publik
    reset_res = client.delete(
        "/api/admin/visual-assets/pro_banner?action=reset",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert reset_res.status_code == 200
    pro_reset = reset_res.json()["visual_assets"]["pro_banner"]
    assert pro_reset["enabled"] is True
    assert pro_reset["is_custom"] is False
    assert pro_reset["url"] is None
    assert client.get("/api/public/visual-assets/pro_banner").status_code == 404
