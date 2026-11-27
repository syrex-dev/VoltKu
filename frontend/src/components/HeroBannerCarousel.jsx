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
  const [trackIdx, setTrackIdx] = useState(1)
  const [disableTransition, setDisableTransition] = useState(false)
  const [paused, setPaused] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [dragOffsetPx, setDragOffsetPx] = useState(0)
  const [dragViewportWidth, setDragViewportWidth] = useState(340)

  const viewportRef = useRef(null)
  const trackIdxRef = useRef(1)
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
  const rafResetRef = useRef(0)

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
  const hasLoop = slideCount > 1
  const safeTrackIdx = !hasLoop
    ? 0
    : Math.max(0, Math.min(slideCount + 1, trackIdx))
  trackIdxRef.current = safeTrackIdx

  const safeActiveIndex =
    slideCount > 0
      ? (((hasLoop ? safeTrackIdx - 1 : 0) % slideCount) + slideCount) % slideCount
      : 0

  const trackSlides = useMemo(() => {
    if (!hasLoop) return slides
    return [
      { ...slides[slideCount - 1], _renderKey: `${slides[slideCount - 1].id}__clone_head`, isClone: true },
      ...slides.map((s) => ({ ...s, _renderKey: s.id, isClone: false })),
      { ...slides[0], _renderKey: `${slides[0].id}__clone_tail`, isClone: true },
    ]
  }, [hasLoop, slides, slideCount])

  const snapLoopBoundaryIfNeeded = useCallback(
    (curIdx) => {
      if (!hasLoop) return curIdx
      if (curIdx !== 0 && curIdx !== slideCount + 1) return curIdx
      const snapped = curIdx === 0 ? slideCount : 1
      window.cancelAnimationFrame(rafResetRef.current)
      setDisableTransition(true)
      setTrackIdx(snapped)
      trackIdxRef.current = snapped
      rafResetRef.current = window.requestAnimationFrame(() => {
        rafResetRef.current = window.requestAnimationFrame(() => {
          setDisableTransition(false)
        })
      })
      return snapped
    },
    [hasLoop, slideCount]
  )

  useEffect(() => () => window.cancelAnimationFrame(rafResetRef.current), [])

  // Jika sedang berada di clone ujung, pastikan tetap snap aman meski transitionend tak terpanggil
  useEffect(() => {
    if (!hasLoop || isDragging) return undefined
    if (safeTrackIdx !== 0 && safeTrackIdx !== slideCount + 1) return undefined
    const id = window.setTimeout(() => {
      snapLoopBoundaryIfNeeded(safeTrackIdx)
    }, 280)
    return () => window.clearTimeout(id)
  }, [hasLoop, isDragging, safeTrackIdx, slideCount, snapLoopBoundaryIfNeeded])

  useEffect(() => {
    if (paused || isDragging || !hasLoop) return undefined
    const timer = window.setInterval(() => {
      setDisableTransition(false)
      setTrackIdx((prev) => {
        const cur = prev <= 0 ? slideCount : prev >= slideCount + 1 ? 1 : prev
        return Math.min(slideCount + 1, cur + 1)
      })
    }, AUTO_SCROLL_MS)
    return () => window.clearInterval(timer)
  }, [paused, isDragging, hasLoop, slideCount])

  const startGesture = useCallback(
    (clientX, clientY) => {
      if (!hasLoop) return
      snapLoopBoundaryIfNeeded(trackIdxRef.current)
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
    },
    [hasLoop, snapLoopBoundaryIfNeeded]
  )

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
        const limit = Math.max(240, g.width)
        const clampedDx = Math.max(-limit, Math.min(limit, dx))
        g.lastDx = clampedDx
        setDragOffsetPx(clampedDx)
      }
    },
    []
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

    const curIdx = trackIdxRef.current
    let nextTrackIdx = curIdx
    if (dx <= -width * 0.18 || velocity <= -0.25) {
      nextTrackIdx = hasLoop ? Math.min(slideCount + 1, curIdx + 1) : 0
    } else if (dx >= width * 0.18 || velocity >= 0.25) {
      nextTrackIdx = hasLoop ? Math.max(0, curIdx - 1) : 0
    }

    setDisableTransition(false)
    setTrackIdx(nextTrackIdx)
  }, [hasLoop, isDragging, slideCount])

  if (slideCount === 0) return null

  // Hitung indikator dot secara sinkron 0ms langsung dari pergeseran jari (melingkar mulus)
  const displayDotIndex = isDragging && hasLoop
    ? ((Math.round(safeTrackIdx - 1 - dragOffsetPx / Math.max(1, dragViewportWidth)) % slideCount) +
        slideCount) %
      slideCount
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
          className={`ewl-hero-track-gpu ${isDragging || disableTransition ? 'is-dragging' : ''}`}
          style={{
            transform: `translate3d(calc(${-safeTrackIdx * 100}% + ${dragOffsetPx}px), 0, 0)`,
          }}
          onTransitionEnd={(e) => {
            if (e.target !== e.currentTarget) return
            snapLoopBoundaryIfNeeded(trackIdxRef.current)
          }}
        >
          {trackSlides.map((slide) => {
            const Icon = slide.Icon
            return (
              <button
                key={slide._renderKey || slide.id}
                type="button"
                tabIndex={slide.isClone ? -1 : undefined}
                aria-hidden={slide.isClone ? 'true' : undefined}
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
              onClick={() => {
                setDisableTransition(false)
                setTrackIdx(hasLoop ? idx + 1 : idx)
              }}
            />
          ))}
        </div>
      )}
    </section>
  )
}
