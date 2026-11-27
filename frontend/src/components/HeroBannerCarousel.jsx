import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Megaphone, ChevronRight } from 'lucide-react'
import {
  DEFAULT_HERO_BANNERS,
  matchesHeroBannerAudience,
  resolveHeroBannerIcon,
} from '../utils/heroBanners'

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
    const isPro = Boolean(currentUser?.plan?.is_pro)
    const sourceBanners = Array.isArray(appConfig?.hero_banners)
      ? appConfig.hero_banners
      : DEFAULT_HERO_BANNERS

    const triggerBannerAction = (banner) => {
      switch (banner.action_type) {
        case 'usage_guide':
          onOpenUsageGuide?.()
          break
        case 'ai_chat':
          if (isAuthenticated) {
            window.dispatchEvent(new CustomEvent('voltku:open-ai-chat'))
          } else {
            onOpenLogin?.()
          }
          break
        case 'upgrade_plan':
          if (isAuthenticated && onOpenPlanModal) {
            onOpenPlanModal('')
          } else {
            onOpenLogin?.()
          }
          break
        case 'add_device':
          onOpenAddDevice?.()
          break
        case 'open_settings':
          onOpenSettings?.()
          break
        case 'open_alerts':
          onOpenAlerts?.()
          break
        case 'open_url':
          if (
            typeof banner.action_url === 'string' &&
            (banner.action_url.startsWith('https://') || banner.action_url.startsWith('http://'))
          ) {
            window.open(banner.action_url, '_blank', 'noopener,noreferrer')
          }
          break
        case 'none':
        default:
          break
      }
    }

    const list = []

    if (appConfig?.announcement_active && appConfig?.announcement_text) {
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
          if (
            typeof appConfig.announcement_url === 'string' &&
            (appConfig.announcement_url.startsWith('https://') ||
              appConfig.announcement_url.startsWith('http://'))
          ) {
            window.open(appConfig.announcement_url, '_blank', 'noopener,noreferrer')
          }
        },
      })
    }

    for (const banner of sourceBanners) {
      if (!banner || banner.enabled === false) continue
      if (!matchesHeroBannerAudience(banner.audience, { isAuthenticated, isPro })) continue
      const Icon = resolveHeroBannerIcon(banner.icon)
      list.push({
        id: banner.id,
        tone: banner.tone || 'is-cobalt',
        badge: banner.badge || '',
        title: banner.title || '',
        subtitle: banner.subtitle || '',
        cta: banner.cta || 'Lihat',
        Icon,
        onClick: () => triggerBannerAction(banner),
      })
    }

    return list
  }, [
    appConfig?.hero_banners,
    appConfig?.announcement_active,
    appConfig?.announcement_text,
    appConfig?.announcement_url,
    currentUser?.plan?.is_pro,
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

  useEffect(() => {
    setDisableTransition(true)
    setTrackIdx(hasLoop ? 1 : 0)
  }, [hasLoop, slideCount])
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
