"""Verifikasi Google ID Token (RS256) menggunakan Google JWKS tanpa dependensi tambahan."""

import json
import threading
import time
import urllib.request
from typing import Any

import jwt

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

_jwks_lock = threading.Lock()
_jwks_cache: dict[str, Any] = {"fetched_at": 0.0, "data": None}
_JWKS_TTL_SECONDS = 3600


class GoogleTokenError(ValueError):
    """Dilempar bila Google ID Token tidak valid atau gagal diverifikasi."""


def _fetch_google_jwks(force_refresh: bool = False) -> dict[str, Any]:
    """Ambil dan cache daftar kunci publik JWKS dari Google."""
    now = time.time()
    with _jwks_lock:
        if (
            not force_refresh
            and _jwks_cache["data"] is not None
            and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS
        ):
            return _jwks_cache["data"]

    req = urllib.request.Request(
        GOOGLE_CERTS_URL,
        headers={"Accept": "application/json", "User-Agent": "VoltKu-Backend/1.0"},
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    with _jwks_lock:
        _jwks_cache["fetched_at"] = now
        _jwks_cache["data"] = data
    return data


def _find_signing_key(jwks_data: dict[str, Any], kid: str | None) -> Any:
    key_set = jwt.PyJWKSet.from_dict(jwks_data)
    if kid:
        for k in key_set.keys:
            if k.key_id == kid:
                return k.key
    return None


def verify_google_id_token(id_token: str, allowed_client_ids: list[str]) -> dict[str, Any]:
    """Verifikasi Google ID Token terhadap signature JWKS, audience, issuer, dan expiry."""
    if not id_token or len(id_token.strip()) < 20:
        raise GoogleTokenError("Token Google tidak valid.")
    if not allowed_client_ids:
        raise GoogleTokenError("Google Sign-In belum dikonfigurasi pada server.")

    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as err:
        raise GoogleTokenError("Header token Google tidak valid.") from err

    kid = unverified_header.get("kid")
    try:
        jwks_data = _fetch_google_jwks(force_refresh=False)
        signing_key = _find_signing_key(jwks_data, kid)
        if signing_key is None:
            jwks_data = _fetch_google_jwks(force_refresh=True)
            signing_key = _find_signing_key(jwks_data, kid)
    except Exception as err:
        raise GoogleTokenError("Gagal memverifikasi kunci publik Google.") from err

    if signing_key is None:
        raise GoogleTokenError("Kunci penandatanganan Google tidak ditemukan.")

    try:
        payload = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            audience=allowed_client_ids,
        )
    except jwt.PyJWTError as err:
        raise GoogleTokenError("Sesi token Google tidak valid atau kedaluwarsa.") from err

    if payload.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleTokenError("Issuer token Google tidak sah.")

    if not payload.get("email_verified"):
        raise GoogleTokenError("Email akun Google belum terverifikasi.")

    email = str(payload.get("email") or "").strip().lower()
    sub = str(payload.get("sub") or "").strip()
    if not email or not sub:
        raise GoogleTokenError("Profil email Google tidak lengkap.")

    return {
        "sub": sub,
        "email": email,
        "name": str(payload.get("name") or email.split("@")[0]).strip()[:128],
        "avatar_url": str(payload.get("picture") or "").strip()[:512] or None,
    }

