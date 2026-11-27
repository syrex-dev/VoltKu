import React, { useState, useEffect, useCallback } from 'react'
import {
  MessageSquare,
  BellRing,
  Send,
  Trash2,
  Star,
  Plus,
  Pencil,
  Check,
  X,
  Bot,
  Users,
  Bug,
  Lightbulb,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatDateTimeWIB } from '../utils/formatters'
import { emitSyncSignal } from '../utils/liveSync'
import { InAppSelect } from './InAppSelect'

const FEEDBACK_STATUS_META = {
  new: { label: 'Baru', cls: 'warn' },
  reviewed: { label: 'Ditinjau', cls: 'awaiting' },
  resolved: { label: 'Selesai', cls: 'ok' },
}

const FEEDBACK_CATEGORY_META = {
  feedback: { label: 'Ulasan / Saran', icon: Star },
  bug: { label: 'Laporan Bug', icon: Bug },
  feature: { label: 'Usul Fitur', icon: Lightbulb },
}

const BROADCAST_TARGET_LABELS = {
  all: 'Semua Pelanggan Aktif',
  free: 'Pelanggan Gratis',
  pro: 'Pelanggan Pro',
  user: 'Akun Tertentu',
}

function FeedbackItemCard({ item, busy, onSave, onDelete }) {
  const [statusVal, setStatusVal] = useState(item.status || 'new')
  const [replyText, setReplyText] = useState(item.admin_reply || '')
  const [notifyUser, setNotifyUser] = useState(true)
  const [confirmDel, setConfirmDel] = useState(false)

  const stMeta = FEEDBACK_STATUS_META[item.status] || FEEDBACK_STATUS_META.new
  const catMeta = FEEDBACK_CATEGORY_META[item.category] || FEEDBACK_CATEGORY_META.feedback
  const CatIcon = catMeta.icon

  return (
    <div className="admin-comms-card">
      <div className="admin-comms-card-head">
        <div>
          <div className="admin-comms-badges">
            <span className={`admin-pill ${stMeta.cls}`}>{stMeta.label}</span>
            <span className="admin-pill muted">
              <CatIcon size={12} />
              <span>{catMeta.label}</span>
            </span>
            <span className="admin-pill ok num-tabular">
              {'★'.repeat(Math.max(1, Math.min(5, item.rating || 5)))} ({item.rating}/5)
            </span>
          </div>
          <div className="admin-dev-name" style={{ marginTop: 4 }}>
            {item.user_name || 'Pelanggan'}
            {item.user_email ? ` · ${item.user_email}` : ''}
          </div>
          <div className="admin-row-sub num-tabular">Dikirim {formatDateTimeWIB(item.created_at)}</div>
        </div>
      </div>

      {item.comment ? (
        <p className="admin-comms-comment">{item.comment}</p>
      ) : (
        <p className="admin-comms-comment is-empty">Tanpa komentar teks (hanya rating bintang).</p>
      )}

      <div className="admin-comms-reply-box">
        <div className="settings-fields-grid">
          <div className="form-field-group" style={{ marginBottom: 0 }}>
            <label className="field-label" htmlFor={`fb-status-${item.id}`}>
              Status Tindak Lanjut
            </label>
            <InAppSelect
              id={`fb-status-${item.id}`}
              value={statusVal}
              onChange={setStatusVal}
              options={[
                { value: 'new', label: 'Baru Masuk' },
                { value: 'reviewed', label: 'Sedang Ditinjau' },
                { value: 'resolved', label: 'Selesai Ditangani' },
              ]}
            />
          </div>
          <div className="form-field-group" style={{ marginBottom: 0 }}>
            <label className="field-label" htmlFor={`fb-reply-${item.id}`}>
              Balasan / Catatan Admin (Opsional)
            </label>
            <input
              id={`fb-reply-${item.id}`}
              type="text"
              className="modern-input"
              placeholder="Contoh: Terima kasih, perbaikan rilis di update berikutnya."
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              maxLength={1000}
            />
          </div>
        </div>

        <div className="admin-comms-card-footer">
          <label className="admin-inline-check">
            <input
              type="checkbox"
              checked={notifyUser}
              onChange={(e) => setNotifyUser(e.target.checked)}
              disabled={!replyText.trim() || !item.user_id}
            />
            <span>Kirim balasan ke Lonceng Notifikasi &amp; Push HP user</span>
          </label>

          <div className="admin-inline-actions">
            {confirmDel ? (
              <div className="admin-inline-confirm">
                <button
                  type="button"
                  className="btn btn-danger-solid btn-compact"
                  disabled={busy}
                  onClick={() => {
                    setConfirmDel(false)
                    onDelete(item.id)
                  }}
                >
                  Ya, Hapus
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  disabled={busy}
                  onClick={() => setConfirmDel(false)}
                >
                  Batal
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                disabled={busy}
                onClick={() => setConfirmDel(true)}
              >
                <Trash2 size={13} />
                <span>Hapus</span>
              </button>
            )}

            <button
              type="button"
              className="btn btn-primary btn-compact"
              disabled={busy}
              onClick={() =>
                onSave(item.id, {
                  status: statusVal,
                  admin_reply: replyText,
                  notify_user: Boolean(notifyUser && replyText.trim()),
                })
              }
            >
              <Check size={13} />
              <span>Simpan Status</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function AdminFeedbackSubTab({ token, onLogout, onNotice, refreshSignal = 0 }) {
  const [data, setData] = useState({ items: [], counts: { total: 0, new: 0, reviewed: 0, resolved: 0 } })
  const [loaded, setLoaded] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')
  const [catFilter, setCatFilter] = useState('')
  const [busyId, setBusyId] = useState(null)

  const reloadFeedback = useCallback(async () => {
    try {
      const qs = new URLSearchParams()
      if (statusFilter) qs.set('status', statusFilter)
      if (catFilter) qs.set('category', catFilter)
      const qStr = qs.toString()
      const res = await apiRequest(
        `/api/admin/feedback${qStr ? `?${qStr}` : ''}`,
        {},
        token,
        onLogout
      )
      setData(res || { items: [], counts: { total: 0, new: 0, reviewed: 0, resolved: 0 } })
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal memuat masukan pelanggan.' })
    } finally {
      setLoaded(true)
    }
  }, [token, onLogout, onNotice, statusFilter, catFilter])

  useEffect(() => {
    let cancelled = false
    const qs = new URLSearchParams()
    if (statusFilter) qs.set('status', statusFilter)
    if (catFilter) qs.set('category', catFilter)
    const qStr = qs.toString()
    apiRequest(`/api/admin/feedback${qStr ? `?${qStr}` : ''}`, {}, token, onLogout)
      .then((res) => {
        if (!cancelled) {
          setData(res || { items: [], counts: { total: 0, new: 0, reviewed: 0, resolved: 0 } })
          setLoaded(true)
        }
      })
      .catch(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [token, onLogout, statusFilter, catFilter, refreshSignal])

  const handleSaveFeedback = async (feedbackId, payload) => {
    setBusyId(feedbackId)
    try {
      await apiRequest(
        `/api/admin/feedback/${feedbackId}`,
        { method: 'PATCH', body: payload },
        token,
        onLogout
      )
      emitSyncSignal('all', { source: 'admin-feedback' })
      onNotice?.({ type: 'success', text: 'Tindak lanjut masukan berhasil disimpan.' })
      await reloadFeedback()
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal memperbarui status masukan.' })
    } finally {
      setBusyId(null)
    }
  }

  const handleDeleteFeedback = async (feedbackId) => {
    setBusyId(feedbackId)
    try {
      await apiRequest(`/api/admin/feedback/${feedbackId}`, { method: 'DELETE' }, token, onLogout)
      emitSyncSignal('all', { source: 'admin-feedback' })
      onNotice?.({ type: 'success', text: 'Masukan dihapus dari daftar.' })
      await reloadFeedback()
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal menghapus masukan.' })
    } finally {
      setBusyId(null)
    }
  }

  const counts = data.counts || { total: 0, new: 0, reviewed: 0, resolved: 0 }

  return (
    <div className="admin-section-stack">
      <div className="admin-kpi-grid num-tabular">
        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Total Masukan</span>
          <strong className="admin-kpi-value">{counts.total}</strong>
        </div>
        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Belum Ditinjau</span>
          <strong className="admin-kpi-value brand-blue-text">{counts.new}</strong>
        </div>
        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Dalam Proses</span>
          <strong className="admin-kpi-value">{counts.reviewed}</strong>
        </div>
        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Selesai</span>
          <strong className="admin-kpi-value brand-emerald-text">{counts.resolved}</strong>
        </div>
      </div>

      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>Daftar Ulasan, Saran &amp; Laporan Bug Pelanggan</h3>
            <p className="admin-row-sub">
              Masukan dari form ulasan aplikasi pelanggan tersimpan langsung di sini.
            </p>
          </div>
        </div>

        <div className="admin-toolbar-row" style={{ marginBottom: 14 }}>
          <div className="admin-filter-pills">
            {[
              { id: '', label: 'Semua Status' },
              { id: 'new', label: `Baru (${counts.new})` },
              { id: 'reviewed', label: `Ditinjau (${counts.reviewed})` },
              { id: 'resolved', label: `Selesai (${counts.resolved})` },
            ].map((s) => (
              <button
                key={s.id || 'all-st'}
                type="button"
                className={`admin-chip-btn ${statusFilter === s.id ? 'active' : ''}`}
                onClick={() => setStatusFilter(s.id)}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div className="admin-filter-pills">
            {[
              { id: '', label: 'Semua Kategori' },
              { id: 'feedback', label: 'Ulasan' },
              { id: 'bug', label: 'Bug' },
              { id: 'feature', label: 'Usul Fitur' },
            ].map((c) => (
              <button
                key={c.id || 'all-cat'}
                type="button"
                className={`admin-chip-btn ${catFilter === c.id ? 'active' : ''}`}
                onClick={() => setCatFilter(c.id)}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        {!loaded ? (
          <div className="admin-empty-box">Memuat data masukan...</div>
        ) : !data.items || data.items.length === 0 ? (
          <div className="admin-empty-box">
            <MessageSquare size={22} style={{ marginBottom: 6, opacity: 0.55 }} />
            <div>Belum ada masukan atau laporan bug pada filter ini.</div>
          </div>
        ) : (
          <div className="admin-comms-list">
            {data.items.map((item) => (
              <FeedbackItemCard
                key={`${item.id}-${item.updated_at}`}
                item={item}
                busy={busyId === item.id}
                onSave={handleSaveFeedback}
                onDelete={handleDeleteFeedback}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export function AdminNotifTelegramSubTab({
  token,
  users = [],
  onLogout,
  onNotice,
  refreshSignal = 0,
}) {
  const [notifData, setNotifData] = useState({ batches: [], recent_items: [] })
  const [tgData, setTgData] = useState({ bot_configured: false, items: [], recent_logs: [] })
  const [sendingBroadcast, setSendingBroadcast] = useState(false)
  const [deletingBatchKey, setDeletingBatchKey] = useState('')
  const [confirmBatchKey, setConfirmBatchKey] = useState('')

  // Form broadcast
  const [bTitle, setBTitle] = useState('')
  const [bBody, setBBody] = useState('')
  const [bCategory, setBCategory] = useState('announcement')
  const [bSeverity, setBSeverity] = useState('info')
  const [bTarget, setBTarget] = useState('all')
  const [bTargetUserId, setBTargetUserId] = useState('')
  const [bSendPush, setBSendPush] = useState(true)

  // Telegram allowlist state
  const [tgChatId, setTgChatId] = useState('')
  const [tgName, setTgName] = useState('')
  const [tgBusyId, setTgBusyId] = useState(null)
  const [editingTgCid, setEditingTgCid] = useState(null)
  const [editingTgName, setEditingTgName] = useState('')
  const [confirmDelTgCid, setConfirmDelTgCid] = useState(null)

  const reloadAll = useCallback(async () => {
    try {
      const [nRes, tRes] = await Promise.all([
        apiRequest('/api/admin/notifications', {}, token, onLogout),
        apiRequest('/api/admin/telegram-users', {}, token, onLogout),
      ])
      if (nRes) setNotifData(nRes)
      if (tRes) setTgData(tRes)
    } catch {
      // Abaikan kegagalan muat latar belakang
    }
  }, [token, onLogout])

  useEffect(() => {
    let cancelled = false
    Promise.all([
      apiRequest('/api/admin/notifications', {}, token, onLogout),
      apiRequest('/api/admin/telegram-users', {}, token, onLogout),
    ])
      .then(([nRes, tRes]) => {
        if (!cancelled) {
          if (nRes) setNotifData(nRes)
          if (tRes) setTgData(tRes)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [token, onLogout, refreshSignal])

  const handleBroadcastSubmit = async (e) => {
    e.preventDefault()
    if (!bTitle.trim() || !bBody.trim()) return
    setSendingBroadcast(true)
    onNotice?.(null)
    try {
      const res = await apiRequest(
        '/api/admin/notifications/broadcast',
        {
          method: 'POST',
          body: {
            title: bTitle.trim(),
            body: bBody.trim(),
            category: bCategory,
            severity: bSeverity,
            target: bTarget,
            target_user_id: bTarget === 'user' && bTargetUserId ? Number(bTargetUserId) : null,
            send_push: bSendPush,
          },
        },
        token,
        onLogout
      )
      setBTitle('')
      setBBody('')
      emitSyncSignal('all', { source: 'admin-broadcast' })
      onNotice?.({
        type: 'success',
        text: `Notifikasi terkirim ke ${res.recipient_count} akun (${res.pushed_count} push HP).`,
      })
      await reloadAll()
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal mengirim siaran notifikasi.' })
    } finally {
      setSendingBroadcast(false)
    }
  }

  const handleDeleteBatch = async (batchKey) => {
    setDeletingBatchKey(batchKey)
    try {
      await apiRequest(
        `/api/admin/notifications?batch_key=${encodeURIComponent(batchKey)}`,
        { method: 'DELETE' },
        token,
        onLogout
      )
      setConfirmBatchKey('')
      emitSyncSignal('all', { source: 'admin-broadcast' })
      onNotice?.({ type: 'success', text: 'Gelombang notifikasi berhasil ditarik dari inbox user.' })
      await reloadAll()
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal menarik notifikasi.' })
    } finally {
      setDeletingBatchKey('')
    }
  }

  const handleAddTelegramUser = async (e) => {
    e.preventDefault()
    if (!tgChatId.trim() || !tgName.trim()) return
    setTgBusyId('add')
    try {
      await apiRequest(
        '/api/admin/telegram-users',
        {
          method: 'POST',
          body: { chat_id: Number(tgChatId.trim()), name: tgName.trim() },
        },
        token,
        onLogout
      )
      setTgChatId('')
      setTgName('')
      emitSyncSignal('admin', { source: 'admin-telegram' })
      onNotice?.({ type: 'success', text: 'Penerima Bot Telegram berhasil ditambahkan.' })
      await reloadAll()
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal menambah penerima Telegram.' })
    } finally {
      setTgBusyId(null)
    }
  }

  const handleSaveTelegramEdit = async (chatId) => {
    if (!editingTgName.trim()) return
    setTgBusyId(chatId)
    try {
      await apiRequest(
        `/api/admin/telegram-users/${chatId}`,
        { method: 'PATCH', body: { name: editingTgName.trim() } },
        token,
        onLogout
      )
      setEditingTgCid(null)
      setEditingTgName('')
      emitSyncSignal('admin', { source: 'admin-telegram' })
      onNotice?.({ type: 'success', text: 'Nama penerima Telegram diperbarui.' })
      await reloadAll()
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal memperbarui nama penerima.' })
    } finally {
      setTgBusyId(null)
    }
  }

  const handleDeleteTelegramUser = async (chatId) => {
    setTgBusyId(chatId)
    try {
      await apiRequest(
        `/api/admin/telegram-users/${chatId}`,
        { method: 'DELETE' },
        token,
        onLogout
      )
      setConfirmDelTgCid(null)
      emitSyncSignal('admin', { source: 'admin-telegram' })
      onNotice?.({ type: 'success', text: `Akses Telegram ${chatId} dihapus.` })
      await reloadAll()
    } catch (err) {
      onNotice?.({ type: 'error', text: err.message || 'Gagal menghapus penerima Telegram.' })
    } finally {
      setTgBusyId(null)
    }
  }

  return (
    <div className="admin-section-stack">
      {/* Broadcast Notifikasi ke Lonceng & Push APK */}
      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>Kirim Broadcast Notifikasi Pelanggan</h3>
            <p className="admin-row-sub">
              Pesan masuk langsung ke ikon Lonceng inbox akun Web/APK dan Push Notification Android.
            </p>
          </div>
          <span className="admin-pill ok">
            <BellRing size={12} />
            <span>{users.filter((u) => u.is_active).length} Akun Aktif</span>
          </span>
        </div>

        <form onSubmit={handleBroadcastSubmit} className="admin-section-stack">
          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="bc-title">
                Judul Notifikasi
              </label>
              <input
                id="bc-title"
                type="text"
                className="modern-input"
                placeholder="Contoh: Pembaruan Sistem atau Promo Akhir Bulan"
                value={bTitle}
                onChange={(e) => setBTitle(e.target.value)}
                minLength={2}
                maxLength={160}
                required
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="bc-target">
                Target Penerima
              </label>
              <InAppSelect
                id="bc-target"
                value={bTarget}
                onChange={setBTarget}
                options={[
                  { value: 'all', label: 'Semua Pelanggan Aktif' },
                  { value: 'free', label: 'Khusus Paket Gratis' },
                  { value: 'pro', label: 'Khusus Paket Pro' },
                  { value: 'user', label: 'Pilih Satu Akun Tertentu' },
                ]}
              />
            </div>
          </div>

          {bTarget === 'user' && (
            <div className="form-field-group">
              <label className="field-label" htmlFor="bc-user">
                Pilih Akun Pelanggan
              </label>
              <InAppSelect
                id="bc-user"
                value={bTargetUserId}
                onChange={setBTargetUserId}
                options={[
                  { value: '', label: '-- Pilih pengguna --' },
                  ...users.map((u) => ({
                    value: String(u.id),
                    label: `${u.name || u.email} (${u.email})`,
                  })),
                ]}
              />
            </div>
          )}

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="bc-cat">
                Kategori
              </label>
              <InAppSelect
                id="bc-cat"
                value={bCategory}
                onChange={setBCategory}
                options={[
                  { value: 'announcement', label: 'Pengumuman' },
                  { value: 'info', label: 'Informasi Akun' },
                  { value: 'promo', label: 'Promo / Diskon' },
                  { value: 'maintenance', label: 'Pemeliharaan' },
                ]}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="bc-sev">
                Tingkat Prioritas
              </label>
              <InAppSelect
                id="bc-sev"
                value={bSeverity}
                onChange={setBSeverity}
                options={[
                  { value: 'info', label: 'Info Normal' },
                  { value: 'warning', label: 'Penting / Peringatan' },
                  { value: 'critical', label: 'Kritis / Mendesak' },
                ]}
              />
            </div>
          </div>

          <div className="form-field-group" style={{ marginBottom: 6 }}>
            <label className="field-label" htmlFor="bc-body">
              Isi Pesan Lengkap
            </label>
            <textarea
              id="bc-body"
              rows={3}
              className="modern-input admin-textarea"
              placeholder="Tulis informasi jelas untuk pelanggan..."
              value={bBody}
              onChange={(e) => setBBody(e.target.value)}
              minLength={2}
              maxLength={2000}
              required
            />
          </div>

          <div className="admin-comms-card-footer">
            <label className="admin-inline-check">
              <input
                type="checkbox"
                checked={bSendPush}
                onChange={(e) => setBSendPush(e.target.checked)}
              />
              <span>Kirim juga Push Notification (FCM) ke perangkat Android</span>
            </label>

            <button type="submit" className="btn btn-primary" disabled={sendingBroadcast}>
              <Send size={14} />
              <span>{sendingBroadcast ? 'Mengirim...' : 'Kirim Notifikasi'}</span>
            </button>
          </div>
        </form>

        <div className="admin-comms-divider" />

        <div className="pay-methods-head">
          <span className="pay-methods-title">Riwayat Broadcast Terkirim</span>
          <span className="admin-pill muted num-tabular">{notifData.batches?.length || 0} batch</span>
        </div>

        {!notifData.batches || notifData.batches.length === 0 ? (
          <div className="pay-methods-empty">Belum ada notifikasi broadcast yang dikirim Admin.</div>
        ) : (
          <div className="admin-comms-list">
            {notifData.batches.map((batch) => (
              <div key={batch.batch_key} className="admin-batch-row">
                <div className="admin-batch-copy">
                  <div className="admin-comms-badges">
                    <span className="admin-pill">{BROADCAST_TARGET_LABELS[batch.target] || batch.target}</span>
                    <span className="admin-pill muted">{batch.category}</span>
                    <span className="admin-pill ok num-tabular">
                      <Users size={11} />
                      <span>
                        {batch.read_count}/{batch.recipient_count} dibaca
                      </span>
                    </span>
                    {batch.pushed_count > 0 && (
                      <span className="admin-pill ok num-tabular">{batch.pushed_count} push</span>
                    )}
                  </div>
                  <div className="admin-dev-name" style={{ marginTop: 4 }}>
                    {batch.title}
                  </div>
                  <div className="admin-row-sub">{batch.body}</div>
                  <div className="admin-row-sub num-tabular" style={{ marginTop: 2 }}>
                    {formatDateTimeWIB(batch.created_at)}
                  </div>
                </div>

                <div className="admin-batch-actions">
                  {confirmBatchKey === batch.batch_key ? (
                    <div className="admin-inline-confirm">
                      <button
                        type="button"
                        className="btn btn-danger-solid btn-compact"
                        disabled={deletingBatchKey === batch.batch_key}
                        onClick={() => handleDeleteBatch(batch.batch_key)}
                      >
                        Ya, Tarik
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-compact"
                        onClick={() => setConfirmBatchKey('')}
                      >
                        Batal
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-secondary btn-compact"
                      onClick={() => setConfirmBatchKey(batch.batch_key)}
                    >
                      <Trash2 size={13} />
                      <span>Tarik</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Allowlist Penerima Bot Telegram */}
      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>Allowlist Penerima &amp; Operator Bot Telegram</h3>
            <p className="admin-row-sub">
              Hanya <code>chat_id</code> di daftar ini yang dapat berinteraksi dengan Bot &amp; menerima alert Telegram.
            </p>
          </div>
          <span className={`admin-pill ${tgData.bot_configured ? 'ok' : 'warn'}`}>
            <Bot size={12} />
            <span>{tgData.bot_configured ? 'Token Bot Aktif' : 'Token Bot Belum Diatur'}</span>
          </span>
        </div>

        <form onSubmit={handleAddTelegramUser} className="admin-tg-add-row">
          <input
            type="number"
            className="modern-input num-tabular"
            placeholder="Chat ID (mis. 123456789)"
            value={tgChatId}
            onChange={(e) => setTgChatId(e.target.value)}
            required
          />
          <input
            type="text"
            className="modern-input"
            placeholder="Nama / Label Operator"
            value={tgName}
            onChange={(e) => setTgName(e.target.value)}
            minLength={2}
            maxLength={128}
            required
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={tgBusyId === 'add'}
          >
            <Plus size={14} />
            <span>Tambah Chat ID</span>
          </button>
        </form>

        {!tgData.items || tgData.items.length === 0 ? (
          <div className="pay-methods-empty">
            Belum ada chat_id terdaftar di database <code>telegram_users</code>.
          </div>
        ) : (
          <div className="admin-table-scroll">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Chat ID</th>
                  <th>Nama / Label</th>
                  <th style={{ textAlign: 'right' }}>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {tgData.items.map((tg) => (
                  <tr key={tg.chat_id}>
                    <td className="num-tabular" style={{ fontWeight: 600 }}>
                      {tg.chat_id}
                    </td>
                    <td>
                      {editingTgCid === tg.chat_id ? (
                        <input
                          type="text"
                          className="modern-input"
                          value={editingTgName}
                          onChange={(e) => setEditingTgName(e.target.value)}
                          maxLength={128}
                        />
                      ) : (
                        tg.name
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div className="admin-inline-actions" style={{ justifyContent: 'flex-end' }}>
                        {editingTgCid === tg.chat_id ? (
                          <>
                            <button
                              type="button"
                              className="btn btn-primary btn-compact"
                              disabled={tgBusyId === tg.chat_id}
                              onClick={() => handleSaveTelegramEdit(tg.chat_id)}
                            >
                              <Check size={13} />
                              <span>Simpan</span>
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary btn-compact"
                              onClick={() => {
                                setEditingTgCid(null)
                                setEditingTgName('')
                              }}
                            >
                              <X size={13} />
                            </button>
                          </>
                        ) : confirmDelTgCid === tg.chat_id ? (
                          <div className="admin-inline-confirm">
                            <button
                              type="button"
                              className="btn btn-danger-solid btn-compact"
                              disabled={tgBusyId === tg.chat_id}
                              onClick={() => handleDeleteTelegramUser(tg.chat_id)}
                            >
                              Ya, Hapus
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary btn-compact"
                              onClick={() => setConfirmDelTgCid(null)}
                            >
                              Batal
                            </button>
                          </div>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="btn btn-secondary btn-compact"
                              onClick={() => {
                                setEditingTgCid(tg.chat_id)
                                setEditingTgName(tg.name)
                              }}
                            >
                              <Pencil size={13} />
                              <span>Edit</span>
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary btn-compact"
                              onClick={() => setConfirmDelTgCid(tg.chat_id)}
                            >
                              <Trash2 size={13} />
                              <span>Hapus</span>
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {tgData.recent_logs?.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div className="pay-methods-head">
              <span className="pay-methods-title">Log Tanya Jawab Bot Terbaru</span>
            </div>
            <div className="admin-comms-list">
              {tgData.recent_logs.slice(0, 8).map((log) => (
                <div key={log.id} className="admin-tg-log-row">
                  <div>
                    <strong>{log.sender_name}</strong>{' '}
                    <span className="num-tabular admin-row-sub">
                      · {formatDateTimeWIB(log.ts)}
                    </span>
                    <div className="admin-row-sub" style={{ marginTop: 2 }}>
                      “{log.question}”
                    </div>
                  </div>
                  <span className="admin-pill muted num-tabular">{log.tokens} tok</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}

