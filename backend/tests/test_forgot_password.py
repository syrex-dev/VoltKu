import hashlib
import time

from app.main import app
from app.models import PasswordResetToken, User
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session
from sqlalchemy import select

client = TestClient(app)


def test_forgot_and_reset_password_full_flow(monkeypatch):
    _, session = open_clean_test_session()
    sent_emails: list[dict[str, str]] = []

    def fake_send_email(
        *, to_email: str, user_name: str, raw_token: str, expires_minutes: int = 30
    ):
        sent_emails.append(
            {
                "to": to_email,
                "name": user_name,
                "token": raw_token,
                "expires_minutes": str(expires_minutes),
            }
        )
        return True

    monkeypatch.setattr("app.routers.users.send_password_reset_email", fake_send_email)

    # 1. Daftar akun pengguna
    reg = client.post(
        "/api/users/register",
        json={
            "name": "Pengguna Lupa",
            "email": "lupa@example.com",
            "password": "PasswordLama123",
            "accept_terms": True,
        },
    )
    assert reg.status_code == 201
    uid = reg.json()["user"]["id"]

    # 2. Email tak terdaftar tetap mendapat respons 200 netral (anti-enumerasi)
    unknown_res = client.post(
        "/api/users/forgot-password",
        json={"email": "tidakada@example.com"},
    )
    assert unknown_res.status_code == 200
    assert unknown_res.json()["sent"] is True
    assert len(sent_emails) == 0

    # 3. Email terdaftar menerima token reset dan hanya hash SHA-256 yang tersimpan di DB
    ok_res = client.post(
        "/api/users/forgot-password",
        json={"email": "LUPA@example.com"},
    )
    assert ok_res.status_code == 200
    assert len(sent_emails) == 1
    raw_token = sent_emails[0]["token"]
    assert len(raw_token) >= 32

    db_row = session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.user_id == uid)
    )
    assert db_row is not None
    assert db_row.token_hash != raw_token
    assert db_row.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert db_row.used_at is None
    assert 1700 <= (db_row.expires_at - db_row.created_at) <= 1810

    # 4. Kata sandi baru yang lemah ditolak (422)
    weak_res = client.post(
        "/api/users/reset-password",
        json={"token": raw_token, "new_password": "password"},
    )
    assert weak_res.status_code == 422

    # 5. Token salah ditolak (400)
    bad_tok_res = client.post(
        "/api/users/reset-password",
        json={"token": "token_ngawur_tidak_terdaftar_123456", "new_password": "PasswordBaru99"},
    )
    assert bad_tok_res.status_code == 400

    # 6. Reset kata sandi dengan token valid berhasil & token langsung hangus
    reset_res = client.post(
        "/api/users/reset-password",
        json={"token": raw_token, "new_password": "PasswordBaru99"},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["reset"] is True

    # Token yang sama tidak boleh dipakai dua kali
    replay_res = client.post(
        "/api/users/reset-password",
        json={"token": raw_token, "new_password": "PasswordLain99"},
    )
    assert replay_res.status_code == 400

    # 7. Kata sandi lama gagal login, kata sandi baru berhasil login
    old_login = client.post(
        "/api/users/login",
        json={"email": "lupa@example.com", "password": "PasswordLama123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/users/login",
        json={"email": "lupa@example.com", "password": "PasswordBaru99"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["user"]["id"] == uid

    # 8. Token yang sudah kedaluwarsa ditolak (400)
    exp_raw = "expired_token_test_1234567890_abcdef"
    exp_hash = hashlib.sha256(exp_raw.encode("utf-8")).hexdigest()
    session.add(
        PasswordResetToken(
            user_id=uid,
            token_hash=exp_hash,
            expires_at=int(time.time()) - 10,
            created_at=int(time.time()) - 2000,
        )
    )
    session.commit()

    exp_res = client.post(
        "/api/users/reset-password",
        json={"token": exp_raw, "new_password": "PasswordBaruLagi1"},
    )
    assert exp_res.status_code == 400
    session.close()


def test_forgot_password_rate_limit(monkeypatch):
    monkeypatch.setattr("app.routers.users.send_password_reset_email", lambda **kw: True)
    # 5 permintaan diizinkan, ke-6 terkena HTTP 429
    for _ in range(5):
        r = client.post("/api/users/forgot-password", json={"email": "spam@example.com"})
        assert r.status_code == 200
    blocked = client.post("/api/users/forgot-password", json={"email": "spam@example.com"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_email_builder_url():
    from app.services.email_service import build_reset_password_url

    url = build_reset_password_url("abc_123")
    assert url.endswith("/?reset_token=abc_123")
    assert User is not None


def test_admin_edit_email_and_trigger_reset_link(monkeypatch):
    from app.auth import create_access_token

    _, session = open_clean_test_session()
    captured: list[str] = []

    def fake_admin_send(
        *, to_email: str, user_name: str, raw_token: str, expires_minutes: int = 30
    ):
        captured.append(f"{to_email}:{raw_token}")
        return True

    monkeypatch.setattr("app.routers.admin.send_password_reset_email", fake_admin_send)

    admin_tok = create_access_token(subject="admin", role="admin")
    adm_headers = {"Authorization": f"Bearer {admin_tok}"}

    u1 = client.post(
        "/api/admin/users",
        headers=adm_headers,
        json={"name": "Pembeli Awal", "email": "lama@example.com", "password": "PasswordAwal1"},
    )
    assert u1.status_code == 201
    uid = u1.json()["id"]

    # Edit email pembeli
    upd = client.patch(
        f"/api/admin/users/{uid}",
        headers=adm_headers,
        json={"email": "baru@example.com"},
    )
    assert upd.status_code == 200
    assert upd.json()["email"] == "baru@example.com"

    # Admin memicu pengiriman tautan reset ke email baru
    trig = client.post(f"/api/admin/users/{uid}/send-reset-link", headers=adm_headers)
    assert trig.status_code == 200
    assert trig.json()["sent"] is True
    assert trig.json()["email"] == "baru@example.com"
    assert len(captured) == 1
    sent_email, raw_tok = captured[0].split(":", 1)
    assert sent_email == "baru@example.com"

    # Pembeli memakai token untuk menyetel kata sandi baru
    rst = client.post(
        "/api/users/reset-password",
        json={"token": raw_tok, "new_password": "PasswordBaru88"},
    )
    assert rst.status_code == 200
    login_ok = client.post(
        "/api/users/login",
        json={"email": "baru@example.com", "password": "PasswordBaru88"},
    )
    assert login_ok.status_code == 200
    session.close()
