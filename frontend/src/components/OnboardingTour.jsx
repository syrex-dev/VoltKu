import React, { useState, useEffect } from 'react'
import { ArrowRight, ArrowLeft, Check, X } from 'lucide-react'
import mascotWelcomeImg from '../assets/mascot/voltku-welcome.jpg'
import mascotAnalyzeImg from '../assets/mascot/voltku-analyze.jpg'
import mascotEcoBadgeImg from '../assets/mascot/voltku-eco-badge.jpg'

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
  const mascotImages = [mascotWelcomeImg, mascotAnalyzeImg, mascotEcoBadgeImg]
  const src = mascotImages[stepIndex % mascotImages.length]
  return (
    <img
      src={src}
      alt=""
      className={`guide-illus-mascot ${stepIndex === 2 ? 'is-badge' : ''}`}
      aria-hidden="true"
    />
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
