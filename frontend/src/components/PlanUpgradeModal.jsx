import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
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
  ShieldCheck,
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Tag,
  Ticket,
} from 'lucide-react'
import { MeterPulseIcon, TierShieldIcon } from './VoltKuIcons'
import { apiRequest, buildApiUrl } from '../api/client'
import { formatDateTimeWIB, formatRp } from '../utils/formatters'
import { compressImageToDataUrl } from '../utils/imageCompress'
import { useAuthImage } from '../utils/authImage'
import { emitSyncSignal, subscribeSyncSignal } from '../utils/liveSync'
import mascotProBannerImg from '../assets/mascot/voltku-pro-banner.jpg'

const TYPE_META = {
  qris: { label: 'QRIS', icon: QrCode },
  bank: { label: 'Transfer Bank', icon: Landmark },
  ewallet: { label: 'E-Wallet', icon: Wallet },
}

function formatCountdown(expiresAtEpoch, nowEpoch) {
  if (!expiresAtEpoch) return ''
  const diff = Math.max(0, expiresAtEpoch - nowEpoch)
  const hrs = Math.floor(diff / 3600)
  const mins = String(Math.floor((diff % 3600) / 60)).padStart(2, '0')
  const secs = String(diff % 60).padStart(2, '0')
  return hrs > 0 ? `${String(hrs).padStart(2, '0')}:${mins}:${secs}` : `${mins}:${secs}`
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
  syncTick = 0,
}) {
  // 'tier' (Pilih Paket) -> 'cycle' (Bulanan / Tahunan) -> 'method' (Pilih Pembayaran & Kupon)
  const [browseStage, setBrowseStage] = useState('tier')
  const [selectedPlanSlug, setSelectedPlanSlug] = useState('pro')
  const [billingCycle, setBillingCycle] = useState('monthly')
  const [paymentMethods, setPaymentMethods] = useState([])
  const [methodsLoading, setMethodsLoading] = useState(false)
  const [selectedMethodId, setSelectedMethodId] = useState(null)
  const [userNote, setUserNote] = useState('')
  const [couponInput, setCouponInput] = useState('')
  const [appliedDiscount, setAppliedDiscount] = useState(null)
  const [applyingCoupon, setApplyingCoupon] = useState(false)
  const [couponFeedback, setCouponFeedback] = useState(null)
  const [proofBase64, setProofBase64] = useState('')
  const [proofName, setProofName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [copiedField, setCopiedField] = useState('')
  const [zoomImageSrc, setZoomImageSrc] = useState('')
  const [localPending, setLocalPending] = useState(undefined)
  const [nowSec, setNowSec] = useState(() => Math.floor(Date.now() / 1000))

  const plansItems = appConfig?.plans?.items
  const freeCfg = useMemo(() => appConfig?.plans?.free || {}, [appConfig?.plans?.free])
  const proCfg = useMemo(() => appConfig?.plans?.pro || {}, [appConfig?.plans?.pro])

  const catalogPlans = useMemo(() => {
    if (Array.isArray(plansItems) && plansItems.length > 0) {
      return plansItems
    }
    const baseMonthly = Number(proCfg.price_monthly_rp ?? 30000)
    const baseYearly = Number(proCfg.price_yearly_rp ?? 300000)
    const effMonthly = Number(proCfg.effective_monthly_price_rp ?? baseMonthly)
    const effYearly = Number(proCfg.effective_yearly_price_rp ?? baseYearly)
    const fullYearly = effMonthly * 12
    const yrSaveRp = fullYearly > effYearly ? fullYearly - effYearly : 0
    const yrSavePct =
      yrSaveRp > 0 && fullYearly > 0 ? Math.round((yrSaveRp / fullYearly) * 100) : 0
    return [
      {
        slug: 'free',
        name: freeCfg.name || 'VoltKu Gratis',
        description: 'Cocok untuk mulai memantau 1 panel listrik rumah',
        price_monthly_rp: 0,
        price_yearly_rp: 0,
        effective_monthly_price_rp: 0,
        effective_yearly_price_rp: 0,
        promo_active: false,
        max_devices: Number(freeCfg.max_devices ?? 1),
        history_days: Number(freeCfg.history_days ?? 3),
        forecast_enabled: Boolean(freeCfg.forecast_enabled),
        export_enabled: Boolean(freeCfg.export_enabled),
        anomaly_advanced: Boolean(freeCfg.anomaly_advanced),
        is_default_free: true,
        is_recommended: false,
      },
      {
        slug: proCfg.slug || 'pro',
        name: proCfg.name || 'VoltKu Pro',
        description: 'Kendali energi lengkap dengan proyeksi tagihan & ekspor CSV',
        price_monthly_rp: baseMonthly,
        price_yearly_rp: baseYearly,
        effective_monthly_price_rp: effMonthly,
        effective_yearly_price_rp: effYearly,
        monthly_promo_discount_rp: Math.max(0, baseMonthly - effMonthly),
        yearly_promo_discount_rp: Math.max(0, baseYearly - effYearly),
        promo_active: Boolean(proCfg.promo_active),
        promo_discount_type: proCfg.promo_discount_type || null,
        promo_discount_value: proCfg.promo_discount_value || 0,
        promo_label: proCfg.promo_label || '',
        yearly_savings_rp: Number(proCfg.yearly_savings_rp ?? yrSaveRp),
        yearly_savings_pct: Number(proCfg.yearly_savings_pct ?? yrSavePct),
        max_devices: Number(proCfg.max_devices ?? 10),
        history_days: Number(proCfg.history_days ?? 90),
        forecast_enabled: proCfg.forecast_enabled !== false,
        export_enabled: proCfg.export_enabled !== false,
        anomaly_advanced: proCfg.anomaly_advanced !== false,
        is_default_free: false,
        is_recommended: true,
      },
    ]
  }, [plansItems, freeCfg, proCfg])

  const paidPlans = useMemo(
    () => catalogPlans.filter((p) => !p.is_default_free && p.slug !== 'free'),
    [catalogPlans]
  )

  const defaultPaidPlan = useMemo(
    () => paidPlans.find((p) => p.is_recommended) || paidPlans[0] || { slug: 'pro', name: 'VoltKu Pro' },
    [paidPlans]
  )

  const selectedPlan = useMemo(
    () => paidPlans.find((p) => p.slug === selectedPlanSlug) || defaultPaidPlan,
    [paidPlans, selectedPlanSlug, defaultPaidPlan]
  )

  const freePlanObj = useMemo(
    () => catalogPlans.find((p) => p.is_default_free || p.slug === 'free') || freeCfg,
    [catalogPlans, freeCfg]
  )

  const selectedPlanName = selectedPlan?.name || 'VoltKu Pro'
  const freeName = freePlanObj?.name || 'VoltKu Gratis'
  const baseMonthlyPrice = Number(selectedPlan?.price_monthly_rp ?? 30000)
  const baseYearlyPrice = Number(selectedPlan?.price_yearly_rp ?? 300000)
  const effMonthlyPrice = Number(selectedPlan?.effective_monthly_price_rp ?? baseMonthlyPrice)
  const effYearlyPrice = Number(selectedPlan?.effective_yearly_price_rp ?? baseYearlyPrice)
  const hasMonthlyPromo =
    Boolean(selectedPlan?.promo_active) && baseMonthlyPrice > effMonthlyPrice
  const hasYearlyPromo =
    Boolean(selectedPlan?.promo_active) && baseYearlyPrice > effYearlyPrice
  const instructions = appConfig?.plans?.upgrade_instructions || proCfg.upgrade_instructions || ''
  const waRaw = String(appConfig?.support_whatsapp || '').replace(/[^0-9]/g, '')

  const userPlan = currentUser?.plan || {}
  const isPro = Boolean(userPlan.is_pro)
  const pending = localPending !== undefined ? localPending : userPlan.pending_upgrade || null
  const latestUpgrade = userPlan.latest_upgrade || null
  const activeStepStatus = pending?.status || ''

  // Hitung penghematan paket tahunan secara deterministik dari harga bulanan x 12
  const yearlyFullPrice = effMonthlyPrice * 12
  const yearlySavingsRp = yearlyFullPrice > effYearlyPrice ? yearlyFullPrice - effYearlyPrice : 0
  const yearlySavingsPct =
    yearlySavingsRp > 0 && yearlyFullPrice > 0
      ? Math.round((yearlySavingsRp / yearlyFullPrice) * 100)
      : 0

  const checkoutStepNum = useMemo(() => {
    if (isPro) return 5
    if (activeStepStatus === 'verifying') return 4
    if (activeStepStatus === 'awaiting_payment' || activeStepStatus === 'pending') return 3
    if (browseStage === 'method') return 3
    if (browseStage === 'cycle') return 2
    return 1
  }, [isPro, activeStepStatus, browseStage])

  const prevProRef = useRef(isPro)

  const loadPaymentMethods = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setMethodsLoading(true)
    try {
      const list = await apiRequest('/api/public/payment-methods')
      const items = Array.isArray(list) ? list : []
      setPaymentMethods(items)
      setSelectedMethodId((prev) => {
        if (prev && items.some((m) => m.id === prev)) return prev
        return items[0]?.id ?? null
      })
    } catch {
      if (!silent) setPaymentMethods([])
    } finally {
      if (!silent) setMethodsLoading(false)
    }
  }, [])

  // Reset saat modal dibuka/ditutup dan muat daftar metode pembayaran aktif
  useEffect(() => {
    if (!isOpen) {
      prevProRef.current = isPro
      setBrowseStage('tier')
      setFeedback(null)
      setCouponInput('')
      setAppliedDiscount(null)
      setCouponFeedback(null)
      setProofBase64('')
      setProofName('')
      setZoomImageSrc('')
      setLocalPending(undefined)
      return undefined
    }
    prevProRef.current = isPro
    setBrowseStage('tier')
    setSelectedPlanSlug(defaultPaidPlan.slug || 'pro')
    setCouponInput('')
    setAppliedDiscount(null)
    setCouponFeedback(null)
    setLocalPending(undefined)
    loadPaymentMethods({ silent: false })
    return subscribeSyncSignal((sig) => {
      if (sig?.scope === 'public' || sig?.scope === 'all') {
        loadPaymentMethods({ silent: true })
      }
    })
  }, [isOpen, loadPaymentMethods]) // eslint-disable-line react-hooks/exhaustive-deps

  // Sinkronkan metode bayar secara senyap jika Admin mengubah saat modal terbuka
  useEffect(() => {
    if (!isOpen || syncTick <= 0) return
    loadPaymentMethods({ silent: true })
  }, [isOpen, syncTick, loadPaymentMethods])

  // Tampilkan feedback otomatis jika Admin menyetujui saat modal checkout terbuka
  useEffect(() => {
    if (isOpen && !prevProRef.current && isPro) {
      setFeedback({
        type: 'success',
        text: `Pembayaran dikonfirmasi! Paket ${userPlan.plan_name || selectedPlanName} Anda kini aktif.`,
      })
    }
    prevProRef.current = isPro
  }, [isOpen, isPro, userPlan.plan_name, selectedPlanName])

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

  const activeQuoteMatch = Boolean(
    appliedDiscount &&
      appliedDiscount.plan_slug === selectedPlan.slug &&
      appliedDiscount.billing_cycle === billingCycle
  )
  const baseOrderAmount = billingCycle === 'yearly' ? baseYearlyPrice : baseMonthlyPrice
  const afterPromoAmount = billingCycle === 'yearly' ? effYearlyPrice : effMonthlyPrice
  const promoDiscAmount = Math.max(0, baseOrderAmount - afterPromoAmount)
  const voucherDiscAmount = activeQuoteMatch
    ? Number(appliedDiscount.voucher_discount_rp || 0)
    : 0
  const selectedPrice = activeQuoteMatch
    ? Number(appliedDiscount.final_amount_rp ?? afterPromoAmount)
    : afterPromoAmount

  const selectedMethod = paymentMethods.find((m) => m.id === selectedMethodId) || null
  const isExpiredInvoice = Boolean(
    pending?.expires_at && activeStepStatus === 'awaiting_payment' && pending.expires_at <= nowSec
  )

  const activeOrderPlanName =
    pending?.plan_name_snapshot ||
    catalogPlans.find((p) => p.slug === pending?.requested_tier)?.name ||
    selectedPlanName

  const waHref = (() => {
    if (!waRaw) return ''
    const waNumber = waRaw.startsWith('0') ? `62${waRaw.slice(1)}` : waRaw
    const orderInfo = pending?.order_code ? ` (Kode: ${pending.order_code})` : ''
    const cycleText =
      (pending?.billing_cycle || billingCycle) === 'yearly' ? 'Tahunan' : 'Bulanan'
    const text = encodeURIComponent(
      `Halo Admin VoltKu, saya ${currentUser?.name || 'Pengguna'} (${currentUser?.email || '-'}) ingin konfirmasi upgrade ${activeOrderPlanName} paket ${cycleText}${orderInfo}.`
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

  const handleApplyCoupon = async (overrideCode = null, overridePlanSlug = null, overrideCycle = null) => {
    if (!token) return
    const codeText = String(overrideCode !== null ? overrideCode : couponInput).trim().toUpperCase()
    const planSlug = overridePlanSlug || selectedPlan.slug
    const cycle = overrideCycle || billingCycle
    if (!codeText) {
      setAppliedDiscount(null)
      setCouponFeedback({ type: 'error', text: 'Masukkan kode kupon terlebih dahulu.' })
      return
    }
    setApplyingCoupon(true)
    setCouponFeedback(null)
    try {
      const quote = await apiRequest(
        '/api/users/apply-discount',
        {
          method: 'POST',
          body: {
            plan_slug: planSlug,
            billing_cycle: cycle,
            discount_code: codeText,
          },
        },
        token,
        onLogout
      )
      setCouponInput(quote.discount_code || codeText)
      setAppliedDiscount(quote)
      setCouponFeedback({
        type: 'success',
        text: `Kupon ${quote.discount_code} berhasil diterapkan (-${formatRp(quote.voucher_discount_rp)})`,
      })
    } catch (err) {
      setAppliedDiscount(null)
      setCouponFeedback({ type: 'error', text: err.message || 'Kode kupon tidak valid.' })
    } finally {
      setApplyingCoupon(false)
    }
  }

  const handleRemoveCoupon = () => {
    setCouponInput('')
    setAppliedDiscount(null)
    setCouponFeedback(null)
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
            plan_slug: selectedPlan.slug,
            billing_cycle: billingCycle,
            discount_code: activeQuoteMatch ? appliedDiscount.discount_code : null,
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
      emitSyncSignal('admin', { source: 'customer-order-created', orderId: created.id })
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
      emitSyncSignal('admin', { source: 'customer-proof-uploaded', orderId: pending.id })
      if (onUpgradeSubmitted) await onUpgradeSubmitted()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message || 'Gagal mengirim bukti pembayaran.' })
    } finally {
      setSubmitting(false)
    }
  }

  const cancelPendingOrder = async ({ nextStage = 'tier', feedbackText = '' } = {}) => {
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
      setBrowseStage(nextStage)
      setProofBase64('')
      setProofName('')
      setFeedback({
        type: 'success',
        text: feedbackText || 'Transaksi dibatalkan.',
      })
      emitSyncSignal('admin', { source: 'customer-order-cancelled', orderId: pending.id })
      if (onUpgradeSubmitted) await onUpgradeSubmitted()
    } catch (err) {
      setFeedback({ type: 'error', text: err.message || 'Gagal membatalkan tagihan.' })
    } finally {
      setCancelling(false)
    }
  }

  const handleChangeMethod = async () => {
    if (pending?.requested_tier) setSelectedPlanSlug(pending.requested_tier)
    if (pending?.billing_cycle) setBillingCycle(pending.billing_cycle)
    await cancelPendingOrder({
      nextStage: 'method',
      feedbackText: 'Tagihan sebelumnya dibatalkan. Silakan pilih metode pembayaran lain.',
    })
  }

  const handleCancelOrder = async () => {
    await cancelPendingOrder({
      nextStage: 'tier',
      feedbackText: 'Transaksi dibatalkan. Anda dapat memilih paket lain kapan saja.',
    })
  }

  const pendingTypeMeta = TYPE_META[pending?.payment_method_type] || TYPE_META.bank
  const PendingMethodIcon = pendingTypeMeta.icon

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className={`modal-dialog-modern pwa-guide-sheet plan-modal-dialog ${
          !isPro && !pending && browseStage === 'tier' && catalogPlans.length > 2 ? 'is-wide' : ''
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="plan-sticky-head">
          <div className="pwa-guide-head" style={{ marginBottom: !isPro && checkoutStepNum >= 2 ? 10 : 0 }}>
            <div className="plan-modal-head-left">
              <span className={`plan-crown-badge ${isPro ? 'is-pro' : ''}`}>
                <Crown size={18} />
              </span>
              <div>
                <h3 className="pwa-guide-title">
                  {pending
                    ? `Pembayaran ${activeOrderPlanName}`
                    : checkoutStepNum === 2
                      ? `Pilih Durasi ${selectedPlanName}`
                      : checkoutStepNum === 3
                        ? 'Metode Pembayaran & Kupon'
                        : `Pilih Paket ${appConfig?.app_name || 'VoltKu'}`}
                </h3>
                <p className="pwa-guide-sub">
                  {isPro
                    ? `Langganan ${userPlan.plan_name || selectedPlanName} Anda sedang aktif`
                    : pending
                      ? `Tagihan ${pending.order_code || `#${pending.id}`}`
                      : checkoutStepNum === 2
                        ? 'Pilih siklus langganan bulanan atau tahunan'
                        : checkoutStepNum === 3
                          ? 'Gunakan kode promo bila ada & pilih metode transfer / QRIS'
                          : 'Mulai gratis selamanya atau pilih paket sesuai kebutuhan panel'}
                </p>
              </div>
            </div>
            <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
              <X size={18} />
            </button>
          </div>

          {/* Stepper baru muncul setelah user memilih paket (tahap 2 ke atas) */}
          {!isPro && checkoutStepNum >= 2 && (
            <div className="plan-steps-bar" aria-label="Tahapan Upgrade Paket">
              {[
                { num: 1, label: 'Paket', stage: 'tier' },
                { num: 2, label: 'Durasi', stage: 'cycle' },
                { num: 3, label: 'Bayar', stage: 'method' },
                { num: 4, label: 'Verifikasi', stage: null },
              ].map((s, idx) => {
                const isDone = checkoutStepNum > s.num
                const isActive = checkoutStepNum === s.num
                const canJumpBack = Boolean(!pending && s.stage && isDone)
                return (
                  <React.Fragment key={s.num}>
                    {idx > 0 && <span className="plan-step-sep" aria-hidden="true" />}
                    <button
                      type="button"
                      disabled={!canJumpBack}
                      className={`plan-step-pill ${isActive ? 'active' : isDone ? 'done' : ''} ${
                        canJumpBack ? 'is-clickable' : ''
                      }`}
                      onClick={() => {
                        if (canJumpBack && s.stage) {
                          setFeedback(null)
                          setBrowseStage(s.stage)
                        }
                      }}
                    >
                      <span className="plan-step-num">{isDone ? '✓' : s.num}</span>
                      <span>{s.label}</span>
                    </button>
                  </React.Fragment>
                )
              })}
            </div>
          )}
        </div>

        <div className="plan-scroll-body">
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

        {/* 1. User sudah berlangganan berbayar */}
        {isPro && (
          <div className="plan-pro-active-card">
            <div className="plan-pro-active-head">
              <div className="plan-pro-active-icon">
                <ShieldCheck size={22} />
              </div>
              <div className="plan-pro-active-copy">
                <div className="plan-pro-active-title">
                  <strong>{userPlan.plan_name || selectedPlanName} Aktif</strong>
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
                  {(userPlan.limits?.max_devices ?? 10) < 0 ? '∞' : userPlan.limits?.max_devices ?? 10}
                </strong>
              </div>
              <div className="plan-pro-stat-box">
                <span>Retensi Riwayat</span>
                <strong className="num-tabular">
                  {userPlan.limits?.history_days ?? 90} Hari
                </strong>
              </div>
            </div>

            <ul className="plan-feature-list" style={{ marginTop: 12 }}>
              <li>
                {userPlan.limits?.forecast_enabled !== false ? (
                  <Check size={14} className="plan-check-icon" />
                ) : (
                  <Lock size={14} className="plan-lock-icon" />
                )}
                <span>Proyeksi tagihan PLN otomatis akhir bulan</span>
              </li>
              <li>
                {userPlan.limits?.export_enabled !== false ? (
                  <Check size={14} className="plan-check-icon" />
                ) : (
                  <Lock size={14} className="plan-lock-icon" />
                )}
                <span>Ekspor laporan konsumsi CSV</span>
              </li>
              <li>
                {userPlan.limits?.anomaly_advanced !== false ? (
                  <Check size={14} className="plan-check-icon" />
                ) : (
                  <Lock size={14} className="plan-lock-icon" />
                )}
                <span>Deteksi anomali lengkap L2/L3</span>
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
                      ? `${activeOrderPlanName} · Tahunan`
                      : `${activeOrderPlanName} · Bulanan`}
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

              {(Number(pending.promo_discount_rp || 0) > 0 ||
                Number(pending.voucher_discount_rp || 0) > 0) && (
                <div className="pay-discount-breakdown num-tabular">
                  <span>Harga normal {formatRp(pending.base_amount_rp)}</span>
                  {Number(pending.promo_discount_rp || 0) > 0 && (
                    <span className="pay-discount-pill">
                      Promo -{formatRp(pending.promo_discount_rp)}
                    </span>
                  )}
                  {Number(pending.voucher_discount_rp || 0) > 0 && (
                    <span className="pay-discount-pill is-voucher">
                      Kupon {pending.discount_code || ''} -{formatRp(pending.voucher_discount_rp)}
                    </span>
                  )}
                </div>
              )}

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
                  {pending.payment_method_type === 'qris' && pending.payment_account_holder && (
                    <span className="pay-target-holder-inline">
                      a.n. {pending.payment_account_holder}
                    </span>
                  )}
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

                {!pending.payment_account_number &&
                  pending.payment_method_type !== 'qris' &&
                  pending.payment_account_holder && (
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
                  <div className="plan-cta-secondary-row">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={cancelling || submitting}
                      onClick={handleChangeMethod}
                    >
                      <RotateCcw size={14} />
                      <span>{cancelling ? 'Memproses...' : 'Ganti Metode'}</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger-ghost"
                      disabled={cancelling || submitting}
                      onClick={handleCancelOrder}
                    >
                      <XCircle size={14} />
                      <span>{cancelling ? 'Membatalkan...' : 'Batalkan Transaksi'}</span>
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="plan-cta-row">
                <button
                  type="button"
                  className="btn btn-primary plan-cta-primary"
                  disabled={cancelling}
                  onClick={handleChangeMethod}
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
                  {pending.billing_cycle === 'yearly'
                    ? `${activeOrderPlanName} Tahunan`
                    : `${activeOrderPlanName} Bulanan`}
                </strong>{' '}
                · <strong className="num-tabular">{formatRp(pending.amount_rp)}</strong>
              </div>
              {pending.discount_code && Number(pending.voucher_discount_rp || 0) > 0 && (
                <div className="pay-verifying-sub num-tabular">
                  Kupon {pending.discount_code} (-{formatRp(pending.voucher_discount_rp)})
                </div>
              )}
              <div className="pay-verifying-sub">
                Metode: {pending.payment_method_label || 'Manual'}
                {pending.submitted_at ? ` · Dikirim ${formatDateTimeWIB(pending.submitted_at)}` : ''}
              </div>
              <p className="pay-verifying-desc">
                Terima kasih! Bukti pembayaran Anda sudah kami terima dan sedang diperiksa oleh
                pengelola. Paket {activeOrderPlanName} akan aktif otomatis setelah dikonfirmasi.
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

        {/* 4. Alur Pemilihan Paket -> Durasi -> Metode Pembayaran */}
        {!isPro && !pending && (
          <>
            {latestUpgrade?.status === 'rejected' && browseStage === 'tier' && (
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

            {/* TAHAP 1: Daftar Paket Dinamis dari Admin (Gratis + Semua Paket Berbayar Aktif) */}
            {browseStage === 'tier' && (
              <>
                <div className="plan-pro-showcase">
                  <img
                    src={mascotProBannerImg}
                    alt="VoltKu Pro Monitoring Listrik Pintar"
                    className="plan-pro-showcase-img"
                  />
                </div>
                <div
                  className={`plan-compare-grid ${catalogPlans.length > 2 ? 'is-multi' : ''}`}
                >
                {catalogPlans.map((planItem) => {
                  const isFreeCard = Boolean(planItem.is_default_free || planItem.slug === 'free')
                  const pBaseMonth = Number(planItem.price_monthly_rp ?? 0)
                  const pEffMonth = Number(planItem.effective_monthly_price_rp ?? pBaseMonth)
                  const pBaseYear = Number(planItem.price_yearly_rp ?? 0)
                  const pEffYear = Number(planItem.effective_yearly_price_rp ?? pBaseYear)
                  const hasCardPromo =
                    !isFreeCard && Boolean(planItem.promo_active) && pBaseMonth > pEffMonth
                  const cardYrSavePct = Number(planItem.yearly_savings_pct ?? 0)
                  const pMaxDev = Number(planItem.max_devices ?? 1)
                  const pHistDays = Number(planItem.history_days ?? 3)
                  const builtinLines = new Set([
                    (pMaxDev < 0 ? 'panel aktif tanpa batas' : `hingga ${pMaxDev} panel aktif`),
                    `grafik historis hingga ${pHistDays} hari`,
                    'proyeksi tagihan akhir bulan otomatis',
                    'ekspor laporan konsumsi csv',
                    'deteksi anomali lengkap l2/l3',
                  ])
                  const customBullets = Array.isArray(planItem.features)
                    ? planItem.features
                        .filter((f) => {
                          const norm = String(f || '').trim().toLowerCase()
                          return norm && !builtinLines.has(norm)
                        })
                        .slice(0, 3)
                    : []

                  if (isFreeCard) {
                    return (
                      <button
                        key={planItem.slug || 'free'}
                        type="button"
                        className="plan-tier-card is-current is-clickable-card"
                        onClick={() => {
                          setFeedback({
                            type: 'success',
                            text: `Anda saat ini sudah aktif menggunakan paket ${freeName}. Pilih paket berbayar untuk upgrade.`,
                          })
                        }}
                      >
                        <div className="plan-tier-head">
                          <span className="plan-tier-name">{planItem.name || freeName}</span>
                          <span className="plan-tier-badge current">Aktif</span>
                        </div>
                        <div className="plan-tier-price num-tabular">
                          Rp 0<span className="plan-tier-unit">/selamanya</span>
                        </div>
                        <div className="plan-alt-price">
                          {planItem.description || 'Cocok untuk coba pantau panel rumah'}
                        </div>
                        <ul className="plan-feature-list">
                          <li>
                            <Check size={14} className="plan-check-icon" />
                            <span>
                              {pMaxDev < 0
                                ? 'Panel aktif tanpa batas'
                                : `Maks. ${pMaxDev} panel aktif`}
                            </span>
                          </li>
                          <li>
                            <Check size={14} className="plan-check-icon" />
                            <span>Pantau Live real-time 10 detik</span>
                          </li>
                          <li>
                            <Check size={14} className="plan-check-icon" />
                            <span>Grafik hingga {pHistDays} hari</span>
                          </li>
                          <li>
                            {planItem.forecast_enabled ? (
                              <Check size={14} className="plan-check-icon" />
                            ) : (
                              <Lock size={14} className="plan-lock-icon" />
                            )}
                            <span className={!planItem.forecast_enabled ? 'plan-feat-locked' : ''}>
                              Proyeksi tagihan akhir bulan
                            </span>
                          </li>
                          <li>
                            {planItem.export_enabled ? (
                              <Check size={14} className="plan-check-icon" />
                            ) : (
                              <Lock size={14} className="plan-lock-icon" />
                            )}
                            <span className={!planItem.export_enabled ? 'plan-feat-locked' : ''}>
                              Ekspor laporan CSV
                            </span>
                          </li>
                        </ul>
                        <div className="plan-tier-footer-cta is-current">
                          <Check size={14} />
                          <span>Paket Anda Saat Ini</span>
                        </div>
                      </button>
                    )
                  }

                  const promoBadgeLabel =
                    planItem.promo_label ||
                    (planItem.promo_discount_type === 'percent' && planItem.promo_discount_value
                      ? `Promo -${planItem.promo_discount_value}%`
                      : 'Promo Spesial')

                  return (
                    <button
                      key={planItem.slug}
                      type="button"
                      className={`plan-tier-card is-pro is-clickable-card ${
                        planItem.is_recommended ? 'is-recommended' : ''
                      }`}
                      onClick={() => {
                        setFeedback(null)
                        if (selectedPlanSlug !== planItem.slug) {
                          setAppliedDiscount(null)
                          setCouponFeedback(null)
                        }
                        setSelectedPlanSlug(planItem.slug)
                        setBrowseStage('cycle')
                      }}
                    >
                      <div className="plan-tier-head">
                        <span className="plan-tier-name">
                          <Crown size={14} className="plan-pro-crown" /> {planItem.name}
                        </span>
                        <div className="plan-tier-badge-group">
                          {hasCardPromo && (
                            <span className="plan-tier-badge is-promo">
                              <Tag size={10} /> {promoBadgeLabel}
                            </span>
                          )}
                          {(planItem.badge_text || planItem.is_recommended) && (
                            <span className="plan-tier-badge pro">
                              <TierShieldIcon size={11} />{' '}
                              {planItem.badge_text &&
                              planItem.badge_text.trim().toLowerCase() !== 'rekomendasi'
                                ? planItem.badge_text
                                : 'Rekomendasi'}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="plan-tier-price-stack num-tabular">
                        {hasCardPromo && (
                          <div className="plan-price-strike-row">
                            <span className="plan-price-strike">{formatRp(pBaseMonth)}</span>
                            <span className="plan-promo-save-note">Harga Promo</span>
                          </div>
                        )}
                        <div className="plan-tier-price">
                          <span className="plan-tier-prefix">Mulai</span> {formatRp(pEffMonth)}
                          <span className="plan-tier-unit">/bulan</span>
                        </div>
                      </div>

                      <div className="plan-alt-price num-tabular">
                        {cardYrSavePct > 0
                          ? `Atau ${formatRp(pEffYear)}/tahun (hemat ${cardYrSavePct}%)`
                          : `Atau ${formatRp(pEffYear)}/tahun`}
                      </div>

                      <ul className="plan-feature-list">
                        <li>
                          <Check size={14} className="plan-check-icon" />
                          <span>
                            {pMaxDev < 0 ? 'Panel aktif tanpa batas' : `Hingga ${pMaxDev} panel aktif`}
                          </span>
                        </li>
                        <li>
                          <Check size={14} className="plan-check-icon" />
                          <span>Grafik historis hingga {pHistDays} hari</span>
                        </li>
                        <li>
                          {planItem.forecast_enabled !== false ? (
                            <Check size={14} className="plan-check-icon" />
                          ) : (
                            <Lock size={14} className="plan-lock-icon" />
                          )}
                          <span
                            className={
                              planItem.forecast_enabled === false ? 'plan-feat-locked' : ''
                            }
                          >
                            Proyeksi tagihan akhir bulan otomatis
                          </span>
                        </li>
                        <li>
                          {planItem.export_enabled !== false ? (
                            <Check size={14} className="plan-check-icon" />
                          ) : (
                            <Lock size={14} className="plan-lock-icon" />
                          )}
                          <span
                            className={planItem.export_enabled === false ? 'plan-feat-locked' : ''}
                          >
                            Ekspor laporan konsumsi CSV
                          </span>
                        </li>
                        <li>
                          {planItem.anomaly_advanced !== false ? (
                            <Check size={14} className="plan-check-icon" />
                          ) : (
                            <Lock size={14} className="plan-lock-icon" />
                          )}
                          <span
                            className={
                              planItem.anomaly_advanced === false ? 'plan-feat-locked' : ''
                            }
                          >
                            Deteksi anomali lengkap L2/L3
                          </span>
                        </li>
                        {customBullets.map((bText, bIdx) => (
                          <li key={bIdx}>
                            <Check size={14} className="plan-check-icon" />
                            <span>{bText}</span>
                          </li>
                        ))}
                      </ul>
                      <div className="plan-tier-footer-cta is-pro">
                        <span>Pilih {planItem.name}</span>
                        <ArrowRight size={15} />
                      </div>
                    </button>
                  )
                })}
              </div>
              </>
            )}

            {/* TAHAP 2: Pilih Siklus Bulanan / Tahunan */}
            {browseStage === 'cycle' && (
              <div className="plan-stage-stack">
                <div className="plan-selected-bar">
                  <div className="plan-selected-bar-copy">
                    <Crown size={15} className="plan-pro-crown" />
                    <span>
                      Paket dipilih: <strong>{selectedPlanName}</strong>
                    </span>
                  </div>
                  <button
                    type="button"
                    className="plan-change-link"
                    onClick={() => {
                      setFeedback(null)
                      setBrowseStage('tier')
                    }}
                  >
                    Ubah Paket
                  </button>
                </div>

                <div className="plan-duration-grid">
                  <button
                    type="button"
                    className={`plan-duration-card ${billingCycle === 'monthly' ? 'selected' : ''}`}
                    onClick={() => {
                      setBillingCycle('monthly')
                      setAppliedDiscount(null)
                      setCouponFeedback(null)
                    }}
                  >
                    <div className="plan-duration-top">
                      <span className="plan-duration-radio" aria-hidden="true">
                        {billingCycle === 'monthly' && <Check size={11} strokeWidth={3} />}
                      </span>
                      <div className="plan-duration-meta">
                        <span className="plan-duration-name">
                          <CalendarDays size={14} /> Paket Bulanan
                        </span>
                        <span className="plan-duration-desc">Aktif 30 hari · Bayar fleksibel tiap bulan</span>
                      </div>
                    </div>
                    <div className="plan-duration-price-row num-tabular">
                      {hasMonthlyPromo && (
                        <span className="plan-price-strike">{formatRp(baseMonthlyPrice)}</span>
                      )}
                      <strong>{formatRp(effMonthlyPrice)}</strong>
                      <span>/bulan</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className={`plan-duration-card is-best ${billingCycle === 'yearly' ? 'selected' : ''}`}
                    onClick={() => {
                      setBillingCycle('yearly')
                      setAppliedDiscount(null)
                      setCouponFeedback(null)
                    }}
                  >
                    <div className="plan-duration-top">
                      <span className="plan-duration-radio" aria-hidden="true">
                        {billingCycle === 'yearly' && <Check size={11} strokeWidth={3} />}
                      </span>
                      <div className="plan-duration-meta">
                        <div className="plan-duration-title-row">
                          <span className="plan-duration-name">
                            <MeterPulseIcon size={14} /> Paket Tahunan
                          </span>
                          {yearlySavingsPct > 0 && (
                            <span className="plan-save-chip">Hemat {yearlySavingsPct}%</span>
                          )}
                        </div>
                        <span className="plan-duration-desc">
                          {yearlySavingsRp > 0
                            ? `Aktif 1 tahun penuh · Hemat ${formatRp(yearlySavingsRp)} (${formatRp(
                                Math.round(effYearlyPrice / 12)
                              )}/bln)`
                            : 'Aktif 1 tahun penuh (365 hari)'}
                        </span>
                      </div>
                    </div>
                    <div className="plan-duration-price-row num-tabular">
                      {hasYearlyPromo && (
                        <span className="plan-price-strike">{formatRp(baseYearlyPrice)}</span>
                      )}
                      <strong>{formatRp(effYearlyPrice)}</strong>
                      <span>/tahun</span>
                    </div>
                  </button>
                </div>

                <div className="plan-stage-footer">
                  <button
                    type="button"
                    className="btn btn-secondary plan-btn-back"
                    onClick={() => {
                      setFeedback(null)
                      setBrowseStage('tier')
                    }}
                  >
                    <ArrowLeft size={15} />
                    <span>Kembali</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary plan-btn-next"
                    onClick={() => {
                      setFeedback(null)
                      setBrowseStage('method')
                    }}
                  >
                    <span>Lanjut ke Pembayaran</span>
                    <ArrowRight size={15} />
                  </button>
                </div>
              </div>
            )}

            {/* TAHAP 3A: Kode Kupon, Pilih Metode Pembayaran & Buat Tagihan */}
            {browseStage === 'method' && (
              <div className="plan-stage-stack">
                <div className="plan-order-summary-card is-detailed">
                  <div className="plan-order-summary-top">
                    <div className="plan-order-summary-left">
                      <span className="plan-order-summary-label">Ringkasan Pesanan</span>
                      <div className="plan-order-summary-name">
                        {selectedPlanName} ·{' '}
                        {billingCycle === 'yearly' ? 'Tahunan (12 Bulan)' : 'Bulanan (1 Bulan)'}
                      </div>
                    </div>
                    <div className="plan-order-summary-right num-tabular">
                      {(promoDiscAmount > 0 || voucherDiscAmount > 0) && (
                        <span className="plan-price-strike">{formatRp(baseOrderAmount)}</span>
                      )}
                      <strong className="plan-order-summary-total">{formatRp(selectedPrice)}</strong>
                      <button
                        type="button"
                        className="plan-change-link"
                        onClick={() => {
                          setFeedback(null)
                          setBrowseStage('cycle')
                        }}
                      >
                        Ubah Durasi
                      </button>
                    </div>
                  </div>

                  {(promoDiscAmount > 0 || voucherDiscAmount > 0) && (
                    <div className="plan-order-breakdown num-tabular">
                      <div className="plan-order-bk-row">
                        <span>Harga Reguler</span>
                        <span>{formatRp(baseOrderAmount)}</span>
                      </div>
                      {promoDiscAmount > 0 && (
                        <div className="plan-order-bk-row is-save">
                          <span>
                            Diskon Promo
                            {selectedPlan?.promo_label ? ` (${selectedPlan.promo_label})` : ''}
                          </span>
                          <span>-{formatRp(promoDiscAmount)}</span>
                        </div>
                      )}
                      {voucherDiscAmount > 0 && (
                        <div className="plan-order-bk-row is-save">
                          <span>Kupon {appliedDiscount?.discount_code}</span>
                          <span>-{formatRp(voucherDiscAmount)}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Kotak Kode Kupon / Voucher Promo */}
                <div className="pay-coupon-box">
                  <div className="pay-coupon-head">
                    <Ticket size={14} />
                    <span>Punya Kode Kupon / Voucher?</span>
                  </div>
                  <div className="pay-coupon-row">
                    <input
                      id="upgrade-coupon-input"
                      type="text"
                      className="modern-input pay-coupon-input num-tabular"
                      placeholder="Masukkan kode kupon (mis. HEMAT30)"
                      value={couponInput}
                      disabled={applyingCoupon}
                      onChange={(e) =>
                        setCouponInput(e.target.value.toUpperCase().replace(/\s+/g, ''))
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          handleApplyCoupon()
                        }
                      }}
                    />
                    {activeQuoteMatch ? (
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-compact"
                        onClick={handleRemoveCoupon}
                      >
                        <X size={14} />
                        <span>Hapus</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-secondary btn-compact"
                        disabled={applyingCoupon || !couponInput.trim()}
                        onClick={() => handleApplyCoupon()}
                      >
                        <span>{applyingCoupon ? 'Mengecek...' : 'Terapkan'}</span>
                      </button>
                    )}
                  </div>
                  {couponFeedback && (
                    <div
                      className={`pay-coupon-msg ${
                        couponFeedback.type === 'error' ? 'is-error' : 'is-success'
                      }`}
                    >
                      {couponFeedback.text}
                    </div>
                  )}
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
                        'Pembayaran dilakukan via konfirmasi manual ke pengelola (QRIS / Transfer / WhatsApp). Klik tombol di bawah untuk membuat tagihan.'}
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

                <div className="form-field-group" style={{ marginBottom: 0 }}>
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

                <div className="plan-stage-footer">
                  <button
                    type="button"
                    className="btn btn-secondary plan-btn-back"
                    disabled={submitting}
                    onClick={() => {
                      setFeedback(null)
                      setBrowseStage('cycle')
                    }}
                  >
                    <ArrowLeft size={15} />
                    <span>Kembali</span>
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary plan-btn-next"
                    disabled={submitting}
                    onClick={handleCreateOrder}
                  >
                    <Crown size={15} />
                    <span>
                      {submitting
                        ? 'Membuat Tagihan...'
                        : selectedMethod
                          ? `Bayar ${formatRp(selectedPrice)} via ${selectedMethod.label}`
                          : `Buat Tagihan (${formatRp(selectedPrice)})`}
                    </span>
                  </button>
                  {waHref && (
                    <a
                      href={waHref}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-ghost plan-wa-icon-btn"
                      title="Tanya Admin via WhatsApp"
                      aria-label="Tanya Admin via WhatsApp"
                    >
                      <MessageCircle size={16} />
                    </a>
                  )}
                </div>
              </div>
            )}
          </>
        )}
        </div>
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
