from datetime import datetime, timezone

from app.models import DailyStat, Device, Reading, Setting, User, UserSetting
from app.services.aggregation import get_wib_day, update_daily_stat, update_hourly_stat
from mysql_test_helper import open_clean_test_session


def get_test_session():
    _, session = open_clean_test_session()
    # Seed default settings
    session.add(Setting(key="tariff_sen_per_kwh", value="144470"))
    session.add(Setting(key="extra_percent", value="0.0"))
    session.commit()
    return session


def test_wib_day_boundary():
    # 2026-05-10 16:59:59 UTC -> 2026-05-10 23:59:59 WIB -> day: 2026-05-10
    ts_prev_day = int(datetime(2026, 5, 10, 16, 59, 59, tzinfo=timezone.utc).timestamp())
    assert get_wib_day(ts_prev_day) == "2026-05-10"

    # 2026-05-10 17:00:00 UTC -> 2026-05-11 00:00:00 WIB -> day: 2026-05-11
    ts_next_day = int(datetime(2026, 5, 10, 17, 0, 0, tzinfo=timezone.utc).timestamp())
    assert get_wib_day(ts_next_day) == "2026-05-11"


def test_daily_stat_preserves_past_tariff_on_recalculation():
    session = get_test_session()

    # Buat record hari lampau dengan tarif lama (misal 135200 sen)
    past_day = "2026-01-01"
    stat = DailyStat(
        device_id="esp_1",
        day=past_day,
        kwh=5.0,
        cost_rp=6760,
        tariff_sen=135200,
        p_max=500.0,
    )
    session.add(stat)

    # Tambahkan reading pada hari lampau tersebut
    ts_past = int(datetime(2026, 1, 1, 3, 0, 0, tzinfo=timezone.utc).timestamp())  # 10:00 WIB
    r = Reading(
        device_id="esp_1",
        ts=ts_past,
        v=220,
        i=1,
        p=220,
        e_kwh=5.0,
        delta_kwh=5.0,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r)
    session.commit()

    # Tarif sekarang di settings berubah naik menjadi 170000 sen
    setting = session.get(Setting, "tariff_sen_per_kwh")
    assert setting is not None
    setting.value = "170000"
    session.commit()

    # Jalankan rekalkulasi agregasi hari lampau
    updated_stat = update_daily_stat(session, "esp_1", ts_past)
    session.commit()

    # Tarif pada hari lampau HARUS TETAP 135200 sen (tidak berubah ke 170000)
    assert updated_stat.tariff_sen == 135200
    # Biaya dihitung berdasarkan tarif lampau: 5.0 * 1352 = 6760
    assert updated_stat.cost_rp == 6760


def test_aggregation_idempotency():
    session = get_test_session()
    ts = int(datetime(2026, 3, 15, 6, 0, 0, tzinfo=timezone.utc).timestamp())

    r = Reading(
        device_id="esp_1",
        ts=ts,
        v=220,
        i=1.5,
        p=330.0,
        e_kwh=10.0,
        delta_kwh=0.015,
        f=50,
        pf=1,
        rssi=-60,
    )
    session.add(r)
    session.commit()

    # Jalankan agregasi pertama
    h1 = update_hourly_stat(session, "esp_1", ts)
    d1 = update_daily_stat(session, "esp_1", ts)
    session.commit()

    # Jalankan agregasi kedua
    h2 = update_hourly_stat(session, "esp_1", ts)
    d2 = update_daily_stat(session, "esp_1", ts)
    session.commit()

    assert h1.kwh == h2.kwh == 0.015
    assert h1.samples == h2.samples == 1
    assert d1.kwh == d2.kwh == 0.015
    assert d1.cost_rp == d2.cost_rp


def test_daily_stat_uses_tenant_tariff():
    session = get_test_session()
    ts = int(datetime(2026, 5, 11, 10, 0, 0, tzinfo=timezone.utc).timestamp())

    owner = User(
        name="Tenant Tarif",
        email="tarif@example.com",
        password_hash="!dummy",
        is_active=1,
        created_at=ts,
    )
    session.add(owner)
    session.commit()

    # Tenant mengatur tarif subsidi 450 VA = Rp 415/kWh (41500 sen)
    session.add(UserSetting(user_id=owner.id, key="tariff_sen_per_kwh", value="41500"))
    session.add(Device(id="esp_sub", name="Subsidi", owner_user_id=owner.id, mcb_watt=450))
    session.add(
        Reading(
            device_id="esp_sub",
            ts=ts,
            v=220.0,
            i=1.0,
            p=220.0,
            e_kwh=10.0,
            delta_kwh=2.0,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
    )
    session.commit()

    stat = update_daily_stat(session, "esp_sub", ts)
    session.commit()
    assert stat.tariff_sen == 41500
    assert stat.cost_rp == 830  # 2.0 kWh * Rp 415.00
