import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  X,
  Sparkles,
  Crown,
  QrCode,
  SlidersHorizontal,
  Megaphone,
  ChevronRight,
  BellRing,
} from 'lucide-react'
import { formatRp } from '../utils/formatters'

const AUTO_SCROLL_MS = 4500

export function HeroBannerCarousel({
  currentUser = null,
  isAuthenticated = false,
  appConfig = {},
  onOpenAddDevice,
  onOpenPlanModal,
  onOpenSettings,
  onOpenAlerts,
  onOpenLogin,
}) {
  const [dismissed, setDismissed] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const trackRef = useRef(null)
  const scrollSyncTimerRef = useRef(null)

  const slides = useMemo(() => {
    const proCfg = appConfig.plans?.pro || {
      name: 'VoltKu Pro',
      price_monthly_rp: 30000,
      max_devices: 10,
      history_days: 90,
    }
    const isPro = Boolean(currentUser?.plan?.is_pro)
    const maxDevsText =
      proCfg.max_devices < 0 ? 'panel tanpa batas' : `hingga ${proCfg.max_devices} panel`

    const list = []

    if (appConfig.announcement_active && appConfig.announcement_text) {
      list.push({
        id: 'announcement',
        tone: 'is-announcement',
        badge: 'INFO TERBARU',
        title: appConfig.announcement_text,
        subtitle: appConfig.announcement_url ? 'Ketuk untuk membuka info lengkap' : 'Pembaruan resmi VoltKu',
        cta: appConfig.announcement_url ? 'Buka Info' : 'Lihat',
        Icon: Megaphone,
        onClick: () => {
          if (appConfig.announcement_url) {
            window.open(appConfig.announcement_url, '_blank', 'noopener,noreferrer')
          }
        },
      })
    }

    list.push({
      id: 'ai-assistant',
      tone: 'is-cobalt',
      badge: 'ASISTEN AI',
      title: 'Tanya Biaya & Jam Boros ke AI',
      subtitle: 'Analisa tagihan listrik & proyeksi bulan ini secara instan',
      cta: 'Tanya AI',
      Icon: Sparkles,
      onClick: () => {
        if (isAuthenticated) {
          window.dispatchEvent(new CustomEvent('voltku:open-ai-chat'))
        } else if (onOpenLogin) {
          onOpenLogin()
        }
      },
    })

    if (isPro) {
      list.push({
        id: 'pro-active',
        tone: 'is-emerald',
        badge: 'PRO AKTIF',
        title: 'Proteksi & Riwayat 90 Hari Aktif',
        subtitle: 'Pantau catatan anomali & tegangan panel secara real-time',
        cta: 'Cek Peringatan',
        Icon: BellRing,
        onClick: () => onOpenAlerts?.(),
      })
    } else {
      list.push({
        id: 'upgrade-pro',
        tone: 'is-gold-dark',
        badge: proCfg.name?.toUpperCase() || 'VOLTKU PRO',
        title: `Pantau ${maxDevsText} dengan Pro`,
        subtitle: `Riwayat ${proCfg.history_days} hari · Mulai ${formatRp(proCfg.price_monthly_rp)}/bulan`,
        cta: 'Lihat Paket',
        Icon: Crown,
        onClick: () => {
          if (isAuthenticated && onOpenPlanModal) {
            onOpenPlanModal('')
          } else if (onOpenLogin) {
            onOpenLogin()
          }
        },
      })
    }

    list.push({
      id: 'quick-pairing',
      tone: 'is-cyan',
      badge: 'PASANG MUDAH',
      title: 'Tautkan Panel Dalam 1 Menit',
      subtitle: 'Scan barcode stiker bodi alat atau ikuti panduan Wi-Fi 2.4 GHz',
      cta: 'Tambah Panel',
      Icon: QrCode,
      onClick: () => onOpenAddDevice?.(),
    })

    list.push({
      id: 'tariff-pln',
      tone: 'is-indigo',
      badge: 'TARIF PLN',
      title: 'Sesuaikan Tarif & Batas Daya MCB',
      subtitle: 'Hitung estimasi tagihan Rp sesuai golongan R-1 hingga Bisnis',
      cta: 'Atur Tarif',
      Icon: SlidersHorizontal,
      onClick: () => onOpenSettings?.(),
    })

    return list
  }, [
    appConfig,
    currentUser?.plan?.is_pro,
    isAuthenticated,
    onOpenAddDevice,
    onOpenPlanModal,
    onOpenSettings,
    onOpenAlerts,
    onOpenLogin,
  ])

  const safeActiveIndex = slides.length > 0 ? activeIndex % slides.length : 0

  const scrollToSlide = useCallback((idx) => {
    const el = trackRef.current
    if (!el) return
    const width = el.clientWidth
    if (width <= 0) return
    el.scrollTo({ left: idx * width, behavior: 'smooth' })
  }, [])

  useEffect(() => {
    if (dismissed || paused || slides.length <= 1) return undefined
    const timer = window.setInterval(() => {
      setActiveIndex((prev) => {
        const next = (prev + 1) % slides.length
        scrollToSlide(next)
        return next
      })
    }, AUTO_SCROLL_MS)
    return () => window.clearInterval(timer)
  }, [dismissed, paused, slides.length, scrollToSlide])

  useEffect(() => {
    return () => {
      if (scrollSyncTimerRef.current) {
        window.clearTimeout(scrollSyncTimerRef.current)
      }
    }
  }, [])

  const handleTrackScroll = () => {
    const el = trackRef.current
    if (!el) return
    const width = el.clientWidth
    if (width <= 0) return
    if (scrollSyncTimerRef.current) {
      window.clearTimeout(scrollSyncTimerRef.current)
    }
    scrollSyncTimerRef.current = window.setTimeout(() => {
      const idx = Math.round(el.scrollLeft / width)
      const clamped = Math.max(0, Math.min(slides.length - 1, idx))
      setActiveIndex(clamped)
    }, 60)
  }

  if (dismissed || slides.length === 0) return null

  return (
    <section
      className="ewl-hero-section"
      aria-roledescription="carousel"
      aria-label="Sorotan Fitur VoltKu"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onTouchStart={() => setPaused(true)}
      onTouchEnd={() => setPaused(false)}
    >
      <div
        ref={trackRef}
        className="ewl-hero-track"
        onScroll={handleTrackScroll}
      >
        {slides.map((slide) => {
          const Icon = slide.Icon
          return (
            <button
              key={slide.id}
              type="button"
              className={`ewl-hero-slide ${slide.tone}`}
              onClick={slide.onClick}
            >
              <div className="ewl-hero-deco-circle a" aria-hidden="true" />
              <div className="ewl-hero-deco-circle b" aria-hidden="true" />

              <div className="ewl-hero-copy">
                <span className="ewl-hero-badge">{slide.badge}</span>
                <div className="ewl-hero-title">{slide.title}</div>
                <div className="ewl-hero-sub">{slide.subtitle}</div>
              </div>

              <div className="ewl-hero-visual" aria-hidden="true">
                <div className="ewl-hero-visual-tile">
                  <Icon size={24} strokeWidth={2} />
                </div>
                <span className="ewl-hero-cta-mini">
                  <span>{slide.cta}</span>
                  <ChevronRight size={12} />
                </span>
              </div>
            </button>
          )
        })}
      </div>

      {/* Dismiss (X) Button matching eWeLink carousel corner */}
      <button
        type="button"
        className="ewl-hero-close"
        aria-label="Tutup banner"
        title="Sembunyikan sementara"
        onClick={(e) => {
          e.stopPropagation()
          setDismissed(true)
        }}
      >
        <X size={13} strokeWidth={2.5} />
      </button>

      {/* Bottom Pagination Dots */}
      {slides.length > 1 && (
        <div className="ewl-hero-dots" role="tablist" aria-label="Pilih slide banner">
          {slides.map((slide, idx) => (
            <button
              key={slide.id}
              type="button"
              role="tab"
              aria-selected={idx === safeActiveIndex}
              aria-label={`Slide ${idx + 1}: ${slide.title}`}
              className={`ewl-hero-dot ${idx === safeActiveIndex ? 'active' : ''}`}
              onClick={() => {
                setActiveIndex(idx)
                scrollToSlide(idx)
              }}
            />
          ))}
        </div>
      )}
    </section>
  )
}

