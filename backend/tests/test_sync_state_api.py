from app.auth import create_access_token, hash_password
from app.db import get_db
from app.models import PaymentMethod, User
from app.services.plans import ensure_default_plans_seeded
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app_main := __import__("app.main", fromlist=["app"]).app)


def _setup_sync_test_db():
    _, session = open_clean_test_session()
    ensure_default_plans_seeded(session)
    user = User(
        email="buyer@voltku.test",
        name="Budi Pembeli",
        password_hash=hash_password("Rahasia123!"),
        plan_tier="free",
        is_active=1,
    )
    pm = PaymentMethod(
        type="bank",
        label="BCA Virtual",
        account_number="1234567890",
        account_holder="VoltKu Billing",
        is_active=1,
        sort_order=1,
    )
    session.add_all([user, pm])
    session.commit()
    session.refresh(user)
    session.refresh(pm)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app_main.dependency_overrides[get_db] = override_get_db
    admin_headers = {"Authorization": f"Bearer {create_access_token()}"}
    user_token = create_access_token(subject=user.email, role="user", user_id=user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}
    return session, user, pm, admin_headers, user_headers


def test_sync_state_updates_across_public_user_and_admin_checkout_flow(monkeypatch, tmp_path):
    monkeypatch.setenv("VOLTKU_STORAGE_DIR", str(tmp_path))
    _, user, pm, admin_headers, user_headers = _setup_sync_test_db()
    try:
        # 1. Initial states
        pub_0 = client.get("/api/public/sync-state")
        assert pub_0.status_code == 200
        pub_data_0 = pub_0.json()

        adm_0 = client.get("/api/admin/sync-state", headers=admin_headers)
        assert adm_0.status_code == 200
        adm_data_0 = adm_0.json()
        assert adm_data_0["counts"]["awaiting"] == 0
        assert adm_data_0["counts"]["verifying"] == 0

        usr_0 = client.get("/api/users/sync-state", headers=user_headers)
        assert usr_0.status_code == 200
        usr_data_0 = usr_0.json()
        assert usr_data_0["latest_upgrade"] is None

        # Unauthenticated /api/users/sync-state & non-admin /api/admin/sync-state rejected
        assert client.get("/api/users/sync-state").status_code == 401
        assert client.get("/api/admin/sync-state", headers=user_headers).status_code == 403

        # 2. Customer creates upgrade request -> Admin awaiting count & rev update immediately
        order_res = client.post(
            "/api/users/upgrade-request",
            json={
                "plan_slug": "pro",
                "billing_cycle": "monthly",
                "payment_method_id": pm.id,
            },
            headers=user_headers,
        )
        assert order_res.status_code == 201
        order_id = order_res.json()["id"]

        adm_1 = client.get("/api/admin/sync-state", headers=admin_headers).json()
        assert adm_1["rev"] != adm_data_0["rev"]
        assert adm_1["upgrades_rev"] != adm_data_0["upgrades_rev"]
        assert adm_1["counts"]["awaiting"] == 1
        assert adm_1["latest_awaiting"]["id"] == order_id
        assert adm_1["latest_awaiting"]["user_name"] == user.name

        usr_1 = client.get("/api/users/sync-state", headers=user_headers).json()
        assert usr_1["user_rev"] != usr_data_0["user_rev"]
        assert usr_1["latest_upgrade"]["status"] == "awaiting_payment"

        # 3. Customer uploads proof -> Admin verifying count & latest_verifying update immediately
        # Minimal valid 1x1 PNG base64
        tiny_png_b64 = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
            "/x8AAwMCAO+aN1sAAAAASUVORK5CYII="
        )
        proof_res = client.post(
            f"/api/users/upgrade-requests/{order_id}/confirm-payment",
            json={"proof_base64": f"data:image/png;base64,{tiny_png_b64}"},
            headers=user_headers,
        )
        assert proof_res.status_code == 200

        adm_2 = client.get("/api/admin/sync-state", headers=admin_headers).json()
        assert adm_2["upgrades_rev"] != adm_1["upgrades_rev"]
        assert adm_2["counts"]["awaiting"] == 0
        assert adm_2["counts"]["verifying"] == 1
        assert adm_2["counts"]["needs_action"] == 1
        assert adm_2["latest_verifying"]["id"] == order_id

        # 4. Admin approves -> Customer user_rev, inbox unread_notifications & latest_upgrade update
        approve_res = client.patch(
            f"/api/admin/upgrade-requests/{order_id}",
            json={"action": "approve"},
            headers=admin_headers,
        )
        assert approve_res.status_code == 200

        adm_3 = client.get("/api/admin/sync-state", headers=admin_headers).json()
        assert adm_3["counts"]["verifying"] == 0
        assert adm_3["users_rev"] != adm_2["users_rev"]

        usr_2 = client.get("/api/users/sync-state", headers=user_headers).json()
        assert usr_2["user_rev"] != usr_1["user_rev"]
        assert usr_2["unread_notifications"] >= 1
        assert usr_2["latest_upgrade"]["status"] == "approved"

        # 5. Admin edits public config / access -> Public rev & Customer public_rev update
        acc_res = client.patch(
            "/api/admin/access",
            json={"public_read_enabled": False},
            headers=admin_headers,
        )
        assert acc_res.status_code == 200

        pub_1 = client.get("/api/public/sync-state").json()
        assert pub_1["rev"] != pub_data_0["rev"]
        assert pub_1["public_read_enabled"] is False

        usr_3 = client.get("/api/users/sync-state", headers=user_headers).json()
        assert usr_3["public_rev"] != usr_2["public_rev"]
        assert usr_3["public_read_enabled"] is False
    finally:
        app_main.dependency_overrides.clear()
