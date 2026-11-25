import React, { useState, useEffect, useCallback } from 'react'
import { Sparkles, X, ArrowRight, Check } from 'lucide-react'

const TOUR_STEPS = [
  {
    id: 'add-panel',
    selector: '[data-tour-target="add-panel"]',
    title: 'Tambah Panel di Sini',
    description:
      'Ketuk tombol biru ini untuk menyambungkan alat VoltKu ke Wi-Fi 2.4 GHz atau mengklaim ID perangkat baru.',
    arrowDirection: 'up',
  },
  {
    id: 'home-overview',
    selector: '[data-tour-target="nav-home"], [data-tour-target="device-grid"]',
    title: 'Pantau Pemakaian & Data Live',
    description:
      'Ketuk kartu panel di Beranda untuk melihat daya real-time (Watt), grafik konsumsi, perkiraan tagihan, dan anomali.',
    arrowDirection: 'down',
  },
  {
    id: 'profile-settings',
    selector: '[data-tour-target="nav-settings"]',
    title: 'Profil, Akun Google & Tarif',
    description:
      'Masuk dengan Google, atur tarif PLN, ubah alamat server APK, atau putar ulang panduan ini kapan saja dari Setelan.',
    arrowDirection: 'down',
  },
]

export function OnboardingTour({ isOpen, onComplete, onSkip }) {
  const [stepIndex, setStepIndex] = useState(0)
  const [rect, setRect] = useState(null)

  const currentStep = TOUR_STEPS[stepIndex] || TOUR_STEPS[0]

  const measureTarget = useCallback(() => {
    if (!isOpen || !currentStep) return
    const selectors = currentStep.selector.split(',').map((s) => s.trim())
    let el = null
    for (const sel of selectors) {
      const candidate = document.querySelector(sel)
      if (candidate) {
        const box = candidate.getBoundingClientRect()
        if (box.width > 0 && box.height > 0) {
          el = candidate
          break
        }
      }
    }

    if (!el) {
      setRect(null)
      return
    }

    const r = el.getBoundingClientRect()
    const pad = 6
    setRect({
      top: Math.max(4, r.top - pad),
      left: Math.max(4, r.left - pad),
      width: Math.min(window.innerWidth - 8, r.width + pad * 2),
      height: r.height + pad * 2,
    })
  }, [isOpen, currentStep])

  useEffect(() => {
    if (!isOpen) return undefined
    const timer = setTimeout(measureTarget, 80)
    window.addEventListener('resize', measureTarget)
    window.addEventListener('scroll', measureTarget, true)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', measureTarget)
      window.removeEventListener('scroll', measureTarget, true)
    }
  }, [isOpen, stepIndex, measureTarget])

  if (!isOpen) return null

  const isLast = stepIndex >= TOUR_STEPS.length - 1

  const handleNext = () => {
    if (isLast) {
      setStepIndex(0)
      if (onComplete) onComplete()
    } else {
      setStepIndex((prev) => prev + 1)
    }
  }

  const handleSkip = () => {
    setStepIndex(0)
    if (onSkip) onSkip()
  }

  // Hitung posisi kartu panduan agar tidak menutupi elemen yang disorot
  const viewportH = typeof window !== 'undefined' ? window.innerHeight : 800
  const targetCenterY = rect ? rect.top + rect.height / 2 : viewportH * 0.45
  const placeCardBelow = targetCenterY < viewportH * 0.45

  return (
    <div className="tour-backdrop" role="dialog" aria-modal="true" aria-label="Panduan VoltKu">
      {/* Spotlight cutout ring di atas elemen target */}
      {rect && (
        <div
          className="tour-spotlight-box"
          style={{
            top: `${rect.top}px`,
            left: `${rect.left}px`,
            width: `${rect.width}px`,
            height: `${rect.height}px`,
          }}
        />
      )}

      {/* Tombol Lewati di pojok kanan atas */}
      <button type="button" className="tour-skip-btn" onClick={handleSkip}>
        <span>Lewati</span>
        <X size={15} />
      </button>

      {/* Kartu instruksi + panah putus-putus */}
      <div
        className={`tour-guide-card ${placeCardBelow ? 'below-target' : 'above-target'}`}
        style={
          rect
            ? placeCardBelow
              ? { top: `${Math.min(viewportH - 250, rect.top + rect.height + 18)}px` }
              : { bottom: `${Math.max(24, viewportH - rect.top + 18)}px` }
            : { top: '50%', transform: 'translate(-50%, -50%)' }
        }
      >
        <div className="tour-step-pill">
          <Sparkles size={13} />
          <span>
            Panduan {stepIndex + 1} / {TOUR_STEPS.length}
          </span>
        </div>

        <h3 className="tour-guide-title">{currentStep.title}</h3>
        <p className="tour-guide-desc">{currentStep.description}</p>

        <div className="tour-dots-row" aria-hidden="true">
          {TOUR_STEPS.map((st, idx) => (
            <span
              key={st.id}
              className={`tour-dot ${idx === stepIndex ? 'active' : ''}`}
            />
          ))}
        </div>

        <button type="button" className="tour-next-sketch-btn" onClick={handleNext}>
          <span>{isLast ? 'Mulai Sekarang' : 'Lanjut'}</span>
          {isLast ? <Check size={16} /> : <ArrowRight size={16} />}
        </button>
      </div>
    </div>
  )
}

