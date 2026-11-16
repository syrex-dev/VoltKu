import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Tipe handler pengirim pesan notifikasi: Callable[[str], bool]
NotificationSender = Callable[[str], bool]

_current_sender: Optional[NotificationSender] = None


class NullNotifier:
    """Default notifier saat channel notifikasi belum dikonfigurasi / token kosong.

    Selalu mengembalikan False agar state alert dan scheduled reports tidak maju.
    """

    def __call__(self, message: str) -> bool:
        logger.debug("[NULL_NOTIFIER] Notifikasi ditolak karena channel belum aktif: %s", message)
        return False


def null_notifier(message: str) -> bool:
    """Fungsi pembungkus singleton untuk NullNotifier."""
    return NullNotifier()(message)


def create_log_notifier() -> NotificationSender:
    """Notifier perekam eksplisit (NOTIFIER=log) untuk logging internal / demo.

    Mencetak peringatan mencolok saat inisialisasi bahwa notifikasi tidak dikirim ke Telegram.
    """
    logger.warning("==================================================================")
    logger.warning("⚠️  PERINGATAN: Notifier perekam (NOTIFIER=log) aktif!")
    logger.warning("    Notifikasi hanya dicatat ke log, BUKAN ke Telegram asli.")
    logger.warning("==================================================================")

    def _log_sender(message: str) -> bool:
        logger.warning("[RECORDED_ALERT] %s", message)
        return True

    return _log_sender


def set_notification_sender(sender: Optional[NotificationSender]) -> None:
    """Mengatur handler pengiriman notifikasi (misal Telegram bot atau test mock)."""
    global _current_sender
    _current_sender = sender


def setup_notifier(settings=None) -> NotificationSender:
    """Kode pemilihan notifier berdasarkan konfigurasi sistem:
    1. NOTIFIER=log (eksplisit lewat env): LogNotifier + mencetak peringatan saat start.
    2. TELEGRAM_BOT_TOKEN terisi dan bot_enabled=True: TelegramNotifier.
    3. Default (token kosong atau bot dinonaktifkan): NullNotifier (gagal, state tidak maju).
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    notifier_type = (getattr(settings, "notifier", "") or "").lower().strip()
    if notifier_type == "log" or getattr(settings, "recording_notifier", False):
        sender = create_log_notifier()
        set_notification_sender(sender)
        return sender

    if settings.is_bot_active and settings.telegram_bot_token:
        from app.services.bot import send_telegram_broadcast_sync

        set_notification_sender(send_telegram_broadcast_sync)
        return send_telegram_broadcast_sync

    # Default fallback saat token kosong: NullNotifier (gagal, state tidak maju)
    set_notification_sender(null_notifier)
    return null_notifier


def send_alert_notification(message: str) -> bool:
    """Mengirim pesan notifikasi alert ke channel tujuan (Telegram/log).

    Mengembalikan True jika pesan berhasil dikirim ke >= 1 channel, False jika gagal.
    """
    global _current_sender
    if _current_sender is not None:
        try:
            return bool(_current_sender(message))
        except Exception as err:
            logger.error("Failed to send notification via custom sender: %s", err)
            return False

    return null_notifier(message)
