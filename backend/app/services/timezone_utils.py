from typing import Optional
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE_ID = "Asia/Jakarta"

SUPPORTED_TIMEZONES: dict[str, dict[str, str]] = {
    "Asia/Jakarta": {
        "short": "WIB",
        "label": "Waktu Indonesia Barat (WIB)",
        "offset": "UTC+07:00",
    },
    "Asia/Makassar": {
        "short": "WITA",
        "label": "Waktu Indonesia Tengah (WITA)",
        "offset": "UTC+08:00",
    },
    "Asia/Jayapura": {
        "short": "WIT",
        "label": "Waktu Indonesia Timur (WIT)",
        "offset": "UTC+09:00",
    },
    "Asia/Singapore": {
        "short": "SGT",
        "label": "Singapore / Malaysia Standard Time",
        "offset": "UTC+08:00",
    },
    "UTC": {
        "short": "UTC",
        "label": "Coordinated Universal Time",
        "offset": "UTC+00:00",
    },
}


def is_supported_timezone(tz_name: Optional[str]) -> bool:
    """Memeriksa apakah nama zona waktu IANA termasuk zona yang didukung."""
    return (tz_name or "").strip() in SUPPORTED_TIMEZONES


def normalize_timezone_name(tz_name: Optional[str]) -> str:
    """Mengembalikan nama zona waktu valid atau fallback ke Asia/Jakarta."""
    clean = (tz_name or "").strip()
    return clean if clean in SUPPORTED_TIMEZONES else DEFAULT_TIMEZONE_ID


def resolve_zoneinfo(tz_name: Optional[str]) -> ZoneInfo:
    """Mengembalikan instance ZoneInfo yang aman untuk nama zona waktu."""
    return ZoneInfo(normalize_timezone_name(tz_name))


def get_timezone_short_label(tz_name: Optional[str]) -> str:
    """Mengembalikan singkatan zona waktu seperti WIB, WITA, WIT, atau UTC."""
    return SUPPORTED_TIMEZONES[normalize_timezone_name(tz_name)]["short"]

