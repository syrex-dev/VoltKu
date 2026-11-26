"""Layanan pembayaran manual, kode order, & penyimpanan aman bukti transfer / QRIS."""

import base64
import binascii
import os
import secrets
import time
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PaymentMethod, UpgradeRequest

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_PAYMENT_TTL_SECONDS = 30 * 60  # 30 menit
ORDER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ALLOWED_PAYMENT_TYPES = {"qris", "bank", "ewallet"}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def get_storage_root() -> Path:
    custom = (os.environ.get("VOLTKU_STORAGE_DIR") or "").strip()
    root = Path(custom).resolve() if custom else (_PROJECT_ROOT / "storage").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _detect_image_type(raw: bytes) -> Optional[tuple[str, str]]:
    if len(raw) < 12:
        return None
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None


def decode_base64_image(raw_input: str) -> tuple[bytes, str, str]:
    """Decode string base64 / data URL dan validasi magic bytes gambar (JPG/PNG/WEBP)."""
    cleaned = (raw_input or "").strip()
    if not cleaned:
        raise ValueError("File gambar wajib dilampirkan.")

    if cleaned.startswith("data:") and "," in cleaned:
        header, cleaned = cleaned.split(",", 1)
        if ";base64" not in header.lower():
            raise ValueError("Format data URL gambar harus menggunakan base64.")

    try:
        raw_bytes = base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Data gambar tidak valid.") from exc

    if not raw_bytes:
        raise ValueError("File gambar kosong.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Ukuran gambar maksimal 5 MB.")

    detected = _detect_image_type(raw_bytes)
    if not detected:
        raise ValueError("Format gambar harus JPG, PNG, atau WebP.")

    ext, media_type = detected
    return raw_bytes, ext, media_type


def save_private_image(subdir: str, base64_data: str) -> str:
    """Simpan gambar tervalidasi ke direktori privat storage dan kembalikan path relatif."""
    if subdir not in ("qris", "payment_proofs"):
        raise ValueError("Subdirektori penyimpanan tidak diizinkan.")
    raw_bytes, ext, _ = decode_base64_image(base64_data)
    root = get_storage_root()
    target_dir = (root / subdir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{ext}"
    target_path = (target_dir / filename).resolve()
    if not target_path.is_relative_to(root):
        raise ValueError("Path penyimpanan tidak valid.")
    target_path.write_bytes(raw_bytes)
    return f"{subdir}/{filename}"


def resolve_private_image_path(rel_path: Optional[str]) -> Optional[tuple[Path, str]]:
    """Resolve path relatif di storage secara aman dan kembalikan (Path, media_type)."""
    if not rel_path:
        return None
    root = get_storage_root()
    try:
        candidate = (root / rel_path).resolve()
    except Exception:
        return None
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    ext = candidate.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    return candidate, media_type


def delete_private_image(rel_path: Optional[str]) -> None:
    resolved = resolve_private_image_path(rel_path)
    if resolved:
        try:
            resolved[0].unlink(missing_ok=True)
        except OSError:
            pass


def generate_order_code(now_utc: Optional[int] = None) -> str:
    ts = now_utc if now_utc is not None else int(time.time())
    day_part = time.strftime("%y%m%d", time.gmtime(ts))
    rand_part = "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(5))
    return f"VK-{day_part}-{rand_part}"


def serialize_payment_method(pm: PaymentMethod) -> dict[str, Any]:
    has_qris = bool(pm.qris_image_path and resolve_private_image_path(pm.qris_image_path))
    return {
        "id": pm.id,
        "type": pm.type,
        "label": pm.label,
        "account_number": pm.account_number,
        "account_holder": pm.account_holder,
        "instructions": pm.instructions,
        "has_qris_image": has_qris,
        "qris_image_url": f"/api/payment-methods/{pm.id}/qris?v={pm.created_at}"
        if has_qris
        else None,
        "is_active": bool(pm.is_active),
        "sort_order": int(pm.sort_order),
        "created_at": pm.created_at,
    }


def expire_stale_awaiting_requests(
    session: Session, user_id: Optional[int] = None, now_utc: Optional[int] = None
) -> int:
    """Tandai tagihan awaiting_payment yang melewati expires_at sebagai expired."""
    now_ts = now_utc if now_utc is not None else int(time.time())
    stmt = select(UpgradeRequest).where(
        UpgradeRequest.status == "awaiting_payment",
        UpgradeRequest.expires_at.is_not(None),
        UpgradeRequest.expires_at <= now_ts,
    )
    if user_id is not None:
        stmt = stmt.where(UpgradeRequest.user_id == int(user_id))
    stale = session.scalars(stmt).all()
    for item in stale:
        item.status = "expired"
        item.resolved_at = now_ts
    if stale:
        session.flush()
    return len(stale)

