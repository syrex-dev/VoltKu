import React, { useState, useEffect, useMemo } from 'react'
import {
  X,
  Check,
  Lock,
  Crown,
  MessageCircle,
  Clock,
  QrCode,
  Landmark,
  Wallet,
  Copy,
  Upload,
  CheckCircle2,
  XCircle,
  ZoomIn,
  Download,
  RotateCcw,
  Sparkles,
  ShieldCheck,
} from 'lucide-react'
import { apiRequest, buildApiUrl } from '../api/client'
import { formatDateTimeWIB, formatRp } from '../utils/formatters'
import { compressImageToDataUrl } from '../utils/imageCompress'
import { useAuthImage } from '../utils/authImage'

const TYPE_META = {
  qris: { label: 'QRIS', icon: QrCode },
  bank: { label: 'Transfer Bank', icon: Landmark },
  ewallet: { label: 'E-Wallet', icon: Wallet },
}

function formatCountdown(expiresAtEpoch, nowEpoch) {
  if (!expiresAtEpoch) return ''
  const diff = Math.max(0, expiresAtEpoch - nowEpoch)
  const hrs = String(Math.floor(diff / 3600)).padStart(2, '0')
  const mins = String(Math.floor((diff % 3600) / 60)).padStart(2, '0')
  const secs = String(diff % 60).padStart(2, '0')
  return `${hrs}:${mins}:${secs}`
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
  const [paymentMethods, setPaymentMethods] = useState([])
  const [methodsLoading, setMethodsLoading] = useState(false)
  const [selectedMethodId, setSelectedMethodId] = useState(null)
  const [userNote, setUserNote] = useState('')
  const [proofBase64, setProofBase64] = useState('')
  const [proofName, setProofName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [copiedField, setCopiedField] = useState('')
  const [zoomImageSrc, setZoomImageSrc] = useState('')
  const [localPending, setLocalPending] = useState(undefined)
  const [nowSec, setNowSec] = useState(() => Math.floor(Date.now() / 1000))

  const plans = appConfig?.plans || {}
  const freeCfg = plans.free || {}
  const proCfg = plans.pro || {}

  const proName = proCfg.name || 'VoltKu Pro'
  const freeName = freeCfg.name || 'VoltKu Gratis'
  const monthlyPrice = Number(proCfg.price_monthly_rp ?? 30000)
  const yearlyPrice = Number(proCfg.price_yearly_rp ?? 300000)
  const freeMaxDevices = Number(freeCfg.max_devices ?? 1)
  const freeHistoryDays = Number(freeCfg.history_days ?? 3)
  const proMaxDevices = Number(proCfg.max_devices ?? 10)
  const proHistoryDays = Number(proCfg.history_days ?? 90)
  const instructions = proCfg.upgrade_instructions || ''
  const waRaw = (appConfig?.support_whatsapp || '').replace(/[^0-9]/g, '')

  const userPlan = currentUser?.plan || {}
  const isPro = Boolean(userPlan.is_pro)
  const pending = localPending !== undefined ? localPending : userPlan.pending_upgrade || null
  const latestUpgrade = userPlan.latest_upgrade || null
  const activeStepStatus = pending?.status || ''

  // Hitung penghematan paket tahunan secara deterministik dari harga bulanan x 12
  const yearlyFullPrice = monthlyPrice * 12
  const yearlySavingsRp = yearlyFullPrice > yearlyPrice ? yearlyFullPrice - yearlyPrice : 0
  const yearlySavingsPct =
    yearlySavingsRp > 0 && yearlyFullPrice > 0
      ? Math.round((yearlySavingsRp / yearlyFullPrice) * 100)
      : 0

  const checkoutStepNum = useMemo(() => {
    if (isPro) return 4
    if (activeStepStatus === 'verifying') return 3
    if (activeStepStatus === 'awaiting_payment' || activeStepStatus === 'pending') return 2
    return 1
  }, [isPro, activeStepStatus])

  // Reset saat modal dibuka/ditutup dan muat daftar metode pembayaran aktif
  useEffect(() => {
    if (!isOpen) {
      setFeedback(null)
      setProofBase64('')
      setProofName('')
      setZoomImageSrc('')
      setLocalPending(undefined)
      return
    }
    setLocalPending(undefined)
    let cancelled = false
    setMethodsLoading(true)
    apiRequest('/api/public/payment-methods')
      .then((list) => {
        if (cancelled) return
        const items = Array.isArray(list) ? list : []
        setPaymentMethods(items)
        setSelectedMethodId((prev) => {
          if (prev && items.some((m) => m.id === prev)) return prev
          return items[0]?.id ?? null
        })
      })
      .catch(() => {
        if (!cancelled) setPaymentMethods([])
      })
      .finally(() => {
        if (!cancelled) setMethodsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isOpen])

  // Sinkronkan timer hitung mundur saat tagihan menunggu pembayaran
  useEffect(() => {
    if (!isOpen || activeStepStatus !== 'awaiting_payment') return undefined
    setNowSec(Math.floor(Date.now() / 1000))
    const id = window.setInterval(() => {
      setNowSec(Math.floor(Date.now() / 1000))
    }, 1000)
    return () => window.clearInterval(id)
  }, [isOpen, activeStepStatus])

  // Clear local override begitu prop currentUser sudah sinkron
  useEffect(() => {
    if (localPending !== undefined && userPlan.pending_upgrade !== undefined) {
      setLocalPending(undefined)
    }
  }, [userPlan.pending_upgrade]) // eslint-disable-line react-hooks/exhaustive-deps

  const { imageUrl: uploadedProofUrl, loading: proofImgLoading } = useAuthImage(
    pending?.id ? `/api/users/upgrade-requests/${pending.id}/proof` : '',
    token,
    Boolean(isOpen && pending?.id && pending?.has_payment_proof)
  )

  const pendingQrisUrl = useMemo(() => {
    if (!pending || pending.payment_method_type !== 'qris') return ''
    const matched = paymentMethods.find((m) => m.id === pending.payment_method_id)
    if (matched?.qris_image_url) return buildApiUrl(matched.qris_image_url)
    if (matched?.has_qris_image === false) return ''
    return pending.payment_method_id
      ? buildApiUrl(`/api/payment-methods/${pending.payment_method_id}/qris`)
      : ''
  }, [pending, paymentMethods])

  if (!isOpen) return null

  const selectedPrice = billingCycle === 'yearly' ? yearlyPrice : monthlyPrice
  const selectedMethod = paymentMethods.find((m) => m.id === selectedMethodId) || null
  const isExpiredInvoice = Boolean(
    pending?.expires_at && activeStepStatus === 'awaiting_payment' && pending.expires_at <= nowSec
  )

  const waHref = (() => {
    if (!waRaw) return ''
    const waNumber = waRaw.startsWith('0') ? `62${waRaw.slice(1)}` : waRaw
    const orderInfo = pending?.order_code ? ` (Kode: ${pending.order_code})` : ''
    const cycleText =
      (pending?.billing_cycle || billingCycle) === 'yearly' ? 'Tahunan' : 'Bulanan'
    const text = encodeURIComponent(
      `Halo Admin VoltKu, saya ${currentUser?.name || 'Pengguna'} (${currentUser?.email || '-'}) ingin konfirmasi upgrade ${proName} paket ${cycleText}${orderInfo}.`
    )
    return `https://wa.me/${waNumber}?text=${text}`
  })()

  const handleCopy = async (key, textVal) => {
    if (!textVal) return
    try {
      await navigator.clipboard.writeText(String(textVal))
      setCopiedField(key)
      window.setTimeout(() => setCopiedField(''), 1800)
    } catch {
      setFeedback({ type: 'error', text: 'Gagal menyalin ke clipboard.' })
    }
  }

  const handleSelectProofFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setFeedback(null)
    try {
      const compressed = await compressImageToDataUrl(file, {
        maxDimension: 1280,
        quality: 0.84,
      })
      setProofBase64(compressed)
      setProofName(file.name || 'bukti-pembayaran.jpg')
    } catch (err) {
      setFeedback({ type: 'error', text: err.message || 'Gagal memproses gambar bukti bayar.' })
    }
  }

  const handleCreateOrder = async () => {
    if (!token) return
    setSubmitting(true)
    setFeedback(null)
    try {
      const created = await apiRequest(
        '/api/users/upgrade-request',
        {
          method: 'POST',
          body: {
            billing_cycle: billingCycle,
            payment_method_id: selectedMethod ? selectedMethod.id : null,
            user_note: userNote.trim() || null,
          },
        },
        token,
        onLogout
      )
      setLocalPending(created)
      setProofBase64('')
      setProofName('')
      setFeedback({
        type: 'success',
        text:
          created.status === 'awaiting_payment'
            ? `Tagihan ${created.order_code} dibuat. Silakan selesaikan pembayaran & unggah bukti transfer.`
            : 'Permintaan upgrade dikirim ke admin.',
      })
      if (onUpgradeSubmitted) await onUpgradeSubmitted()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message || 'Gagal membuat tagihan upgrade.' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleConfirmPayment = async () => {
    if (!token || !pending?.id) return
    if (!proofBase64) {
      setFeedback({ type: 'error', text: 'Pilih foto bukti transfer atau QRIS terlebih dahulu.' })
      return
    }
    setSubmitting(true)
    setFeedback(null)
    try {
      const updated = await apiRequest(
        `/api/users/upgrade-requests/${pending.id}/confirm-payment`,
        {
          method: 'POST',
          body: {
            proof_base64: proofBase64,
            user_note: userNote.trim() || null,
          },
        },
        token,
        onLogout
      )
      setLocalPending(updated)
      setProofBase64('')
      setProofName('')
      setFeedback({
        type: 'success',
        text: 'Bukti pembayaran dikirim! Menunggu pengecekan & konfirmasi Admin.',
      })
      if (onUpgradeSubmitted) await onUpgradeSubmitted()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message || 'Gagal mengirim bukti pembayaran.' })
    } finally {
      setSubmitting(false)
    }
  }

  const handleCancelOrder = async () => {
    if (!token || !pending?.id) return
    setCancelling(true)
    setFeedback(null)
    try {
      await apiRequest(
        `/api/users/upgrade-requests/${pending.id}/cancel`,
        { method: 'POST', body: {} },
        token,
        onLogout
      )
      setLocalPending(null)
      setProofBase64('')
      setProofName('')
      setFeedback({
        type: 'success',
        text: 'Tagihan sebelumnya dibatalkan. Silakan pilih paket atau metode lain.',
      })
      if (onUpgradeSubmitted) await onUpgradeSubmitted()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message || 'Gagal membatalkan tagihan.' })
    } finally {
      setCancelling(false)
    }
  }

  const pendingTypeMeta = TYPE_META[pending?.payment_method_type] || TYPE_META.bank
  const PendingMethodIcon = pendingTypeMeta.icon

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head">
          <div className="plan-modal-head-left">
            <span className={`plan-crown-badge ${isPro ? 'is-pro' : ''}`}>
              <Crown size={18} />
            </span>
            <div>
              <h3 className="pwa-guide-title">
                {pending
                  ? `Pembayaran ${proName}`
                  : `Paket & Fitur ${appConfig?.app_name || 'VoltKu'}`}
              </h3>
              <p className="pwa-guide-sub">
                {isPro
                  ? `Langganan ${proName} Anda sedang aktif`
                  : pending
                    ? `Tagihan ${pending.order_code || `#${pending.id}`}`
                    : `Tingkatkan ke ${proName} untuk kendali energi lengkap`}
              </p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        {/* Stepper alur upgrade manual untuk pengguna non-Pro */}
        {!isPro && (
          <div className="plan-steps-bar" aria-label="Tahapan Pembayaran">
            <div className={`plan-step-pill ${checkoutStepNum === 1 ? 'active' : 'done'}`}>
              <span className="plan-step-num">{checkoutStepNum > 1 ? '✓' : '1'}</span>
              <span>Pilih Paket</span>
            </div>
            <span className="plan-step-sep" aria-hidden="true" />
            <div
              className={`plan-step-pill ${
                checkoutStepNum === 2 ? 'active' : checkoutStepNum > 2 ? 'done' : ''
              }`}
            >
              <span className="plan-step-num">{checkoutStepNum > 2 ? '✓' : '2'}</span>
              <span>Bayar &amp; Bukti</span>
            </div>
            <span className="plan-step-sep" aria-hidden="true" />
            <div className={`plan-step-pill ${checkoutStepNum === 3 ? 'active' : ''}`}>
              <span className="plan-step-num">3</span>
              <span>Verifikasi</span>
            </div>
          </div>
        )}

        {lockedReason && (
          <div className="plan-locked-banner">
            <Lock size={15} />
            <span>{lockedReason}</span>
          </div>
        )}

        {feedback && (
          <div className={`feedback-msg ${feedback.type === 'error' ? 'error' : 'success'}`}>
            {feedback.text}
          </div>
        )}

        {/* 1. User sudah Pro */}
        {isPro && (
          <div className="plan-pro-active-card">
            <div className="plan-pro-active-head">
              <div className="plan-pro-active-icon">
                <ShieldCheck size={22} />
              </div>
              <div className="plan-pro-active-copy">
                <div className="plan-pro-active-title">
                  <strong>{proName} Aktif</strong>
                  <span className="plan-tier-badge pro">Prioritas</span>
                </div>
                <div className="plan-sub-note">
                  {userPlan.expires_at
                    ? `Berlaku hingga ${formatDateTimeWIB(userPlan.expires_at)}`
                    : 'Aktif Permanen (Tanpa Batas Waktu)'}
                </div>
              </div>
            </div>

            <div className="plan-pro-stats-row">
              <div className="plan-pro-stat-box">
                <span>Panel Terpakai</span>
                <strong className="num-tabular">
                  {userPlan.usage?.device_count || 0} /{' '}
                  {proMaxDevices < 0 ? '∞' : proMaxDevices}
                </strong>
              </div>
              <div className="plan-pro-stat-box">
                <span>Retensi Riwayat</span>
                <strong className="num-tabular">{proHistoryDays} Hari</strong>
              </div>
            </div>

            <ul className="plan-feature-list" style={{ marginTop: 12 }}>
              <li>
                <Check size={14} className="plan-check-icon" />
                <span>Proyeksi tagihan PLN otomatis akhir bulan</span>
              </li>
              <li>
                <Check size={14} className="plan-check-icon" />
                <span>Ekspor laporan konsumsi CSV &amp; analisis anomali lengkap</span>
              </li>
            </ul>
          </div>
        )}

        {/* 2. Menunggu Pembayaran / Upload Bukti */}
        {!isPro && (activeStepStatus === 'awaiting_payment' || activeStepStatus === 'pending') && (
          <div className="pay-invoice-stack">
            <div className="pay-invoice-summary">
              <div className="pay-invoice-top">
                <div>
                  <span className="pay-order-code num-tabular">
                    {pending.order_code || `INV-${pending.id}`}
                  </span>
                  <div className="pay-order-cycle">
                    {pending.billing_cycle === 'yearly'
                      ? `${proName} · Tahunan`
                      : `${proName} · Bulanan`}
                  </div>
                </div>
                <span className={`pay-status-badge ${isExpiredInvoice ? 'expired' : 'awaiting'}`}>
                  <Clock size={12} />
                  <span>
                    {isExpiredInvoice
                      ? 'Kedaluwarsa'
                      : pending.expires_at
                        ? `Batas ${formatCountdown(pending.expires_at, nowSec)}`
                        : 'Menunggu Bayar'}
                  </span>
                </span>
              </div>

              <div className="pay-amount-row">
                <div>
                  <div className="pay-amount-label">Total yang harus dibayar</div>
                  <div className="pay-amount-value num-tabular">{formatRp(pending.amount_rp)}</div>
                </div>
                <button
                  type="button"
                  className="btn-copy-pill"
                  onClick={() => handleCopy('amount', pending.amount_rp)}
                >
                  <Copy size={13} />
                  <span>{copiedField === 'amount' ? 'Disalin' : 'Salin Nominal'}</span>
                </button>
              </div>
            </div>

            {pending.payment_method_label && (
              <div className="pay-target-card">
                <div className="pay-target-head">
                  <span className="pay-method-type-badge">
                    <PendingMethodIcon size={14} />
                    <span>{pendingTypeMeta.label}</span>
                  </span>
                  <strong>{pending.payment_method_label}</strong>
                </div>

                {pending.payment_method_type === 'qris' && pendingQrisUrl && (
                  <div className="pay-qris-preview-wrap">
                    <button
                      type="button"
                      className="pay-qris-thumb-btn"
                      onClick={() => setZoomImageSrc(pendingQrisUrl)}
                      title="Perbesar gambar QRIS"
                    >
                      <img src={pendingQrisUrl} alt="Kode QRIS VoltKu" className="pay-qris-img" />
                      <span className="pay-zoom-hint">
                        <ZoomIn size={13} />
                        <span>Ketuk untuk perbesar</span>
                      </span>
                    </button>
                    <a
                      href={pendingQrisUrl}
                      download={`QRIS-${pending.order_code || 'VoltKu'}.png`}
                      className="btn-copy-pill"
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Download size={13} />
                      <span>Simpan Gambar QRIS</span>
                    </a>
                  </div>
                )}

                {pending.payment_account_number && (
                  <div className="pay-account-row">
                    <div>
                      <div className="pay-account-label">Nomor Rekening / Tujuan</div>
                      <div className="pay-account-num num-tabular">
                        {pending.payment_account_number}
                      </div>
                      {pending.payment_account_holder && (
                        <div className="pay-account-holder">
                          a.n. {pending.payment_account_holder}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      className="btn-copy-pill"
                      onClick={() => handleCopy('acct', pending.payment_account_number)}
                    >
                      <Copy size={13} />
                      <span>{copiedField === 'acct' ? 'Disalin' : 'Salin Nomor'}</span>
                    </button>
                  </div>
                )}

                {!pending.payment_account_number && pending.payment_account_holder && (
                  <div className="pay-account-holder">
                    Penerima: <strong>{pending.payment_account_holder}</strong>
                  </div>
                )}

                {(pending.payment_instructions || instructions) && (
                  <div className="pay-instructions-note">
                    {pending.payment_instructions || instructions}
                  </div>
                )}
              </div>
            )}

            {!isExpiredInvoice ? (
              <div className="pay-upload-card">
                <label className="field-label" style={{ marginBottom: 6, display: 'block' }}>
                  Unggah Bukti Pembayaran (Screenshot / Struk Transfer)
                </label>

                <label className="pay-upload-dropzone">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleSelectProofFile}
                    className="pay-file-input-hidden"
                  />
                  {proofBase64 ? (
                    <div className="pay-proof-selected">
                      <img src={proofBase64} alt="Preview bukti bayar" className="pay-proof-thumb" />
                      <div className="pay-proof-meta">
                        <strong>{proofName || 'Bukti siap dikirim'}</strong>
                        <span>Ketuk untuk ganti gambar lain</span>
                      </div>
                    </div>
                  ) : (
                    <div className="pay-upload-placeholder">
                      <Upload size={20} />
                      <span>Pilih Foto / Screenshot Bukti Bayar</span>
                      <small>JPG, PNG, atau WEBP — dikompresi otomatis</small>
                    </div>
                  )}
                </label>

                <div className="form-field-group" style={{ marginTop: 10, marginBottom: 10 }}>
                  <input
                    type="text"
                    className="modern-input"
                    maxLength={140}
                    placeholder="Catatan pengirim (opsional, mis. a.n. Budi via BCA)"
                    value={userNote}
                    onChange={(e) => setUserNote(e.target.value)}
                  />
                </div>

                <div className="plan-cta-row">
                  <button
                    type="button"
                    className="btn btn-primary plan-cta-primary"
                    disabled={submitting || !proofBase64}
                    onClick={handleConfirmPayment}
                  >
                    <CheckCircle2 size={15} />
                    <span>
                      {submitting ? 'Mengirim Bukti...' : 'Saya Sudah Bayar & Kirim Bukti'}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={cancelling || submitting}
                    onClick={handleCancelOrder}
                  >
                    <RotateCcw size={14} />
                    <span>{cancelling ? 'Membatalkan...' : 'Ganti Metode'}</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="plan-cta-row">
                <button
                  type="button"
                  className="btn btn-primary plan-cta-primary"
                  disabled={cancelling}
                  onClick={handleCancelOrder}
                >
                  <RotateCcw size={15} />
                  <span>Buat Tagihan Baru</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* 3. Bukti Sudah Dikirim, Menunggu Verifikasi Admin */}
        {!isPro && activeStepStatus === 'verifying' && (
          <div className="pay-verifying-box">
            <div className="pay-verifying-head">
              <span className="pay-status-badge verifying">
                <Clock size={13} />
                <span>Menunggu Verifikasi Admin</span>
              </span>
              <span className="pay-order-code num-tabular">{pending.order_code}</span>
            </div>

            <div className="pay-verifying-summary">
              <div>
                Paket{' '}
                <strong>
                  {pending.billing_cycle === 'yearly' ? `${proName} Tahunan` : `${proName} Bulanan`}
                </strong>{' '}
                · <strong className="num-tabular">{formatRp(pending.amount_rp)}</strong>
              </div>
              <div className="pay-verifying-sub">
                Metode: {pending.payment_method_label || 'Manual'}
                {pending.submitted_at ? ` · Dikirim ${formatDateTimeWIB(pending.submitted_at)}` : ''}
              </div>
              <p className="pay-verifying-desc">
                Terima kasih! Bukti pembayaran Anda sudah kami terima dan sedang diperiksa oleh
                pengelola. Paket {proName} akan aktif otomatis setelah dikonfirmasi.
              </p>
            </div>

            {pending.has_payment_proof && (
              <div className="pay-uploaded-proof-box">
                <div className="pay-uploaded-label">Bukti pembayaran yang Anda unggah:</div>
                {proofImgLoading ? (
                  <div className="pay-img-loading">Memuat pratinjau bukti...</div>
                ) : uploadedProofUrl ? (
                  <button
                    type="button"
                    className="pay-proof-btn"
                    onClick={() => setZoomImageSrc(uploadedProofUrl)}
                  >
                    <img
                      src={uploadedProofUrl}
                      alt="Bukti pembayaran terkirim"
                      className="pay-proof-preview-img"
                    />
                  </button>
                ) : null}
              </div>
            )}

            {waHref && (
              <div className="plan-cta-row" style={{ marginTop: 12 }}>
                <a
                  href={waHref}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-ghost plan-cta-primary"
                >
                  <MessageCircle size={15} />
                  <span>Hubungi Admin via WhatsApp</span>
                </a>
              </div>
            )}
          </div>
        )}

        {/* 4. Pilih Paket & Metode Pembayaran Baru */}
        {!isPro && !pending && (
          <>
            {latestUpgrade?.status === 'rejected' && (
              <div className="pay-rejected-alert">
                <XCircle size={16} />
                <div>
                  <strong>
                    Tagihan {latestUpgrade.order_code || `#${latestUpgrade.id}`} Ditolak Admin
                  </strong>
                  <div>
                    {latestUpgrade.admin_note ||
                      'Bukti pembayaran belum sesuai atau dana belum masuk. Silakan ajukan ulang.'}
                  </div>
                </div>
              </div>
            )}

            {/* Toggle Periode Langganan di atas agar harga kartu langsung mencerminkan pilihan */}
            <div className="plan-cycle-toggle">
              <button
                type="button"
                className={`plan-cycle-btn ${billingCycle === 'monthly' ? 'active' : ''}`}
                onClick={() => setBillingCycle('monthly')}
              >
                <span>Bulanan</span>
                <strong className="num-tabular">{formatRp(monthlyPrice)}</strong>
              </button>
              <button
                type="button"
                className={`plan-cycle-btn ${billingCycle === 'yearly' ? 'active' : ''}`}
                onClick={() => setBillingCycle('yearly')}
              >
                <span className="plan-cycle-title-row">
                  <span>Tahunan</span>
                  {yearlySavingsPct > 0 && (
                    <span className="plan-save-chip">Hemat {yearlySavingsPct}%</span>
                  )}
                </span>
                <strong className="num-tabular">{formatRp(yearlyPrice)}</strong>
              </button>
            </div>

            <div className="plan-compare-grid">
              <div className="plan-tier-card is-current">
                <div className="plan-tier-head">
                  <span className="plan-tier-name">{freeName}</span>
                  <span className="plan-tier-badge current">Aktif</span>
                </div>
                <div className="plan-tier-price num-tabular">
                  Rp 0<span className="plan-tier-unit">/selamanya</span>
                </div>
                <div className="plan-alt-price">Cocok untuk coba 1 panel rumah</div>
                <ul className="plan-feature-list">
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>Maks. {freeMaxDevices} panel aktif</span>
                  </li>
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>Pantau Live real-time 10 detik</span>
                  </li>
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>Grafik hingga {freeHistoryDays} hari</span>
                  </li>
                  <li>
                    {freeCfg.forecast_enabled ? (
                      <Check size={14} className="plan-check-icon" />
                    ) : (
                      <Lock size={14} className="plan-lock-icon" />
                    )}
                    <span className={!freeCfg.forecast_enabled ? 'plan-feat-locked' : ''}>
                      Proyeksi tagihan akhir bulan
                    </span>
                  </li>
                  <li>
                    {freeCfg.export_enabled ? (
                      <Check size={14} className="plan-check-icon" />
                    ) : (
                      <Lock size={14} className="plan-lock-icon" />
                    )}
                    <span className={!freeCfg.export_enabled ? 'plan-feat-locked' : ''}>
                      Ekspor laporan CSV
                    </span>
                  </li>
                </ul>
              </div>

              <div className="plan-tier-card is-pro">
                <div className="plan-tier-head">
                  <span className="plan-tier-name">
                    <Crown size={14} className="plan-pro-crown" /> {proName}
                  </span>
                  <span className="plan-tier-badge pro">
                    <Sparkles size={10} /> Rekomendasi
                  </span>
                </div>
                <div className="plan-tier-price num-tabular">
                  {formatRp(selectedPrice)}
                  <span className="plan-tier-unit">
                    /{billingCycle === 'yearly' ? 'tahun' : 'bulan'}
                  </span>
                </div>
                <div className="plan-alt-price num-tabular">
                  {billingCycle === 'yearly' && yearlySavingsRp > 0
                    ? `Hemat ${formatRp(yearlySavingsRp)}/thn (${formatRp(Math.round(yearlyPrice / 12))}/bln)`
                    : `atau ${formatRp(yearlyPrice)}/tahun`}
                </div>
                <ul className="plan-feature-list">
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>
                      {proMaxDevices < 0
                        ? 'Panel aktif tanpa batas'
                        : `Hingga ${proMaxDevices} panel aktif`}
                    </span>
                  </li>
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>Grafik historis hingga {proHistoryDays} hari</span>
                  </li>
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>Proyeksi tagihan akhir bulan otomatis</span>
                  </li>
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>Ekspor laporan konsumsi CSV</span>
                  </li>
                  <li>
                    <Check size={14} className="plan-check-icon" />
                    <span>Deteksi anomali lengkap L2/L3</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Pilihan Metode Pembayaran Manual */}
            <div className="pay-methods-section">
              <div className="pay-methods-head">
                <span className="pay-methods-title">Pilih Metode Pembayaran Manual</span>
                <span className="pay-methods-sub">Verifikasi cepat oleh Admin VoltKu</span>
              </div>
              {methodsLoading ? (
                <div className="pay-methods-loading">Memuat metode pembayaran...</div>
              ) : paymentMethods.length === 0 ? (
                <div className="pay-methods-empty">
                  {instructions ||
                    'Pembayaran dilakukan via konfirmasi manual ke pengelola (QRIS / Transfer / WhatsApp). Klik tombol di bawah untuk membuat pengajuan.'}
                </div>
              ) : (
                <div className="pay-method-grid">
                  {paymentMethods.map((pm) => {
                    const meta = TYPE_META[pm.type] || TYPE_META.bank
                    const Icon = meta.icon
                    const isSelected = selectedMethodId === pm.id
                    return (
                      <button
                        key={pm.id}
                        type="button"
                        className={`pay-method-card ${isSelected ? 'selected' : ''}`}
                        onClick={() => setSelectedMethodId(pm.id)}
                      >
                        <div className="pay-method-card-top">
                          <span className="pay-method-icon-box">
                            <Icon size={15} />
                          </span>
                          <span className="pay-method-type-text">{meta.label}</span>
                          {isSelected && (
                            <span className="pay-method-check">
                              <Check size={12} />
                            </span>
                          )}
                        </div>
                        <div className="pay-method-label">{pm.label}</div>
                        {(pm.account_number || pm.account_holder) && (
                          <div className="pay-method-sub">
                            {pm.account_number ? pm.account_number : `a.n. ${pm.account_holder}`}
                          </div>
                        )}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="form-field-group" style={{ marginTop: 10, marginBottom: 12 }}>
              <input
                id="upgrade-user-note"
                type="text"
                className="modern-input"
                maxLength={140}
                placeholder="Catatan konfirmasi (opsional, mis. nama pengirim transfer/QRIS)"
                value={userNote}
                onChange={(e) => setUserNote(e.target.value)}
              />
            </div>

            <div className="plan-cta-row">
              <button
                type="button"
                className="btn btn-primary plan-cta-primary"
                disabled={submitting}
                onClick={handleCreateOrder}
              >
                <Crown size={15} />
                <span>
                  {submitting
                    ? 'Membuat Tagihan...'
                    : selectedMethod
                      ? `Bayar ${formatRp(selectedPrice)} via ${selectedMethod.label}`
                      : `Ajukan Upgrade (${formatRp(selectedPrice)})`}
                </span>
              </button>
              {waHref && (
                <a href={waHref} target="_blank" rel="noreferrer" className="btn btn-ghost">
                  <MessageCircle size={15} />
                  <span>WhatsApp</span>
                </a>
              )}
            </div>
          </>
        )}
      </div>

      {/* Lightbox Zoom Gambar QRIS / Bukti Transfer */}
      {zoomImageSrc && (
        <div
          className="pay-lightbox-overlay"
          onClick={(e) => {
            e.stopPropagation()
            setZoomImageSrc('')
          }}
        >
          <div className="pay-lightbox-box" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="btn-icon-close pay-lightbox-close"
              onClick={() => setZoomImageSrc('')}
              aria-label="Tutup perbesaran"
            >
              <X size={18} />
            </button>
            <img src={zoomImageSrc} alt="Pratinjau gambar penuh" className="pay-lightbox-img" />
          </div>
        </div>
      )}
    </div>
  )
}
