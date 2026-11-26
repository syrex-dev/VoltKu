import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  CheckCircle2,
  XCircle,
  Eye,
  QrCode,
  Landmark,
  Wallet,
  Plus,
  Pencil,
  Trash2,
  Upload,
  X,
  Save,
  Search,
  Copy,
  Clock,
  ZoomIn,
} from 'lucide-react'
import { apiRequest, buildApiUrl } from '../api/client'
import { formatDateTimeWIB, formatRp } from '../utils/formatters'
import { compressImageToDataUrl } from '../utils/imageCompress'
import { useAuthImage } from '../utils/authImage'
import { InAppSelect } from './InAppSelect'

const ACTIVE_UPGRADE_STATUSES = ['verifying', 'awaiting_payment', 'pending']

const STATUS_BADGE = {
  verifying: { cls: 'verifying', label: 'Perlu Dicek' },
  awaiting_payment: { cls: 'awaiting', label: 'Menunggu Bayar' },
  pending: { cls: 'awaiting', label: 'Menunggu' },
  approved: { cls: 'approved', label: 'Lunas / Disetujui' },
  rejected: { cls: 'rejected', label: 'Ditolak' },
  cancelled: { cls: 'muted', label: 'Dibatalkan' },
  expired: { cls: 'expired', label: 'Kedaluwarsa' },
}

const TYPE_META = {
  qris: { label: 'QRIS', icon: QrCode },
  bank: { label: 'Transfer Bank', icon: Landmark },
  ewallet: { label: 'E-Wallet', icon: Wallet },
}

const PM_TYPES = [
  { value: 'qris', label: 'QRIS (Scan Kode QR)' },
  { value: 'bank', label: 'Transfer Bank' },
  { value: 'ewallet', label: 'E-Wallet (DANA / OVO / GoPay)' },
]

function AdminProofPreviewModal({ req, token, resolvingId, onClose, onApprove, onReject }) {
  const { imageUrl, loading, error } = useAuthImage(
    req?.id ? `/api/admin/upgrade-requests/${req.id}/proof` : '',
    token,
    Boolean(req?.id)
  )
  const [rejectReason, setRejectReason] = useState('')

  if (!req) return null
  const isActive = ACTIVE_UPGRADE_STATUSES.includes(req.status)
  const defaultDays = req.billing_cycle === 'yearly' ? 365 : 30

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head">
          <div>
            <h3 className="pwa-guide-title">
              Bukti Pembayaran {req.order_code || `#${req.id}`}
            </h3>
            <p className="pwa-guide-sub">
              {req.user_name || `User #${req.user_id}`} ({req.user_email || '—'}) ·{' '}
              <strong className="num-tabular">{formatRp(req.amount_rp)}</strong>
            </p>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <div className="pay-verifying-summary" style={{ marginBottom: 12 }}>
          <div>
            Metode: <strong>{req.payment_method_label || 'Manual'}</strong> · Paket{' '}
            <strong>{req.billing_cycle === 'yearly' ? 'Tahunan' : 'Bulanan'}</strong>
          </div>
          {req.submitted_at && (
            <div className="pay-verifying-sub">
              Dikirim pada {formatDateTimeWIB(req.submitted_at)}
            </div>
          )}
          {req.user_note && (
            <div className="pay-verifying-sub">Catatan pembeli: &ldquo;{req.user_note}&rdquo;</div>
          )}
        </div>

        <div className="pay-uploaded-proof-box" style={{ marginTop: 0, textAlign: 'center' }}>
          {loading ? (
            <div className="pay-methods-loading">Memuat foto bukti transfer...</div>
          ) : error ? (
            <div className="feedback-msg error">{error}</div>
          ) : imageUrl ? (
            <img
              src={imageUrl}
              alt={`Bukti bayar ${req.order_code || req.id}`}
              style={{
                maxWidth: '100%',
                maxHeight: '46vh',
                objectFit: 'contain',
                borderRadius: 10,
                border: '1px solid var(--border-subtle)',
              }}
            />
          ) : null}
        </div>

        {isActive && (
          <div style={{ marginTop: 14 }}>
            <div className="form-field-group" style={{ marginBottom: 10 }}>
              <input
                type="text"
                className="modern-input"
                maxLength={180}
                placeholder="Catatan admin / alasan penolakan (opsional)"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
              />
            </div>
            <div className="plan-cta-row">
              <button
                type="button"
                className="btn btn-primary plan-cta-primary"
                disabled={resolvingId === req.id}
                onClick={async () => {
                  await onApprove(req.id, defaultDays, rejectReason.trim() || null)
                  onClose()
                }}
              >
                <CheckCircle2 size={15} />
                <span>
                  Konfirmasi &amp; Aktifkan Pro ({req.billing_cycle === 'yearly' ? '1 Thn' : '30 Hr'})
                </span>
              </button>
              <button
                type="button"
                className="btn btn-danger-ghost"
                disabled={resolvingId === req.id}
                onClick={async () => {
                  await onReject(req.id, rejectReason.trim() || null)
                  onClose()
                }}
              >
                <XCircle size={15} />
                <span>Tolak</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export function AdminPaymentSummaryStrip({ upgradeRequests = [], methodsCount = null }) {
  const stats = useMemo(() => {
    let verifying = 0
    let awaiting = 0
    let approved = 0
    let approvedRevenueRp = 0

    for (const r of upgradeRequests) {
      if (r.status === 'verifying' || r.status === 'pending') {
        verifying += 1
      } else if (r.status === 'awaiting_payment') {
        awaiting += 1
      } else if (r.status === 'approved') {
        approved += 1
        approvedRevenueRp += Number(r.amount_rp || 0)
      }
    }
    return { verifying, awaiting, approved, approvedRevenueRp }
  }, [upgradeRequests])

  return (
    <div className="admin-kpi-grid">
      <div className={`clean-sheet admin-kpi-card ${stats.verifying > 0 ? 'is-highlight-warn' : ''}`}>
        <span className="admin-kpi-label">Perlu Verifikasi</span>
        <strong className={`admin-kpi-value num-tabular ${stats.verifying > 0 ? 'brand-amber-text' : ''}`}>
          {stats.verifying}
        </strong>
        <span className="admin-kpi-sub">
          {stats.verifying > 0 ? 'Bukti bayar siap diperiksa' : 'Semua bukti sudah ditinjau'}
        </span>
      </div>

      <div className="clean-sheet admin-kpi-card">
        <span className="admin-kpi-label">Menunggu Bayar</span>
        <strong className="admin-kpi-value num-tabular brand-blue-text">{stats.awaiting}</strong>
        <span className="admin-kpi-sub">Tagihan aktif belum dibayar</span>
      </div>

      <div className="clean-sheet admin-kpi-card">
        <span className="admin-kpi-label">Omzet Terkonfirmasi</span>
        <strong className="admin-kpi-value num-tabular brand-emerald-text">
          {formatRp(stats.approvedRevenueRp)}
        </strong>
        <span className="admin-kpi-sub">{stats.approved} transaksi lunas</span>
      </div>

      <div className="clean-sheet admin-kpi-card">
        <span className="admin-kpi-label">Metode Pembayaran</span>
        <strong className="admin-kpi-value num-tabular">
          {methodsCount ? `${methodsCount.active}/${methodsCount.total}` : '—'}
        </strong>
        <span className="admin-kpi-sub">Saluran aktif tampil ke pembeli</span>
      </div>
    </div>
  )
}

export function AdminUpgradeRequestsCard({
  upgradeRequests = [],
  token,
  onLogout,
  onResolved,
  onNotice,
}) {
  const [filterMode, setFilterMode] = useState('needs_action')
  const [searchQuery, setSearchQuery] = useState('')
  const [resolvingId, setResolvingId] = useState(null)
  const [previewReq, setPreviewReq] = useState(null)
  const [rejectDraftId, setRejectDraftId] = useState(null)
  const [rejectNote, setRejectNote] = useState('')

  const counts = useMemo(() => {
    const needsAction = upgradeRequests.filter((r) => ACTIVE_UPGRADE_STATUSES.includes(r.status)).length
    const verifying = upgradeRequests.filter((r) => r.status === 'verifying' || r.status === 'pending').length
    const awaiting = upgradeRequests.filter((r) => r.status === 'awaiting_payment').length
    const approved = upgradeRequests.filter((r) => r.status === 'approved').length
    return { needsAction, verifying, awaiting, approved, all: upgradeRequests.length }
  }, [upgradeRequests])

  const visibleItems = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return upgradeRequests
      .filter((r) => {
        if (filterMode === 'needs_action' && !ACTIVE_UPGRADE_STATUSES.includes(r.status)) return false
        if (filterMode === 'awaiting' && r.status !== 'awaiting_payment') return false
        if (filterMode === 'approved' && r.status !== 'approved') return false
        if (!q) return true
        return (
          (r.order_code || '').toLowerCase().includes(q) ||
          (r.user_name || '').toLowerCase().includes(q) ||
          (r.user_email || '').toLowerCase().includes(q) ||
          (r.payment_method_label || '').toLowerCase().includes(q)
        )
      })
      .slice(0, 30)
  }, [upgradeRequests, filterMode, searchQuery])

  const handleResolve = async (reqId, action, durationDays = null, adminNote = null) => {
    setResolvingId(reqId)
    if (onNotice) onNotice(null)
    try {
      const body = { action }
      if (durationDays !== null) body.duration_days = durationDays
      if (adminNote) body.admin_note = adminNote
      await apiRequest(
        `/api/admin/upgrade-requests/${reqId}`,
        { method: 'PATCH', body },
        token,
        onLogout
      )
      setRejectDraftId(null)
      setRejectNote('')
      if (onNotice) {
        onNotice({
          type: 'success',
          text:
            action === 'approve'
              ? 'Pembayaran dikonfirmasi dan paket VoltKu Pro langsung aktif.'
              : 'Tagihan ditolak beserta catatan ke pembeli.',
        })
      }
      if (onResolved) await onResolved()
    } catch (err) {
      if (onNotice) {
        onNotice({ type: 'error', text: err.message || 'Gagal memproses tagihan upgrade.' })
      }
    } finally {
      setResolvingId(null)
    }
  }

  return (
    <>
      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>
              Konfirmasi Pembayaran &amp; Upgrade Pro
              {counts.verifying > 0 && (
                <span className="admin-pill warn" style={{ marginLeft: 8 }}>
                  {counts.verifying} Perlu Dicek
                </span>
              )}
            </h3>
            <p className="admin-row-sub">
              Periksa bukti transfer masuk lalu aktifkan paket Pro pelanggan secara instan.
            </p>
          </div>
          <div className="admin-pm-filter-tabs">
            <button
              type="button"
              className={`admin-filter-pill ${filterMode === 'needs_action' ? 'active' : ''}`}
              onClick={() => setFilterMode('needs_action')}
            >
              Perlu Tindakan ({counts.needsAction})
            </button>
            <button
              type="button"
              className={`admin-filter-pill ${filterMode === 'awaiting' ? 'active' : ''}`}
              onClick={() => setFilterMode('awaiting')}
            >
              Menunggu Bayar ({counts.awaiting})
            </button>
            <button
              type="button"
              className={`admin-filter-pill ${filterMode === 'approved' ? 'active' : ''}`}
              onClick={() => setFilterMode('approved')}
            >
              Lunas ({counts.approved})
            </button>
            <button
              type="button"
              className={`admin-filter-pill ${filterMode === 'all' ? 'active' : ''}`}
              onClick={() => setFilterMode('all')}
            >
              Semua ({counts.all})
            </button>
          </div>
        </div>

        {upgradeRequests.length > 0 && (
          <div className="admin-search-wrap" style={{ marginBottom: 12 }}>
            <Search size={15} className="admin-search-icon" />
            <input
              type="text"
              className="modern-input admin-search-input"
              placeholder="Cari kode order (VK-...), nama, email, atau metode bayar..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        )}

        {visibleItems.length === 0 ? (
          <div className="pay-empty-state">
            <Clock size={22} />
            <div>
              <strong>
                {filterMode === 'needs_action'
                  ? 'Belum ada bukti bayar atau tagihan aktif yang perlu diproses'
                  : 'Tidak ada transaksi yang cocok'}
              </strong>
              <span>
                {filterMode === 'needs_action' && counts.all > 0
                  ? `Ada ${counts.all} riwayat transaksi sebelumnya — klik tab "Semua" untuk meninjau.`
                  : 'Saat pelanggan membuat tagihan upgrade VoltKu Pro, datanya akan muncul di sini.'}
              </span>
            </div>
          </div>
        ) : (
          <div className="admin-upgrade-list">
            {visibleItems.map((req) => {
              const badge = STATUS_BADGE[req.status] || STATUS_BADGE.pending
              const isActive = ACTIVE_UPGRADE_STATUSES.includes(req.status)
              const defaultDays = req.billing_cycle === 'yearly' ? 365 : 30
              const initialLetter = (req.user_name || req.user_email || 'U').charAt(0).toUpperCase()
              return (
                <div
                  key={req.id}
                  className={`admin-tx-card ${req.status === 'verifying' ? 'is-verifying' : ''}`}
                >
                  <div className="admin-tx-main">
                    <div className="admin-tx-avatar">{initialLetter}</div>
                    <div className="admin-upgrade-info">
                      <div className="admin-tx-top-line">
                        {req.order_code && (
                          <span className="pay-order-code num-tabular">{req.order_code}</span>
                        )}
                        <strong className="admin-dev-name">
                          {req.user_name || `User #${req.user_id}`}
                        </strong>
                        <span className="admin-dev-id">({req.user_email || '—'})</span>
                        <span className={`pay-status-badge ${badge.cls}`}>{badge.label}</span>
                      </div>

                      <div className="admin-tx-meta-line num-tabular">
                        <span className="admin-tx-amount">{formatRp(req.amount_rp)}</span>
                        <span>·</span>
                        <span>{req.billing_cycle === 'yearly' ? 'Paket Tahunan' : 'Paket Bulanan'}</span>
                        <span>·</span>
                        <span>{req.payment_method_label || 'Manual'}</span>
                        <span>·</span>
                        <span>{formatDateTimeWIB(req.submitted_at || req.created_at)}</span>
                      </div>

                      {req.user_note && (
                        <div className="admin-tx-note">Catatan pembeli: &ldquo;{req.user_note}&rdquo;</div>
                      )}
                      {req.admin_note && (
                        <div className="admin-tx-note is-admin">Admin: {req.admin_note}</div>
                      )}

                      {rejectDraftId === req.id && (
                        <div className="admin-tx-reject-box">
                          <input
                            type="text"
                            className="modern-input"
                            style={{ flex: 1, minWidth: 180 }}
                            placeholder="Alasan penolakan untuk pembeli..."
                            value={rejectNote}
                            onChange={(e) => setRejectNote(e.target.value)}
                          />
                          <button
                            type="button"
                            className="btn btn-danger-ghost btn-compact"
                            disabled={resolvingId === req.id}
                            onClick={() =>
                              handleResolve(req.id, 'reject', null, rejectNote.trim() || null)
                            }
                          >
                            Kirim Tolak
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-compact"
                            onClick={() => {
                              setRejectDraftId(null)
                              setRejectNote('')
                            }}
                          >
                            Batal
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="admin-upgrade-actions">
                    {req.has_payment_proof && (
                      <button
                        type="button"
                        className="btn btn-secondary btn-compact"
                        onClick={() => setPreviewReq(req)}
                      >
                        <Eye size={14} />
                        <span>Lihat Bukti</span>
                      </button>
                    )}

                    {isActive && (
                      <>
                        <button
                          type="button"
                          className="btn btn-primary btn-compact"
                          disabled={resolvingId === req.id}
                          onClick={() => handleResolve(req.id, 'approve', defaultDays)}
                        >
                          <CheckCircle2 size={14} />
                          <span>
                            Konfirmasi ({req.billing_cycle === 'yearly' ? '1 Thn' : '30 Hr'})
                          </span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-compact"
                          disabled={resolvingId === req.id}
                          onClick={() => handleResolve(req.id, 'approve', 0)}
                        >
                          <span>Permanen</span>
                        </button>
                        <button
                          type="button"
                          className="btn btn-danger-ghost btn-compact"
                          disabled={resolvingId === req.id}
                          onClick={() => {
                            setRejectDraftId(req.id)
                            setRejectNote('')
                          }}
                        >
                          <XCircle size={14} />
                          <span>Tolak</span>
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      <AdminProofPreviewModal
        req={previewReq}
        token={token}
        resolvingId={resolvingId}
        onClose={() => setPreviewReq(null)}
        onApprove={(id, days, note) => handleResolve(id, 'approve', days, note)}
        onReject={(id, note) => handleResolve(id, 'reject', null, note)}
      />
    </>
  )
}

export function AdminPaymentMethodsCard({
  token,
  onLogout,
  onNotice,
  refreshSignal = 0,
  onMethodsLoaded = null,
}) {
  const [methods, setMethods] = useState([])
  const [loading, setLoading] = useState(true)
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [pmType, setPmType] = useState('qris')
  const [label, setLabel] = useState('')
  const [accountNumber, setAccountNumber] = useState('')
  const [accountHolder, setAccountHolder] = useState('')
  const [instructions, setInstructions] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [sortOrder, setSortOrder] = useState('1')
  const [qrisBase64, setQrisBase64] = useState('')
  const [saving, setSaving] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [copiedId, setCopiedId] = useState(null)
  const [zoomQrisSrc, setZoomQrisSrc] = useState('')

  const loadMethods = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const list = await apiRequest('/api/admin/payment-methods', {}, token, onLogout)
      const items = Array.isArray(list) ? list : []
      setMethods(items)
      if (onMethodsLoaded) {
        onMethodsLoaded({
          total: items.length,
          active: items.filter((m) => m.is_active).length,
        })
      }
    } catch {
      setMethods([])
    } finally {
      setLoading(false)
    }
  }, [token, onLogout, onMethodsLoaded])

  useEffect(() => {
    loadMethods()
  }, [loadMethods, refreshSignal])

  const openCreate = () => {
    setEditingId(null)
    setPmType('qris')
    setLabel('')
    setAccountNumber('')
    setAccountHolder('')
    setInstructions('')
    setIsActive(true)
    setSortOrder(String(methods.length + 1))
    setQrisBase64('')
    setEditorOpen(true)
  }

  const openEdit = (pm) => {
    setEditingId(pm.id)
    setPmType(pm.type || 'bank')
    setLabel(pm.label || '')
    setAccountNumber(pm.account_number || '')
    setAccountHolder(pm.account_holder || '')
    setInstructions(pm.instructions || '')
    setIsActive(Boolean(pm.is_active))
    setSortOrder(String(pm.sort_order ?? 0))
    setQrisBase64('')
    setEditorOpen(true)
  }

  const handleSelectQrisFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    try {
      const encoded = await compressImageToDataUrl(file, {
        maxDimension: 1200,
        quality: 0.92,
        mimeType: 'image/png',
        preserveSharpQr: true,
      })
      setQrisBase64(encoded)
    } catch (err) {
      if (onNotice) {
        onNotice({ type: 'error', text: err.message || 'Gagal memuat gambar QRIS.' })
      }
    }
  }

  const handleCopyAccount = async (pm) => {
    if (!pm.account_number) return
    try {
      await navigator.clipboard.writeText(pm.account_number)
      setCopiedId(pm.id)
      window.setTimeout(() => setCopiedId(null), 1600)
    } catch {
      // Abaikan jika clipboard ditolak
    }
  }

  const handleSaveMethod = async () => {
    if (!label.trim() || label.trim().length < 2) {
      if (onNotice) onNotice({ type: 'error', text: 'Nama metode pembayaran minimal 2 karakter.' })
      return
    }
    setSaving(true)
    if (onNotice) onNotice(null)
    try {
      const payload = {
        type: pmType,
        label: label.trim(),
        account_number: accountNumber.trim() || null,
        account_holder: accountHolder.trim() || null,
        instructions: instructions.trim() || null,
        is_active: isActive,
        sort_order: parseInt(sortOrder, 10) || 0,
      }
      if (qrisBase64) {
        payload.qris_image_base64 = qrisBase64
      }

      if (editingId) {
        await apiRequest(
          `/api/admin/payment-methods/${editingId}`,
          { method: 'PATCH', body: payload },
          token,
          onLogout
        )
      } else {
        await apiRequest(
          '/api/admin/payment-methods',
          { method: 'POST', body: payload },
          token,
          onLogout
        )
      }
      setEditorOpen(false)
      if (onNotice) {
        onNotice({
          type: 'success',
          text: editingId ? 'Metode pembayaran diperbarui.' : 'Metode pembayaran ditambahkan.',
        })
      }
      await loadMethods()
    } catch (err) {
      if (onNotice) {
        onNotice({ type: 'error', text: err.message || 'Gagal menyimpan metode pembayaran.' })
      }
    } finally {
      setSaving(false)
    }
  }

  const handleToggleActive = async (pm) => {
    try {
      await apiRequest(
        `/api/admin/payment-methods/${pm.id}`,
        { method: 'PATCH', body: { is_active: !pm.is_active } },
        token,
        onLogout
      )
      await loadMethods()
    } catch (err) {
      if (onNotice) onNotice({ type: 'error', text: err.message || 'Gagal mengubah status.' })
    }
  }

  const handleDeleteMethod = async (id) => {
    try {
      await apiRequest(`/api/admin/payment-methods/${id}`, { method: 'DELETE' }, token, onLogout)
      setConfirmDeleteId(null)
      if (onNotice) onNotice({ type: 'success', text: 'Metode pembayaran dihapus.' })
      await loadMethods()
    } catch (err) {
      if (onNotice) onNotice({ type: 'error', text: err.message || 'Gagal menghapus metode.' })
    }
  }

  return (
    <section className="clean-sheet admin-card-block">
      <div className="admin-card-head is-split">
        <div>
          <h3>Metode Pembayaran Manual (QRIS / Rekening / E-Wallet)</h3>
          <p className="admin-row-sub">
            Saluran aktif otomatis tampil di halaman checkout pelanggan saat upgrade VoltKu Pro.
          </p>
        </div>
        <button type="button" className="btn btn-primary btn-compact" onClick={openCreate}>
          <Plus size={14} />
          <span>Tambah Metode</span>
        </button>
      </div>

      {loading ? (
        <div className="pay-methods-loading">Memuat daftar metode pembayaran...</div>
      ) : methods.length === 0 ? (
        <div className="pay-empty-state">
          <Wallet size={22} />
          <div>
            <strong>Belum ada metode pembayaran manual</strong>
            <span>
              Klik <strong>Tambah Metode</strong> untuk mengunggah QRIS atau menambahkan rekening bank /
              e-wallet.
            </span>
          </div>
        </div>
      ) : (
        <div className="admin-pm-grid">
          {methods.map((pm) => {
            const meta = TYPE_META[pm.type] || TYPE_META.bank
            const Icon = meta.icon
            const qrisUrl = pm.has_qris_image && pm.qris_image_url ? buildApiUrl(pm.qris_image_url) : ''
            return (
              <div key={pm.id} className={`admin-pm-card ${pm.is_active ? '' : 'is-inactive'}`}>
                <div className="admin-pm-card-head">
                  <span className="pay-method-type-badge">
                    <Icon size={13} />
                    <span>{meta.label}</span>
                  </span>
                  <div className="admin-pm-head-right">
                    <span className={`admin-pill ${pm.is_active ? 'ok' : 'muted'}`}>
                      {pm.is_active ? 'Aktif' : 'Nonaktif'}
                    </span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={Boolean(pm.is_active)}
                      aria-label={`Aktifkan ${pm.label}`}
                      className={`admin-switch is-sm ${pm.is_active ? 'on' : ''}`}
                      onClick={() => handleToggleActive(pm)}
                    >
                      <span className="admin-switch-thumb" />
                    </button>
                  </div>
                </div>

                <div className="admin-pm-card-body">
                  {qrisUrl ? (
                    <button
                      type="button"
                      className="admin-pm-qris-btn"
                      onClick={() => setZoomQrisSrc(qrisUrl)}
                      title="Perbesar QRIS"
                    >
                      <img src={qrisUrl} alt={pm.label} className="admin-pm-qris-thumb" />
                      <span className="admin-pm-qris-zoom">
                        <ZoomIn size={11} />
                      </span>
                    </button>
                  ) : (
                    <span className="admin-pm-icon-tile">
                      <Icon size={22} />
                    </span>
                  )}

                  <div className="admin-pm-details">
                    <div className="admin-pm-title">{pm.label}</div>
                    {pm.account_number && (
                      <div className="admin-pm-acct-row">
                        <span className="admin-pm-acct num-tabular">{pm.account_number}</span>
                        <button
                          type="button"
                          className="admin-pm-copy-btn"
                          onClick={() => handleCopyAccount(pm)}
                          title="Salin nomor rekening"
                        >
                          <Copy size={12} />
                          <span>{copiedId === pm.id ? 'Disalin' : 'Salin'}</span>
                        </button>
                      </div>
                    )}
                    <div className="admin-pm-holder">
                      {pm.account_holder ? `a.n. ${pm.account_holder}` : 'Tanpa keterangan penerima'}
                    </div>
                  </div>
                </div>

                {pm.instructions && <div className="admin-pm-inst">{pm.instructions}</div>}

                <div className="admin-pm-card-footer">
                  <span className="admin-pm-sort num-tabular">Urutan #{pm.sort_order ?? 0}</span>
                  <div className="admin-pm-actions">
                    <button
                      type="button"
                      className="btn btn-secondary btn-compact"
                      onClick={() => openEdit(pm)}
                    >
                      <Pencil size={13} />
                      <span>Edit</span>
                    </button>
                    {confirmDeleteId === pm.id ? (
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-compact"
                        onClick={() => handleDeleteMethod(pm.id)}
                      >
                        Yakin Hapus?
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-compact"
                        onClick={() => setConfirmDeleteId(pm.id)}
                        aria-label={`Hapus ${pm.label}`}
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {editorOpen && (
        <div className="admin-pm-form-card">
          <div className="admin-card-head is-split" style={{ marginBottom: 12 }}>
            <div>
              <strong style={{ fontSize: 14 }}>
                {editingId ? 'Edit Metode Pembayaran' : 'Tambah Metode Pembayaran Baru'}
              </strong>
            </div>
            <button
              type="button"
              className="btn-icon-close"
              onClick={() => setEditorOpen(false)}
              aria-label="Tutup form metode"
            >
              <X size={16} />
            </button>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="pm-type-sel">
                Tipe Metode
              </label>
              <InAppSelect id="pm-type-sel" value={pmType} onChange={setPmType} options={PM_TYPES} />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="pm-label-inp">
                Nama Tampilan
              </label>
              <input
                id="pm-label-inp"
                type="text"
                className="modern-input"
                placeholder="Contoh: QRIS VoltKu / Transfer BCA / DANA"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="pm-acct-inp">
                Nomor Rekening / No. E-Wallet (opsional untuk QRIS)
              </label>
              <input
                id="pm-acct-inp"
                type="text"
                className="modern-input num-tabular"
                placeholder="Contoh: 1234567890"
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="pm-holder-inp">
                Nama Penerima (Atas Nama)
              </label>
              <input
                id="pm-holder-inp"
                type="text"
                className="modern-input"
                placeholder="Contoh: VoltKu Indonesia"
                value={accountHolder}
                onChange={(e) => setAccountHolder(e.target.value)}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="pm-sort-inp">
                Urutan Tampil
              </label>
              <input
                id="pm-sort-inp"
                type="number"
                className="modern-input num-tabular"
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)}
              />
            </div>

            {pmType === 'qris' && (
              <div className="form-field-group">
                <label className="field-label">Gambar Kode QRIS (JPG / PNG / WEBP)</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <label className="btn btn-secondary btn-compact" style={{ cursor: 'pointer' }}>
                    <Upload size={14} />
                    <span>{qrisBase64 ? 'Ganti Gambar QRIS' : 'Pilih File QRIS'}</span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleSelectQrisFile}
                      className="pay-file-input-hidden"
                    />
                  </label>
                  {qrisBase64 && (
                    <img
                      src={qrisBase64}
                      alt="Pratinjau QRIS baru"
                      className="admin-pm-qris-mini"
                    />
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="form-field-group" style={{ marginTop: 8 }}>
            <label className="field-label" htmlFor="pm-inst-inp">
              Instruksi Tambahan (opsional)
            </label>
            <textarea
              id="pm-inst-inp"
              rows={2}
              className="modern-input admin-textarea"
              placeholder="Contoh: Scan QRIS di atas lalu unggah bukti bayar agar segera diproses admin."
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
            />
          </div>

          <label className="admin-checkbox-row" style={{ marginBottom: 12 }}>
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            <span>Aktif (tampilkan ke pelanggan di halaman checkout)</span>
          </label>

          <div className="admin-pm-actions">
            <button
              type="button"
              className="btn btn-primary btn-compact"
              disabled={saving}
              onClick={handleSaveMethod}
            >
              <Save size={14} />
              <span>{saving ? 'Menyimpan...' : 'Simpan Metode'}</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              onClick={() => setEditorOpen(false)}
            >
              Batal
            </button>
          </div>
        </div>
      )}

      {zoomQrisSrc && (
        <div
          className="pay-lightbox-overlay"
          onClick={() => setZoomQrisSrc('')}
        >
          <div className="pay-lightbox-box" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="btn-icon-close pay-lightbox-close"
              onClick={() => setZoomQrisSrc('')}
              aria-label="Tutup perbesaran QRIS"
            >
              <X size={18} />
            </button>
            <img src={zoomQrisSrc} alt="Kode QRIS" className="pay-lightbox-img" />
          </div>
        </div>
      )}
    </section>
  )
}
