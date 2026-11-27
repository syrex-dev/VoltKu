import {
  Crown,
  QrCode,
  SlidersHorizontal,
  Megaphone,
  BellRing,
  BookOpen,
  Zap,
  Sparkles,
  ExternalLink,
} from 'lucide-react'
import { EnergyAssistantIcon } from '../components/VoltKuIcons'

export const HERO_BANNER_TONES = [
  { id: 'is-teal-guide', label: 'Teal Panduan', color: '#11434d' },
  { id: 'is-cobalt', label: 'Biru Cobalt', color: '#173a7a' },
  { id: 'is-gold-dark', label: 'Gelap Emas', color: '#27273a' },
  { id: 'is-emerald', label: 'Hijau Emerald', color: '#0f4c3a' },
  { id: 'is-cyan', label: 'Biru Cyan', color: '#103b5c' },
  { id: 'is-indigo', label: 'Indigo Gelap', color: '#1f2b52' },
  { id: 'is-announcement', label: 'Oranye Info', color: '#7c3b0e' },
]

export const HERO_BANNER_ICONS = [
  { id: 'book-open', label: 'Buku Panduan', Component: BookOpen },
  { id: 'assistant', label: 'Asisten AI VoltKu', Component: EnergyAssistantIcon },
  { id: 'crown', label: 'Mahkota Pro', Component: Crown },
  { id: 'qr-code', label: 'Scan QR / Alat', Component: QrCode },
  { id: 'sliders', label: 'Pengaturan Tarif', Component: SlidersHorizontal },
  { id: 'bell-ring', label: 'Lonceng Peringatan', Component: BellRing },
  { id: 'megaphone', label: 'Megafon Pengumuman', Component: Megaphone },
  { id: 'zap', label: 'Petir Energi', Component: Zap },
  { id: 'sparkles', label: 'Sorotan Promo', Component: Sparkles },
  { id: 'external-link', label: 'Tautan Luar', Component: ExternalLink },
]

export const HERO_BANNER_ACTIONS = [
  { id: 'usage_guide', label: 'Buka Panduan Pasang & Pakai' },
  { id: 'ai_chat', label: 'Buka Asisten Tanya VoltKu' },
  { id: 'upgrade_plan', label: 'Buka Menu Paket & Upgrade' },
  { id: 'add_device', label: 'Buka Tambah / Scan Panel' },
  { id: 'open_settings', label: 'Buka Tab Tarif & Daya' },
  { id: 'open_alerts', label: 'Buka Tab Peringatan' },
  { id: 'open_url', label: 'Buka Tautan URL Eksternal' },
  { id: 'none', label: 'Tanpa Aksi Klik (Info Saja)' },
]

export const HERO_BANNER_AUDIENCES = [
  { id: 'all', label: 'Semua Pengguna' },
  { id: 'free_only', label: 'Khusus Paket Gratis' },
  { id: 'pro_only', label: 'Khusus Paket Pro' },
  { id: 'authenticated_only', label: 'Pengguna Sudah Login' },
  { id: 'guest_only', label: 'Mode Tamu (Guest)' },
]

export const DEFAULT_HERO_BANNERS = [
  {
    id: 'usage-guide',
    badge: 'CARA PEMAKAIAN',
    title: 'Panduan Pasang & Pakai VoltKu',
    subtitle: 'Langkah mudah konek Wi-Fi 2.4 GHz, scan QR & pantau tagihan PLN',
    cta: 'Lihat Panduan',
    tone: 'is-teal-guide',
    icon: 'book-open',
    action_type: 'usage_guide',
    action_url: '',
    audience: 'all',
    enabled: true,
  },
  {
    id: 'ai-assistant',
    badge: 'ANALISA TAGIHAN',
    title: 'Cek Jam Boros & Estimasi Biaya',
    subtitle: 'Tanya ringkasan kWh harian & proyeksi bulan ini berbasis data meteran',
    cta: 'Buka Asisten',
    tone: 'is-cobalt',
    icon: 'assistant',
    action_type: 'ai_chat',
    action_url: '',
    audience: 'all',
    enabled: true,
  },
  {
    id: 'pro-active',
    badge: 'VOLTKU PRO AKTIF',
    title: 'Proteksi & Riwayat Panjang Aktif',
    subtitle: 'Pantau catatan anomali & tegangan panel secara real-time',
    cta: 'Cek Peringatan',
    tone: 'is-emerald',
    icon: 'bell-ring',
    action_type: 'open_alerts',
    action_url: '',
    audience: 'pro_only',
    enabled: true,
  },
  {
    id: 'upgrade-pro',
    badge: 'VOLTKU PRO',
    title: 'Pantau Banyak Panel dengan VoltKu Pro',
    subtitle: 'Riwayat lebih panjang, ekspor CSV, dan dukungan multi-panel',
    cta: 'Lihat Paket',
    tone: 'is-gold-dark',
    icon: 'crown',
    action_type: 'upgrade_plan',
    action_url: '',
    audience: 'free_only',
    enabled: true,
  },
  {
    id: 'quick-pairing',
    badge: 'PASANG MUDAH',
    title: 'Tautkan Panel Dalam 1 Menit',
    subtitle: 'Scan barcode stiker bodi alat atau ikuti panduan Wi-Fi 2.4 GHz',
    cta: 'Tambah Panel',
    tone: 'is-cyan',
    icon: 'qr-code',
    action_type: 'add_device',
    action_url: '',
    audience: 'all',
    enabled: true,
  },
  {
    id: 'tariff-pln',
    badge: 'TARIF PLN',
    title: 'Sesuaikan Tarif & Batas Daya MCB',
    subtitle: 'Hitung estimasi tagihan Rp sesuai golongan R-1 hingga Bisnis',
    cta: 'Atur Tarif',
    tone: 'is-indigo',
    icon: 'sliders',
    action_type: 'open_settings',
    action_url: '',
    audience: 'all',
    enabled: true,
  },
]

const ICON_MAP = Object.fromEntries(HERO_BANNER_ICONS.map((i) => [i.id, i.Component]))
const ACTION_LABEL_MAP = Object.fromEntries(HERO_BANNER_ACTIONS.map((a) => [a.id, a.label]))
const AUDIENCE_LABEL_MAP = Object.fromEntries(HERO_BANNER_AUDIENCES.map((a) => [a.id, a.label]))

/** Kembalikan komponen ikon Lucide/SVG sesuai ID ikon banner. */
export function resolveHeroBannerIcon(iconId) {
  return ICON_MAP[iconId] || Zap
}

/** Kembalikan label manusia untuk jenis aksi & audiens banner. */
export function getHeroBannerActionLabel(actionType) {
  return ACTION_LABEL_MAP[actionType] || 'Tanpa Aksi'
}

export function getHeroBannerAudienceLabel(audience) {
  return AUDIENCE_LABEL_MAP[audience] || 'Semua Pengguna'
}

/** Tentukan apakah banner harus tampil bagi profil pengguna saat ini. */
export function matchesHeroBannerAudience(audience, { isAuthenticated = false, isPro = false } = {}) {
  switch (audience) {
    case 'free_only':
      return !isPro
    case 'pro_only':
      return Boolean(isPro)
    case 'authenticated_only':
      return Boolean(isAuthenticated)
    case 'guest_only':
      return !isAuthenticated
    case 'all':
    default:
      return true
  }
}

