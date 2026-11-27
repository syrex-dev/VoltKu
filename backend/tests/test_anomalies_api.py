import json
import time

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Anomaly, Device, Reading, User
from app.services.anomaly_service import evaluate_all_l2_l3_anomalies
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}


def setup_test_db():
    _, session = open_clean_test_session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return session


def test_get_anomalies_unauthorized():
    setup_test_db()
    resp = client.get("/api/anomalies")
    assert resp.status_code == 401


def test_get_anomalies_empty():
    session = setup_test_db()
    session.query(Anomaly).delete()
    session.commit()

    resp = client.get("/api/anomalies", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_anomalies_default_7_days_and_ordering():
    session = setup_test_db()
    now_ts = int(time.time())

    # Anomali 1: 1 jam lalu (dalam 7 hari)
    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - 3600,
            type="power_limit",
            severity="warning",
            details_json=json.dumps({"p": 2500}),
            message="Daya melebihi batas",
            notified=1,
        )
    )
    # Anomali 2: 2 hari lalu (dalam 7 hari)
    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - 172800,
            type="voltage_low",
            severity="warning",
            details_json=json.dumps({"v": 195}),
            message="Tegangan rendah",
            notified=1,
        )
    )
    # Anomali 3: 10 hari lalu (di luar 7 hari)
    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - (10 * 86400),
            type="offline",
            severity="critical",
            details_json=json.dumps({"last_seen": now_ts - 10 * 86400}),
            message="Perangkat offline",
            notified=1,
        )
    )
    session.commit()

    resp = client.get("/api/anomalies", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Hanya 2 yang dalam 7 hari terakhir
    assert len(data) == 2
    # Terurut terbaru dulu
    assert data[0]["type"] == "power_limit"
    assert data[1]["type"] == "voltage_low"
    assert data[0]["ts"] > data[1]["ts"]
    assert data[0]["details"] == {"p": 2500}
    assert data[0]["notified"] is True

    # Jika 'from' ditentukan 15 hari lalu -> Anomali 3 juga masuk
    from_15d = now_ts - (15 * 86400)
    resp_all = client.get(f"/api/anomalies?from={from_15d}", headers=auth_headers)
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 3


def test_get_anomalies_device_filter():
    session = setup_test_db()
    now_ts = int(time.time())

    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - 100,
            type="power_limit",
            severity="warning",
            details_json=json.dumps({}),
            message="Demo 1 Overload",
            notified=1,
        )
    )
    session.add(
        Anomaly(
            device_id="demo-2",
            ts=now_ts - 50,
            type="voltage_high",
            severity="warning",
            details_json=json.dumps({}),
            message="Demo 2 High Voltage",
            notified=1,
        )
    )
    session.commit()

    # Filter untuk demo-1
    resp1 = client.get("/api/anomalies?device_id=demo-1", headers=auth_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) == 1
    assert data1[0]["device_id"] == "demo-1"

    # Filter untuk demo-2
    resp2 = client.get("/api/anomalies?device_id=demo-2", headers=auth_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 1
    assert data2[0]["device_id"] == "demo-2"


def test_l2_anomaly_runtime_wiring_and_tier_gate():
    """AnomalyEngine L2/L3 berjalan via evaluate_all_l2_l3_anomalies dan dibatasi per tier."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    session = setup_test_db()
    tz_wib = ZoneInfo("Asia/Jakarta")
    now_dt = datetime.now(tz_wib).replace(hour=14, minute=15, second=0, microsecond=0)
    while now_dt.weekday() >= 5:
        now_dt -= timedelta(days=1)
    now_ts = int(now_dt.timestamp())

    free_user = User(
        name="User Free", email="free_anom@voltku.id", password_hash="x", plan_tier="free"
    )
    pro_user = User(
        name="User Pro",
        email="pro_anom@voltku.id",
        password_hash="x",
        plan_tier="pro",
        plan_expires_at=int(time.time()) + 86400,
    )
    session.add_all([free_user, pro_user])
    session.flush()

    session.add_all(
        [
            Device(id="dev-free", name="Panel Free", mcb_watt=2200, owner_user_id=free_user.id),
            Device(id="dev-pro", name="Panel Pro", mcb_watt=2200, owner_user_id=pro_user.id),
        ]
    )

    # Buat 4 hari riwayat jam 14:xx WIB (~150W, >=24 jendela @5m) + 3 jendela spike ~600W
    cur_bucket = (now_ts // 300) * 300
    for dev_id in ("dev-free", "dev-pro"):
        for d_off in (4, 3, 2, 1):
            day_base = cur_bucket - (d_off * 86400) - 900
            for w_idx in range(10):
                w_start = day_base + w_idx * 300
                for s in range(25):
                    session.add(
                        Reading(
                            device_id=dev_id,
                            ts=w_start + s * 10,
                            v=220.0,
                            i=0.7,
                            p=150.0 + (s % 3) * 5.0,
                            e_kwh=10.0,
                            delta_kwh=0.001,
                            f=50.0,
                            pf=0.95,
                            rssi=-60,
                        )
                    )
        # 3 jendela 5 menit berturut-turut dengan lonjakan 600W sebelum now_ts
        for step, w_start in enumerate(
            [cur_bucket - 900, cur_bucket - 600, cur_bucket - 300], start=1
        ):
            for s in range(25):
                session.add(
                    Reading(
                        device_id=dev_id,
                        ts=w_start + s * 10,
                        v=220.0,
                        i=2.7,
                        p=600.0,
                        e_kwh=12.0 + step,
                        delta_kwh=0.005,
                        f=50.0,
                        pf=0.98,
                        rssi=-60,
                    )
                )
    session.commit()

    # Jalankan 3 tick beruntun per akhir masing-masing jendela spike agar persistence=3 terpicu
    cur_bucket = (now_ts // 300) * 300
    evaluate_all_l2_l3_anomalies(session, now_ts=cur_bucket - 590)
    evaluate_all_l2_l3_anomalies(session, now_ts=cur_bucket - 290)
    evaluate_all_l2_l3_anomalies(session, now_ts=cur_bucket + 10)

    pro_anoms = session.query(Anomaly).filter_by(device_id="dev-pro", type="l2_spike").all()
    free_anoms = session.query(Anomaly).filter_by(device_id="dev-free", type="l2_spike").all()
    assert len(pro_anoms) >= 1
    assert len(free_anoms) == 0

    # Uji endpoint GET /api/anomalies untuk user Free (disaring L2/L3) vs Pro (muncul)
    recent_ts = int(time.time())
    session.add(
        Anomaly(
            device_id="dev-free",
            ts=recent_ts - 60,
            type="l2_spike",
            severity="warning",
            details_json="{}",
            message="Spike",
            notified=0,
        )
    )
    session.add(
        Anomaly(
            device_id="dev-free",
            ts=recent_ts - 50,
            type="power_limit",
            severity="warning",
            details_json="{}",
            message="Overload",
            notified=0,
        )
    )
    session.commit()

    free_tok = create_access_token(subject=free_user.email, role="user", user_id=free_user.id)
    res_free = client.get(
        "/api/anomalies", headers={"Authorization": f"Bearer {free_tok}"}
    ).json()
    assert [a["type"] for a in res_free] == ["power_limit"]

    pro_tok = create_access_token(subject=pro_user.email, role="user", user_id=pro_user.id)
    res_pro = client.get(
        "/api/anomalies", headers={"Authorization": f"Bearer {pro_tok}"}
    ).json()
    assert any(a["type"] == "l2_spike" for a in res_pro)
