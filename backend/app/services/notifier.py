import inspect
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Tipe handler pengirim pesan notifikasi: Callable[[str], bool]
NotificationSender = Callable[..., bool]

_current_sender: Optional[NotificationSender] = None


class NullNotifier:
    """Default notifier saat channel notifikasi belum dikonfigurasi / token kosong.

    Selalu mengembalikan False agar state alert dan scheduled reports tidak maju jika dipanggil langsung.
    """

    def __call__(self, message: str, event_key: Optional[str] = None) -> bool:
        return False


def null_notifier(message: str, event_key: Optional[str] = None) -> bool:
    """Fungsi pembungkus singleton untuk NullNotifier."""
    return NullNotifier()(message, event_key=event_key)


def is_channel_configured() -> bool:
    """Memeriksa apakah terdapat kanal notifikasi yang aktif/terkonfigurasi.

    Mengembalikan False jika sender adalah null_notifier atau NullNotifier
    (karena TELEGRAM_BOT_TOKEN kosong dan NOTIFIER bukan 'log').
    """
    global _current_sender
    if _current_sender is None:
        return False
    if _current_sender is null_notifier:
        return False
    if isinstance(_current_sender, NullNotifier):
        return False
    fn_name = getattr(_current_sender, "__name__", "")
    if fn_name in ("null_notifier", "_null_sender"):
        return False
    return True


def create_log_notifier() -> NotificationSender:
    """Notifier perekam eksplisit (NOTIFIER=log) untuk logging internal / demo.

    Mencetak peringatan mencolok saat inisialisasi bahwa notifikasi tidak dikirim ke Telegram.
    """
    logger.warning("==================================================================")
    logger.warning("⚠️  PERINGATAN: Notifier perekam (NOTIFIER=log) aktif!")
    logger.warning("    Notifikasi hanya dicatat ke log, BUKAN ke Telegram asli.")
    logger.warning("==================================================================")

    def _log_sender(message: str, event_key: Optional[str] = None) -> bool:
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
        logger.info("Notifier aktif: LogNotifier (NOTIFIER=log)")
        return sender

    if settings.is_bot_active and settings.telegram_bot_token:
        from app.services.bot import send_telegram_broadcast_sync

        set_notification_sender(send_telegram_broadcast_sync)
        n_chats = len(settings.allowed_chat_id_list)
        logger.info("Notifier aktif: Telegram (%d chat terdaftar)", n_chats)
        return send_telegram_broadcast_sync

    # Default fallback saat token kosong: NullNotifier (gagal, state tidak maju)
    set_notification_sender(null_notifier)
    logger.info("Notifier aktif: tidak ada kanal terkonfigurasi (mode pencatatan lokal, notified=0)")
    return null_notifier


def send_alert_notification(message: str, event_key: Optional[str] = None) -> bool:
    """Mengirim pesan notifikasi alert ke channel tujuan (Telegram/log).

    Mengembalikan True jika pesan berhasil dikirim ke >= 1 channel, False jika gagal.
    """
    global _current_sender
    if _current_sender is not None:
        try:
            sig = inspect.signature(_current_sender)
            if "event_key" in sig.parameters:
                return bool(_current_sender(message, event_key=event_key))
            return bool(_current_sender(message))
        except Exception as err:
            logger.error("Failed to send notification via custom sender: %s", err)
            return False

    return null_notifier(message, event_key=event_key)
