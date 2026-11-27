import React, { useState, useEffect } from 'react'
import { ArrowRight, ArrowLeft, Check, X } from 'lucide-react'

const DEFAULT_GUIDE_STEPS = [
  {
    id: 'home-panels',
    title: 'Kenali Panel Listrik Anda',
    description:
      'Lihat status setiap panel listrik secara ringkas di Beranda. Ketuk Tambah Panel kapan saja untuk menyambungkan sensor baru atau mengklaim unit Anda.',
  },
  {
    id: 'monitor-usage',
    title: 'Pantau Beban & Estimasi Tagihan',
    description:
      'Ketuk salah satu panel untuk melihat daya real-time (Watt), tren pemakaian harian, perkiraan biaya PLN, serta peringatan anomali.',
  },
  {
    id: 'profile-tariff',
    title: 'Atur Profil & Batas Aman Daya',
    description:
      'Ketuk ikon profil di kanan atas untuk masuk atau daftar akun, lalu sesuaikan tarif listrik PLN dan batas daya MCB di Tarif & Daya.',
  },
]

function StepIllustration({ stepIndex }) {
  if (stepIndex === 0) {
    return (
      <svg viewBox="0 0 240 120" className="guide-illus-svg" aria-hidden="true">
        <rect x="20" y="16" width="112" height="88" rx="14" className="guide-card-bg" />
        <rect x="34" y="30" width="28" height="28" rx="8" fill="#0B1933" />
        <g transform="translate(38 34) scale(0.3125)">
          <path fill="#FFFFFF" d="M10.4 14.4C9.8 12.9 10.9 11.4 12.5 11.4H20.8C21.8 11.4 22.7 12 23.1 12.9L36.2 44.3L33.4 50.6C32.4 52.8 29.2 52.8 28.2 50.6L10.4 14.4Z" />
          <path fill="#38BDF8" d="M43.2 11.4H51.5C53.1 11.4 54.2 12.9 53.6 14.4L36.2 50.5C35.4 52.1 33.8 52.6 32 52.6C30.4 52.6 29 51.8 28.3 50.5L32.8 40.3L40.9 13C41.3 12 42.2 11.4 43.2 11.4Z" />
          <circle cx="32" cy="17.5" r="3.4" fill="#FBBF24" />
        </g>
        <rect x="74" y="34" width="44" height="8" rx="4" className="guide-line-strong" />
        <rect x="74" y="47" width="30" height="6" rx="3" className="guide-line-muted" />
        <rect x="34" y="74" width="84" height="16" rx="8" className="guide-line-pill" />
        <circle cx="46" cy="82" r="3.5" fill="#10B981" />
        <rect x="144" y="28" width="76" height="64" rx="14" className="guide-accent-solid" />
        <path
          d="M182 48 V68 M172 58 H192"
          stroke="#FFFFFF"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  if (stepIndex === 1) {
    return (
      <svg viewBox="0 0 240 120" className="guide-illus-svg" aria-hidden="true">
        <rect x="24" y="14" width="192" height="92" rx="14" className="guide-card-bg" />
        <path
          d="M42 78 C64 78, 72 44, 96 48 C118 52, 128 32, 152 38 C172 42, 182 28, 198 30"
          fill="none"
          stroke="#1A63E8"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
        <circle cx="152" cy="38" r="5" fill="#FFC53D" stroke="#FFFFFF" strokeWidth="2" />
        <rect x="42" y="88" width="54" height="7" rx="3.5" className="guide-line-muted" />
        <rect x="148" y="86" width="50" height="9" rx="4.5" className="guide-accent-soft" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 240 120" className="guide-illus-svg" aria-hidden="true">
      <rect x="28" y="18" width="184" height="84" rx="14" className="guide-card-bg" />
      <circle cx="64" cy="48" r="16" className="guide-accent-soft" />
      <circle cx="64" cy="44" r="5.5" fill="#1A63E8" />
      <path d="M53 59 C55 53, 73 53, 75 59" fill="none" stroke="#1A63E8" strokeWidth="3" strokeLinecap="round" />
      <rect x="92" y="39" width="76" height="8" rx="4" className="guide-line-strong" />
      <rect x="92" y="53" width="52" height="6" rx="3" className="guide-line-muted" />
      <rect x="48" y="78" width="144" height="6" rx="3" className="guide-line-pill" />
      <rect x="48" y="78" width="92" height="6" rx="3" fill="#1A63E8" />
      <circle cx="140" cy="81" r="6" fill="#FFB703" stroke="#FFFFFF" strokeWidth="2" />
    </svg>
  )
}

export function OnboardingTour({ isOpen, steps = null, onComplete, onSkip }) {
  const [stepIndex, setStepIndex] = useState(0)

  const guideSteps =
    Array.isArray(steps) && steps.length >= 3 ? steps : DEFAULT_GUIDE_STEPS

  useEffect(() => {
    if (isOpen) setStepIndex(0)
  }, [isOpen])

  if (!isOpen) return null

  const currentStep = guideSteps[stepIndex] || guideSteps[0]
  const isFirst = stepIndex === 0
  const isLast = stepIndex >= guideSteps.length - 1

  const handleNext = () => {
    if (isLast) {
      if (onComplete) onComplete()
    } else {
      setStepIndex((prev) => Math.min(guideSteps.length - 1, prev + 1))
    }
  }

  return (
    <div
      className="modal-overlay guide-sheet-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Pengenalan Aplikasi VoltKu"
      onClick={onSkip}
    >
      <div className="guide-sheet-card" onClick={(e) => e.stopPropagation()}>
        {/* Bar progres tipis dan tombol tutup */}
        <div className="guide-top-row">
          <div className="guide-progress-segments" aria-label={`Langkah ${stepIndex + 1} dari ${guideSteps.length}`}>
            {guideSteps.map((s, idx) => (
              <button
                key={s.id || idx}
                type="button"
                aria-label={`Langkah ${idx + 1}`}
                className={`guide-progress-seg ${idx <= stepIndex ? 'active' : ''}`}
                onClick={() => setStepIndex(idx)}
              />
            ))}
          </div>
          <button
            type="button"
            className="btn-icon-close"
            onClick={onSkip}
            aria-label="Lewati panduan"
          >
            <X size={17} />
          </button>
        </div>

        {/* Ilustrasi Vektor Bersih */}
        <div className="guide-illus-stage">
          <StepIllustration stepIndex={stepIndex % 3} />
        </div>

        <div className="guide-copy-block">
          <h3 className="guide-step-title">{currentStep.title}</h3>
          <p className="guide-step-desc">{currentStep.description}</p>
        </div>

        <div className="guide-footer-actions">
          {isFirst ? (
            <button type="button" className="guide-ghost-btn" onClick={onSkip}>
              Lewati
            </button>
          ) : (
            <button
              type="button"
              className="guide-ghost-btn"
              onClick={() => setStepIndex((prev) => Math.max(0, prev - 1))}
            >
              <ArrowLeft size={15} />
              <span>Sebelumnya</span>
            </button>
          )}

          <button type="button" className="btn btn-primary guide-next-btn" onClick={handleNext}>
            <span>{isLast ? 'Mulai Memantau' : 'Lanjutkan'}</span>
            {isLast ? <Check size={16} /> : <ArrowRight size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}
