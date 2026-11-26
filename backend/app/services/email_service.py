"""Layanan pengiriman email transaksional (reset kata sandi) via SMTP standar."""

import hashlib
import html
import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from urllib.parse import urlencode

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PasswordResetToken

logger = logging.getLogger(__name__)

PASSWORD_RESET_TTL_SECONDS = 30 * 60


def issue_password_reset_token(session: Session, user_id: int) -> str:
    """Membatalkan token reset lama milik user dan membuat token baru sekali pakai (30 menit)."""
    now_utc = int(datetime.now(timezone.utc).timestamp())
    session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == int(user_id),
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now_utc)
    )
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session.add(
        PasswordResetToken(
            user_id=int(user_id),
            token_hash=token_hash,
            expires_at=now_utc + PASSWORD_RESET_TTL_SECONDS,
            created_at=now_utc,
        )
    )
    session.commit()
    return raw_token


def is_smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_host.strip())


def build_reset_password_url(raw_token: str) -> str:
    settings = get_settings()
    base = (settings.app_public_url or "https://voltku.synemax.web.id").strip().rstrip("/")
    query = urlencode({"reset_token": raw_token})
    return f"{base}/?{query}"


def build_password_reset_message(
    *,
    to_email: str,
    user_name: str,
    raw_token: str,
    expires_minutes: int = 30,
) -> EmailMessage:
    """Menyusun objek EmailMessage berstandar RFC 5322 untuk tautan reset kata sandi."""
    settings = get_settings()
    app_label_raw = (settings.app_name or "VoltKu").strip() or "VoltKu"
    reset_url = build_reset_password_url(raw_token)
    from_email = (settings.smtp_from_email or settings.smtp_user or "noreply@voltku.id").strip()
    from_name = (settings.smtp_from_name or app_label_raw).strip()
    sender_domain = (
        from_email.split("@")[-1].strip() if "@" in from_email else "voltku.synemax.web.id"
    )

    safe_name = html.escape(user_name or "Pengguna")
    safe_url = html.escape(reset_url)
    app_label = html.escape(app_label_raw)
    greeting_name = (user_name or "Pengguna").strip()

    msg = EmailMessage()
    msg["Subject"] = f"Atur Ulang Kata Sandi Akun {app_label_raw}"
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    msg["Reply-To"] = from_email
    msg["Date"] = formatdate(usegmt=True)
    msg["Message-ID"] = make_msgid(domain=sender_domain)
    msg["X-Mailer"] = f"{app_label_raw} Auth Mailer"

    plain_body = (
        f"Halo {greeting_name},\n\n"
        f"Kami menerima permintaan pengaturan ulang kata sandi untuk akun {app_label_raw} Anda "
        f"({to_email}).\n\n"
        f"Buka tautan berikut dalam {expires_minutes} menit untuk membuat kata sandi baru:\n"
        f"{reset_url}\n\n"
        f"Jika Anda tidak pernah mengajukan permintaan ini, abaikan pesan ini.\n\n"
        f"Salam,\nTim {app_label_raw}\n"
        f"https://voltku.synemax.web.id\n"
    )
    html_body = f"""<!doctype html>
<html lang="id">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Atur Ulang Kata Sandi {app_label}</title>
  </head>
  <body
    style="margin:0;padding:24px;background:#f4f6f9;font-family:Arial,sans-serif;color:#181c20;"
  >
    <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
      style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:14px;
      border:1px solid #e6e9ef;padding:28px;">
      <tr>
        <td>
          <div style="font-size:13px;font-weight:700;color:#1677ff;margin-bottom:6px;">
            {app_label}
          </div>
          <h2 style="margin:0 0 12px;font-size:20px;line-height:1.3;color:#0b1b3a;">
            Permintaan Atur Ulang Kata Sandi
          </h2>
          <p style="margin:0 0 14px;font-size:14px;line-height:1.6;color:#475569;">
            Halo <strong>{safe_name}</strong>, kami menerima permintaan untuk mengatur ulang
            kata sandi akun <strong>{app_label}</strong> yang terdaftar dengan alamat email ini.
          </p>
          <p style="margin:22px 0;">
            <a href="{safe_url}"
              style="display:inline-block;padding:12px 24px;background:#1677ff;color:#ffffff;
              text-decoration:none;font-weight:700;font-size:14px;border-radius:10px;">
              Buat Kata Sandi Baru
            </a>
          </p>
          <p style="margin:0 0 14px;font-size:13px;line-height:1.55;color:#64748b;">
            Demi keamanan akun Anda, tautan ini hanya berlaku selama
            <strong>{expires_minutes} menit</strong> dan hanya dapat digunakan satu kali.
          </p>
          <hr style="border:none;border-top:1px solid #e6e9ef;margin:18px 0;" />
          <p style="margin:0;font-size:12px;line-height:1.5;color:#94a3b8;">
            Jika Anda tidak merasa meminta pengaturan ulang kata sandi, Anda dapat mengabaikan
            email ini dengan aman. Kata sandi Anda tidak akan berubah sebelum Anda membukanya
            melalui tombol di atas.
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def send_password_reset_email(
    *,
    to_email: str,
    user_name: str,
    raw_token: str,
    expires_minutes: int = 30,
) -> bool:
    """Mengirim email tautan reset kata sandi. Mengembalikan True bila dikirim via SMTP."""
    settings = get_settings()
    host = (settings.smtp_host or "").strip()
    if not host:
        logger.warning(
            "Permintaan reset kata sandi untuk %s tidak terkirim: SMTP_HOST belum diatur.",
            to_email,
        )
        return False

    msg = build_password_reset_message(
        to_email=to_email,
        user_name=user_name,
        raw_token=raw_token,
        expires_minutes=expires_minutes,
    )

    port = int(settings.smtp_port or 587)
    smtp_user = (settings.smtp_user or "").strip()
    smtp_pass = settings.smtp_pass or ""
    ssl_ctx = ssl.create_default_context()

    try:
        if settings.smtp_use_ssl or port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15, context=ssl_ctx) as client:
                if smtp_user and smtp_pass:
                    client.login(smtp_user, smtp_pass)
                client.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as client:
                if settings.smtp_use_tls:
                    client.starttls(context=ssl_ctx)
                if smtp_user and smtp_pass:
                    client.login(smtp_user, smtp_pass)
                client.send_message(msg)
        return True
    except Exception:
        logger.exception(
            "Gagal mengirim email reset kata sandi ke %s via %s:%s", to_email, host, port
        )
        return False
