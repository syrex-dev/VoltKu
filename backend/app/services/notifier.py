import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Tipe handler pengirim pesan notifikasi: Callable[[str], bool]
NotificationSender = Callable[[str], bool]

_current_sender: Optional[NotificationSender] = None


def set_notification_sender(sender: Optional[NotificationSender]) -> None:
    """Mengatur handler pengiriman notifikasi (misal Telegram bot atau test mock)."""
    global _current_sender
    _current_sender = sender


def send_alert_notification(message: str) -> bool:
    """Mengirim pesan notifikasi alert ke channel tujuan (Telegram/log).

    Mengembalikan True jika pesan berhasil dikirim, False jika gagal.
    """
    global _current_sender
    if _current_sender is not None:
        try:
            return bool(_current_sender(message))
        except Exception as err:
            logger.error("Failed to send notification via custom sender: %s", err)
            return False

    # Default fallback jika belum ada bot token atau handler: log pesan dan anggap sukses
    logger.info("[ALERT NOTIFICATION] %s", message)
    return True

