import copy
import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AppConfig, Setting, TermsConsent, User
from app.routers.settings import (
    apply_settings_updates,
    format_settings_response,
    get_all_settings,
)
from app.services.plans import (
    build_public_plans_payload,
    get_freemium_config,
    sync_legacy_app_config_to_default_plans,
)

PUBLIC_ACCESS_KEY = "public_dashboard_enabled"

HERO_BANNER_TONES = (
    "is-teal-guide",
    "is-cobalt",
    "is-gold-dark",
    "is-emerald",
    "is-cyan",
    "is-indigo",
    "is-announcement",
)
HERO_BANNER_ICONS = (
    "book-open",
    "assistant",
    "crown",
    "qr-code",
    "sliders",
    "bell-ring",
    "megaphone",
    "zap",
    "sparkles",
    "external-link",
)
HERO_BANNER_ACTIONS = (
    "usage_guide",
    "ai_chat",
    "upgrade_plan",
    "add_device",
    "open_settings",
    "open_alerts",
    "open_url",
    "none",
)
HERO_BANNER_AUDIENCES = (
    "all",
    "free_only",
    "pro_only",
    "authenticated_only",
    "guest_only",
)
_BANNER_ID_RE = re.compile(r"[^a-z0-9_-]+")
MAX_HERO_BANNERS = 12

DEFAULT_HERO_BANNERS: list[dict[str, Any]] = [
    {
        "id": "usage-guide",
        "badge": "CARA PEMAKAIAN",
        "title": "Panduan Pasang & Pakai VoltKu",
        "subtitle": "Langkah mudah konek Wi-Fi 2.4 GHz, scan QR & pantau tagihan PLN",
        "cta": "Lihat Panduan",
        "tone": "is-teal-guide",
        "icon": "book-open",
        "action_type": "usage_guide",
        "action_url": "",
        "audience": "all",
        "enabled": True,
    },
    {
        "id": "ai-assistant",
        "badge": "ANALISA TAGIHAN",
        "title": "Cek Jam Boros & Estimasi Biaya",
        "subtitle": "Tanya ringkasan kWh harian & proyeksi bulan ini berbasis data meteran",
        "cta": "Buka Asisten",
        "tone": "is-cobalt",
        "icon": "assistant",
        "action_type": "ai_chat",
        "action_url": "",
        "audience": "all",
        "enabled": True,
    },
    {
        "id": "pro-active",
        "badge": "VOLTKU PRO AKTIF",
        "title": "Proteksi & Riwayat Panjang Aktif",
        "subtitle": "Pantau catatan anomali & tegangan panel secara real-time",
        "cta": "Cek Peringatan",
        "tone": "is-emerald",
        "icon": "bell-ring",
        "action_type": "open_alerts",
        "action_url": "",
        "audience": "pro_only",
        "enabled": True,
    },
    {
        "id": "upgrade-pro",
        "badge": "VOLTKU PRO",
        "title": "Pantau Banyak Panel dengan VoltKu Pro",
        "subtitle": "Riwayat lebih panjang, ekspor CSV, dan dukungan multi-panel",
        "cta": "Lihat Paket",
        "tone": "is-gold-dark",
        "icon": "crown",
        "action_type": "upgrade_plan",
        "action_url": "",
        "audience": "free_only",
        "enabled": True,
    },
    {
        "id": "quick-pairing",
        "badge": "PASANG MUDAH",
        "title": "Tautkan Panel Dalam 1 Menit",
        "subtitle": "Scan barcode stiker bodi alat atau ikuti panduan Wi-Fi 2.4 GHz",
        "cta": "Tambah Panel",
        "tone": "is-cyan",
        "icon": "qr-code",
        "action_type": "add_device",
        "action_url": "",
        "audience": "all",
        "enabled": True,
    },
    {
        "id": "tariff-pln",
        "badge": "TARIF PLN",
        "title": "Sesuaikan Tarif & Batas Daya MCB",
        "subtitle": "Hitung estimasi tagihan Rp sesuai golongan R-1 hingga Bisnis",
        "cta": "Atur Tarif",
        "tone": "is-indigo",
        "icon": "sliders",
        "action_type": "open_settings",
        "action_url": "",
        "audience": "all",
        "enabled": True,
    },
]

DEFAULT_TERMS_CONTENT = (
    "1. Ruang Lingkup Layanan\n"
    "VoltKu menyediakan layanan pemantauan parameter kelistrikan (tegangan, arus, daya aktif, "
    "energi kWh, faktor daya), perkiraan tagihan listrik, serta deteksi dini anomali kelistrikan "
    "berbasis sensor IoT. Aplikasi ini bersifat pemantauan dan diagnostik (read-only), serta "
    "tidak mengendalikan atau memutus sakelar beban AC jarak jauh secara sepihak.\n\n"
    "2. Akun Pengguna & Kepemilikan Perangkat\n"
    "Anda bertanggung jawab menjaga kerahasiaan kata sandi, sesi masuk, dan kepemilikan ID "
    "perangkat yang diklaim pada akun Anda. Mode Guest tanpa login hanya menampilkan unit demo "
    "publik secara terbatas sesuai kebijakan pengelola.\n\n"
    "3. Akurasi Pengukuran & Estimasi Biaya\n"
    "Angka biaya rupiah dan proyeksi tagihan bulanan dihitung secara matematis berdasarkan "
    "pembacaan sensor lokal serta tarif dasar/biaya tambahan yang Anda atau pengelola tetapkan. "
    "Hasil estimasi berfungsi sebagai alat bantu pemantauan dan dapat berbeda tipis dengan "
    "tagihan resmi penyedia listrik setempat akibat selisih kalibrasi atau komponen non-kWh.\n\n"
    "4. Kepatuhan Persetujuan & Pembaharuan\n"
    "Dengan menekan tombol Setuju atau membuat akun, Anda menyetujui pencatatan bukti persetujuan "
    "(waktu persetujuan, versi dokumen, serta metadata perangkat/klien dasar) sebagai catatan "
    "kepatuhan penggunaan aplikasi. Apabila pengelola memperbarui versi ketentuan ini, Anda akan "
    "diminta menyetujui pembaruan tersebut.\n\n"
    "5. Keselamatan Instalasi\n"
    "Pemasangan fisik perangkat ukur maupun panel kelistrikan wajib mematuhi standar keselamatan "
    "listrik setempat dan dilakukan oleh tenaga yang kompeten."
)

DEFAULT_PRIVACY_CONTENT = (
    "1. Data yang Kami Kumpulkan\n"
    "Saat Anda mendaftar atau masuk (termasuk melalui Akun Google), VoltKu menyimpan nama, "
    "alamat email terverifikasi, foto profil opsional, pengenal penyedia autentikasi, ID panel "
    "listrik milik Anda, serta preferensi tarif/batas daya akun.\n\n"
    "2. Data Telemetri & Audit Persetujuan\n"
    "Sistem menyimpan data telemetri kelistrikan dari perangkat milik Anda, konfigurasi "
    "operasional, serta log persetujuan Syarat & Ketentuan dan Kebijakan Privasi (versi "
    "ketentuan, penanda waktu UTC, pengenal sesi klien/aplikasi, serta alamat IP dan agen "
    "perangkat standar untuk kebutuhan audit keamanan).\n\n"
    "3. Keamanan Penyimpanan Lokal & Kredensial\n"
    "Kredensial Wi-Fi sensor ESP32 disimpan secara lokal pada memori perangkat keras Anda dan "
    "tidak dikirim ke pihak ketiga. Sesi otorisasi pengguna dilindungi token terenkripsi dan tidak "
    "memuat kata sandi mentah.\n\n"
    "4. Isolasi Data & Larangan Penjualan Data\n"
    "Setiap perangkat tenant terisolasi ketat berdasarkan kepemilikan akun kecuali bila unit "
    "ditetapkan secara eksplisit oleh pengelola sebagai Demo Publik. Kami tidak menjual, "
    "menyewakan, atau membagikan data pribadi maupun histori pemakaian Anda kepada pihak ketiga "
    "untuk iklan atau pemasaran.\n\n"
    "5. Kontrol Penghapusan & Dukungan\n"
    "Anda dapat menghapus perangkat dari akun kapan saja atau menghubungi pengelola aplikasi "
    "melalui kanal dukungan resmi untuk penonaktifan akun maupun permintaan penghapusan data."
)

DEFAULT_APP_CONFIG: dict[str, str] = {
    "app_name": "VoltKu",
    "app_tagline": "Pantau listrik rumah lebih tenang dan akurat",
    "navbar_brand_display": "logo_only",
    "announcement_active": "false",
    "announcement_text": "",
    "announcement_url": "",
    "hero_banners_json": "",
    "default_theme": "light",
    "onboarding_enabled": "true",
    "onboarding_step1_title": "Kenali Panel Listrik Anda",
    "onboarding_step1_desc": (
        "Lihat status setiap panel listrik secara ringkas di Beranda. Ketuk Tambah Panel "
        "kapan saja untuk menyambungkan sensor baru atau mengklaim unit milik Anda."
    ),
    "onboarding_step2_title": "Pantau Beban & Estimasi Tagihan",
    "onboarding_step2_desc": (
        "Pilih salah satu kartu panel untuk memantau daya real-time (Watt), tren grafik "
        "harian, perkiraan tagihan PLN, dan catatan anomali."
    ),
    "onboarding_step3_title": "Kelola Profil & Preferensi Tarif",
    "onboarding_step3_desc": (
        "Ketuk ikon profil di pojok kanan atas untuk masuk ke akun Anda, lalu sesuaikan "
        "tarif dasar PLN dan batas aman daya pada menu Tarif & Daya."
    ),
    "registration_enabled": "true",
    "google_auth_enabled": "true",
    "google_client_id": "",
    "google_android_client_id": "",
    "require_terms_consent": "true",
    "terms_version": "",
    "privacy_version": "2026-11-v1",
    "legal_updated_at": "25 November 2026",
    "terms_title": "Syarat & Ketentuan Layanan",
    "terms_content": DEFAULT_TERMS_CONTENT,
    "privacy_title": "Kebijakan Privasi",
    "privacy_content": DEFAULT_PRIVACY_CONTENT,
    "support_whatsapp": "",
    "support_telegram": "",
    "support_email": "",
    "freemium_enabled": "true",
    "free_plan_name": "VoltKu Gratis",
    "free_max_devices": "1",
    "free_history_days": "3",
    "free_forecast_enabled": "false",
    "free_export_enabled": "false",
    "pro_plan_name": "VoltKu Pro",
    "pro_monthly_price_rp": "30000",
    "pro_yearly_price_rp": "300000",
    "pro_max_devices": "10",
    "pro_history_days": "90",
    "upgrade_instructions": (
        "Ajukan upgrade dari aplikasi lalu konfirmasi pembayaran via WhatsApp / QRIS "
        "ke pengelola untuk aktivasi paket VoltKu Pro."
    ),
}

_BOOL_CONFIG_KEYS = {
    "announcement_active",
    "onboarding_enabled",
    "registration_enabled",
    "google_auth_enabled",
    "require_terms_consent",
    "freemium_enabled",
    "free_forecast_enabled",
    "free_export_enabled",
}


def _to_bool(val: str, default: bool = False) -> bool:
    if not val:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _normalize_banner_id(raw_id: Any, fallback_idx: int, used: set[str]) -> str:
    cleaned = _BANNER_ID_RE.sub("-", str(raw_id or "").strip().lower()).strip("-")[:48]
    if not cleaned:
        cleaned = f"banner-{fallback_idx + 1}"
    candidate = cleaned
    suffix = 2
    while candidate in used:
        base = cleaned[:40]
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _sanitize_banner_item(
    raw: Any,
    idx: int,
    used_ids: set[str],
    *,
    strict: bool,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Format banner ke-{idx + 1} tidak valid")

    title = str(raw.get("title") or "").strip()
    if strict and not title:
        raise ValueError(f"Judul hero banner ke-{idx + 1} wajib diisi")
    if len(title) > 120:
        if strict:
            raise ValueError(f"Judul hero banner ke-{idx + 1} maksimal 120 karakter")
        title = title[:120]

    badge = str(raw.get("badge") or "").strip()[:40]
    subtitle = str(raw.get("subtitle") or "").strip()[:200]
    cta = str(raw.get("cta") or "").strip()[:32] or "Lihat"

    tone = str(raw.get("tone") or "is-cobalt").strip()
    if tone not in HERO_BANNER_TONES:
        if strict:
            raise ValueError(f"Tema warna banner '{tone}' tidak dikenal")
        tone = "is-cobalt"

    icon = str(raw.get("icon") or "zap").strip()
    if icon not in HERO_BANNER_ICONS:
        if strict:
            raise ValueError(f"Ikon banner '{icon}' tidak dikenal")
        icon = "zap"

    action_type = str(raw.get("action_type") or "none").strip()
    if action_type not in HERO_BANNER_ACTIONS:
        if strict:
            raise ValueError(f"Jenis aksi banner '{action_type}' tidak dikenal")
        action_type = "none"

    action_url = str(raw.get("action_url") or "").strip()[:500]
    if action_type == "open_url":
        if not action_url.startswith(("https://", "http://")):
            raise ValueError(
                f"URL tautan banner ke-{idx + 1} wajib diawali http:// atau https://"
            )
    elif action_url and not action_url.startswith(("https://", "http://")):
        action_url = ""

    audience = str(raw.get("audience") or "all").strip()
    if audience not in HERO_BANNER_AUDIENCES:
        if strict:
            raise ValueError(f"Target audiens banner '{audience}' tidak dikenal")
        audience = "all"

    return {
        "id": _normalize_banner_id(raw.get("id"), idx, used_ids),
        "badge": badge,
        "title": title or "Info VoltKu",
        "subtitle": subtitle,
        "cta": cta,
        "tone": tone,
        "icon": icon,
        "action_type": action_type,
        "action_url": action_url,
        "audience": audience,
        "enabled": bool(raw.get("enabled", True)),
    }


def parse_hero_banners(raw_json: str) -> list[dict[str, Any]]:
    """Parse daftar hero banner dari DB; kembalikan default bila belum pernah diatur."""
    if not raw_json or not raw_json.strip():
        return copy.deepcopy(DEFAULT_HERO_BANNERS)
    try:
        parsed = json.loads(raw_json)
    except (ValueError, TypeError):
        return copy.deepcopy(DEFAULT_HERO_BANNERS)
    if not isinstance(parsed, list):
        return copy.deepcopy(DEFAULT_HERO_BANNERS)

    used_ids: set[str] = set()
    items: list[dict[str, Any]] = []
    for idx, entry in enumerate(parsed[:MAX_HERO_BANNERS]):
        try:
            items.append(_sanitize_banner_item(entry, idx, used_ids, strict=False))
        except ValueError:
            continue
    return items


def validate_hero_banners(raw_list: Any) -> list[dict[str, Any]]:
    """Validasi daftar hero banner yang dikirim dari Panel Admin sebelum disimpan."""
    if not isinstance(raw_list, list):
        raise ValueError("Format daftar hero banner harus berupa array")
    if len(raw_list) > MAX_HERO_BANNERS:
        raise ValueError(f"Maksimal {MAX_HERO_BANNERS} slide hero banner")

    used_ids: set[str] = set()
    return [
        _sanitize_banner_item(entry, idx, used_ids, strict=True)
        for idx, entry in enumerate(raw_list)
    ]


def get_app_config_map(session: Session) -> dict[str, str]:
    """Gabungkan nilai default aplikasi dengan override di tabel app_config."""
    merged = dict(DEFAULT_APP_CONFIG)
    rows = session.scalars(select(AppConfig)).all()
    for row in rows:
        if row.key in merged:
            merged[row.key] = row.value
    return merged


def upsert_app_config(session: Session, key: str, value: str) -> None:
    now_utc = int(time.time())
    existing = session.scalar(select(AppConfig).where(AppConfig.key == key))
    if existing:
        existing.value = value
        existing.updated_at = now_utc
    else:
        session.add(AppConfig(key=key, value=value, updated_at=now_utc))


def is_public_read_enabled(session: Session) -> bool:
    row = session.scalar(select(Setting).where(Setting.key == PUBLIC_ACCESS_KEY))
    if row is not None:
        return row.value.strip().lower() in ("true", "1", "yes", "on")
    return bool(get_settings().public_dashboard_enabled)


def is_registration_enabled(session: Session) -> bool:
    cfg_map = get_app_config_map(session)
    return _to_bool(cfg_map["registration_enabled"], True)


def get_active_terms_version(session: Session, cfg_map: Optional[dict[str, str]] = None) -> str:
    data = cfg_map if cfg_map is not None else get_app_config_map(session)
    db_ver = (data.get("terms_version") or "").strip()
    if db_ver:
        return db_ver
    return (get_settings().terms_version or "2026-11-v1").strip()


def get_effective_google_oauth(
    session: Session, cfg_map: Optional[dict[str, str]] = None
) -> dict[str, Any]:
    """Ambil Google OAuth config dengan prioritas override Admin DB lalu .env fallback."""
    data = cfg_map if cfg_map is not None else get_app_config_map(session)
    env_cfg = get_settings()

    google_auth_enabled = _to_bool(data.get("google_auth_enabled", "true"), True)
    db_web_cid = (data.get("google_client_id") or "").strip()
    db_android_cid = (data.get("google_android_client_id") or "").strip()

    env_web_cid = (env_cfg.google_client_id or "").strip()
    env_android_cid = (env_cfg.google_android_client_id or "").strip()

    effective_web_cid = db_web_cid or env_web_cid or None
    effective_android_cid = db_android_cid or env_android_cid or None

    allowed_ids: list[str] = []
    for raw in (effective_web_cid, effective_android_cid):
        if raw and raw not in allowed_ids:
            allowed_ids.append(raw)

    return {
        "google_auth_enabled": google_auth_enabled,
        "google_enabled": bool(google_auth_enabled and allowed_ids),
        "google_client_id": effective_web_cid,
        "google_android_client_id": effective_android_cid,
        "allowed_client_ids": allowed_ids,
        "has_env_web_cid": bool(env_web_cid),
        "has_env_android_cid": bool(env_android_cid),
        "env_web_cid": env_web_cid,
        "env_android_cid": env_android_cid,
    }


def _build_public_config_payload(session: Session, data: dict[str, str]) -> dict[str, Any]:
    oauth = get_effective_google_oauth(session, data)
    terms_ver = get_active_terms_version(session, data)
    return {
        "app_name": data["app_name"] or "VoltKu",
        "app_tagline": data["app_tagline"],
        "navbar_brand_display": data["navbar_brand_display"] or "logo_only",
        "announcement_active": _to_bool(data["announcement_active"], False),
        "announcement_text": data["announcement_text"],
        "announcement_url": data["announcement_url"],
        "default_theme": data["default_theme"] or "light",
        "onboarding_enabled": _to_bool(data["onboarding_enabled"], True),
        "onboarding_steps": [
            {
                "id": "home-panels",
                "title": data["onboarding_step1_title"],
                "description": data["onboarding_step1_desc"],
            },
            {
                "id": "monitor-usage",
                "title": data["onboarding_step2_title"],
                "description": data["onboarding_step2_desc"],
            },
            {
                "id": "profile-tariff",
                "title": data["onboarding_step3_title"],
                "description": data["onboarding_step3_desc"],
            },
        ],
        "public_read_enabled": is_public_read_enabled(session),
        "registration_enabled": _to_bool(data["registration_enabled"], True),
        "google_enabled": oauth["google_enabled"],
        "google_auth_enabled": oauth["google_auth_enabled"],
        "google_client_id": oauth["google_client_id"] if oauth["google_auth_enabled"] else None,
        "google_android_client_id": (
            oauth["google_android_client_id"] if oauth["google_auth_enabled"] else None
        ),
        "require_terms_consent": _to_bool(data["require_terms_consent"], True),
        "terms_version": terms_ver,
        "privacy_version": data["privacy_version"] or terms_ver,
        "legal_updated_at": data["legal_updated_at"],
        "terms_title": data["terms_title"],
        "terms_content": data["terms_content"],
        "privacy_title": data["privacy_title"],
        "privacy_content": data["privacy_content"],
        "support_whatsapp": data["support_whatsapp"],
        "support_telegram": data["support_telegram"],
        "support_email": data["support_email"],
        "hero_banners": parse_hero_banners(data.get("hero_banners_json", "")),
        "plans": build_public_plans_payload(data, session=session),
    }


def get_public_app_config(session: Session) -> dict[str, Any]:
    data = get_app_config_map(session)
    return _build_public_config_payload(session, data)


def get_admin_app_settings(session: Session) -> dict[str, Any]:
    data = get_app_config_map(session)
    oauth = get_effective_google_oauth(session, data)
    sys_settings = format_settings_response(get_all_settings(session))
    terms_ver = get_active_terms_version(session, data)

    return {
        "app_name": data["app_name"],
        "app_tagline": data["app_tagline"],
        "navbar_brand_display": data["navbar_brand_display"],
        "announcement_active": _to_bool(data["announcement_active"], False),
        "announcement_text": data["announcement_text"],
        "announcement_url": data["announcement_url"],
        "default_theme": data["default_theme"],
        "onboarding_enabled": _to_bool(data["onboarding_enabled"], True),
        "onboarding_step1_title": data["onboarding_step1_title"],
        "onboarding_step1_desc": data["onboarding_step1_desc"],
        "onboarding_step2_title": data["onboarding_step2_title"],
        "onboarding_step2_desc": data["onboarding_step2_desc"],
        "onboarding_step3_title": data["onboarding_step3_title"],
        "onboarding_step3_desc": data["onboarding_step3_desc"],
        "public_read_enabled": is_public_read_enabled(session),
        "registration_enabled": _to_bool(data["registration_enabled"], True),
        "google_auth_enabled": oauth["google_auth_enabled"],
        "google_client_id": data["google_client_id"],
        "google_android_client_id": data["google_android_client_id"],
        "effective_google_client_id": oauth["google_client_id"] or "",
        "effective_google_android_client_id": oauth["google_android_client_id"] or "",
        "google_enabled": oauth["google_enabled"],
        "require_terms_consent": _to_bool(data["require_terms_consent"], True),
        "terms_version": terms_ver,
        "privacy_version": data["privacy_version"] or terms_ver,
        "legal_updated_at": data["legal_updated_at"],
        "terms_title": data["terms_title"],
        "terms_content": data["terms_content"],
        "privacy_title": data["privacy_title"],
        "privacy_content": data["privacy_content"],
        "support_whatsapp": data["support_whatsapp"],
        "support_telegram": data["support_telegram"],
        "support_email": data["support_email"],
        "tariff_rp": sys_settings["tariff_rp"],
        "power_limit_w": sys_settings["power_limit_w"],
        "alert_cooldown_min": sys_settings["alert_cooldown_min"],
        "extra_percent": sys_settings["extra_percent"],
        "report_hour": sys_settings["report_hour"],
        "report_timezone": sys_settings["report_timezone"],
        "report_enabled": sys_settings["report_enabled"],
        "hero_banners": parse_hero_banners(data.get("hero_banners_json", "")),
        "default_hero_banners": copy.deepcopy(DEFAULT_HERO_BANNERS),
        **get_freemium_config(data),
    }


def _validate_and_store_config_field(session: Session, key: str, value: Any) -> None:
    if value is None:
        return
    if key in _BOOL_CONFIG_KEYS:
        upsert_app_config(session, key, "true" if bool(value) else "false")
        return

    text_val = str(value).strip()
    if key == "navbar_brand_display" and text_val not in ("logo_only", "logo_text", "text_only"):
        raise ValueError("Format brand navbar tidak valid")
    if key == "default_theme" and text_val not in ("light", "dark", "system"):
        raise ValueError("Tema bawaan harus light, dark, atau system")
    if key == "app_name":
        if not text_val or len(text_val) > 64:
            raise ValueError("Nama aplikasi harus antara 1 hingga 64 karakter")
    if key in ("terms_version", "privacy_version") and len(text_val) > 32:
        raise ValueError("Versi dokumen maksimal 32 karakter")
    if key == "terms_title" and (not text_val or len(text_val) > 128):
        raise ValueError("Judul Syarat & Ketentuan harus antara 1 hingga 128 karakter")
    if key == "privacy_title" and (not text_val or len(text_val) > 128):
        raise ValueError("Judul Kebijakan Privasi harus antara 1 hingga 128 karakter")
    if key in ("terms_content", "privacy_content") and not text_val:
        raise ValueError("Isi dokumen legal tidak boleh kosong")
    if key == "free_max_devices":
        if not text_val.isdigit() or not (1 <= int(text_val) <= 100):
            raise ValueError("Batas panel paket Gratis harus antara 1 hingga 100")
    if key == "free_history_days":
        if not text_val.isdigit() or not (1 <= int(text_val) <= 366):
            raise ValueError("Riwayat hari paket Gratis harus antara 1 hingga 366 hari")
    if key == "pro_max_devices":
        try:
            v = int(text_val)
            if v < -1 or v > 10000:
                raise ValueError
        except ValueError as exc:
            raise ValueError("Batas panel paket Pro harus -1 (tak terbatas) hingga 10000") from exc
    if key == "pro_history_days":
        if not text_val.isdigit() or not (1 <= int(text_val) <= 366):
            raise ValueError("Riwayat hari paket Pro harus antara 1 hingga 366 hari")
    if key in ("pro_monthly_price_rp", "pro_yearly_price_rp"):
        if not text_val.isdigit() or int(text_val) < 0:
            raise ValueError("Harga paket Pro harus angka Rupiah bulat >= 0")

    upsert_app_config(session, key, text_val)


def update_admin_app_settings(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Validasi & simpan pembaruan pengaturan aplikasi serta default operasional dari Admin."""
    for key in DEFAULT_APP_CONFIG:
        if key == "hero_banners_json":
            continue
        if key in payload and payload[key] is not None:
            _validate_and_store_config_field(session, key, payload[key])

    if "hero_banners" in payload and payload["hero_banners"] is not None:
        cleaned_banners = validate_hero_banners(payload["hero_banners"])
        upsert_app_config(
            session,
            "hero_banners_json",
            json.dumps(cleaned_banners, ensure_ascii=False),
        )

    legacy_plan_keys = {
        "free_plan_name",
        "free_max_devices",
        "free_history_days",
        "free_forecast_enabled",
        "free_export_enabled",
        "pro_plan_name",
        "pro_monthly_price_rp",
        "pro_yearly_price_rp",
        "pro_max_devices",
        "pro_history_days",
    }
    if any(k in payload and payload[k] is not None for k in legacy_plan_keys):
        sync_legacy_app_config_to_default_plans(session, get_app_config_map(session))

    if payload.get("public_read_enabled") is not None:
        val_str = "true" if bool(payload["public_read_enabled"]) else "false"
        row = session.scalar(select(Setting).where(Setting.key == PUBLIC_ACCESS_KEY))
        if not row:
            session.add(Setting(key=PUBLIC_ACCESS_KEY, value=val_str))
        else:
            row.value = val_str

    op_fields = {
        k: payload[k]
        for k in (
            "tariff_rp",
            "power_limit_w",
            "alert_cooldown_min",
            "extra_percent",
            "report_hour",
            "report_timezone",
            "report_enabled",
        )
        if payload.get(k) is not None
    }
    if op_fields:
        apply_settings_updates(
            session=session,
            tariff_rp=op_fields.get("tariff_rp"),
            power_limit_w=op_fields.get("power_limit_w"),
            alert_cooldown_min=op_fields.get("alert_cooldown_min"),
            extra_percent=op_fields.get("extra_percent"),
            report_hour=op_fields.get("report_hour"),
            report_timezone=op_fields.get("report_timezone"),
            report_enabled=op_fields.get("report_enabled"),
            user_id=None,
        )

    session.commit()
    return get_admin_app_settings(session)


def extract_client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    from app.auth import get_trusted_client_ip

    return get_trusted_client_ip(request)


def extract_user_agent(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    ua = request.headers.get("user-agent")
    return ua.strip()[:255] if ua else None


def record_terms_consent(
    session: Session,
    *,
    user: Optional[User],
    email_snapshot: Optional[str],
    client_id: Optional[str],
    accepted_via: str,
    accepted_terms_version: Optional[str] = None,
    request: Optional[Request] = None,
) -> TermsConsent:
    """Catat bukti persetujuan Syarat & Ketentuan + Kebijakan Privasi ke database."""
    data = get_app_config_map(session)
    active_terms = get_active_terms_version(session, data)
    terms_ver = (accepted_terms_version or "").strip()[:32] or active_terms
    privacy_ver = (data.get("privacy_version") or terms_ver).strip()[:32]
    now_utc = int(datetime.now(timezone.utc).timestamp())

    if user is not None:
        user.terms_version_accepted = terms_ver
        user.terms_accepted_at = now_utc

    clean_client = client_id.strip()[:128] if client_id and client_id.strip() else None
    entry = TermsConsent(
        user_id=user.id if user is not None else None,
        email_snapshot=(email_snapshot or (user.email if user else None)),
        client_id=clean_client,
        terms_version=terms_ver,
        privacy_version=privacy_ver,
        accepted_via=(accepted_via or "web")[:32],
        ip_address=extract_client_ip(request),
        user_agent=extract_user_agent(request),
        accepted_at=now_utc,
    )
    session.add(entry)
    return entry
