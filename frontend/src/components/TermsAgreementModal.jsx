import React, { useState, useEffect } from 'react'
import { FileText, ArrowLeft, Check } from 'lucide-react'
import { BrandLogo } from './BrandLogo'

function renderLegalSections(rawText = '') {
  const blocks = String(rawText || '')
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .filter(Boolean)

  return blocks.map((block, idx) => {
    const lines = block.split('\n').map((l) => l.trim()).filter(Boolean)
    if (lines.length === 0) return null
    const first = lines[0]
    const looksLikeHeading = /^\d+\.\s+/.test(first) || (lines.length > 1 && first.length < 72)

    if (looksLikeHeading && lines.length > 1) {
      return (
        <section key={idx} className="legal-doc-section">
          <h4>{first}</h4>
          {lines.slice(1).map((p, pIdx) => (
            <p key={pIdx}>{p}</p>
          ))}
        </section>
      )
    }
    return (
      <section key={idx} className="legal-doc-section">
        <p>{block}</p>
      </section>
    )
  })
}

export function TermsAgreementModal({
  isOpen,
  isUpdate = false,
  readOnly = false,
  submitting = false,
  termsVersion = '2026-11-v1',
  legalUpdatedAt = '25 November 2026',
  appName = 'VoltKu',
  termsTitle = 'Syarat & Ketentuan Layanan',
  termsContent = '',
  privacyTitle = 'Kebijakan Privasi',
  privacyContent = '',
  initialDoc = null,
  onAgree,
  onDecline,
  onClose,
}) {
  const [activeDoc, setActiveDoc] = useState(initialDoc)

  useEffect(() => {
    if (isOpen) {
      setActiveDoc(initialDoc)
    }
  }, [isOpen, initialDoc])

  if (!isOpen) return null

  const title = isUpdate
    ? 'Pembaruan Kebijakan Pengguna'
    : 'Persetujuan Ketentuan & Privasi'

  return (
    <div
      className="modal-overlay app-terms-overlay"
      onClick={readOnly && onClose ? onClose : undefined}
    >
      <div
        className="app-dialog-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        {!activeDoc ? (
          <>
            <div className="app-dialog-body">
              <div className="app-dialog-brand-wrap">
                <BrandLogo variant="icon" appName={appName} />
              </div>
              <h2 id="terms-modal-title" className="app-dialog-title">
                {title}
              </h2>
              <p className="app-dialog-copy">
                {isUpdate
                  ? `${appName} telah memperbarui Syarat & Ketentuan Layanan serta Kebijakan Privasi (versi ${termsVersion}). Mohon tinjau sebelum melanjutkan penggunaan aplikasi.`
                  : `Sebelum menggunakan ${appName}, harap baca dan setujui Syarat & Ketentuan Layanan serta Kebijakan Privasi mengenai pengelolaan akun, perangkat, dan data kelistrikan Anda.`}
              </p>
              <p className="app-dialog-copy app-dialog-copy-muted">
                Persetujuan Anda dicatat resmi dengan versi <code>{termsVersion}</code> (diperbarui{' '}
                {legalUpdatedAt}).
              </p>

              <div className="app-dialog-links-row">
                <button
                  type="button"
                  className="app-link-btn"
                  onClick={() => setActiveDoc('terms')}
                >
                  {termsTitle}
                </button>
                <span className="app-link-sep">&middot;</span>
                <button
                  type="button"
                  className="app-link-btn"
                  onClick={() => setActiveDoc('privacy')}
                >
                  {privacyTitle}
                </button>
              </div>
            </div>

            {readOnly ? (
              <div className="app-dialog-single-footer">
                <button type="button" className="app-dialog-action-agree" onClick={onClose}>
                  <Check size={16} />
                  <span>Tutup</span>
                </button>
              </div>
            ) : (
              <div className="app-dialog-split-footer">
                <button
                  type="button"
                  className="app-dialog-action-exit"
                  onClick={onDecline}
                  disabled={submitting}
                >
                  Tolak
                </button>
                <button
                  type="button"
                  className="app-dialog-action-agree"
                  onClick={onAgree}
                  disabled={submitting}
                >
                  {submitting ? 'Menyimpan...' : 'Setuju & Lanjutkan'}
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="app-doc-reader">
            <div className="app-doc-header">
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setActiveDoc(null)}
                aria-label="Kembali"
              >
                <ArrowLeft size={18} />
              </button>
              <h3>{activeDoc === 'terms' ? termsTitle : privacyTitle}</h3>
              <span className="app-doc-version">{termsVersion}</span>
            </div>

            <div className="app-doc-scroll">
              {activeDoc === 'terms'
                ? renderLegalSections(termsContent)
                : renderLegalSections(privacyContent)}
            </div>

            <div className="app-doc-footer">
              <button
                type="button"
                className="btn btn-primary"
                style={{ width: '100%' }}
                onClick={() => (readOnly && initialDoc ? onClose && onClose() : setActiveDoc(null))}
              >
                <FileText size={16} />
                <span>{readOnly && initialDoc ? 'Tutup Dokumen' : 'Kembali ke Persetujuan'}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
