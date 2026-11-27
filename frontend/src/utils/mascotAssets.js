import { buildApiUrl } from '../api/client'
import mascotAvatarImg from '../assets/mascot/voltku-avatar.jpg'
import mascotAnalyzeImg from '../assets/mascot/voltku-analyze.jpg'
import mascotEmptyPanelImg from '../assets/mascot/voltku-empty-panel.jpg'
import mascotAlertImg from '../assets/mascot/voltku-alert.jpg'
import mascotEcoBadgeImg from '../assets/mascot/voltku-eco-badge.jpg'
import mascotWelcomeImg from '../assets/mascot/voltku-welcome.jpg'
import mascotProBannerImg from '../assets/mascot/voltku-pro-banner.jpg'

export const VISUAL_ASSET_CATALOG = [
  {
    slot: 'chatbot_avatar',
    label: 'Avatar Chatbot AI',
    usage: 'Ikon tombol melayang Tanya VoltKu & header laci chat AI',
    defaultSrc: mascotAvatarImg,
  },
  {
    slot: 'chatbot_empty',
    label: 'Ilustrasi AI Analisa kWh',
    usage: 'Sambutan awal obrolan AI & Panduan Tab Pantau',
    defaultSrc: mascotAnalyzeImg,
  },
  {
    slot: 'home_empty',
    label: 'Ilustrasi Beranda Kosong',
    usage: 'Tampilan saat belum ada panel listrik terhubung',
    defaultSrc: mascotEmptyPanelImg,
  },
  {
    slot: 'anomaly_alert',
    label: 'Ilustrasi Peringatan Anomali',
    usage: 'Banner atas halaman Peringatan saat gangguan terdeteksi',
    defaultSrc: mascotAlertImg,
  },
  {
    slot: 'anomaly_healthy',
    label: 'Emblem Status Normal',
    usage: 'Tampilan "Semua Berjalan Normal" & Panduan Efisiensi',
    defaultSrc: mascotEcoBadgeImg,
  },
  {
    slot: 'onboarding_welcome',
    label: 'Maskot Sambutan & Panduan',
    usage: 'Panduan Awal Langkah 1 & Header Tab Pasang Panel',
    defaultSrc: mascotWelcomeImg,
  },
  {
    slot: 'pro_banner',
    label: 'Banner Showcase VoltKu Pro',
    usage: 'Gambar header atas di modal Pilih Paket VoltKu',
    defaultSrc: mascotProBannerImg,
  },
]

const DEFAULT_SRC_MAP = Object.fromEntries(
  VISUAL_ASSET_CATALOG.map((item) => [item.slot, item.defaultSrc])
)

/**
 * Mengembalikan URL gambar aktif untuk suatu slot UI sesuai kontrol Admin:
 * - `null` bila Admin menonaktifkan / menghapus visual slot tersebut
 * - URL `/api/public/visual-assets/{slot}?v=...` bila memakai gambar custom Admin
 * - Gambar bawaan bundel bila default
 */
export function resolveVisualAsset(appConfig, slot) {
  const meta = appConfig?.visual_assets?.[slot]
  if (meta && meta.enabled === false) {
    return null
  }
  if (meta?.is_custom && meta?.url) {
    return buildApiUrl(meta.url)
  }
  return DEFAULT_SRC_MAP[slot] || null
}

