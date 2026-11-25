import json
import time

import jwt
from app.auth import create_access_token, hash_password, user_login_limiter
from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import User
from app.services import google_oauth
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)


def _setup_db():
    _, session = open_clean_test_session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return session


def _generate_rsa_jwk_pair(kid: str = "test-google-kid"):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = kid
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return private_key, {"keys": [public_jwk]}


def _sign_google_token(
    private_key,
    *,
    kid: str = "test-google-kid",
    aud: str = "test-web-client.apps.googleusercontent.com",
    sub: str = "google-sub-12345",
    email: str = "budi.google@example.com",
    name: str = "Budi Google",
    email_verified: bool = True,
    iss: str = "https://accounts.google.com",
    exp_offset: int = 3600,
) -> str:
    now = int(time.time())
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": "https://example.com/avatar.png",
        "iat": now,
        "exp": now + exp_offset,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


def test_oauth_config_endpoint(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_ANDROID_CLIENT_ID", "")
    get_settings.cache_clear()

    res = client.get("/api/users/oauth-config")
    assert res.status_code == 200
    body = res.json()
    assert body["google_enabled"] is False
    assert body["google_client_id"] is None
    assert "terms_version" in body

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "web-cid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_ANDROID_CLIENT_ID", "android-cid.apps.googleusercontent.com")
    get_settings.cache_clear()

    res2 = client.get("/api/users/oauth-config")
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["google_enabled"] is True
    assert body2["google_client_id"] == "web-cid.apps.googleusercontent.com"
    assert body2["google_android_client_id"] == "android-cid.apps.googleusercontent.com"


def test_google_login_unconfigured_returns_503(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_ANDROID_CLIENT_ID", "")
    get_settings.cache_clear()
    user_login_limiter.reset()

    res = client.post("/api/users/google", json={"id_token": "x" * 40})
    assert res.status_code == 503


def test_google_login_creates_and_authenticates_user(monkeypatch):
    session = _setup_db()
    user_login_limiter.reset()
    priv, jwks = _generate_rsa_jwk_pair()
    client_id = "test-web-client.apps.googleusercontent.com"

    monkeypatch.setenv("GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setenv("GOOGLE_ANDROID_CLIENT_ID", "")
    get_settings.cache_clear()
    monkeypatch.setattr(google_oauth, "_fetch_google_jwks", lambda force_refresh=False: jwks)

    id_token = _sign_google_token(priv, aud=client_id)
    res = client.post("/api/users/google", json={"id_token": id_token})
    assert res.status_code == 200
    data = res.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "budi.google@example.com"
    assert data["user"]["auth_provider"] == "google"
    assert data["user"]["avatar_url"] == "https://example.com/avatar.png"

    # Pastikan token JWT user valid untuk /api/users/me
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {data['token']}"})
    assert me.status_code == 200
    assert me.json()["name"] == "Budi Google"

    # Akun Google-only tidak boleh bisa login via kata sandi kosong/sentinel
    bad_local = client.post(
        "/api/users/login",
        json={"email": "budi.google@example.com", "password": "!google_oauth_only"},
    )
    assert bad_local.status_code == 401
    session.close()


def test_google_login_links_existing_local_user_and_blocks_inactive(monkeypatch):
    session = _setup_db()
    user_login_limiter.reset()
    priv, jwks = _generate_rsa_jwk_pair()
    client_id = "test-android-client.apps.googleusercontent.com"

    now = int(time.time())
    existing = User(
        name="Ani Lokal",
        email="ani@example.com",
        password_hash=hash_password("rahasia123"),
        auth_provider="local",
        is_active=1,
        created_at=now,
    )
    session.add(existing)
    session.commit()

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_ANDROID_CLIENT_ID", client_id)
    get_settings.cache_clear()
    monkeypatch.setattr(google_oauth, "_fetch_google_jwks", lambda force_refresh=False: jwks)

    id_token = _sign_google_token(
        priv,
        aud=client_id,
        sub="google-ani-sub",
        email="ani@example.com",
        name="Ani Google",
    )
    res = client.post("/api/users/google", json={"id_token": id_token})
    assert res.status_code == 200
    assert res.json()["user"]["auth_provider"] == "both"
    assert res.json()["user"]["id"] == existing.id

    # Login lokal masih tetap berfungsi
    local_res = client.post(
        "/api/users/login",
        json={"email": "ani@example.com", "password": "rahasia123"},
    )
    assert local_res.status_code == 200

    # Jika akun dinonaktifkan admin, Google login ditolak 403
    existing.is_active = 0
    session.commit()
    blocked_res = client.post("/api/users/google", json={"id_token": id_token})
    assert blocked_res.status_code == 403
    session.close()


def test_google_login_rejects_unverified_or_wrong_audience(monkeypatch):
    _setup_db()
    user_login_limiter.reset()
    priv, jwks = _generate_rsa_jwk_pair()
    client_id = "expected-cid.apps.googleusercontent.com"

    monkeypatch.setenv("GOOGLE_CLIENT_ID", client_id)
    monkeypatch.setenv("GOOGLE_ANDROID_CLIENT_ID", "")
    get_settings.cache_clear()
    monkeypatch.setattr(google_oauth, "_fetch_google_jwks", lambda force_refresh=False: jwks)

    bad_aud = _sign_google_token(priv, aud="other-app.apps.googleusercontent.com")
    r1 = client.post("/api/users/google", json={"id_token": bad_aud})
    assert r1.status_code == 401

    unverified = _sign_google_token(priv, aud=client_id, email_verified=False)
    r2 = client.post("/api/users/google", json={"id_token": unverified})
    assert r2.status_code == 401

    # Admin token tidak bisa memalsukan /api/users/me? Pastikan token admin ter-handle aman
    admin_tok = create_access_token(subject="admin", role="admin")
    assert admin_tok
