from datetime import datetime, timezone

from app.models import DailyStat, Device, HourlyStat, Reading
from mysql_test_helper import open_clean_test_session

from scripts.live_demo_stream import build_live_sample, ensure_demo_devices_and_backfill


def test_build_live_sample_monotonic_and_contract_valid():
    ts = int(datetime.now(timezone.utc).timestamp())
    p1, e1 = build_live_sample(ts, prev_p=420.0, curr_e=100.0, interval_sec=10, scale=1.0)
    assert set(p1.keys()) == {"ts", "v", "i", "p", "e", "f", "pf", "rssi", "fw"}
    assert 200.0 < p1["v"] < 240.0
    assert e1 >= 100.0

    p2, e2 = build_live_sample(ts + 10, prev_p=p1["p"], curr_e=e1, interval_sec=10, scale=1.0)
    assert e2 >= e1


def test_ensure_demo_devices_and_backfill_populates_db_and_preserves_custom_name():
    _, session = open_clean_test_session()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Buat perangkat dengan nama kustom dari admin lebih dulu
    custom = Device(
        id="sim-warung",
        name="Warung Bu Ani",
        location="Warung",
        mcb_watt=2200,
        is_public_demo=0,
        status="offline",
    )
    session.add(custom)
    session.commit()

    states = ensure_demo_devices_and_backfill(
        session,
        now_ts=now_ts,
        backfill_hours=2,
        backfill_step_sec=300,
    )
    assert "sim-warung" in states
    assert "sim-rumah" in states

    refreshed = session.get(Device, "sim-warung")
    assert refreshed is not None
    assert refreshed.name == "Warung Bu Ani"
    assert refreshed.is_public_demo == 1
    assert refreshed.status == "online"

    r_cnt = session.query(Reading).filter_by(device_id="sim-rumah").count()
    h_cnt = session.query(HourlyStat).filter_by(device_id="sim-rumah").count()
    d_cnt = session.query(DailyStat).filter_by(device_id="sim-rumah").count()
    assert r_cnt >= 20
    assert h_cnt >= 1
    assert d_cnt >= 1
    session.close()

