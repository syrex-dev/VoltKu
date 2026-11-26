"""Layanan pengiriman email transaksional (reset kata sandi) via SMTP standar."""

import html
import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

from app.config import get_settings

logger = logging.getLogger(__name__)


def is_smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_host.strip())


def build_reset_password_url(raw_token: str) -> str:
    settings = get_settings()
    base = (settings.app_public_url or "https://voltku.synemax.web.id").strip().rstrip("/")
    query = urlencode({"reset_token": raw_token})
    return f"{base}/?{query}"


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

    reset_url = build_reset_password_url(raw_token)
    from_email = (settings.smtp_from_email or settings.smtp_user or "noreply@voltku.id").strip()
    from_name = (settings.smtp_from_name or settings.app_name or "VoltKu").strip()
    safe_name = html.escape(user_name or "Pengguna")
    safe_url = html.escape(reset_url)
    app_label = html.escape(settings.app_name or "VoltKu")

    msg = EmailMessage()
    msg["Subject"] = f"Atur Ulang Kata Sandi {settings.app_name or 'VoltKu'}"
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email

    plain_body = (
        f"Halo {user_name or 'Pengguna'},\n\n"
        f"Kami menerima permintaan untuk mengatur ulang kata sandi akun {settings.app_name} Anda.\n"
        f"Silakan buka tautan berikut dalam {expires_minutes} menit ke depan:\n\n"
        f"{reset_url}\n\n"
        "Jika Anda tidak pernah meminta reset kata sandi, abaikan email ini.\n"
    )
    html_body = f"""<!doctype html>
<html lang="id">
  <body style="margin:0;padding:24px;background:#f4f6f9;font-family:Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0"
      style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:14px;
      border:1px solid #e6e9ef;padding:28px;color:#181c20;">
      <tr>
        <td>
          <h2 style="margin:0 0 8px;font-size:20px;color:#0b1b3a;">
            Atur Ulang Kata Sandi {app_label}
          </h2>
          <p style="margin:0 0 16px;font-size:14px;line-height:1.55;color:#525b66;">
            Halo <strong>{safe_name}</strong>, kami menerima permintaan untuk mengatur ulang
            kata sandi akun Anda. Klik tombol di bawah ini untuk membuat kata sandi baru:
          </p>
          <p style="margin:22px 0;">
            <a href="{safe_url}"
              style="display:inline-block;padding:12px 22px;background:#1677ff;color:#ffffff;
              text-decoration:none;font-weight:700;font-size:14px;border-radius:10px;">
              Reset Kata Sandi
            </a>
          </p>
          <p style="margin:0 0 10px;font-size:12.5px;line-height:1.5;color:#7d8694;">
            Tautan ini berlaku selama <strong>{expires_minutes} menit</strong> dan hanya dapat
            dipakai satu kali. Jika tombol tidak bisa diklik, salin tautan ini ke browser Anda:
          </p>
          <p style="margin:0 0 16px;font-size:12px;word-break:break-all;color:#1677ff;">
            {safe_url}
          </p>
          <hr style="border:none;border-top:1px solid #e6e9ef;margin:18px 0;" />
          <p style="margin:0;font-size:12px;color:#7d8694;">
            Jika Anda tidak meminta pengaturan ulang kata sandi, abaikan saja email ini.
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

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
