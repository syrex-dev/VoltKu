from datetime import datetime, timezone

from app.mqtt_ingest import validate_telemetry_payload


def test_validation_valid_payload() -> None:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "ts": now_ts,
        "v": 220.5,
        "i": 1.23,
        "p": 271.2,
        "e": 12.345,
        "f": 50.0,
        "pf": 0.98,
        "rssi": -65,
    }
    is_valid, err = validate_telemetry_payload(payload)
    assert is_valid is True
    assert err is None


def test_validation_out_of_range_voltage() -> None:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {"ts": now_ts, "v": 350.0, "i": 1.0, "p": 220.0, "e": 1.0, "f": 50.0, "pf": 1.0}
    is_valid, err = validate_telemetry_payload(payload)
    assert is_valid is False
    assert "Voltage" in str(err)


def test_validation_negative_energy() -> None:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {"ts": now_ts, "v": 220.0, "i": 1.0, "p": 220.0, "e": -5.0, "f": 50.0, "pf": 1.0}
    is_valid, err = validate_telemetry_payload(payload)
    assert is_valid is False
    assert "negative" in str(err)


def test_validation_timestamp_too_old() -> None:
    # 2024-12-31 23:59:59 (ts < 2025-01-01)
    payload = {"ts": 1735689599, "v": 220.0, "i": 1.0, "p": 220.0, "e": 1.0, "f": 50.0, "pf": 1.0}
    is_valid, err = validate_telemetry_payload(payload)
    assert is_valid is False
    assert "2025-01-01" in str(err)


def test_validation_timestamp_in_future() -> None:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    # 6 menit di masa depan (melebihi toleransi 5 menit)
    future_ts = now_ts + 360
    payload = {"ts": future_ts, "v": 220.0, "i": 1.0, "p": 220.0, "e": 1.0, "f": 50.0, "pf": 1.0}
    is_valid, err = validate_telemetry_payload(payload)
    assert is_valid is False
    assert "future" in str(err)
