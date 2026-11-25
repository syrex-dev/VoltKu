import React, { useState } from 'react'
import { Crown, Check, Lock, X, MessageCircle, Clock, Send } from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatRp, formatTimeWIB } from '../utils/formatters'

function normalizeWaHref(raw = '', prefill = '') {
  const digits = String(raw || '').replace(/[^0-9]/g, '')
  if (!digits) return ''
  const intl = digits.startsWith('0') ? `62${digits.slice(1)}` : digits
  const q = prefill ? `?text=${encodeURIComponent(prefill)}` : ''
  return `https://wa.me/${intl}${q}`
}

export function PlanUpgradeModal({
  isOpen,
  onClose,
  currentUser,
  appConfig = {},
  token,
  onLogout,
  onUpgradeSubmitted,
  lockedReason = '',
}) {
  const [billingCycle, setBillingCycle] = useState('monthly')
  const [userNote, setUserNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState(null)

  if (!isOpen) return null

  const plansCfg = appConfig.plans || {}
  const freeCfg = plansCfg.free || {
    name: 'VoltKu Gratis',
    price_monthly_rp: 0,
    max_devices: 1,
    history_days: 3,
    forecast_enabled: false,
    export_enabled: false,
  }
  const proCfg = plansCfg.pro || {
    name: 'VoltKu Pro',
    price_monthly_rp: 30000,
    price_yearly_rp: 300000,
    max_devices: 10,
    history_days: 90,
    forecast_enabled: true,
    export_enabled: true,
  }

  const userPlan = currentUser?.plan || {}
  const isPro = Boolean(userPlan.is_pro)
  const pending = userPlan.pending_upgrade || null
  const proMaxLabel =
    proCfg.max_devices < 0 ? 'Tanpa batas panel' : `Hingga ${proCfg.max_devices} panel aktif`
  const selectedPrice =
    billingCycle === 'yearly' ? proCfg.price_yearly_rp : proCfg.price_monthly_rp

  const waPrefill = `Halo Admin ${appConfig.app_name || 'VoltKu'}, saya ${currentUser?.name || ''} (${currentUser?.email || ''}) ingin konfirmasi upgrade ke ${proCfg.name} (${billingCycle === 'yearly' ? 'Tahunan' : 'Bulanan'} - ${formatRp(selectedPrice)}).`
  const waHref = normalizeWaHref(appConfig.support_whatsapp || '', waPrefill)

  const handleSubmitRequest = async (e) => {
    e.preventDefault()
    if (!token) return
    setSubmitting(true)
    setFeedback(null)
    try {
      await apiRequest(
        '/api/users/upgrade-request',
        {
          method: 'POST',
          body: {
            billing_cycle: billingCycle,
            user_note: userNote.trim() || undefined,
          },
        },
        token,
        onLogout
      )
      setUserNote('')
      setFeedback({
        type: 'success',
        text: 'Permintaan upgrade berhasil dikirim! Konfirmasikan pembayaran ke pengelola untuk aktivasi instan.',
      })
      if (onUpgradeSubmitted) await onUpgradeSubmitted()
    } catch (err) {
      setFeedback({
        type: 'error',
        text: err.message || 'Gagal mengajukan permintaan upgrade.',
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern plan-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Paket Langganan VoltKu"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head" style={{ marginBottom: 12 }}>
          <div className="pwa-guide-brand">
            <span className="plan-modal-crown">
              <Crown size={20} />
            </span>
            <div>
              <h3 className="pwa-guide-title">Paket &amp; Fitur {appConfig.app_name || 'VoltKu'}</h3>
              <p className="pwa-guide-sub">
                {isPro
                  ? `Paket ${proCfg.name} aktif di akun Anda`
                  : `Tingkatkan ke ${proCfg.name} untuk buka semua fitur`}
              </p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        {lockedReason && (
          <div className="plan-lock-notice">
            <Lock size={15} />
            <span>{lockedReason}</span>
          </div>
        )}

        {feedback && (
          <div className={`feedback-msg ${feedback.type === 'error' ? 'error' : 'success'}`}>
            {feedback.text}
          </div>
        )}

        <div className="plan-compare-grid">
          <div className={`plan-tier-card ${!isPro ? 'is-current' : ''}`}>
            <div className="plan-tier-head">
              <strong>{freeCfg.name}</strong>
              {!isPro && <span className="plan-current-tag">Aktif</span>}
            </div>
            <div className="plan-tier-price num-tabular">Rp 0</div>
            <ul className="plan-feature-list">
              <li>
                <Check size={14} /> Maks. {freeCfg.max_devices} panel aktif
              </li>
              <li>
                <Check size={14} /> Pantau Live real-time 10 detik
              </li>
              <li>
                <Check size={14} /> Grafik hingga {freeCfg.history_days} hari
              </li>
              <li className={!freeCfg.forecast_enabled ? 'is-locked' : ''}>
                {freeCfg.forecast_enabled ? <Check size={14} /> : <Lock size={14} />}
                Proyeksi tagihan akhir bulan
              </li>
              <li className={!freeCfg.export_enabled ? 'is-locked' : ''}>
                {freeCfg.export_enabled ? <Check size={14} /> : <Lock size={14} />}
                Ekspor laporan CSV
              </li>
            </ul>
          </div>

          <div className={`plan-tier-card is-pro ${isPro ? 'is-current' : ''}`}>
            <div className="plan-tier-head">
              <strong>
                <Crown size={14} /> {proCfg.name}
              </strong>
              {isPro && <span className="plan-current-tag is-pro">Aktif</span>}
            </div>
            <div className="plan-tier-price num-tabular">
              {formatRp(proCfg.price_monthly_rp)}
              <span>/bulan</span>
            </div>
            <div className="plan-tier-subprice num-tabular">
              atau {formatRp(proCfg.price_yearly_rp)}/tahun
            </div>
            <ul className="plan-feature-list">
              <li>
                <Check size={14} /> {proMaxLabel}
              </li>
              <li>
                <Check size={14} /> Grafik historis hingga {proCfg.history_days} hari
              </li>
              <li>
                <Check size={14} /> Proyeksi tagihan akhir bulan otomatis
              </li>
              <li>
                <Check size={14} /> Ekspor laporan konsumsi CSV
              </li>
              <li>
                <Check size={14} /> Deteksi anomali lengkap L2/L3
              </li>
            </ul>
          </div>
        </div>

        {isPro ? (
          <div className="plan-active-summary">
            <div>
              <strong>Status: {proCfg.name} Aktif</strong>
              <p>
                {userPlan.expires_at
                  ? `Masa aktif hingga ${formatTimeWIB(userPlan.expires_at)}`
                  : 'Akses penuh aktif permanen di akun ini.'}
              </p>
            </div>
          </div>
        ) : pending ? (
          <div className="plan-pending-box">
            <div className="plan-pending-head">
              <Clock size={16} />
              <strong>Menunggu Aktivasi Pengelola</strong>
            </div>
            <p className="num-tabular">
              Paket {pending.billing_cycle === 'yearly' ? 'Tahunan' : 'Bulanan'} ·{' '}
              {formatRp(pending.amount_rp)} (diajukan {formatTimeWIB(pending.created_at)}).
            </p>
            {plansCfg.upgrade_instructions && (
              <p className="plan-inst-copy">{plansCfg.upgrade_instructions}</p>
            )}
            {waHref && (
              <a
                href={waHref}
                target="_blank"
                rel="noreferrer"
                className="btn btn-primary btn-compact"
                style={{ marginTop: 8 }}
              >
                <MessageCircle size={15} />
                <span>Konfirmasi via WhatsApp Admin</span>
              </a>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmitRequest} className="plan-upgrade-form">
            <div className="plan-cycle-toggle" role="tablist" aria-label="Pilih Siklus Paket">
              <button
                type="button"
                className={`plan-cycle-btn ${billingCycle === 'monthly' ? 'active' : ''}`}
                onClick={() => setBillingCycle('monthly')}
              >
                Bulanan · {formatRp(proCfg.price_monthly_rp)}
              </button>
              <button
                type="button"
                className={`plan-cycle-btn ${billingCycle === 'yearly' ? 'active' : ''}`}
                onClick={() => setBillingCycle('yearly')}
              >
                Tahunan · {formatRp(proCfg.price_yearly_rp)}
              </button>
            </div>

            {plansCfg.upgrade_instructions && (
              <div className="plan-inst-box">{plansCfg.upgrade_instructions}</div>
            )}

            <div className="form-field-group" style={{ marginBottom: 10 }}>
              <input
                type="text"
                className="modern-input"
                placeholder="Catatan konfirmasi (opsional, mis. nama pengirim transfer/QRIS)"
                value={userNote}
                onChange={(e) => setUserNote(e.target.value)}
                maxLength={255}
              />
            </div>

            <div className="plan-modal-actions">
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                <Send size={15} />
                <span>
                  {submitting
                    ? 'Mengirim...'
                    : `Ajukan Upgrade (${formatRp(selectedPrice)})`}
                </span>
              </button>
              {waHref && (
                <a
                  href={waHref}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-secondary"
                >
                  <MessageCircle size={15} />
                  <span>Chat Admin</span>
                </a>
              )}
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

