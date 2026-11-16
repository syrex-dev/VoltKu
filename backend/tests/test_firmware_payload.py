import json
from pathlib import Path

from app.mqtt_ingest import validate_telemetry_payload


def test_firmware_golden_payload_conforms_to_contract():
    golden_path = Path("firmware/test/golden_payload.json")
    if not golden_path.exists():
        golden_path = (
            Path(__file__).resolve().parent.parent.parent
            / "firmware"
            / "test"
            / "golden_payload.json"
        )

    assert golden_path.exists(), f"Golden payload file not found: {golden_path}"

    with open(golden_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    data = json.loads(content)

    # 1. Validasi via fungsi backend validate_telemetry_payload
    is_valid, err_msg = validate_telemetry_payload(data)
    assert is_valid is True, f"Validasi gagal: {err_msg}"

    # 2. Periksa kesesuaian nilai persis sesuai kontrak
    assert data["ts"] == 1736000000
    assert data["v"] == 220.5
    assert data["i"] == 1.234
    assert data["p"] == 272.1
    assert data["e"] == 12.345
    assert data["f"] == 50.0
    assert data["pf"] == 0.98
    assert data["rssi"] == -61
    assert data["fw"] == "1.0.0"
