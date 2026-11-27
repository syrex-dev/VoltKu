from app.auth import create_access_token, hash_password, pin_verify_limiter
from app.db import get_db
from app.models import User, UserSetting
from app.services.plans import ensure_default_plans_seeded
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session
from sqlalchemy import select

app_main = __import__("app.main", fromlist=["app"]).app
client = TestClient(app_main)


def _setup_pin_test_db():
    pin_verify_limiter.reset()
    _, session = open_clean_test_session()
    ensure_default_plans_seeded(session)
    user = User(
        email="pinbuyer@voltku.test",
        name="Pembeli Aman",
        password_hash=hash_password("SandiKuat99!"),
        plan_tier="free",
        is_active=1,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app_main.dependency_overrides[get_db] = override_get_db
    tok = create_access_token(subject=user.email, role="user", user_id=user.id)
    headers = {"Authorization": f"Bearer {tok}"}
    return session, user, headers


def test_pin_lifecycle_sync_weak_policy_and_brute_force_lockout():
    session, user, headers = _setup_pin_test_db()
    try:
        me_0 = client.get("/api/users/me", headers=headers)
        assert me_0.status_code == 200
        assert me_0.json()["app_lock"]["pin_enabled"] is False
        assert "app_pin_hash" not in me_0.text

        sync_0 = client.get("/api/users/sync-state", headers=headers).json()

        # 1. Tolak PIN tidak valid & pola lemah
        for bad_pin in ("12345", "12a456", "111111", "123456", "654321", "112233"):
            r = client.post("/api/users/pin", json={"new_pin": bad_pin}, headers=headers)
            assert r.status_code == 422

        # 2. Set PIN kuat -> tersimpan terhash PBKDF2 & terpantau oleh sync-state
        ok_set = client.post("/api/users/pin", json={"new_pin": "482915"}, headers=headers)
        assert ok_set.status_code == 200
        assert ok_set.json()["app_lock"]["pin_enabled"] is True

        stored = session.scalar(
            select(UserSetting).where(
                UserSetting.user_id == user.id,
                UserSetting.key == "app_pin_hash",
            )
        )
        assert stored is not None
        assert stored.value.startswith("pbkdf2_sha256$")
        assert "482915" not in stored.value

        me_1 = client.get("/api/users/me", headers=headers).json()
        assert me_1["app_lock"]["pin_enabled"] is True
        assert me_1["app_lock"]["pin_updated_at"] > 0

        sync_1 = client.get("/api/users/sync-state", headers=headers).json()
        assert sync_1["user_rev"] != sync_0["user_rev"]

        # 3. Verifikasi PIN benar
        v_ok = client.post("/api/users/pin/verify", json={"pin": "482915"}, headers=headers)
        assert v_ok.status_code == 200
        assert v_ok.json()["verified"] is True

        # 4. Ganti PIN wajib menyertakan current_pin yang benar
        chg_missing = client.post("/api/users/pin", json={"new_pin": "739204"}, headers=headers)
        assert chg_missing.status_code == 401
        chg_wrong = client.post(
            "/api/users/pin",
            json={"current_pin": "000001", "new_pin": "739204"},
            headers=headers,
        )
        assert chg_wrong.status_code == 401
        chg_ok = client.post(
            "/api/users/pin",
            json={"current_pin": "482915", "new_pin": "739204"},
            headers=headers,
        )
        assert chg_ok.status_code == 200

        # 5. Salah 5 kali -> lockout progresif (429 pada percobaan berikutnya)
        for attempt in range(1, 6):
            r_bad = client.post("/api/users/pin/verify", json={"pin": "999998"}, headers=headers)
            assert r_bad.status_code == 200
            body = r_bad.json()
            assert body["verified"] is False
            assert body["attempts"] == attempt
            if attempt < 5:
                assert body["retry_after"] == 0
            else:
                assert body["retry_after"] >= 60

        r_locked = client.post("/api/users/pin/verify", json={"pin": "739204"}, headers=headers)
        assert r_locked.status_code == 429

        # 6. Matikan PIN dengan kata sandi akun (pemulihan saat lupa/terkunci)
        dis_bad = client.post(
            "/api/users/pin/disable",
            json={"account_password": "SandiSalah"},
            headers=headers,
        )
        assert dis_bad.status_code == 401

        dis_ok = client.post(
            "/api/users/pin/disable",
            json={"account_password": "SandiKuat99!"},
            headers=headers,
        )
        assert dis_ok.status_code == 200
        assert dis_ok.json()["app_lock"]["pin_enabled"] is False

        me_2 = client.get("/api/users/me", headers=headers).json()
        assert me_2["app_lock"]["pin_enabled"] is False
        sync_2 = client.get("/api/users/sync-state", headers=headers).json()
        assert sync_2["user_rev"] != sync_1["user_rev"]
    finally:
        app_main.dependency_overrides.pop(get_db, None)
        pin_verify_limiter.reset()

