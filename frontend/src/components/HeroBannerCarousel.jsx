import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  Crown,
  QrCode,
  SlidersHorizontal,
  Megaphone,
  ChevronRight,
  BellRing,
  BookOpen,
} from 'lucide-react'
import { EnergyAssistantIcon } from './VoltKuIcons'
import { formatRp } from '../utils/formatters'

const AUTO_SCROLL_MS = 4500

export function HeroBannerCarousel({
  currentUser = null,
  isAuthenticated = false,
  appConfig = {},
  onOpenAddDevice,
  onOpenUsageGuide,
  onOpenPlanModal,
  onOpenSettings,
  onOpenAlerts,
  onOpenLogin,
}) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffsetPx, setDragOffsetPx] = useState(0)
  const [dragViewportWidth, setDragViewportWidth] = useState(340)

  const viewportRef = useRef(null)
  const gestureRef = useRef({
    active: false,
    axis: null, // null | 'x' | 'y'
    startX: 0,
    startY: 0,
    startTime: 0,
    width: 340,
    lastDx: 0,
  })
  const suppressClickRef = useRef(false)

  const slides = useMemo(() => {
    const planItems = Array.isArray(appConfig.plans?.items) ? appConfig.plans.items : []
    const paidPlans = planItems.filter((p) => !p.is_default_free && p.slug !== 'free')
    const proCfg = paidPlans.find((p) => p.is_recommended) ||
      paidPlans[0] ||
      appConfig.plans?.pro || {
        name: 'VoltKu Pro',
        price_monthly_rp: 30000,
        effective_monthly_price_rp: 30000,
        max_devices: 10,
        history_days: 90,
        promo_active: false,
      }
    const effPrice = Number(proCfg.effective_monthly_price_rp ?? proCfg.price_monthly_rp ?? 30000)
    const basePrice = Number(proCfg.price_monthly_rp ?? effPrice)
    const hasPromo = Boolean(proCfg.promo_active) && basePrice > effPrice
    const isPro = Boolean(currentUser?.plan?.is_pro)
    const activePlanName = currentUser?.plan?.plan_name || proCfg.name || 'VoltKu Pro'
    const activeHistDays = currentUser?.plan?.limits?.history_days || proCfg.history_days || 90
    const maxDevsText =
      proCfg.max_devices < 0 ? 'panel tanpa batas' : `hingga ${proCfg.max_devices} panel`

    const list = []

    if (appConfig.announcement_active && appConfig.announcement_text) {
      list.push({
        id: 'announcement',
        tone: 'is-announcement',
        badge: 'INFO TERBARU',
        title: appConfig.announcement_text,
        subtitle: appConfig.announcement_url
          ? 'Ketuk untuk membuka info lengkap'
          : 'Pembaruan resmi VoltKu',
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
      id: 'usage-guide',
      tone: 'is-teal-guide',
      badge: 'CARA PEMAKAIAN',
      title: 'Panduan Pasang & Pakai VoltKu',
      subtitle: 'Langkah mudah konek Wi-Fi 2.4 GHz, scan QR & pantau tagihan PLN',
      cta: 'Lihat Panduan',
      Icon: BookOpen,
      onClick: () => onOpenUsageGuide?.(),
    })

    list.push({
      id: 'ai-assistant',
      tone: 'is-cobalt',
      badge: 'ANALISA TAGIHAN',
      title: 'Cek Jam Boros & Estimasi Biaya',
      subtitle: 'Tanya ringkasan kWh harian & proyeksi bulan ini berbasis data meteran',
      cta: 'Buka Asisten',
      Icon: EnergyAssistantIcon,
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
        badge: `${activePlanName.toUpperCase()} AKTIF`,
        title: `Proteksi & Riwayat ${activeHistDays} Hari Aktif`,
        subtitle: 'Pantau catatan anomali & tegangan panel secara real-time',
        cta: 'Cek Peringatan',
        Icon: BellRing,
        onClick: () => onOpenAlerts?.(),
      })
    } else {
      list.push({
        id: 'upgrade-pro',
        tone: 'is-gold-dark',
        badge: hasPromo
          ? proCfg.promo_label?.toUpperCase() || 'PROMO SPESIAL'
          : proCfg.name?.toUpperCase() || 'VOLTKU PRO',
        title: `Pantau ${maxDevsText} dengan ${proCfg.name || 'Pro'}`,
        subtitle: hasPromo
          ? `Promo mulai ${formatRp(effPrice)}/bln (normal ${formatRp(basePrice)}) · Riwayat ${proCfg.history_days} hr`
          : `Riwayat ${proCfg.history_days} hari · Mulai ${formatRp(effPrice)}/bulan`,
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
    currentUser?.plan?.plan_name,
    currentUser?.plan?.limits?.history_days,
    isAuthenticated,
    onOpenAddDevice,
    onOpenUsageGuide,
    onOpenPlanModal,
    onOpenSettings,
    onOpenAlerts,
    onOpenLogin,
  ])

  const slideCount = slides.length
  const safeActiveIndex = slideCount > 0 ? activeIndex % slideCount : 0

  useEffect(() => {
    if (paused || isDragging || slideCount <= 1) return undefined
    const timer = window.setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % slideCount)
    }, AUTO_SCROLL_MS)
    return () => window.clearInterval(timer)
  }, [paused, isDragging, slideCount])

  const startGesture = useCallback((clientX, clientY) => {
    if (slideCount <= 1) return
    const width = viewportRef.current?.clientWidth || 340
    setDragViewportWidth(width)
    gestureRef.current = {
      active: true,
      axis: null,
      startX: clientX,
      startY: clientY,
      startTime: performance.now(),
      width,
      lastDx: 0,
    }
    suppressClickRef.current = false
    setPaused(true)
  }, [slideCount])

  const moveGesture = useCallback(
    (clientX, clientY) => {
      const g = gestureRef.current
      if (!g.active) return
      const dx = clientX - g.startX
      const dy = clientY - g.startY

      if (!g.axis) {
        if (Math.abs(dx) < 5 && Math.abs(dy) < 5) return
        if (Math.abs(dy) > Math.abs(dx)) {
          g.axis = 'y'
          g.active = false
          setIsDragging(false)
          setDragOffsetPx(0)
          return
        }
        g.axis = 'x'
        suppressClickRef.current = true
        setIsDragging(true)
      }

      if (g.axis === 'x') {
        let clampedDx = dx
        if ((safeActiveIndex === 0 && dx > 0) || (safeActiveIndex === slideCount - 1 && dx < 0)) {
          clampedDx = dx * 0.28
        }
        g.lastDx = clampedDx
        setDragOffsetPx(clampedDx)
      }
    },
    [safeActiveIndex, slideCount]
  )

  const endGesture = useCallback(() => {
    const g = gestureRef.current
    if (!g.active && !isDragging) {
      setPaused(false)
      return
    }
    const dx = g.lastDx
    const width = Math.max(1, g.width)
    const elapsed = Math.max(1, performance.now() - g.startTime)
    const velocity = dx / elapsed

    g.active = false
    g.axis = null
    g.lastDx = 0
    setIsDragging(false)
    setDragOffsetPx(0)
    setPaused(false)

    let nextIdx = safeActiveIndex
    if (dx <= -width * 0.22 || velocity <= -0.28) {
      nextIdx = Math.min(slideCount - 1, safeActiveIndex + 1)
    } else if (dx >= width * 0.22 || velocity >= 0.28) {
      nextIdx = Math.max(0, safeActiveIndex - 1)
    }

    setActiveIndex(nextIdx)
  }, [isDragging, safeActiveIndex, slideCount])

  if (slideCount === 0) return null

  // Hitung indikator dot secara sinkron 0ms langsung dari pergeseran jari
  const displayDotIndex = isDragging
    ? Math.max(
        0,
        Math.min(
          slideCount - 1,
          Math.round(safeActiveIndex - dragOffsetPx / Math.max(1, dragViewportWidth))
        )
      )
    : safeActiveIndex

  return (
    <section
      className="ewl-hero-section"
      aria-roledescription="carousel"
      aria-label="Sorotan Fitur VoltKu"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => {
        if (gestureRef.current.active) endGesture()
        setPaused(false)
      }}
    >
      <div
        ref={viewportRef}
        className="ewl-hero-viewport"
        onTouchStart={(e) => {
          const t = e.touches?.[0]
          if (t) startGesture(t.clientX, t.clientY)
        }}
        onTouchMove={(e) => {
          const t = e.touches?.[0]
          if (t) moveGesture(t.clientX, t.clientY)
        }}
        onTouchEnd={endGesture}
        onTouchCancel={endGesture}
        onMouseDown={(e) => {
          if (e.button !== 0) return
          startGesture(e.clientX, e.clientY)
        }}
        onMouseMove={(e) => {
          if (!gestureRef.current.active) return
          moveGesture(e.clientX, e.clientY)
        }}
        onMouseUp={endGesture}
      >
        <div
          className={`ewl-hero-track-gpu ${isDragging ? 'is-dragging' : ''}`}
          style={{
            transform: `translate3d(calc(${-safeActiveIndex * 100}% + ${dragOffsetPx}px), 0, 0)`,
          }}
        >
          {slides.map((slide) => {
            const Icon = slide.Icon
            return (
              <button
                key={slide.id}
                type="button"
                className={`ewl-hero-slide ${slide.tone}`}
                onClick={(e) => {
                  if (suppressClickRef.current) {
                    e.preventDefault()
                    suppressClickRef.current = false
                    return
                  }
                  slide.onClick?.(e)
                }}
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
      </div>

      {/* Bottom Pagination Dots */}
      {slideCount > 1 && (
        <div className="ewl-hero-dots" role="tablist" aria-label="Pilih slide banner">
          {slides.map((slide, idx) => (
            <button
              key={slide.id}
              type="button"
              role="tab"
              aria-selected={idx === displayDotIndex}
              aria-label={`Slide ${idx + 1}: ${slide.title}`}
              className={`ewl-hero-dot ${idx === displayDotIndex ? 'active' : ''}`}
              onClick={() => setActiveIndex(idx)}
            />
          ))}
        </div>
      )}
    </section>
  )
}
