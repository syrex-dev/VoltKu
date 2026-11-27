import React, { useState, useMemo } from 'react'
import {
  Crown,
  Sparkles,
  Tag,
  Ticket,
  Plus,
  Pencil,
  Trash2,
  X,
  Save,
  Copy,
  Check,
  Search,
  Percent,
  CalendarClock,
  Users,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatDateTimeWIB, formatRp } from '../utils/formatters'
import { InAppSelect } from './InAppSelect'

const WIB_OFFSET_SEC = 7 * 3600

function epochToWibInput(epochSec) {
  if (!epochSec || Number.isNaN(Number(epochSec))) return ''
  const ms = (Number(epochSec) + WIB_OFFSET_SEC) * 1000
  return new Date(ms).toISOString().slice(0, 16)
}

function wibInputToEpoch(strVal) {
  const clean = String(strVal || '').trim()
  if (!clean) return null
  const normalized = clean.length === 16 ? `${clean}:00+07:00` : `${clean}+07:00`
  const ms = Date.parse(normalized)
  if (Number.isNaN(ms)) return null
  return Math.floor(ms / 1000)
}

function slugifyPlanName(val) {
  return String(val || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 32)
}

function computeClientPromoPreview(baseRp, promoType, promoValue) {
  const base = Math.max(0, Number(baseRp || 0))
  const val = Math.max(0, Number(promoValue || 0))
  if (!promoType || val <= 0 || base <= 0) {
    return { effective: base, discount: 0 }
  }
  let disc = 0
  if (promoType === 'percent') {
    const clampedPct = Math.min(100, val)
    disc = Math.round((base * clampedPct) / 100)
  } else if (promoType === 'fixed_rp') {
    disc = Math.min(base, val)
  }
  disc = Math.max(0, Math.min(base, disc))
  return { effective: Math.max(0, base - disc), discount: disc }
}

function getDiscountStatusMeta(dc, nowSec) {
  if (!dc.is_active) return { cls: 'muted', label: 'Nonaktif', key: 'inactive' }
  if (dc.max_uses != null && Number(dc.used_count || 0) >= Number(dc.max_uses)) {
    return { cls: 'warn', label: 'Kuota Habis', key: 'exhausted' }
  }
  if (dc.starts_at && Number(dc.starts_at) > nowSec) {
    return { cls: 'awaiting', label: 'Terjadwal', key: 'scheduled' }
  }
  if (dc.expires_at && Number(dc.expires_at) <= nowSec) {
    return { cls: 'expired', label: 'Kedaluwarsa', key: 'expired' }
  }
  return { cls: 'ok', label: 'Aktif', key: 'active' }
}

const EMPTY_PLAN_FORM = {
  slug: '',
  name: '',
  description: '',
  badge_text: '',
  price_monthly_rp: '50000',
  price_yearly_rp: '500000',
  promo_discount_type: '',
  promo_discount_value: '0',
  promo_label: '',
  promo_starts_at: '',
  promo_expires_at: '',
  max_devices: '10',
  history_days: '90',
  forecast_enabled: true,
  export_enabled: true,
  anomaly_advanced: true,
  features_text: '',
  is_recommended: false,
  is_active: true,
  sort_order: '25',
  is_default_free: false,
}

const EMPTY_DISCOUNT_FORM = {
  code: '',
  label: '',
  discount_type: 'percent',
  discount_value: '10',
  max_discount_rp: '',
  min_purchase_rp: '0',
  target_plan_slug: '',
  target_cycle: '',
  max_uses: '',
  starts_at: '',
  expires_at: '',
  is_active: true,
}

export function AdminPlansDiscountsSection({
  plans = [],
  discounts = [],
  token,
  onLogout,
  onReload,
  onNotice,
}) {
  const [planModalOpen, setPlanModalOpen] = useState(false)
  const [editingPlanId, setEditingPlanId] = useState(null)
  const [planForm, setPlanForm] = useState(EMPTY_PLAN_FORM)
  const [slugTouched, setSlugTouched] = useState(false)
  const [savingPlan, setSavingPlan] = useState(false)
  const [confirmDeletePlanId, setConfirmDeletePlanId] = useState(null)
  const [busyPlanId, setBusyPlanId] = useState(null)

  const [discountModalOpen, setDiscountModalOpen] = useState(false)
  const [editingDiscountId, setEditingDiscountId] = useState(null)
  const [discountForm, setDiscountForm] = useState(EMPTY_DISCOUNT_FORM)
  const [savingDiscount, setSavingDiscount] = useState(false)
  const [confirmDeleteDiscountId, setConfirmDeleteDiscountId] = useState(null)
  const [busyDiscountId, setBusyDiscountId] = useState(null)

  const [sectionTab, setSectionTab] = useState('plans') // 'plans' | 'discounts'
  const [dcSearch, setDcSearch] = useState('')
  const [dcFilter, setDcFilter] = useState('all')
  const [copiedCode, setCopiedCode] = useState('')
  const [modalErr, setModalErr] = useState('')

  const [quickPromoPlan, setQuickPromoPlan] = useState(null)
  const [quickPromoForm, setQuickPromoForm] = useState({
    promo_discount_type: 'percent',
    promo_discount_value: '20',
    promo_label: '',
    promo_starts_at: '',
    promo_expires_at: '',
  })
  const [savingQuickPromo, setSavingQuickPromo] = useState(false)

  const nowSec = Math.floor(Date.now() / 1000)

  const stats = useMemo(() => {
    const activePlans = plans.filter((p) => p.is_active).length
    const promoPlans = plans.filter((p) => p.promo_active).length
    const activeDiscounts = discounts.filter(
      (d) => getDiscountStatusMeta(d, nowSec).key === 'active'
    ).length
    const totalCouponUses = discounts.reduce((acc, d) => acc + Number(d.used_count || 0), 0)
    return { activePlans, promoPlans, activeDiscounts, totalCouponUses }
  }, [plans, discounts, nowSec])

  const paidPlans = useMemo(
    () => plans.filter((p) => !p.is_default_free && p.slug !== 'free'),
    [plans]
  )

  const filteredDiscounts = useMemo(() => {
    const q = dcSearch.trim().toLowerCase()
    return discounts.filter((dc) => {
      const st = getDiscountStatusMeta(dc, nowSec).key
      if (dcFilter === 'active' && st !== 'active') return false
      if (dcFilter === 'ended' && st !== 'exhausted' && st !== 'expired') return false
      if (dcFilter === 'inactive' && st !== 'inactive') return false
      if (!q) return true
      return (
        (dc.code || '').toLowerCase().includes(q) ||
        (dc.label || '').toLowerCase().includes(q) ||
        (dc.target_plan_slug || '').toLowerCase().includes(q)
      )
    })
  }, [discounts, dcSearch, dcFilter, nowSec])

  const openCreatePlan = () => {
    setEditingPlanId(null)
    setSlugTouched(false)
    setModalErr('')
    const nextOrder = plans.reduce((mx, p) => Math.max(mx, Number(p.sort_order || 0)), 10) + 10
    setPlanForm({
      ...EMPTY_PLAN_FORM,
      sort_order: String(nextOrder),
    })
    setPlanModalOpen(true)
  }

  const openEditPlan = (plan) => {
    setEditingPlanId(plan.id)
    setSlugTouched(true)
    setModalErr('')
    setPlanForm({
      slug: plan.slug || '',
      name: plan.name || '',
      description: plan.description || '',
      badge_text: plan.badge_text || '',
      price_monthly_rp: String(plan.price_monthly_rp ?? 0),
      price_yearly_rp: String(plan.price_yearly_rp ?? 0),
      promo_discount_type: plan.promo_discount_type || '',
      promo_discount_value: String(plan.promo_discount_value ?? 0),
      promo_label: plan.promo_label || '',
      promo_starts_at: epochToWibInput(plan.promo_starts_at),
      promo_expires_at: epochToWibInput(plan.promo_expires_at),
      max_devices: String(plan.max_devices ?? 1),
      history_days: String(plan.history_days ?? 3),
      forecast_enabled: Boolean(plan.forecast_enabled),
      export_enabled: Boolean(plan.export_enabled),
      anomaly_advanced: Boolean(plan.anomaly_advanced),
      features_text: Array.isArray(plan.features) ? plan.features.join('\n') : '',
      is_recommended: Boolean(plan.is_recommended),
      is_active: Boolean(plan.is_active),
      sort_order: String(plan.sort_order ?? 10),
      is_default_free: Boolean(plan.is_default_free),
    })
    setPlanModalOpen(true)
  }

  const handleSavePlan = async (e) => {
    e.preventDefault()
    setModalErr('')
    if (onNotice) onNotice(null)

    const cleanSlug = planForm.slug.trim().toLowerCase()
    const cleanName = planForm.name.trim()
    if (!editingPlanId && (!cleanSlug || cleanSlug.length < 2)) {
      setModalErr('Kode slug paket minimal 2 karakter (huruf kecil/angka/strip).')
      return
    }
    if (!cleanName || cleanName.length < 2) {
      setModalErr('Nama tampilan paket minimal 2 karakter.')
      return
    }

    const promoType = planForm.is_default_free ? null : planForm.promo_discount_type || null
    const promoValue = promoType ? Number(planForm.promo_discount_value || 0) : 0
    const promoStart = promoType ? wibInputToEpoch(planForm.promo_starts_at) : null
    const promoEnd = promoType ? wibInputToEpoch(planForm.promo_expires_at) : null

    const featuresList = planForm.features_text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    const payload = {
      name: cleanName,
      description: planForm.description.trim(),
      badge_text: planForm.badge_text.trim(),
      price_monthly_rp: planForm.is_default_free ? 0 : Number(planForm.price_monthly_rp || 0),
      price_yearly_rp: planForm.is_default_free ? 0 : Number(planForm.price_yearly_rp || 0),
      promo_discount_type: promoType,
      promo_discount_value: promoValue,
      promo_label: promoType ? planForm.promo_label.trim() : '',
      promo_starts_at: promoStart,
      promo_expires_at: promoEnd,
      max_devices: Number(planForm.max_devices ?? 1),
      history_days: Number(planForm.history_days ?? 3),
      forecast_enabled: Boolean(planForm.forecast_enabled),
      export_enabled: Boolean(planForm.export_enabled),
      anomaly_advanced: Boolean(planForm.anomaly_advanced),
      features: featuresList,
      is_recommended: planForm.is_default_free ? false : Boolean(planForm.is_recommended),
      is_active: planForm.is_default_free ? true : Boolean(planForm.is_active),
      sort_order: Number(planForm.sort_order ?? 10),
    }

    setSavingPlan(true)
    try {
      if (editingPlanId) {
        await apiRequest(
          `/api/admin/plans/${editingPlanId}`,
          { method: 'PATCH', body: payload },
          token,
          onLogout
        )
        if (onNotice) onNotice({ type: 'success', text: `Paket "${cleanName}" berhasil diperbarui.` })
      } else {
        await apiRequest(
          '/api/admin/plans',
          { method: 'POST', body: { slug: cleanSlug, ...payload } },
          token,
          onLogout
        )
        if (onNotice) onNotice({ type: 'success', text: `Paket baru "${cleanName}" ditambahkan.` })
      }
      setPlanModalOpen(false)
      if (onReload) await onReload()
    } catch (err) {
      setModalErr(err.message || 'Gagal menyimpan paket langganan.')
    } finally {
      setSavingPlan(false)
    }
  }

  const handleTogglePlanActive = async (plan) => {
    if (plan.is_default_free) return
    setBusyPlanId(plan.id)
    if (onNotice) onNotice(null)
    try {
      await apiRequest(
        `/api/admin/plans/${plan.id}`,
        { method: 'PATCH', body: { is_active: !plan.is_active } },
        token,
        onLogout
      )
      if (onNotice) {
        onNotice({
          type: 'success',
          text: !plan.is_active
            ? `Paket "${plan.name}" diaktifkan kembali.`
            : `Paket "${plan.name}" dinonaktifkan dari katalog baru.`,
        })
      }
      if (onReload) await onReload()
    } catch (err) {
      if (onNotice) onNotice({ type: 'error', text: err.message || 'Gagal mengubah status paket.' })
    } finally {
      setBusyPlanId(null)
    }
  }

  const handleDeletePlan = async (plan) => {
    setBusyPlanId(plan.id)
    if (onNotice) onNotice(null)
    try {
      await apiRequest(`/api/admin/plans/${plan.id}`, { method: 'DELETE' }, token, onLogout)
      setConfirmDeletePlanId(null)
      if (onNotice) onNotice({ type: 'success', text: `Paket "${plan.name}" dihapus.` })
      if (onReload) await onReload()
    } catch (err) {
      setConfirmDeletePlanId(null)
      if (onNotice) onNotice({ type: 'error', text: err.message || 'Gagal menghapus paket.' })
    } finally {
      setBusyPlanId(null)
    }
  }

  const openCreateDiscount = () => {
    setEditingDiscountId(null)
    setModalErr('')
    setDiscountForm({ ...EMPTY_DISCOUNT_FORM })
    setDiscountModalOpen(true)
  }

  const openEditDiscount = (dc) => {
    setEditingDiscountId(dc.id)
    setModalErr('')
    setDiscountForm({
      code: dc.code || '',
      label: dc.label || '',
      discount_type: dc.discount_type || 'percent',
      discount_value: String(dc.discount_value ?? 10),
      max_discount_rp: dc.max_discount_rp != null ? String(dc.max_discount_rp) : '',
      min_purchase_rp: String(dc.min_purchase_rp ?? 0),
      target_plan_slug: dc.target_plan_slug || '',
      target_cycle: dc.target_cycle || '',
      max_uses: dc.max_uses != null ? String(dc.max_uses) : '',
      starts_at: epochToWibInput(dc.starts_at),
      expires_at: epochToWibInput(dc.expires_at),
      is_active: Boolean(dc.is_active),
    })
    setDiscountModalOpen(true)
  }

  const handleSaveDiscount = async (e) => {
    e.preventDefault()
    setModalErr('')
    if (onNotice) onNotice(null)

    const cleanCode = discountForm.code.trim().toUpperCase()
    if (!cleanCode || cleanCode.length < 2) {
      setModalErr('Kode kupon minimal 2 karakter (huruf/angka tanpa spasi).')
      return
    }

    const isPct = discountForm.discount_type === 'percent'
    const payload = {
      code: cleanCode,
      label: discountForm.label.trim(),
      discount_type: discountForm.discount_type,
      discount_value: Number(discountForm.discount_value || 0),
      max_discount_rp:
        isPct && Number(discountForm.max_discount_rp || 0) > 0
          ? Number(discountForm.max_discount_rp)
          : null,
      min_purchase_rp: Math.max(0, Number(discountForm.min_purchase_rp || 0)),
      target_plan_slug: discountForm.target_plan_slug || null,
      target_cycle: discountForm.target_cycle || null,
      max_uses: Number(discountForm.max_uses || 0) > 0 ? Number(discountForm.max_uses) : null,
      starts_at: wibInputToEpoch(discountForm.starts_at),
      expires_at: wibInputToEpoch(discountForm.expires_at),
      is_active: Boolean(discountForm.is_active),
    }

    setSavingDiscount(true)
    try {
      if (editingDiscountId) {
        await apiRequest(
          `/api/admin/discounts/${editingDiscountId}`,
          { method: 'PATCH', body: payload },
          token,
          onLogout
        )
        if (onNotice) onNotice({ type: 'success', text: `Kupon "${cleanCode}" diperbarui.` })
      } else {
        await apiRequest('/api/admin/discounts', { method: 'POST', body: payload }, token, onLogout)
        if (onNotice) onNotice({ type: 'success', text: `Kupon baru "${cleanCode}" dibuat.` })
      }
      setDiscountModalOpen(false)
      if (onReload) await onReload()
    } catch (err) {
      setModalErr(err.message || 'Gagal menyimpan kode promo.')
    } finally {
      setSavingDiscount(false)
    }
  }

  const handleToggleDiscountActive = async (dc) => {
    setBusyDiscountId(dc.id)
    if (onNotice) onNotice(null)
    try {
      await apiRequest(
        `/api/admin/discounts/${dc.id}`,
        { method: 'PATCH', body: { is_active: !dc.is_active } },
        token,
        onLogout
      )
      if (onNotice) {
        onNotice({
          type: 'success',
          text: !dc.is_active
            ? `Kupon "${dc.code}" diaktifkan.`
            : `Kupon "${dc.code}" dinonaktifkan sementara.`,
        })
      }
      if (onReload) await onReload()
    } catch (err) {
      if (onNotice) onNotice({ type: 'error', text: err.message || 'Gagal mengubah status kupon.' })
    } finally {
      setBusyDiscountId(null)
    }
  }

  const handleDeleteDiscount = async (dc) => {
    setBusyDiscountId(dc.id)
    if (onNotice) onNotice(null)
    try {
      await apiRequest(`/api/admin/discounts/${dc.id}`, { method: 'DELETE' }, token, onLogout)
      setConfirmDeleteDiscountId(null)
      if (onNotice) onNotice({ type: 'success', text: `Kupon "${dc.code}" dihapus.` })
      if (onReload) await onReload()
    } catch (err) {
      setConfirmDeleteDiscountId(null)
      if (onNotice) onNotice({ type: 'error', text: err.message || 'Gagal menghapus kupon.' })
    } finally {
      setBusyDiscountId(null)
    }
  }

  const handleCopyCode = async (codeText) => {
    if (!codeText) return
    try {
      await navigator.clipboard.writeText(codeText)
      setCopiedCode(codeText)
      window.setTimeout(() => setCopiedCode(''), 1500)
    } catch {
      // Abaikan jika ditolak browser
    }
  }

  const monthlyPromoPreview = useMemo(
    () =>
      computeClientPromoPreview(
        planForm.price_monthly_rp,
        planForm.promo_discount_type,
        planForm.promo_discount_value
      ),
    [planForm.price_monthly_rp, planForm.promo_discount_type, planForm.promo_discount_value]
  )

  const yearlyPromoPreview = useMemo(
    () =>
      computeClientPromoPreview(
        planForm.price_yearly_rp,
        planForm.promo_discount_type,
        planForm.promo_discount_value
      ),
    [planForm.price_yearly_rp, planForm.promo_discount_type, planForm.promo_discount_value]
  )

  const openQuickPromoModal = (plan) => {
    setModalErr('')
    setQuickPromoPlan(plan)
    setQuickPromoForm({
      promo_discount_type: plan.promo_discount_type || 'percent',
      promo_discount_value:
        plan.promo_discount_type && Number(plan.promo_discount_value || 0) > 0
          ? String(plan.promo_discount_value)
          : '20',
      promo_label: plan.promo_label || '',
      promo_starts_at: epochToWibInput(plan.promo_starts_at),
      promo_expires_at: epochToWibInput(plan.promo_expires_at),
    })
  }

  const handleSaveQuickPromo = async (e) => {
    e.preventDefault()
    if (!quickPromoPlan) return
    setModalErr('')
    const val = Number(quickPromoForm.promo_discount_value || 0)
    if (!quickPromoForm.promo_discount_type || val <= 0) {
      setModalErr('Pilih tipe promo dan masukkan nilai diskon lebih dari 0.')
      return
    }
    setSavingQuickPromo(true)
    try {
      await apiRequest(
        `/api/admin/plans/${quickPromoPlan.id}`,
        {
          method: 'PATCH',
          body: {
            promo_discount_type: quickPromoForm.promo_discount_type,
            promo_discount_value: val,
            promo_label: quickPromoForm.promo_label.trim(),
            promo_starts_at: wibInputToEpoch(quickPromoForm.promo_starts_at),
            promo_expires_at: wibInputToEpoch(quickPromoForm.promo_expires_at),
          },
        },
        token,
        onLogout
      )
      setQuickPromoPlan(null)
      if (onNotice) {
        onNotice({
          type: 'success',
          text: `Promo harga coret untuk paket "${quickPromoPlan.name}" berhasil disimpan.`,
        })
      }
      if (onReload) await onReload()
    } catch (err) {
      setModalErr(err.message || 'Gagal menyimpan promo paket.')
    } finally {
      setSavingQuickPromo(false)
    }
  }

  const handleClearQuickPromo = async (plan) => {
    if (!plan) return
    setBusyPlanId(plan.id)
    setModalErr('')
    if (onNotice) onNotice(null)
    try {
      await apiRequest(
        `/api/admin/plans/${plan.id}`,
        {
          method: 'PATCH',
          body: {
            promo_discount_type: null,
            promo_discount_value: 0,
            promo_label: '',
            promo_starts_at: null,
            promo_expires_at: null,
          },
        },
        token,
        onLogout
      )
      if (quickPromoPlan?.id === plan.id) setQuickPromoPlan(null)
      if (onNotice) {
        onNotice({ type: 'success', text: `Promo harga coret "${plan.name}" dihentikan.` })
      }
      if (onReload) await onReload()
    } catch (err) {
      if (onNotice) onNotice({ type: 'error', text: err.message || 'Gagal menghentikan promo.' })
    } finally {
      setBusyPlanId(null)
    }
  }

  const quickMonthPreview = useMemo(
    () =>
      computeClientPromoPreview(
        quickPromoPlan?.price_monthly_rp || 0,
        quickPromoForm.promo_discount_type,
        quickPromoForm.promo_discount_value
      ),
    [quickPromoPlan, quickPromoForm.promo_discount_type, quickPromoForm.promo_discount_value]
  )

  const quickYearPreview = useMemo(
    () =>
      computeClientPromoPreview(
        quickPromoPlan?.price_yearly_rp || 0,
        quickPromoForm.promo_discount_type,
        quickPromoForm.promo_discount_value
      ),
    [quickPromoPlan, quickPromoForm.promo_discount_type, quickPromoForm.promo_discount_value]
  )

  return (
    <div className="admin-section-stack tab-pane-fade">
      {/* 1. Ringkasan KPI Ringkas */}
      <div className="admin-kpi-grid admin-plans-kpi-grid">
        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Paket Aktif</span>
          <strong className="admin-kpi-value num-tabular">
            {stats.activePlans}/{plans.length}
          </strong>
          <span className="admin-kpi-sub">Katalog berlangganan</span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Promo Harga Coret</span>
          <strong className="admin-kpi-value num-tabular brand-amber-text">
            {stats.promoPlans} Paket
          </strong>
          <span className="admin-kpi-sub">Diskon langsung berjalan</span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Kupon Checkout</span>
          <strong className="admin-kpi-value num-tabular brand-blue-text">
            {stats.activeDiscounts}/{discounts.length}
          </strong>
          <span className="admin-kpi-sub">Kode aktif siap klaim</span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Klaim Kupon</span>
          <strong className="admin-kpi-value num-tabular brand-emerald-text">
            {stats.totalCouponUses}x
          </strong>
          <span className="admin-kpi-sub">Total pemakaian order</span>
        </div>
      </div>

      {/* 2. Sub-Tab Switcher Terstruktur: Katalog Paket vs Promo & Kupon */}
      <div className="admin-subtab-bar" role="tablist" aria-label="Kelola Paket dan Diskon">
        <button
          type="button"
          role="tab"
          aria-selected={sectionTab === 'plans'}
          className={`admin-subtab-btn ${sectionTab === 'plans' ? 'active' : ''}`}
          onClick={() => setSectionTab('plans')}
        >
          <Crown size={15} />
          <span>Katalog Paket</span>
          <span className="admin-subtab-count num-tabular">{plans.length}</span>
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={sectionTab === 'discounts'}
          className={`admin-subtab-btn ${sectionTab === 'discounts' ? 'active' : ''}`}
          onClick={() => setSectionTab('discounts')}
        >
          <Ticket size={15} />
          <span>Promo &amp; Kupon</span>
          <span className="admin-subtab-count num-tabular">
            {stats.promoPlans + discounts.length}
          </span>
        </button>
      </div>

      {/* TAB A: KATALOG PAKET LANGGANAN */}
      {sectionTab === 'plans' && (
        <section className="clean-sheet admin-card-block tab-pane-fade">
          <div className="admin-section-header-bar">
            <div className="admin-section-header-copy">
              <h3>Katalog Paket Langganan</h3>
              <p className="admin-row-sub">
                Kelola tier paket, harga bulanan/tahunan, batas panel, dan fitur eksklusif.
              </p>
            </div>
            <button type="button" className="btn btn-primary btn-compact" onClick={openCreatePlan}>
              <Plus size={15} />
              <span>Tambah Paket</span>
            </button>
          </div>

          {plans.length === 0 ? (
            <div className="pay-empty-state">
              <Crown size={22} />
              <div>
                <strong>Belum ada paket termuat</strong>
                <span>Tekan Muat Ulang atau Tambah Paket untuk mulai menyusun katalog.</span>
              </div>
            </div>
          ) : (
            <div className="admin-plan-grid">
              {plans.map((p) => {
                const isFree = Boolean(p.is_default_free || p.slug === 'free')
                const hasMonthlyPromo =
                  !isFree && Boolean(p.promo_active) && Number(p.monthly_promo_discount_rp || 0) > 0
                const hasYearlyPromo =
                  !isFree && Boolean(p.promo_active) && Number(p.yearly_promo_discount_rp || 0) > 0
                const subCount = Number(p.subscriber_count || 0)
                const deleteBlocked = isFree || subCount > 0

                const badgeClean = (p.badge_text || '').trim()
                const showCustomBadge = Boolean(
                  badgeClean &&
                    !(p.is_recommended && !isFree && badgeClean.toLowerCase() === 'rekomendasi') &&
                    !(isFree && badgeClean.toLowerCase() === 'gratis bawaan')
                )

                return (
                  <div
                    key={p.id}
                    className={`admin-plan-card ${!p.is_active ? 'is-inactive' : ''} ${
                      p.is_recommended ? 'is-recommended' : ''
                    }`}
                  >
                    <div className="admin-plan-card-head">
                      <div className="admin-plan-title-wrap">
                        <div className="admin-plan-title-row">
                          <span className={`admin-plan-icon ${isFree ? 'is-free' : 'is-paid'}`}>
                            {isFree ? <Sparkles size={14} /> : <Crown size={14} />}
                          </span>
                          <strong className="admin-plan-name">{p.name}</strong>
                          <span className="admin-plan-slug num-tabular">{p.slug}</span>
                        </div>
                        <div className="admin-plan-badges">
                          {isFree && <span className="admin-pill ok">Gratis Bawaan</span>}
                          {p.is_recommended && !isFree && (
                            <span className="admin-pill pro">Rekomendasi</span>
                          )}
                          {showCustomBadge && <span className="admin-pill muted">{badgeClean}</span>}
                          {p.promo_active && !isFree && (
                            <span className="admin-pill warn">
                              {p.promo_label ||
                                (p.promo_discount_type === 'percent'
                                  ? `Promo -${p.promo_discount_value}%`
                                  : `Promo -${formatRp(p.promo_discount_value)}`)}
                            </span>
                          )}
                          {!p.is_active && <span className="admin-pill muted">Nonaktif</span>}
                        </div>
                      </div>

                      <button
                        type="button"
                        role="switch"
                        aria-checked={Boolean(p.is_active)}
                        aria-label={`Aktifkan paket ${p.name}`}
                        className={`admin-switch is-sm ${p.is_active ? 'on' : ''}`}
                        disabled={isFree || busyPlanId === p.id}
                        title={
                          isFree
                            ? 'Paket gratis bawaan wajib aktif'
                            : p.is_active
                              ? 'Nonaktifkan paket dari pembeli baru'
                              : 'Aktifkan paket'
                        }
                        onClick={() => handleTogglePlanActive(p)}
                      >
                        <span className="admin-switch-thumb" />
                      </button>
                    </div>

                    {p.description && <p className="admin-plan-desc">{p.description}</p>}

                    {isFree ? (
                      <div className="admin-plan-price-box num-tabular">
                        <div className="admin-plan-price-line">
                          <strong>Rp 0</strong>
                          <span>/selamanya</span>
                        </div>
                      </div>
                    ) : (
                      <div className="admin-plan-price-split num-tabular">
                        <div className="admin-plan-price-col">
                          <span className="admin-plan-price-col-label">Bulanan</span>
                          {hasMonthlyPromo && (
                            <span className="price-strike">{formatRp(p.price_monthly_rp)}</span>
                          )}
                          <strong className="admin-plan-price-col-val">
                            {formatRp(
                              hasMonthlyPromo ? p.effective_monthly_price_rp : p.price_monthly_rp
                            )}
                          </strong>
                        </div>

                        <div className="admin-plan-price-col">
                          <span className="admin-plan-price-col-label">
                            Tahunan
                            {Number(p.yearly_savings_pct || 0) > 0 && (
                              <span className="admin-plan-save-tag">-{p.yearly_savings_pct}%</span>
                            )}
                          </span>
                          {hasYearlyPromo && (
                            <span className="price-strike">{formatRp(p.price_yearly_rp)}</span>
                          )}
                          <strong className="admin-plan-price-col-val">
                            {formatRp(
                              hasYearlyPromo ? p.effective_yearly_price_rp : p.price_yearly_rp
                            )}
                          </strong>
                        </div>
                      </div>
                    )}

                    {!isFree && p.promo_discount_type && !p.promo_active && (
                      <div className="admin-plan-promo-sched num-tabular">
                        <CalendarClock size={12} />
                        <span>
                          Jadwal promo {p.promo_label || ''}:{' '}
                          {p.promo_starts_at ? formatDateTimeWIB(p.promo_starts_at) : 'sekarang'}{' '}
                          s.d.{' '}
                          {p.promo_expires_at ? formatDateTimeWIB(p.promo_expires_at) : 'seterusnya'}
                        </span>
                      </div>
                    )}

                    <div className="admin-plan-specs-grid num-tabular">
                      <div className="admin-plan-spec-row">
                        <span>
                          {p.max_devices < 0 ? 'Panel: Tanpa Batas' : `Maks ${p.max_devices} Panel`}
                        </span>
                      </div>
                      <div className="admin-plan-spec-row">
                        <span>Riwayat {p.history_days} Hari</span>
                      </div>
                      <div
                        className={`admin-plan-spec-row ${p.forecast_enabled ? 'is-on' : 'is-off'}`}
                      >
                        <span>Proyeksi {p.forecast_enabled ? '✓' : '✕'}</span>
                      </div>
                      <div className={`admin-plan-spec-row ${p.export_enabled ? 'is-on' : 'is-off'}`}>
                        <span>Ekspor CSV {p.export_enabled ? '✓' : '✕'}</span>
                      </div>
                      <div
                        className={`admin-plan-spec-row ${p.anomaly_advanced ? 'is-on' : 'is-off'}`}
                        style={{ gridColumn: 'span 2' }}
                      >
                        <span>Deteksi Anomali L2/L3 {p.anomaly_advanced ? '✓' : '✕'}</span>
                      </div>
                    </div>

                    <div className="admin-plan-foot">
                      <span className="admin-plan-subs num-tabular">
                        <Users size={13} />
                        <span>
                          {subCount} akun · #{p.sort_order}
                        </span>
                      </span>

                      <div className="admin-row-actions">
                        {!isFree && (
                          <button
                            type="button"
                            className="btn btn-secondary btn-compact"
                            onClick={() => openQuickPromoModal(p)}
                          >
                            <Tag size={13} />
                            <span>Promo</span>
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-secondary btn-compact"
                          onClick={() => openEditPlan(p)}
                        >
                          <Pencil size={13} />
                          <span>Edit</span>
                        </button>

                        {!isFree &&
                          (confirmDeletePlanId === p.id ? (
                            <button
                              type="button"
                              className="btn btn-danger-solid btn-compact"
                              disabled={busyPlanId === p.id}
                              onClick={() => handleDeletePlan(p)}
                            >
                              Hapus?
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-danger-ghost btn-compact"
                              disabled={deleteBlocked || busyPlanId === p.id}
                              title={
                                subCount > 0
                                  ? `Dipakai ${subCount} akun (nonaktifkan saja)`
                                  : 'Hapus paket ini'
                              }
                              onClick={() => setConfirmDeletePlanId(p.id)}
                            >
                              <Trash2 size={13} />
                            </button>
                          ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      )}

      {/* TAB B: PROMO HARGA CORET & KODE KUPON */}
      {sectionTab === 'discounts' && (
        <div className="admin-section-stack tab-pane-fade">
          {/* B1. Promo Harga Coret Langsung per Paket */}
          <section className="clean-sheet admin-card-block">
            <div className="admin-section-header-bar">
              <div className="admin-section-header-copy">
                <h3>Promo Harga Coret per Paket</h3>
                <p className="admin-row-sub">
                  Potongan otomatis yang langsung mencoret harga asli pada halaman paket pelanggan.
                </p>
              </div>
            </div>

            {paidPlans.length === 0 ? (
              <div className="pay-empty-state">
                <Tag size={20} />
                <div>
                  <strong>Belum ada paket berbayar</strong>
                  <span>Tambahkan paket berbayar di tab Katalog Paket terlebih dahulu.</span>
                </div>
              </div>
            ) : (
              <div className="admin-promo-plan-strip">
                {paidPlans.map((p) => {
                  const hasPromo = Boolean(p.promo_discount_type)
                  const isLive = Boolean(p.promo_active)
                  return (
                    <div key={p.id} className="admin-promo-plan-row">
                      <div className="admin-promo-plan-info">
                        <div className="admin-promo-plan-top">
                          <strong style={{ fontSize: 14 }}>{p.name}</strong>
                          <span className={`admin-pill ${isLive ? 'warn' : hasPromo ? 'awaiting' : 'muted'}`}>
                            {isLive
                              ? p.promo_label ||
                                (p.promo_discount_type === 'percent'
                                  ? `Promo -${p.promo_discount_value}%`
                                  : `Promo -${formatRp(p.promo_discount_value)}`)
                              : hasPromo
                                ? 'Terjadwal / Berakhir'
                                : 'Harga Normal'}
                          </span>
                        </div>
                        <div className="admin-promo-plan-prices num-tabular">
                          <span>
                            Bulanan:{' '}
                            {isLive && (
                              <span className="price-strike" style={{ marginRight: 4 }}>
                                {formatRp(p.price_monthly_rp)}
                              </span>
                            )}
                            <strong>{formatRp(p.effective_monthly_price_rp)}</strong>
                          </span>
                          <span>·</span>
                          <span>
                            Tahunan:{' '}
                            {isLive && (
                              <span className="price-strike" style={{ marginRight: 4 }}>
                                {formatRp(p.price_yearly_rp)}
                              </span>
                            )}
                            <strong>{formatRp(p.effective_yearly_price_rp)}</strong>
                          </span>
                        </div>
                      </div>

                      <div className="admin-promo-plan-actions">
                        <button
                          type="button"
                          className="btn btn-primary btn-compact"
                          onClick={() => openQuickPromoModal(p)}
                        >
                          <Tag size={13} />
                          <span>{hasPromo ? 'Ubah Promo' : 'Pasang Promo'}</span>
                        </button>
                        {hasPromo && (
                          <button
                            type="button"
                            className="btn btn-danger-ghost btn-compact"
                            disabled={busyPlanId === p.id}
                            onClick={() => handleClearQuickPromo(p)}
                          >
                            Matikan
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {/* B2. Kode Kupon & Voucher Checkout */}
          <section className="clean-sheet admin-card-block">
            <div className="admin-section-header-bar">
              <div className="admin-section-header-copy">
                <h3>Kode Kupon &amp; Voucher Checkout</h3>
                <p className="admin-row-sub">
                  Pelanggan dapat mengklaim kode ini di tahap pembayaran untuk potongan ekstra.
                </p>
              </div>
              <button
                type="button"
                className="btn btn-primary btn-compact"
                onClick={openCreateDiscount}
              >
                <Plus size={15} />
                <span>Buat Kupon</span>
              </button>
            </div>

            <div className="admin-pm-toolbar" style={{ marginBottom: 14 }}>
              <div className="admin-search-wrap" style={{ flex: '1 1 220px' }}>
                <Search size={15} className="admin-search-icon" />
                <input
                  type="text"
                  className="modern-input admin-search-input"
                  placeholder="Cari kode kupon, label, atau target paket..."
                  value={dcSearch}
                  onChange={(e) => setDcSearch(e.target.value)}
                />
              </div>

              <div className="admin-pm-filter-tabs cols-4">
                {[
                  { id: 'all', label: `Semua (${discounts.length})` },
                  { id: 'active', label: `Aktif (${stats.activeDiscounts})` },
                  { id: 'ended', label: 'Habis / Berakhir' },
                  { id: 'inactive', label: 'Nonaktif' },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    className={`admin-filter-pill ${dcFilter === f.id ? 'active' : ''}`}
                    onClick={() => setDcFilter(f.id)}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {filteredDiscounts.length === 0 ? (
              <div className="pay-empty-state">
                <Ticket size={22} />
                <div>
                  <strong>
                    {discounts.length === 0
                      ? 'Belum ada kode kupon dibuat'
                      : 'Tidak ada kupon yang cocok'}
                  </strong>
                  <span>
                    Klik &ldquo;Buat Kupon&rdquo; untuk membuat kode diskon persentase atau nominal
                    Rupiah.
                  </span>
                </div>
              </div>
            ) : (
              <>
                <div className="admin-table-desktop">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Kode &amp; Label</th>
                        <th>Potongan</th>
                        <th>Target</th>
                        <th>Kuota</th>
                        <th>Masa Berlaku (WIB)</th>
                        <th>Status</th>
                        <th style={{ textAlign: 'right' }}>Aksi</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredDiscounts.map((dc) => {
                        const st = getDiscountStatusMeta(dc, nowSec)
                        const isPct = dc.discount_type === 'percent'
                        return (
                          <tr key={dc.id}>
                            <td>
                              <div className="admin-dc-code-cell">
                                <span className="admin-dc-code-badge num-tabular">{dc.code}</span>
                                <button
                                  type="button"
                                  className="admin-pm-copy-btn"
                                  onClick={() => handleCopyCode(dc.code)}
                                  title="Salin kode"
                                >
                                  {copiedCode === dc.code ? (
                                    <Check size={11} />
                                  ) : (
                                    <Copy size={11} />
                                  )}
                                  <span>{copiedCode === dc.code ? 'Disalin' : 'Salin'}</span>
                                </button>
                              </div>
                              {dc.label && <div className="admin-dev-id">{dc.label}</div>}
                            </td>

                            <td className="num-tabular">
                              <div className="admin-dev-name">
                                {isPct
                                  ? `${dc.discount_value}%${
                                      dc.max_discount_rp
                                        ? ` (Maks ${formatRp(dc.max_discount_rp)})`
                                        : ''
                                    }`
                                  : formatRp(dc.discount_value)}
                              </div>
                              {Number(dc.min_purchase_rp || 0) > 0 && (
                                <div className="admin-dev-id">
                                  Min. {formatRp(dc.min_purchase_rp)}
                                </div>
                              )}
                            </td>

                            <td>
                              <div className="admin-dev-name">
                                {dc.target_plan_slug
                                  ? `Paket ${dc.target_plan_slug}`
                                  : 'Semua Paket'}
                              </div>
                              <div className="admin-dev-id">
                                {dc.target_cycle === 'monthly'
                                  ? 'Khusus Bulanan'
                                  : dc.target_cycle === 'yearly'
                                    ? 'Khusus Tahunan'
                                    : 'Semua Siklus'}
                              </div>
                            </td>

                            <td className="num-tabular">
                              <div className="admin-dev-name">
                                {dc.used_count} / {dc.max_uses != null ? dc.max_uses : '∞'}
                              </div>
                            </td>

                            <td className="num-tabular">
                              {dc.starts_at || dc.expires_at ? (
                                <div className="admin-dev-id">
                                  <div>
                                    {dc.starts_at
                                      ? formatDateTimeWIB(dc.starts_at)
                                      : 'Mulai kapan saja'}
                                  </div>
                                  <div>
                                    s.d.{' '}
                                    {dc.expires_at ? formatDateTimeWIB(dc.expires_at) : 'Tanpa batas'}
                                  </div>
                                </div>
                              ) : (
                                <span className="admin-dev-id">Tanpa Batas Waktu</span>
                              )}
                            </td>

                            <td>
                              <div className="admin-user-status-cell">
                                <button
                                  type="button"
                                  role="switch"
                                  aria-checked={Boolean(dc.is_active)}
                                  aria-label={`Ubah status kupon ${dc.code}`}
                                  className={`admin-switch is-sm ${dc.is_active ? 'on' : ''}`}
                                  disabled={busyDiscountId === dc.id}
                                  onClick={() => handleToggleDiscountActive(dc)}
                                >
                                  <span className="admin-switch-thumb" />
                                </button>
                                <span className={`admin-pill ${st.cls}`}>{st.label}</span>
                              </div>
                            </td>

                            <td style={{ textAlign: 'right' }}>
                              <div className="admin-row-actions">
                                <button
                                  type="button"
                                  className="admin-icon-action"
                                  title="Edit Kupon"
                                  onClick={() => openEditDiscount(dc)}
                                >
                                  <Pencil size={15} />
                                </button>
                                {confirmDeleteDiscountId === dc.id ? (
                                  <button
                                    type="button"
                                    className="btn btn-danger-solid btn-compact"
                                    disabled={busyDiscountId === dc.id}
                                    onClick={() => handleDeleteDiscount(dc)}
                                  >
                                    Hapus?
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    className="admin-icon-action danger"
                                    title="Hapus Kupon"
                                    onClick={() => setConfirmDeleteDiscountId(dc.id)}
                                  >
                                    <Trash2 size={15} />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="admin-cards-mobile">
                  {filteredDiscounts.map((dc) => {
                    const st = getDiscountStatusMeta(dc, nowSec)
                    const isPct = dc.discount_type === 'percent'
                    return (
                      <div key={dc.id} className="admin-dc-card-m">
                        <div className="admin-dc-card-m-head">
                          <div>
                            <div className="admin-dc-code-cell">
                              <span className="admin-dc-code-badge num-tabular">{dc.code}</span>
                              <button
                                type="button"
                                className="admin-pm-copy-btn"
                                onClick={() => handleCopyCode(dc.code)}
                              >
                                {copiedCode === dc.code ? <Check size={11} /> : <Copy size={11} />}
                                <span>{copiedCode === dc.code ? 'Disalin' : 'Salin'}</span>
                              </button>
                            </div>
                            {dc.label && (
                              <div className="admin-dev-id" style={{ marginTop: 3 }}>
                                {dc.label}
                              </div>
                            )}
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span className={`admin-pill ${st.cls}`}>{st.label}</span>
                            <button
                              type="button"
                              role="switch"
                              aria-checked={Boolean(dc.is_active)}
                              aria-label={`Ubah status kupon ${dc.code}`}
                              className={`admin-switch is-sm ${dc.is_active ? 'on' : ''}`}
                              disabled={busyDiscountId === dc.id}
                              onClick={() => handleToggleDiscountActive(dc)}
                            >
                              <span className="admin-switch-thumb" />
                            </button>
                          </div>
                        </div>

                        <div className="admin-dc-card-m-grid num-tabular">
                          <div className="admin-dc-card-m-item">
                            <span>Potongan</span>
                            <strong>
                              {isPct
                                ? `${dc.discount_value}%${
                                    dc.max_discount_rp ? ` (≤ ${formatRp(dc.max_discount_rp)})` : ''
                                  }`
                                : formatRp(dc.discount_value)}
                            </strong>
                          </div>
                          <div className="admin-dc-card-m-item">
                            <span>Kuota Dipakai</span>
                            <strong>
                              {dc.used_count} / {dc.max_uses != null ? dc.max_uses : '∞'}
                            </strong>
                          </div>
                          <div className="admin-dc-card-m-item">
                            <span>Target Paket</span>
                            <strong>
                              {dc.target_plan_slug ? dc.target_plan_slug : 'Semua'} ·{' '}
                              {dc.target_cycle === 'monthly'
                                ? 'Bulanan'
                                : dc.target_cycle === 'yearly'
                                  ? 'Tahunan'
                                  : 'Semua'}
                            </strong>
                          </div>
                          <div className="admin-dc-card-m-item">
                            <span>Berakhir (WIB)</span>
                            <strong>
                              {dc.expires_at ? formatDateTimeWIB(dc.expires_at) : 'Tanpa Batas'}
                            </strong>
                          </div>
                        </div>

                        <div className="admin-m-actions admin-m-actions-2col">
                          <button
                            type="button"
                            className="btn btn-secondary btn-compact"
                            onClick={() => openEditDiscount(dc)}
                          >
                            <Pencil size={13} />
                            <span>Edit</span>
                          </button>
                          {confirmDeleteDiscountId === dc.id ? (
                            <button
                              type="button"
                              className="btn btn-danger-solid btn-compact"
                              onClick={() => handleDeleteDiscount(dc)}
                            >
                              Hapus?
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-danger-ghost btn-compact"
                              onClick={() => setConfirmDeleteDiscountId(dc.id)}
                            >
                              <Trash2 size={13} />
                              <span>Hapus</span>
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </section>
        </div>
      )}

      {/* Modal Tambah / Edit Paket Langganan */}
      {planModalOpen && (
        <div className="modal-overlay pwa-guide-overlay" onClick={() => setPlanModalOpen(false)}>
          <div
            className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pwa-guide-head">
              <div>
                <h3 className="pwa-guide-title">
                  {editingPlanId ? 'Edit Paket Langganan' : 'Tambah Paket Langganan Baru'}
                </h3>
                <p className="pwa-guide-sub">
                  Atur harga reguler, promo harga coret otomatis, serta kuota fitur pelanggan.
                </p>
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setPlanModalOpen(false)}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>

            {modalErr && <div className="feedback-msg error">{modalErr}</div>}

            <form onSubmit={handleSavePlan} className="admin-modal-stack">
              <div className="admin-modal-section">
                <div className="admin-modal-sec-head">
                  <Crown size={14} />
                  <span>1. Identitas &amp; Tampilan Paket</span>
                </div>
                <div className="settings-fields-grid">
                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="plan-inp-name">
                      Nama Paket
                    </label>
                    <input
                      id="plan-inp-name"
                      type="text"
                      className="modern-input"
                      placeholder="Contoh: VoltKu Bisnis"
                      value={planForm.name}
                      onChange={(e) => {
                        const val = e.target.value
                        setPlanForm((prev) => ({
                          ...prev,
                          name: val,
                          slug:
                            !editingPlanId && !slugTouched
                              ? slugifyPlanName(val.replace(/^voltku\s+/i, ''))
                              : prev.slug,
                        }))
                      }}
                      required
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="plan-inp-slug">
                      Kode Slug Unik
                    </label>
                    <input
                      id="plan-inp-slug"
                      type="text"
                      className="modern-input num-tabular"
                      placeholder="mis. bisnis"
                      value={planForm.slug}
                      disabled={Boolean(editingPlanId)}
                      onChange={(e) => {
                        setSlugTouched(true)
                        setPlanForm((prev) => ({ ...prev, slug: e.target.value.toLowerCase() }))
                      }}
                      required
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="plan-inp-badge">
                      Label Badge Kartu (Opsional)
                    </label>
                    <input
                      id="plan-inp-badge"
                      type="text"
                      className="modern-input"
                      placeholder="Mis: Populer / Terbaik"
                      value={planForm.badge_text}
                      onChange={(e) =>
                        setPlanForm((prev) => ({ ...prev, badge_text: e.target.value }))
                      }
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="plan-inp-sort">
                      Urutan Tampil
                    </label>
                    <input
                      id="plan-inp-sort"
                      type="number"
                      className="modern-input num-tabular"
                      value={planForm.sort_order}
                      onChange={(e) =>
                        setPlanForm((prev) => ({ ...prev, sort_order: e.target.value }))
                      }
                    />
                  </div>
                </div>

                <div className="form-field-group" style={{ marginTop: 10, marginBottom: 0 }}>
                  <label className="field-label" htmlFor="plan-inp-desc">
                    Deskripsi Singkat
                  </label>
                  <input
                    id="plan-inp-desc"
                    type="text"
                    className="modern-input"
                    placeholder="Contoh: Pantau banyak cabang toko atau kos secara terpusat"
                    value={planForm.description}
                    onChange={(e) =>
                      setPlanForm((prev) => ({ ...prev, description: e.target.value }))
                    }
                  />
                </div>
              </div>

              {!planForm.is_default_free && (
                <div className="admin-modal-section">
                  <div className="admin-modal-sec-head">
                    <Tag size={14} />
                    <span>2. Harga Reguler &amp; Promo Harga Coret</span>
                  </div>

                  <div className="settings-fields-grid">
                    <div className="form-field-group" style={{ marginBottom: 0 }}>
                      <label className="field-label" htmlFor="plan-inp-pmonth">
                        Harga Bulanan Normal (Rp)
                      </label>
                      <input
                        id="plan-inp-pmonth"
                        type="number"
                        min="0"
                        className="modern-input num-tabular"
                        value={planForm.price_monthly_rp}
                        onChange={(e) =>
                          setPlanForm((prev) => ({ ...prev, price_monthly_rp: e.target.value }))
                        }
                        required
                      />
                    </div>

                    <div className="form-field-group" style={{ marginBottom: 0 }}>
                      <label className="field-label" htmlFor="plan-inp-pyear">
                        Harga Tahunan Normal (Rp)
                      </label>
                      <input
                        id="plan-inp-pyear"
                        type="number"
                        min="0"
                        className="modern-input num-tabular"
                        value={planForm.price_yearly_rp}
                        onChange={(e) =>
                          setPlanForm((prev) => ({ ...prev, price_yearly_rp: e.target.value }))
                        }
                        required
                      />
                    </div>

                    <div className="form-field-group" style={{ marginBottom: 0 }}>
                      <label className="field-label" htmlFor="plan-inp-ptype">
                        Jenis Promo Harga Coret
                      </label>
                      <InAppSelect
                        id="plan-inp-ptype"
                        value={planForm.promo_discount_type}
                        onChange={(val) =>
                          setPlanForm((prev) => ({ ...prev, promo_discount_type: val }))
                        }
                        options={[
                          { value: '', label: 'Tidak ada promo harga coret' },
                          { value: 'percent', label: 'Persentase (%)' },
                          { value: 'fixed_rp', label: 'Potongan Nominal (Rp)' },
                        ]}
                      />
                    </div>

                    {planForm.promo_discount_type && (
                      <>
                        <div className="form-field-group" style={{ marginBottom: 0 }}>
                          <label className="field-label" htmlFor="plan-inp-pval">
                            {planForm.promo_discount_type === 'percent'
                              ? 'Persen Diskon (1-100%)'
                              : 'Nominal Potongan (Rp)'}
                          </label>
                          <input
                            id="plan-inp-pval"
                            type="number"
                            min="1"
                            max={planForm.promo_discount_type === 'percent' ? 100 : 100000000}
                            className="modern-input num-tabular"
                            value={planForm.promo_discount_value}
                            onChange={(e) =>
                              setPlanForm((prev) => ({
                                ...prev,
                                promo_discount_value: e.target.value,
                              }))
                            }
                          />
                        </div>

                        <div className="form-field-group" style={{ marginBottom: 0 }}>
                          <label className="field-label" htmlFor="plan-inp-plabel">
                            Label Promo di Kartu (Opsional)
                          </label>
                          <input
                            id="plan-inp-plabel"
                            type="text"
                            className="modern-input"
                            placeholder="Contoh: Flash Sale / Diskon Opening"
                            value={planForm.promo_label}
                            onChange={(e) =>
                              setPlanForm((prev) => ({ ...prev, promo_label: e.target.value }))
                            }
                          />
                        </div>

                        <div className="form-field-group" style={{ marginBottom: 0 }}>
                          <label className="field-label" htmlFor="plan-inp-pstart">
                            Mulai Promo (WIB · Opsional)
                          </label>
                          <input
                            id="plan-inp-pstart"
                            type="datetime-local"
                            className="modern-input num-tabular"
                            value={planForm.promo_starts_at}
                            onChange={(e) =>
                              setPlanForm((prev) => ({ ...prev, promo_starts_at: e.target.value }))
                            }
                          />
                        </div>

                        <div className="form-field-group" style={{ marginBottom: 0 }}>
                          <label className="field-label" htmlFor="plan-inp-pend">
                            Berakhir Promo (WIB · Opsional)
                          </label>
                          <input
                            id="plan-inp-pend"
                            type="datetime-local"
                            className="modern-input num-tabular"
                            value={planForm.promo_expires_at}
                            onChange={(e) =>
                              setPlanForm((prev) => ({ ...prev, promo_expires_at: e.target.value }))
                            }
                          />
                        </div>
                      </>
                    )}
                  </div>

                  {planForm.promo_discount_type && (
                    <div className="admin-promo-preview-bar num-tabular">
                      <span>Pratinjau Harga Promo:</span>
                      <strong>
                        Bulanan: {formatRp(monthlyPromoPreview.effective)}
                        {monthlyPromoPreview.discount > 0 &&
                          ` (hemat ${formatRp(monthlyPromoPreview.discount)})`}
                      </strong>
                      <span>·</span>
                      <strong>
                        Tahunan: {formatRp(yearlyPromoPreview.effective)}
                        {yearlyPromoPreview.discount > 0 &&
                          ` (hemat ${formatRp(yearlyPromoPreview.discount)})`}
                      </strong>
                    </div>
                  )}
                </div>
              )}

              <div className="admin-modal-section">
                <div className="admin-modal-sec-head">
                  <Sparkles size={14} />
                  <span>3. Kuota Fitur &amp; Pembatasan</span>
                </div>
                <div className="settings-fields-grid">
                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="plan-inp-maxdev">
                      Maksimal Panel (-1 = Tanpa Batas)
                    </label>
                    <input
                      id="plan-inp-maxdev"
                      type="number"
                      min="-1"
                      max="10000"
                      className="modern-input num-tabular"
                      value={planForm.max_devices}
                      onChange={(e) =>
                        setPlanForm((prev) => ({ ...prev, max_devices: e.target.value }))
                      }
                      required
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="plan-inp-days">
                      Retensi Riwayat Grafik (Hari)
                    </label>
                    <input
                      id="plan-inp-days"
                      type="number"
                      min="1"
                      max="3660"
                      className="modern-input num-tabular"
                      value={planForm.history_days}
                      onChange={(e) =>
                        setPlanForm((prev) => ({ ...prev, history_days: e.target.value }))
                      }
                      required
                    />
                  </div>
                </div>

                <div className="admin-switches-compact" style={{ marginTop: 12 }}>
                  <div className="admin-toggle-row">
                    <div>
                      <div className="admin-row-title">Proyeksi Tagihan PLN</div>
                      <div className="admin-row-sub">Buka kalkulasi estimasi akhir bulan</div>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={planForm.forecast_enabled}
                      className={`admin-switch is-sm ${planForm.forecast_enabled ? 'on' : ''}`}
                      onClick={() =>
                        setPlanForm((prev) => ({
                          ...prev,
                          forecast_enabled: !prev.forecast_enabled,
                        }))
                      }
                    >
                      <span className="admin-switch-thumb" />
                    </button>
                  </div>

                  <div className="admin-toggle-row">
                    <div>
                      <div className="admin-row-title">Ekspor Laporan CSV</div>
                      <div className="admin-row-sub">Unduh riwayat penggunaan listrik Excel/CSV</div>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={planForm.export_enabled}
                      className={`admin-switch is-sm ${planForm.export_enabled ? 'on' : ''}`}
                      onClick={() =>
                        setPlanForm((prev) => ({
                          ...prev,
                          export_enabled: !prev.export_enabled,
                        }))
                      }
                    >
                      <span className="admin-switch-thumb" />
                    </button>
                  </div>

                  <div className="admin-toggle-row">
                    <div>
                      <div className="admin-row-title">Deteksi Anomali Lengkap (L2/L3)</div>
                      <div className="admin-row-sub">Alert kualitas tegangan &amp; lonjakan daya</div>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={planForm.anomaly_advanced}
                      className={`admin-switch is-sm ${planForm.anomaly_advanced ? 'on' : ''}`}
                      onClick={() =>
                        setPlanForm((prev) => ({
                          ...prev,
                          anomaly_advanced: !prev.anomaly_advanced,
                        }))
                      }
                    >
                      <span className="admin-switch-thumb" />
                    </button>
                  </div>

                  {!planForm.is_default_free && (
                    <>
                      <div className="admin-toggle-row">
                        <div>
                          <div className="admin-row-title">Tandai Sebagai Rekomendasi</div>
                          <div className="admin-row-sub">Sorot kartu di halaman upgrade pelanggan</div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={planForm.is_recommended}
                          className={`admin-switch is-sm ${planForm.is_recommended ? 'on' : ''}`}
                          onClick={() =>
                            setPlanForm((prev) => ({
                              ...prev,
                              is_recommended: !prev.is_recommended,
                            }))
                          }
                        >
                          <span className="admin-switch-thumb" />
                        </button>
                      </div>

                      <div className="admin-toggle-row">
                        <div>
                          <div className="admin-row-title">Paket Aktif di Katalog</div>
                          <div className="admin-row-sub">Bisa dipilih pelanggan saat upgrade</div>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={planForm.is_active}
                          className={`admin-switch is-sm ${planForm.is_active ? 'on' : ''}`}
                          onClick={() =>
                            setPlanForm((prev) => ({ ...prev, is_active: !prev.is_active }))
                          }
                        >
                          <span className="admin-switch-thumb" />
                        </button>
                      </div>
                    </>
                  )}
                </div>

                <div className="form-field-group" style={{ marginTop: 12, marginBottom: 0 }}>
                  <label className="field-label" htmlFor="plan-inp-features">
                    Poin Keunggulan Tambahan (Satu poin per baris · Opsional)
                  </label>
                  <textarea
                    id="plan-inp-features"
                    rows={3}
                    className="modern-input admin-textarea"
                    placeholder={'Misal:\nPrioritas dukungan WhatsApp\nPantau banyak lokasi terpusat'}
                    value={planForm.features_text}
                    onChange={(e) =>
                      setPlanForm((prev) => ({ ...prev, features_text: e.target.value }))
                    }
                  />
                </div>
              </div>

              <div className="pwa-guide-footer" style={{ gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setPlanModalOpen(false)}
                >
                  Batal
                </button>
                <button type="submit" className="btn btn-primary" disabled={savingPlan}>
                  <Save size={15} />
                  <span>{savingPlan ? 'Menyimpan...' : 'Simpan Paket'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Tambah / Edit Kode Kupon */}
      {discountModalOpen && (
        <div
          className="modal-overlay pwa-guide-overlay"
          onClick={() => setDiscountModalOpen(false)}
        >
          <div
            className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pwa-guide-head">
              <div>
                <h3 className="pwa-guide-title">
                  {editingDiscountId ? 'Edit Kode Kupon Promo' : 'Buat Kode Kupon Promo Baru'}
                </h3>
                <p className="pwa-guide-sub">
                  Kode dapat diklaim pelanggan saat memilih metode pembayaran untuk potongan ekstra.
                </p>
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setDiscountModalOpen(false)}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>

            {modalErr && <div className="feedback-msg error">{modalErr}</div>}

            <form onSubmit={handleSaveDiscount} className="admin-modal-stack">
              <div className="admin-modal-section">
                <div className="admin-modal-sec-head">
                  <Percent size={14} />
                  <span>1. Kode &amp; Nilai Potongan</span>
                </div>
                <div className="settings-fields-grid">
                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-code">
                      Kode Kupon (Huruf Kapital / Angka)
                    </label>
                    <input
                      id="dc-inp-code"
                      type="text"
                      className="modern-input num-tabular"
                      placeholder="Contoh: HEMAT30"
                      value={discountForm.code}
                      onChange={(e) =>
                        setDiscountForm((prev) => ({
                          ...prev,
                          code: e.target.value.toUpperCase().replace(/\s+/g, ''),
                        }))
                      }
                      required
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-label">
                      Label Promo (Tampil di Ringkasan)
                    </label>
                    <input
                      id="dc-inp-label"
                      type="text"
                      className="modern-input"
                      placeholder="Contoh: Voucher Tahun Baru"
                      value={discountForm.label}
                      onChange={(e) =>
                        setDiscountForm((prev) => ({ ...prev, label: e.target.value }))
                      }
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-type">
                      Tipe Potongan
                    </label>
                    <InAppSelect
                      id="dc-inp-type"
                      value={discountForm.discount_type}
                      onChange={(val) =>
                        setDiscountForm((prev) => ({ ...prev, discount_type: val }))
                      }
                      options={[
                        { value: 'percent', label: 'Persentase (%)' },
                        { value: 'fixed_rp', label: 'Nominal Tetap (Rp)' },
                      ]}
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-val">
                      {discountForm.discount_type === 'percent'
                        ? 'Persen Potongan (1-100%)'
                        : 'Nominal Potongan (Rp)'}
                    </label>
                    <input
                      id="dc-inp-val"
                      type="number"
                      min="1"
                      max={discountForm.discount_type === 'percent' ? 100 : 100000000}
                      className="modern-input num-tabular"
                      value={discountForm.discount_value}
                      onChange={(e) =>
                        setDiscountForm((prev) => ({ ...prev, discount_value: e.target.value }))
                      }
                      required
                    />
                  </div>

                  {discountForm.discount_type === 'percent' && (
                    <div className="form-field-group" style={{ marginBottom: 0 }}>
                      <label className="field-label" htmlFor="dc-inp-cap">
                        Maksimal Potongan (Rp · Kosong = Tanpa Batas)
                      </label>
                      <input
                        id="dc-inp-cap"
                        type="number"
                        min="0"
                        className="modern-input num-tabular"
                        placeholder="Mis. 25000"
                        value={discountForm.max_discount_rp}
                        onChange={(e) =>
                          setDiscountForm((prev) => ({ ...prev, max_discount_rp: e.target.value }))
                        }
                      />
                    </div>
                  )}

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-min">
                      Minimal Tagihan (Rp · 0 = Bebas)
                    </label>
                    <input
                      id="dc-inp-min"
                      type="number"
                      min="0"
                      className="modern-input num-tabular"
                      value={discountForm.min_purchase_rp}
                      onChange={(e) =>
                        setDiscountForm((prev) => ({ ...prev, min_purchase_rp: e.target.value }))
                      }
                    />
                  </div>
                </div>
              </div>

              <div className="admin-modal-section">
                <div className="admin-modal-sec-head">
                  <CalendarClock size={14} />
                  <span>2. Sasaran, Kuota &amp; Masa Berlaku (WIB)</span>
                </div>
                <div className="settings-fields-grid">
                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-plan">
                      Target Paket Langganan
                    </label>
                    <InAppSelect
                      id="dc-inp-plan"
                      value={discountForm.target_plan_slug}
                      onChange={(val) =>
                        setDiscountForm((prev) => ({ ...prev, target_plan_slug: val }))
                      }
                      options={[
                        { value: '', label: 'Semua Paket Berbayar' },
                        ...paidPlans.map((p) => ({
                          value: p.slug,
                          label: `Khusus ${p.name} (${p.slug})`,
                        })),
                      ]}
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-cycle">
                      Target Siklus Tagihan
                    </label>
                    <InAppSelect
                      id="dc-inp-cycle"
                      value={discountForm.target_cycle}
                      onChange={(val) =>
                        setDiscountForm((prev) => ({ ...prev, target_cycle: val }))
                      }
                      options={[
                        { value: '', label: 'Bulanan & Tahunan' },
                        { value: 'monthly', label: 'Hanya Bulanan' },
                        { value: 'yearly', label: 'Hanya Tahunan' },
                      ]}
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-uses">
                      Batas Total Klaim (Kosong = Tanpa Batas)
                    </label>
                    <input
                      id="dc-inp-uses"
                      type="number"
                      min="1"
                      className="modern-input num-tabular"
                      placeholder="Mis. 50"
                      value={discountForm.max_uses}
                      onChange={(e) =>
                        setDiscountForm((prev) => ({ ...prev, max_uses: e.target.value }))
                      }
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-start">
                      Mulai Berlaku (WIB · Opsional)
                    </label>
                    <input
                      id="dc-inp-start"
                      type="datetime-local"
                      className="modern-input num-tabular"
                      value={discountForm.starts_at}
                      onChange={(e) =>
                        setDiscountForm((prev) => ({ ...prev, starts_at: e.target.value }))
                      }
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="dc-inp-end">
                      Berakhir (WIB · Opsional)
                    </label>
                    <input
                      id="dc-inp-end"
                      type="datetime-local"
                      className="modern-input num-tabular"
                      value={discountForm.expires_at}
                      onChange={(e) =>
                        setDiscountForm((prev) => ({ ...prev, expires_at: e.target.value }))
                      }
                    />
                  </div>
                </div>

                <div className="admin-toggle-row" style={{ marginTop: 12 }}>
                  <div>
                    <div className="admin-row-title">Status Kupon Aktif</div>
                    <div className="admin-row-sub">Matikan untuk menunda/menghentikan pemakaian</div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={discountForm.is_active}
                    className={`admin-switch is-sm ${discountForm.is_active ? 'on' : ''}`}
                    onClick={() =>
                      setDiscountForm((prev) => ({ ...prev, is_active: !prev.is_active }))
                    }
                  >
                    <span className="admin-switch-thumb" />
                  </button>
                </div>
              </div>

              <div className="pwa-guide-footer" style={{ gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setDiscountModalOpen(false)}
                >
                  Batal
                </button>
                <button type="submit" className="btn btn-primary" disabled={savingDiscount}>
                  <Save size={15} />
                  <span>{savingDiscount ? 'Menyimpan...' : 'Simpan Kupon'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Cepat Atur Promo Harga Coret Paket */}
      {quickPromoPlan && (
        <div
          className="modal-overlay pwa-guide-overlay"
          onClick={() => setQuickPromoPlan(null)}
        >
          <div
            className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pwa-guide-head">
              <div>
                <h3 className="pwa-guide-title">Promo Harga Coret · {quickPromoPlan.name}</h3>
                <p className="pwa-guide-sub">
                  Potongan otomatis langsung tampil dengan harga asli dicoret di katalog pelanggan.
                </p>
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setQuickPromoPlan(null)}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>

            {modalErr && <div className="feedback-msg error">{modalErr}</div>}

            <form onSubmit={handleSaveQuickPromo} className="admin-modal-stack">
              <div className="admin-modal-section">
                <div className="settings-fields-grid">
                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="qp-type">
                      Jenis Potongan
                    </label>
                    <InAppSelect
                      id="qp-type"
                      value={quickPromoForm.promo_discount_type}
                      onChange={(val) =>
                        setQuickPromoForm((prev) => ({ ...prev, promo_discount_type: val }))
                      }
                      options={[
                        { value: 'percent', label: 'Persentase (%)' },
                        { value: 'fixed_rp', label: 'Potongan Nominal (Rp)' },
                      ]}
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="qp-val">
                      {quickPromoForm.promo_discount_type === 'percent'
                        ? 'Persen Diskon (1-100%)'
                        : 'Nominal Potongan (Rp)'}
                    </label>
                    <input
                      id="qp-val"
                      type="number"
                      min="1"
                      max={quickPromoForm.promo_discount_type === 'percent' ? 100 : 100000000}
                      className="modern-input num-tabular"
                      value={quickPromoForm.promo_discount_value}
                      onChange={(e) =>
                        setQuickPromoForm((prev) => ({
                          ...prev,
                          promo_discount_value: e.target.value,
                        }))
                      }
                      required
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="qp-label">
                      Label Badge Promo (Opsional)
                    </label>
                    <input
                      id="qp-label"
                      type="text"
                      className="modern-input"
                      placeholder="Contoh: Flash Sale / Diskon Awal Bulan"
                      value={quickPromoForm.promo_label}
                      onChange={(e) =>
                        setQuickPromoForm((prev) => ({ ...prev, promo_label: e.target.value }))
                      }
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="qp-start">
                      Mulai Berlaku (WIB · Opsional)
                    </label>
                    <input
                      id="qp-start"
                      type="datetime-local"
                      className="modern-input num-tabular"
                      value={quickPromoForm.promo_starts_at}
                      onChange={(e) =>
                        setQuickPromoForm((prev) => ({
                          ...prev,
                          promo_starts_at: e.target.value,
                        }))
                      }
                    />
                  </div>

                  <div className="form-field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label" htmlFor="qp-end">
                      Berakhir (WIB · Opsional)
                    </label>
                    <input
                      id="qp-end"
                      type="datetime-local"
                      className="modern-input num-tabular"
                      value={quickPromoForm.promo_expires_at}
                      onChange={(e) =>
                        setQuickPromoForm((prev) => ({
                          ...prev,
                          promo_expires_at: e.target.value,
                        }))
                      }
                    />
                  </div>
                </div>

                <div className="admin-promo-preview-bar num-tabular">
                  <span>Pratinjau Harga Akhir:</span>
                  <strong>
                    Bulanan: {formatRp(quickMonthPreview.effective)} (normal{' '}
                    {formatRp(quickPromoPlan.price_monthly_rp)})
                  </strong>
                  <span>·</span>
                  <strong>
                    Tahunan: {formatRp(quickYearPreview.effective)} (normal{' '}
                    {formatRp(quickPromoPlan.price_yearly_rp)})
                  </strong>
                </div>
              </div>

              <div className="pwa-guide-footer" style={{ gap: 8, flexWrap: 'wrap' }}>
                {quickPromoPlan.promo_discount_type && (
                  <button
                    type="button"
                    className="btn btn-danger-ghost"
                    disabled={savingQuickPromo}
                    onClick={() => handleClearQuickPromo(quickPromoPlan)}
                  >
                    Hapus Promo
                  </button>
                )}
                <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setQuickPromoPlan(null)}
                  >
                    Batal
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={savingQuickPromo}>
                    <Save size={15} />
                    <span>{savingQuickPromo ? 'Menyimpan...' : 'Simpan Promo'}</span>
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

