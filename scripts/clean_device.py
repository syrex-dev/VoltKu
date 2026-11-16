import argparse
import os
import sys

# Tambahkan direktori root dan backend ke path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import AlertState, Anomaly, DailyStat, Device, HourlyStat, Reading  # noqa: E402
from sqlalchemy import delete  # noqa: E402


def check_clean_safety(device_id: str) -> None:
    """Memeriksa apakah device_id aman untuk dibersihkan (hanya sim- atau demo-)."""
    if not (device_id.startswith("sim-") or device_id.startswith("demo-")):
        raise ValueError(
            f"ERROR: Penolakan perlindungan data! Perangkat '{device_id}' "
            f"bukan perangkat simulasi/demo ('sim-' atau 'demo-').\n"
            f"Operasi pembersihan dibatalkan untuk mencegah kehilangan data produksi."
        )


def clean_device(device_id: str, session: SessionLocal = None) -> dict[str, int]:
    # Penjagaan ketat: hanya perbolehkan awalan 'sim-' atau 'demo-'
    check_clean_safety(device_id)

    def _execute(sess):
        dev = sess.get(Device, device_id)
        n_readings = sess.execute(
            delete(Reading).where(Reading.device_id == device_id)
        ).rowcount
        n_hourly = sess.execute(
            delete(HourlyStat).where(HourlyStat.device_id == device_id)
        ).rowcount
        n_daily = sess.execute(
            delete(DailyStat).where(DailyStat.device_id == device_id)
        ).rowcount
        n_alerts = sess.execute(
            delete(AlertState).where(AlertState.device_id == device_id)
        ).rowcount
        n_anomalies = sess.execute(
            delete(Anomaly).where(Anomaly.device_id == device_id)
        ).rowcount

        if dev:
            sess.delete(dev)

        sess.commit()
        return {
            "readings": n_readings,
            "hourly": n_hourly,
            "daily": n_daily,
            "alerts": n_alerts,
            "anomalies": n_anomalies,
            "device_deleted": 1 if dev else 0,
        }

    if session is not None:
        return _execute(session)
    else:
        init_db()
        with SessionLocal() as sess:
            res = _execute(sess)
            print(f"=== Pembersihan Perangkat Berhasil: {device_id} ===")
            print(f"- Readings dihapus: {res['readings']}")
            print(f"- Hourly stats dihapus: {res['hourly']}")
            print(f"- Daily stats dihapus: {res['daily']}")
            print(f"- Alert states dihapus: {res['alerts']}")
            print(f"- Anomalies dihapus: {res['anomalies']}")
            print(f"- Device record dihapus: {'Ya' if res['device_deleted'] else 'Tidak ada'}")
            return res


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Skrip aman untuk membersihkan perangkat demo/simulasi dan data terkait."
    )
    parser.add_argument(
        "--device",
        required=True,
        help="ID perangkat yang akan dibersihkan (wajib berawalan 'sim-' atau 'demo-')",
    )
    args = parser.parse_args()
    clean_device(args.device)


if __name__ == "__main__":
    main()
