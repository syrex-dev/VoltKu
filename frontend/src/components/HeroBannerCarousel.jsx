import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  Sparkles,
  Crown,
  QrCode,
  SlidersHorizontal,
  Megaphone,
  ChevronRight,
  BellRing,
  BookOpen,
} from 'lucide-react'
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
  const trackRef = useRef(null)
  const activeIndexRef = useRef(0)
  const rafRef = useRef(0)
  const settleTimerRef = useRef(null)
  const touchStartPosRef = useRef(null)
  const suppressNextClickRef = useRef(false)

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
    onOpenUsageGuide,
    onOpenPlanModal,
    onOpenSettings,
    onOpenAlerts,
    onOpenLogin,
  ])

  const safeActiveIndex = slides.length > 0 ? activeIndex % slides.length : 0

  useEffect(() => {
    activeIndexRef.current = safeActiveIndex
  }, [safeActiveIndex])

  const commitActiveIndex = useCallback((nextIdx) => {
    const clamped = Math.max(0, Math.min(slides.length - 1, nextIdx))
    if (activeIndexRef.current !== clamped) {
      activeIndexRef.current = clamped
      setActiveIndex(clamped)
    }
  }, [slides.length])

  // Baca indeks slide terdekat dari posisi scroll aktual DOM track
  const measureNearestSlideIndex = useCallback(() => {
    const el = trackRef.current
    if (!el || el.children.length === 0) return
    const scrollLeft = el.scrollLeft
    let bestIdx = 0
    let bestDist = Infinity
    for (let i = 0; i < el.children.length; i += 1) {
      const child = el.children[i]
      const dist = Math.abs(child.offsetLeft - scrollLeft)
      if (dist < bestDist) {
        bestDist = dist
        bestIdx = i
      }
    }
    commitActiveIndex(bestIdx)
  }, [commitActiveIndex])

  const scrollToSlide = useCallback((idx) => {
    const el = trackRef.current
    if (!el || slides.length === 0) return
    const clamped = Math.max(0, Math.min(slides.length - 1, idx))
    const targetChild = el.children[clamped]
    const targetLeft = targetChild ? targetChild.offsetLeft : clamped * el.clientWidth
    commitActiveIndex(clamped)
    el.scrollTo({ left: targetLeft, behavior: 'smooth' })
  }, [slides.length, commitActiveIndex])

  // Auto-advance timer di luar state updater React
  useEffect(() => {
    if (paused || slides.length <= 1) return undefined
    const timer = window.setInterval(() => {
      const next = (activeIndexRef.current + 1) % slides.length
      scrollToSlide(next)
    }, AUTO_SCROLL_MS)
    return () => window.clearInterval(timer)
  }, [paused, slides.length, scrollToSlide])

  // Sinkronisasi multi-jalur: scroll rAF langsung + scrollend + IntersectionObserver
  useEffect(() => {
    const el = trackRef.current
    if (!el) return undefined

    const handleNativeScroll = () => {
      if (rafRef.current) {
        window.cancelAnimationFrame(rafRef.current)
      }
      rafRef.current = window.requestAnimationFrame(() => {
        measureNearestSlideIndex()
      })
      if (settleTimerRef.current) {
        window.clearTimeout(settleTimerRef.current)
      }
      settleTimerRef.current = window.setTimeout(() => {
        measureNearestSlideIndex()
      }, 120)
    }

    el.addEventListener('scroll', handleNativeScroll, { passive: true })
    el.addEventListener('scrollend', measureNearestSlideIndex, { passive: true })

    let observer = null
    if (typeof IntersectionObserver !== 'undefined') {
      observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting && entry.intersectionRatio >= 0.55) {
              const idxAttr = Number(entry.target.getAttribute('data-slide-idx'))
              if (!Number.isNaN(idxAttr)) {
                commitActiveIndex(idxAttr)
              }
            }
          }
        },
        { root: el, threshold: 0.55 }
      )
      Array.from(el.children).forEach((child) => observer.observe(child))
    }

    return () => {
      el.removeEventListener('scroll', handleNativeScroll)
      el.removeEventListener('scrollend', measureNearestSlideIndex)
      if (rafRef.current) window.cancelAnimationFrame(rafRef.current)
      if (settleTimerRef.current) window.clearTimeout(settleTimerRef.current)
      if (observer) observer.disconnect()
    }
  }, [slides.length, measureNearestSlideIndex, commitActiveIndex])

  if (slides.length === 0) return null

  return (
    <section
      className="ewl-hero-section"
      aria-roledescription="carousel"
      aria-label="Sorotan Fitur VoltKu"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onTouchStart={(e) => {
        setPaused(true)
        const t = e.touches?.[0]
        if (t) {
          touchStartPosRef.current = { x: t.clientX, y: t.clientY }
          suppressNextClickRef.current = false
        }
      }}
      onTouchMove={(e) => {
        const start = touchStartPosRef.current
        const t = e.touches?.[0]
        if (start && t && Math.abs(t.clientX - start.x) > 10) {
          suppressNextClickRef.current = true
        }
      }}
      onTouchEnd={() => {
        setPaused(false)
        measureNearestSlideIndex()
      }}
    >
      <div ref={trackRef} className="ewl-hero-track">
        {slides.map((slide, idx) => {
          const Icon = slide.Icon
          return (
            <button
              key={slide.id}
              type="button"
              data-slide-idx={idx}
              className={`ewl-hero-slide ${slide.tone}`}
              onClick={(e) => {
                if (suppressNextClickRef.current) {
                  e.preventDefault()
                  suppressNextClickRef.current = false
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
              onClick={() => scrollToSlide(idx)}
            />
          ))}
        </div>
      )}
    </section>
  )
}
