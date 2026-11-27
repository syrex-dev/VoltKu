"""Default dan validator konten dinamis aplikasi (Tarif PLN, Rilis APK, Panduan, AI Prompts)."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

DEFAULT_AI_QUICK_PROMPTS: list[str] = [
    "Berapa biaya listrik hari ini?",
    "Jam berapa paling boros?",
    "Berapa proyeksi tagihan bulan ini?",
    "Apakah ada anomali minggu ini?",
]

VALID_TARIFF_CATEGORIES = ("rumah", "bisnis", "sosial", "lainnya")

DEFAULT_PLN_TARIFFS: list[dict[str, str]] = [
    {
        "id": "r1-450",
        "category": "rumah",
        "group": "Rumah Tangga",
        "label": "R-1/TR · 450 VA (Subsidi)",
        "tariff_rp": "415.00",
    },
    {
        "id": "r1-900-sub",
        "category": "rumah",
        "group": "Rumah Tangga",
        "label": "R-1/TR · 900 VA (Subsidi)",
        "tariff_rp": "605.00",
    },
    {
        "id": "r1-900-rtm",
        "category": "rumah",
        "group": "Rumah Tangga",
        "label": "R-1/TR · 900 VA (RTM)",
        "tariff_rp": "1352.00",
    },
    {
        "id": "r1-1300",
        "category": "rumah",
        "group": "Rumah Tangga",
        "label": "R-1/TR · 1.300 VA",
        "tariff_rp": "1444.70",
    },
    {
        "id": "r1-2200",
        "category": "rumah",
        "group": "Rumah Tangga",
        "label": "R-1/TR · 2.200 VA",
        "tariff_rp": "1444.70",
    },
    {
        "id": "r2-3500",
        "category": "rumah",
        "group": "Rumah Tangga",
        "label": "R-2/TR · 3.500–5.500 VA",
        "tariff_rp": "1699.53",
    },
    {
        "id": "r3-6600",
        "category": "rumah",
        "group": "Rumah Tangga",
        "label": "R-3/TR · ≥ 6.600 VA",
        "tariff_rp": "1699.53",
    },
    {
        "id": "b1-450",
        "category": "bisnis",
        "group": "Bisnis",
        "label": "B-1/TR · 450 VA",
        "tariff_rp": "254.00",
    },
    {
        "id": "b1-900",
        "category": "bisnis",
        "group": "Bisnis",
        "label": "B-1/TR · 451–900 VA",
        "tariff_rp": "420.00",
    },
    {
        "id": "b1-1300",
        "category": "bisnis",
        "group": "Bisnis",
        "label": "B-1/TR · 901–1.300 VA",
        "tariff_rp": "966.00",
    },
    {
        "id": "b1-2200",
        "category": "bisnis",
        "group": "Bisnis",
        "label": "B-1/TR · 1.301–5.500 VA",
        "tariff_rp": "1100.00",
    },
    {
        "id": "b2-6600",
        "category": "bisnis",
        "group": "Bisnis",
        "label": "B-2/TR · 6.600 VA–200 kVA",
        "tariff_rp": "1444.70",
    },
    {
        "id": "b3-tm",
        "category": "bisnis",
        "group": "Bisnis",
        "label": "B-3/TM · > 200 kVA",
        "tariff_rp": "1114.74",
    },
    {
        "id": "s1-450",
        "category": "sosial",
        "group": "Sosial",
        "label": "S-1/TR · 450 VA",
        "tariff_rp": "325.00",
    },
    {
        "id": "s1-900",
        "category": "sosial",
        "group": "Sosial",
        "label": "S-1/TR · 900 VA",
        "tariff_rp": "455.00",
    },
    {
        "id": "s1-1300",
        "category": "sosial",
        "group": "Sosial",
        "label": "S-1/TR · 1.300 VA",
        "tariff_rp": "708.00",
    },
    {
        "id": "s1-2200",
        "category": "sosial",
        "group": "Sosial",
        "label": "S-1/TR · 2.200 VA",
        "tariff_rp": "760.00",
    },
    {
        "id": "s1-3500",
        "category": "sosial",
        "group": "Sosial",
        "label": "S-1/TR · 3.500 VA–200 kVA",
        "tariff_rp": "900.00",
    },
    {
        "id": "s2-tm",
        "category": "sosial",
        "group": "Sosial",
        "label": "S-2/TM · > 200 kVA",
        "tariff_rp": "925.00",
    },
    {
        "id": "p1-tr",
        "category": "lainnya",
        "group": "Pemerintah & Industri",
        "label": "P-1/TR · Kantor Pem 6.600 VA–200 kVA",
        "tariff_rp": "1699.53",
    },
    {
        "id": "p2-tm",
        "category": "lainnya",
        "group": "Pemerintah & Industri",
        "label": "P-2/TM · Kantor Pem > 200 kVA",
        "tariff_rp": "1522.88",
    },
    {
        "id": "p3-tr",
        "category": "lainnya",
        "group": "Pemerintah & Industri",
        "label": "P-3/TR · Penerangan Jalan Umum",
        "tariff_rp": "1699.53",
    },
    {
        "id": "i3-tm",
        "category": "lainnya",
        "group": "Pemerintah & Industri",
        "label": "I-3/TM · Industri > 200 kVA",
        "tariff_rp": "1114.74",
    },
    {
        "id": "i4-tt",
        "category": "lainnya",
        "group": "Pemerintah & Industri",
        "label": "I-4/TT · Industri ≥ 30.000 kVA",
        "tariff_rp": "996.74",
    },
]

DEFAULT_APP_RELEASE: dict[str, Any] = {
    "version": "v2.5.0",
    "apk_download_url": "https://github.com/syrex-dev/VoltKu/releases/download/voltku-apk/VoltKu.apk",
    "release_notes": "Pembaruan aplikasi VoltKu Android & Web siap diunduh.",
    "changelog": [
        {
            "version": "v2.5.0",
            "date": "27 Nov 2026",
            "badge": "Terbaru",
            "items": [
                "Kontrol admin lengkap: gambar maskot, masukan/bug, broadcast & Telegram.",
                "Keamanan PIN 6 Digit + Biometrik tersinkron lintas perangkat.",
                (
                    "Pemilih Bahasa (Indonesia & English), Zona Waktu (WIB/WITA/WIT) "
                    "& target anggaran."
                ),
            ],
        },
        {
            "version": "v2.4.2",
            "date": "26 Nov 2026",
            "badge": "Stabilitas",
            "items": [
                "Banner panduan instalasi Wi-Fi 2.4 GHz & pairing PZEM-004T.",
                "Alur upgrade paket bertahap lengkap dengan pembayaran QRIS/Bank/E-Wallet.",
            ],
        },
    ],
}

DEFAULT_USAGE_GUIDE: dict[str, Any] = {
    "pairing_intro_title": "Persiapan Sebelum Pasang",
    "pairing_intro_desc": (
        "Pastikan ponsel terhubung ke Wi-Fi 2.4 GHz (bukan 5 GHz) dan siapkan "
        "stiker QR Code pada unit VoltKu."
    ),
    "usage_intro_title": "Kenali Menu & Fitur dalam 1 Menit",
    "usage_intro_desc": (
        "Setelah panel aktif, pantau watt secara langsung, cek grafik rupiah, "
        "hingga tanya analisa hemat listrik ke Asisten AI."
    ),
    "pairing_steps": [
        {
            "step": 1,
            "text": (
                "Colokkan panel VoltKu ke listrik, lalu tekan & tahan tombol Pairing selama "
                "5 detik hingga lampu biru berkedip cepat."
            ),
        },
        {
            "step": 2,
            "text": "Buka tab Beranda, lalu ketuk + Tambah Panel atau + Tambah Sekarang.",
        },
        {
            "step": 3,
            "text": (
                "Pilih Belum, Hubungkan ke Wi-Fi Dulu untuk unit baru, atau langsung Sudah "
                "Terhubung bila alat sudah online."
            ),
        },
        {
            "step": 4,
            "text": (
                "Hubungkan Wi-Fi HP ke hotspot VoltKu-XXXX, masukkan nama & kata sandi Wi-Fi "
                "2.4 GHz rumah, lalu tekan Simpan & Lanjut."
            ),
        },
        {
            "step": 5,
            "text": (
                "Kembalikan HP ke internet biasa, lalu Scan QR Code di stiker bodi alat dan "
                "atur nama ruangan serta kapasitas MCB."
            ),
        },
    ],
    "usage_cards": [
        {
            "title": "1. Pantau Beban Live & Grafik",
            "desc": (
                "Ketuk kartu panel di Beranda untuk membuka tab Live (daya Watt, V, A, PF) "
                "dan tab Konsumsi untuk grafik harian serta jam paling boros."
            ),
        },
        {
            "title": "2. Tarif PLN, Zona Waktu & Rekap Harian",
            "desc": (
                "Buka tab Tarif & Daya atau ketuk Atur Alat di panel untuk memilih golongan "
                "PLN (R-1/R-2/Bisnis), batas aman Watt, zona WIB/WITA/WIT, dan jam rekap."
            ),
        },
        {
            "title": "3. Bedakan Peringatan Alat vs Notifikasi Akun",
            "desc": (
                "Menu Peringatan menampilkan anomali listrik (tegangan, overload, offline). "
                "Ikon Lonceng kanan atas berisi kotak masuk akun & info admin."
            ),
        },
        {
            "title": "4. Asisten AI Tanya VoltKu",
            "desc": (
                "Ketuk tombol Tanya VoltKu di pojok kanan bawah untuk menanyakan biaya hari "
                "ini, jam tersibuk, proyeksi tagihan, atau ringkasan gangguan."
            ),
        },
        {
            "title": "5. Kunci PIN 6 Digit Tersinkron Lintas Perangkat",
            "desc": (
                "Buka Profil → Keamanan Aplikasi untuk menyalakan PIN 6 digit yang aktif "
                "otomatis di Web maupun APK Android."
            ),
        },
    ],
}

_TARIFF_ID_RE = re.compile(r"[^a-z0-9_-]+")
_GROUP_DEFAULT_LABELS = {
    "rumah": "Rumah Tangga",
    "bisnis": "Bisnis",
    "sosial": "Sosial",
    "lainnya": "Pemerintah & Industri",
}


def validate_ai_quick_prompts(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError("Daftar pertanyaan cepat AI harus berupa array teks.")
    cleaned: list[str] = []
    for item in raw[:8]:
        text = str(item or "").strip()
        if not text:
            continue
        if len(text) > 120:
            raise ValueError("Setiap pertanyaan cepat AI maksimal 120 karakter.")
        if text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        raise ValueError("Minimal sertakan 1 pertanyaan cepat untuk Asisten AI.")
    return cleaned


def parse_ai_quick_prompts(raw_json: str) -> list[str]:
    if not raw_json or not raw_json.strip():
        return list(DEFAULT_AI_QUICK_PROMPTS)
    try:
        parsed = json.loads(raw_json)
        return validate_ai_quick_prompts(parsed)
    except Exception:
        return list(DEFAULT_AI_QUICK_PROMPTS)


def validate_pln_tariffs(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise ValueError("Daftar tarif PLN harus berupa list objek.")
    if len(raw) == 0 or len(raw) > 60:
        raise ValueError("Daftar tarif PLN harus berisi 1 hingga 60 preset.")

    used_ids: set[str] = set()
    cleaned: list[dict[str, str]] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"Format preset tarif #{idx + 1} tidak valid.")
        cat = str(entry.get("category") or "rumah").strip().lower()
        if cat not in VALID_TARIFF_CATEGORIES:
            cat = "lainnya"
        label = str(entry.get("label") or "").strip()
        if not label or len(label) > 80:
            raise ValueError(f"Label preset tarif #{idx + 1} wajib diisi (maks 80 karakter).")
        group = str(entry.get("group") or _GROUP_DEFAULT_LABELS.get(cat, "Lainnya")).strip()[:48]
        raw_val = (
            entry.get("tariff_rp")
            if entry.get("tariff_rp") is not None
            else entry.get("tariffRp")
        )
        raw_rate = str(raw_val or "").strip().replace(",", ".")
        try:
            num_rate = float(raw_rate)
            if num_rate <= 0 or num_rate > 100000:
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"Tarif Rp/kWh preset '{label}' harus angka > 0.") from exc

        base_id = _TARIFF_ID_RE.sub("-", str(entry.get("id") or label).lower()).strip("-")[:36]
        if not base_id:
            base_id = f"tarif-{idx + 1}"
        cand_id = base_id
        suffix = 2
        while cand_id in used_ids:
            cand_id = f"{base_id[:30]}-{suffix}"
            suffix += 1
        used_ids.add(cand_id)

        cleaned.append(
            {
                "id": cand_id,
                "category": cat,
                "group": group or _GROUP_DEFAULT_LABELS[cat],
                "label": label,
                "tariff_rp": f"{num_rate:.2f}",
            }
        )
    return cleaned


def parse_pln_tariffs(raw_json: str) -> list[dict[str, str]]:
    if not raw_json or not raw_json.strip():
        return copy.deepcopy(DEFAULT_PLN_TARIFFS)
    try:
        parsed = json.loads(raw_json)
        return validate_pln_tariffs(parsed)
    except Exception:
        return copy.deepcopy(DEFAULT_PLN_TARIFFS)


def validate_app_release(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Format info rilis aplikasi tidak valid.")
    version = str(raw.get("version") or "").strip()[:32]
    if not version:
        raise ValueError("Nomor versi aplikasi wajib diisi (misal v2.5.0).")
    apk_url = str(raw.get("apk_download_url") or "").strip()
    if apk_url and not re.match(r"^https?://", apk_url, re.IGNORECASE):
        raise ValueError("URL unduhan APK harus diawali http:// atau https://.")
    if len(apk_url) > 512:
        raise ValueError("URL unduhan APK maksimal 512 karakter.")
    notes = str(raw.get("release_notes") or "").strip()[:300]

    raw_changelog = raw.get("changelog")
    cleaned_log: list[dict[str, Any]] = []
    if isinstance(raw_changelog, list):
        for rel in raw_changelog[:15]:
            if not isinstance(rel, dict):
                continue
            r_ver = str(rel.get("version") or "").strip()[:32]
            if not r_ver:
                continue
            r_date = str(rel.get("date") or "").strip()[:32]
            r_badge = str(rel.get("badge") or "Rilis").strip()[:24]
            r_items = [
                str(x or "").strip()[:240]
                for x in (rel.get("items") or [])
                if str(x or "").strip()
            ][:10]
            cleaned_log.append(
                {
                    "version": r_ver,
                    "date": r_date,
                    "badge": r_badge,
                    "items": r_items,
                }
            )
    if not cleaned_log:
        cleaned_log = copy.deepcopy(DEFAULT_APP_RELEASE["changelog"])

    return {
        "version": version,
        "apk_download_url": apk_url,
        "release_notes": notes,
        "changelog": cleaned_log,
    }


def parse_app_release(raw_json: str) -> dict[str, Any]:
    if not raw_json or not raw_json.strip():
        return copy.deepcopy(DEFAULT_APP_RELEASE)
    try:
        parsed = json.loads(raw_json)
        return validate_app_release(parsed)
    except Exception:
        return copy.deepcopy(DEFAULT_APP_RELEASE)


def validate_usage_guide(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Format panduan cara pemakaian tidak valid.")

    def _clean_text(key: str, fallback: str, max_len: int = 360) -> str:
        val = str(raw.get(key) if raw.get(key) is not None else fallback).strip()
        return (val or fallback)[:max_len]

    raw_steps = raw.get("pairing_steps")
    pairing_steps: list[dict[str, Any]] = []
    if isinstance(raw_steps, list) and raw_steps:
        for idx, s in enumerate(raw_steps[:8]):
            txt = (
                str(s.get("text") if isinstance(s, dict) else s or "").strip()[:320]
            )
            if txt:
                pairing_steps.append({"step": idx + 1, "text": txt})
    if not pairing_steps:
        pairing_steps = copy.deepcopy(DEFAULT_USAGE_GUIDE["pairing_steps"])

    raw_cards = raw.get("usage_cards")
    usage_cards: list[dict[str, str]] = []
    if isinstance(raw_cards, list) and raw_cards:
        for c in raw_cards[:8]:
            if not isinstance(c, dict):
                continue
            title = str(c.get("title") or "").strip()[:100]
            desc = str(c.get("desc") or "").strip()[:360]
            if title and desc:
                usage_cards.append({"title": title, "desc": desc})
    if not usage_cards:
        usage_cards = copy.deepcopy(DEFAULT_USAGE_GUIDE["usage_cards"])

    return {
        "pairing_intro_title": _clean_text(
            "pairing_intro_title", DEFAULT_USAGE_GUIDE["pairing_intro_title"], 100
        ),
        "pairing_intro_desc": _clean_text(
            "pairing_intro_desc", DEFAULT_USAGE_GUIDE["pairing_intro_desc"], 300
        ),
        "usage_intro_title": _clean_text(
            "usage_intro_title", DEFAULT_USAGE_GUIDE["usage_intro_title"], 100
        ),
        "usage_intro_desc": _clean_text(
            "usage_intro_desc", DEFAULT_USAGE_GUIDE["usage_intro_desc"], 300
        ),
        "pairing_steps": pairing_steps,
        "usage_cards": usage_cards,
    }


def parse_usage_guide(raw_json: str) -> dict[str, Any]:
    if not raw_json or not raw_json.strip():
        return copy.deepcopy(DEFAULT_USAGE_GUIDE)
    try:
        parsed = json.loads(raw_json)
        return validate_usage_guide(parsed)
    except Exception:
        return copy.deepcopy(DEFAULT_USAGE_GUIDE)
