from app.auth import get_trusted_client_ip, register_limiter
from app.main import app
from fastapi.testclient import TestClient


def test_security_headers_and_strict_csp():
    client = TestClient(app)
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert res.headers["X-Permitted-Cross-Domain-Policies"] == "none"
    assert "camera=(self)" in res.headers["Permissions-Policy"]
    assert "microphone=()" in res.headers["Permissions-Policy"]
    csp = res.headers["Content-Security-Policy"]
    assert "unsafe-eval" not in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_cors_rejects_untrusted_origin_and_allows_production_origin():
    client = TestClient(app)

    evil = client.options(
        "/api/public/access",
        headers={
            "Origin": "https://evil-attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert evil.headers.get("access-control-allow-origin") is None

    good = client.options(
        "/api/public/access",
        headers={
            "Origin": "https://voltku.synemax.web.id",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert good.headers.get("access-control-allow-origin") == "https://voltku.synemax.web.id"


def test_login_rate_limit_is_isolated_per_ip():
    client = TestClient(app)
    for _ in range(5):
        res = client.post(
            "/api/login",
            json={"password": "wrong_password_123"},
            headers={"CF-Connecting-IP": "198.51.100.10"},
        )
        assert res.status_code == 401

    blocked = client.post(
        "/api/login",
        json={"password": "test_password_12chars"},
        headers={"CF-Connecting-IP": "198.51.100.10"},
    )
    assert blocked.status_code == 429

    # IP lain tetap dapat login tanpa terkena lockout DoS
    other_ip_ok = client.post(
        "/api/login",
        json={"password": "test_password_12chars"},
        headers={"CF-Connecting-IP": "198.51.100.25"},
    )
    assert other_ip_ok.status_code == 200


def test_register_rejects_weak_passwords_and_rate_limits_spam():
    client = TestClient(app)
    weak = client.post(
        "/api/users/register",
        json={
            "name": "Tester Lemah",
            "email": "lemah@contoh.id",
            "password": "123456",
            "accept_terms": True,
        },
        headers={"CF-Connecting-IP": "203.0.113.5"},
    )
    assert weak.status_code == 422

    register_limiter.reset()
    for i in range(10):
        res = client.post(
            "/api/users/register",
            json={
                "name": f"User {i}",
                "email": f"spam{i}@contoh.id",
                "password": f"kuat_sandi_{i}_99",
                "accept_terms": True,
            },
            headers={"CF-Connecting-IP": "203.0.113.5"},
        )
        assert res.status_code == 201

    spam_blocked = client.post(
        "/api/users/register",
        json={
            "name": "User 11",
            "email": "spam11@contoh.id",
            "password": "kuat_sandi_11_99",
            "accept_terms": True,
        },
        headers={"CF-Connecting-IP": "203.0.113.5"},
    )
    assert spam_blocked.status_code == 429


def test_trusted_client_ip_ignores_spoofed_headers_from_untrusted_peer():
    class _FakeClient:
        def __init__(self, host: str):
            self.host = host

    class _FakeReq:
        def __init__(self, peer: str, headers: dict[str, str]):
            self.client = _FakeClient(peer)
            self.headers = headers

    # Peer langsung dari internet -> abaikan header spoofing
    direct = _FakeReq("198.51.100.77", {"cf-connecting-ip": "1.2.3.4"})
    assert get_trusted_client_ip(direct) == "198.51.100.77"

    # Peer dari Nginx lokal -> percaya CF-Connecting-IP
    proxied = _FakeReq("127.0.0.1", {"cf-connecting-ip": "203.0.113.99"})
    assert get_trusted_client_ip(proxied) == "203.0.113.99"


def test_mqtt_ingest_client_applies_tls_when_enabled(monkeypatch):
    from unittest.mock import patch

    import paho.mqtt.client as paho_mqtt
    from app.config import get_settings
    from app.mqtt_ingest import IngestService

    svc = IngestService()

    # Non-TLS default
    get_settings.cache_clear()
    with patch.object(paho_mqtt.Client, "tls_set") as mock_tls_set:
        svc.init_mqtt_client()
        mock_tls_set.assert_not_called()

    # TLS aktif dengan CA cert custom
    monkeypatch.setenv("MQTT_USE_TLS", "true")
    monkeypatch.setenv("MQTT_CA_CERT", "/mosquitto/certs/ca.crt")
    monkeypatch.setenv("MQTT_TLS_INSECURE", "false")
    get_settings.cache_clear()

    with (
        patch.object(paho_mqtt.Client, "tls_set") as mock_tls_set,
        patch.object(paho_mqtt.Client, "tls_insecure_set") as mock_insecure,
    ):
        svc.init_mqtt_client()
        mock_tls_set.assert_called_once_with(ca_certs="/mosquitto/certs/ca.crt")
        mock_insecure.assert_not_called()
    get_settings.cache_clear()

