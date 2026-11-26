"""Pengujian end-to-end Push Notification & Inbox Android ala WhatsApp."""

import os
import time

import pytest
from app.auth import hash_password
from app.db import SessionLocal
from app.main import app
from app.models import Device, PushToken, Reading, UpgradeRequest, User
from app.services.alert import evaluate_device_alerts
from app.services.push_notifier import (
    create_and_dispatch_user_notification,
    set_custom_fcm_sender,
)
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_fcm_stub():
    set_custom_fcm_sender(None)
    yield
    set_custom_fcm_sender(None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _create_user_and_token(client: TestClient, email: str, name: str) -> tuple[int, str]:
    with SessionLocal() as db:
        u = User(
            email=email,
            name=name,
            password_hash=hash_password("Rahasia123"),
            auth_provider="local",
            plan_tier="free",
            is_active=1,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        uid = u.id

    resp = client.post("/api/users/login", json={"email": email, "password": "Rahasia123"})
    assert resp.status_code == 200
    return uid, resp.json()["token"]


def _get_admin_token(client: TestClient) -> str:
    pwd = os.environ.get("DASHBOARD_PASSWORD", "test_password_12chars")
    resp = client.post("/api/admin/login", json={"password": pwd})
    assert resp.status_code == 200
    return resp.json()["token"]


def test_notification_endpoints_require_auth(client: TestClient):
    res_post = client.post("/api/users/push-token", json={"token": "abcdef1234567890"})
    assert res_post.status_code == 401
    assert client.delete("/api/users/push-token?token=abcdef1234567890").status_code == 401
    assert client.get("/api/users/notifications").status_code == 401
    assert client.post("/api/users/notifications/read").status_code == 401


def test_register_upsert_and_delete_push_token(client: TestClient):
    _uid_a, tok_a = _create_user_and_token(client, "usera@voltku.id", "User A")
    uid_b, tok_b = _create_user_and_token(client, "userb@voltku.id", "User B")

    # Tolak token pendek atau platform tidak dikenal
    bad = client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={"token": "short", "platform": "android"},
    )
    assert bad.status_code == 422

    bad_plat = client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={"token": "fcm_token_device_1234567890", "platform": "symbian"},
    )
    assert bad_plat.status_code == 422

    # Registrasi milik User A
    reg = client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={
            "token": "fcm_token_device_1234567890",
            "platform": "android",
            "device_label": "Pixel 8",
        },
    )
    assert reg.status_code == 200
    assert reg.json()["status"] == "registered"

    # Login akun baru User B pada perangkat fisik sama memindahkan kepemilikan token
    reg_b = client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok_b}"},
        json={"token": "fcm_token_device_1234567890", "platform": "android"},
    )
    assert reg_b.status_code == 200
    assert reg_b.json()["status"] == "updated"

    with SessionLocal() as db:
        row = db.query(PushToken).filter_by(token="fcm_token_device_1234567890").one()
        assert row.user_id == uid_b
        assert row.is_active == 1

    # User A tidak boleh menonaktifkan token milik User B
    del_a = client.delete(
        "/api/users/push-token?token=fcm_token_device_1234567890",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert del_a.status_code == 200
    assert del_a.json()["deactivated"] is False

    # User B bisa menonaktifkan tokennya sendiri
    del_b = client.delete(
        "/api/users/push-token?token=fcm_token_device_1234567890",
        headers={"Authorization": f"Bearer {tok_b}"},
    )
    assert del_b.status_code == 200
    assert del_b.json()["deactivated"] is True


def test_tenant_isolation_fcm_dispatch_and_mark_read(client: TestClient):
    uid_a, tok_a = _create_user_and_token(client, "alice@voltku.id", "Alice")
    _uid_b, tok_b = _create_user_and_token(client, "bob@voltku.id", "Bob")

    client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={"token": "fcm_alice_phone_99999999", "platform": "android"},
    )
    client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok_b}"},
        json={"token": "fcm_bob_phone_888888888", "platform": "android"},
    )

    sent_fcm: list[dict] = []

    def _stub_fcm(token: str, title: str, body: str, data: dict[str, str]):
        sent_fcm.append({"token": token, "title": title, "body": body, "data": data})
        return True, False

    set_custom_fcm_sender(_stub_fcm)

    with SessionLocal() as db:
        n1 = create_and_dispatch_user_notification(
            db,
            user_id=uid_a,
            device_id="panel-alice-01",
            title="Daya Tinggi!",
            body="Daya rumah melewati 2500 W.",
            category="alert",
            severity="warning",
            event_key="evt-alice-1",
            now_ts=1764000000,
        )
        assert n1 is not None and n1.pushed_fcm == 1
        # event_key idempoten tidak mengirim duplikat
        n1_dup = create_and_dispatch_user_notification(
            db,
            user_id=uid_a,
            device_id="panel-alice-01",
            title="Daya Tinggi!",
            body="Duplikat.",
            event_key="evt-alice-1",
            now_ts=1764000010,
        )
        assert n1_dup is not None and n1_dup.id == n1.id

        create_and_dispatch_user_notification(
            db,
            user_id=uid_a,
            device_id="panel-alice-01",
            title="Tegangan Normal",
            body="Tegangan kembali 220 V.",
            category="recovery",
            severity="success",
            event_key="evt-alice-2",
            now_ts=1764000020,
        )

    assert len(sent_fcm) == 2
    assert all(item["token"] == "fcm_alice_phone_99999999" for item in sent_fcm)

    # Bob tidak melihat notifikasi Alice
    bob_list = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {tok_b}"},
    ).json()
    assert bob_list["items"] == []
    assert bob_list["unread_count"] == 0

    # Alice melihat 2 notifikasi & since_id incremental sync (dipakai WorkManager APK) bekerja
    alice_list = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {tok_a}"},
    ).json()
    assert len(alice_list["items"]) == 2
    assert alice_list["unread_count"] == 2
    first_id = alice_list["items"][1]["id"]

    inc = client.get(
        f"/api/users/notifications?since_id={first_id}",
        headers={"Authorization": f"Bearer {tok_a}"},
    ).json()
    assert len(inc["items"]) == 1
    assert inc["items"][0]["title"] == "Tegangan Normal"

    # Tandai 1 sudah dibaca
    read_one = client.post(
        "/api/users/notifications/read",
        headers={"Authorization": f"Bearer {tok_a}"},
        json={"notification_id": first_id},
    )
    assert read_one.status_code == 200
    assert read_one.json()["updated"] == 1

    # Tandai sisa yang belum dibaca
    read_all = client.post(
        "/api/users/notifications/read",
        headers={"Authorization": f"Bearer {tok_a}"},
    )
    assert read_all.status_code == 200
    assert read_all.json()["updated"] == 1


def test_unregistered_fcm_token_auto_deactivates():
    with SessionLocal() as db:
        u = User(
            email="stale@voltku.id",
            name="Stale",
            password_hash=hash_password("Rahasia123"),
            is_active=1,
        )
        db.add(u)
        db.commit()
        db.refresh(u)

        pt = PushToken(
            user_id=u.id,
            token="fcm_unregistered_stale_token_123",
            platform="android",
            is_active=1,
        )
        db.add(pt)
        db.commit()

        set_custom_fcm_sender(lambda tok, t, b, d: (False, True))
        n = create_and_dispatch_user_notification(
            db,
            user_id=u.id,
            title="Test",
            body="Body",
            event_key="evt-stale-1",
        )
        assert n is not None and n.pushed_fcm == 0
        db.refresh(pt)
        assert pt.is_active == 0


def test_alert_evaluator_dispatches_android_push_even_without_telegram(client: TestClient):
    uid, tok = _create_user_and_token(client, "homeowner@voltku.id", "Owner")
    client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok}"},
        json={"token": "fcm_owner_device_token_12345", "platform": "android"},
    )

    fcm_calls: list[dict] = []

    def _stub_alert_fcm(tok, title, body, data):
        fcm_calls.append({"tok": tok, "title": title, "body": body})
        return True, False

    set_custom_fcm_sender(_stub_alert_fcm)

    now_ts = int(time.time())
    with SessionLocal() as db:
        dev = Device(
            id="voltku-rumah-01",
            name="Panel Utama",
            mcb_watt=2200,
            owner_user_id=uid,
            last_seen_at=now_ts,
            last_data_ts=now_ts,
            status="online",
        )
        db.add(dev)
        for offset in (-60, -45, -30, -15, 0):
            db.add(
                Reading(
                    device_id=dev.id,
                    ts=now_ts + offset,
                    v=220.0,
                    i=12.0,
                    p=2640.0,
                    e_kwh=10.0,
                    delta_kwh=0.01,
                    f=50.0,
                    pf=0.99,
                    rssi=-55,
                    is_gap=0,
                )
            )
        db.commit()

        evaluate_device_alerts(db, dev, now_ts=now_ts, power_limit_w=2200, alert_cooldown_min=30)

    assert len(fcm_calls) == 1
    assert "Daya Melebihi Batas" in fcm_calls[0]["title"]

    notifs = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {tok}"},
    ).json()
    assert notifs["unread_count"] == 1
    assert notifs["items"][0]["device_id"] == "voltku-rumah-01"


def test_admin_upgrade_approve_sends_push_notification(client: TestClient):
    uid, tok = _create_user_and_token(client, "pro@voltku.id", "Calon Pro")
    admin_tok = _get_admin_token(client)
    client.post(
        "/api/users/push-token",
        headers={"Authorization": f"Bearer {tok}"},
        json={"token": "fcm_pro_candidate_token_1234", "platform": "android"},
    )

    fcm_calls: list[dict] = []

    def _stub_pro_fcm(tok, title, body, data):
        fcm_calls.append({"tok": tok, "title": title})
        return True, False

    set_custom_fcm_sender(_stub_pro_fcm)

    with SessionLocal() as db:
        req = UpgradeRequest(
            user_id=uid,
            order_code="VK-TEST-99",
            requested_tier="pro",
            billing_cycle="monthly",
            amount_rp=49000,
            status="verifying",
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        req_id = req.id

    resp = client.patch(
        f"/api/admin/upgrade-requests/{req_id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"action": "approve", "admin_note": "Lunas"},
    )
    assert resp.status_code == 200
    assert len(fcm_calls) == 1
    assert "Aktif" in fcm_calls[0]["title"]

    notifs = client.get(
        "/api/users/notifications",
        headers={"Authorization": f"Bearer {tok}"},
    ).json()
    assert notifs["unread_count"] == 1
    assert notifs["items"][0]["category"] == "billing"
