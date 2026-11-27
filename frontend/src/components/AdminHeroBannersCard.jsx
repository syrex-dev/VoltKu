import React, { useState } from 'react'
import {
  Plus,
  RotateCcw,
  ArrowUp,
  ArrowDown,
  Pencil,
  Trash2,
  ChevronRight,
  Save,
  X,
  Check,
  Sparkles,
} from 'lucide-react'
import { InAppSelect } from './InAppSelect'
import {
  HERO_BANNER_TONES,
  HERO_BANNER_ICONS,
  HERO_BANNER_ACTIONS,
  HERO_BANNER_AUDIENCES,
  DEFAULT_HERO_BANNERS,
  resolveHeroBannerIcon,
  getHeroBannerActionLabel,
  getHeroBannerAudienceLabel,
} from '../utils/heroBanners'

function HeroBannerIcon({ icon = 'zap', size = 24, strokeWidth = 2 }) {
  return React.createElement(resolveHeroBannerIcon(icon), { size, strokeWidth })
}

const EMPTY_DRAFT = {
  id: '',
  badge: 'INFO TERBARU',
  title: '',
  subtitle: '',
  cta: 'Lihat',
  tone: 'is-cobalt',
  icon: 'sparkles',
  action_type: 'usage_guide',
  action_url: '',
  audience: 'all',
  enabled: true,
}

export function AdminHeroBannersCard({
  banners = [],
  defaultBanners = DEFAULT_HERO_BANNERS,
  busy = false,
  onPersistBanners,
}) {
  const [editingIndex, setEditingIndex] = useState(null) // null | -1 (create) | >= 0
  const [draft, setDraft] = useState(EMPTY_DRAFT)
  const [formErr, setFormErr] = useState('')
  const [confirmDeleteIdx, setConfirmDeleteIdx] = useState(null)
  const [confirmReset, setConfirmReset] = useState(false)

  const list = Array.isArray(banners) ? banners : []
  const activeCount = list.filter((b) => b.enabled !== false).length

  const openCreate = () => {
    setConfirmDeleteIdx(null)
    setConfirmReset(false)
    setFormErr('')
    setDraft({
      ...EMPTY_DRAFT,
      id: `banner-${Date.now().toString(36)}`,
    })
    setEditingIndex(-1)
  }

  const openEdit = (idx) => {
    const item = list[idx]
    if (!item) return
    setConfirmDeleteIdx(null)
    setConfirmReset(false)
    setFormErr('')
    setDraft({ ...EMPTY_DRAFT, ...item })
    setEditingIndex(idx)
  }

  const closeEditor = () => {
    setEditingIndex(null)
    setFormErr('')
  }

  const handleSaveDraft = async () => {
    const cleanTitle = (draft.title || '').trim()
    if (!cleanTitle) {
      setFormErr('Judul hero banner wajib diisi.')
      return
    }
    if (draft.action_type === 'open_url') {
      const url = (draft.action_url || '').trim()
      if (!url.startsWith('https://') && !url.startsWith('http://')) {
        setFormErr('URL tautan wajib diawali http:// atau https://')
        return
      }
    }

    const nextItem = {
      ...draft,
      id: (draft.id || '').trim() || `banner-${Date.now().toString(36)}`,
      badge: (draft.badge || '').trim(),
      title: cleanTitle,
      subtitle: (draft.subtitle || '').trim(),
      cta: (draft.cta || '').trim() || 'Lihat',
      action_url: draft.action_type === 'open_url' ? (draft.action_url || '').trim() : '',
      enabled: draft.enabled !== false,
    }

    const nextList =
      editingIndex === -1
        ? [...list, nextItem]
        : list.map((item, i) => (i === editingIndex ? nextItem : item))

    const ok = await onPersistBanners?.(
      nextList,
      editingIndex === -1 ? 'Banner baru berhasil ditambahkan.' : 'Perubahan banner berhasil disimpan.'
    )
    if (ok !== false) {
      setEditingIndex(null)
      setFormErr('')
    }
  }

  const handleToggleEnabled = async (idx) => {
    const target = list[idx]
    if (!target) return
    const nextList = list.map((b, i) => (i === idx ? { ...b, enabled: b.enabled === false } : b))
    await onPersistBanners?.(
      nextList,
      target.enabled === false ? 'Banner diaktifkan kembali.' : 'Banner dinonaktifkan.'
    )
  }

  const handleMove = async (idx, dir) => {
    const swapIdx = idx + dir
    if (swapIdx < 0 || swapIdx >= list.length) return
    const nextList = [...list]
    const [moved] = nextList.splice(idx, 1)
    nextList.splice(swapIdx, 0, moved)
    await onPersistBanners?.(nextList, 'Urutan hero banner diperbarui.')
  }

  const handleDelete = async (idx) => {
    const nextList = list.filter((_, i) => i !== idx)
    setConfirmDeleteIdx(null)
    if (editingIndex === idx) setEditingIndex(null)
    await onPersistBanners?.(nextList, 'Hero banner berhasil dihapus.')
  }

  const handleResetDefaults = async () => {
    const presetSource =
      Array.isArray(defaultBanners) && defaultBanners.length > 0
        ? defaultBanners
        : DEFAULT_HERO_BANNERS
    setConfirmReset(false)
    setEditingIndex(null)
    await onPersistBanners?.(
      presetSource.map((b) => ({ ...b })),
      'Daftar hero banner dipulihkan ke bawaan.'
    )
  }

  return (
    <section className="clean-sheet admin-card-block">
      <div className="admin-card-head is-split">
        <div>
          <h3>Kontrol Hero Banner Beranda</h3>
          <p className="admin-row-sub">
            Atur, ubah, sembunyikan, atau hapus kartu slide banner yang tampil di Beranda Web &amp;
            APK ({activeCount} aktif dari {list.length} slide).
          </p>
        </div>

        <div className="admin-hero-head-actions">
          {confirmReset ? (
            <div className="admin-inline-confirm">
              <span>Pulihkan default?</span>
              <button
                type="button"
                className="btn btn-primary btn-compact"
                disabled={busy}
                onClick={handleResetDefaults}
              >
                Ya
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                disabled={busy}
                onClick={() => setConfirmReset(false)}
              >
                Batal
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              disabled={busy}
              onClick={() => setConfirmReset(true)}
            >
              <RotateCcw size={14} />
              <span>Pulihkan Bawaan</span>
            </button>
          )}

          <button
            type="button"
            className="btn btn-primary btn-compact"
            disabled={busy || list.length >= 12}
            onClick={openCreate}
          >
            <Plus size={14} />
            <span>Tambah Banner</span>
          </button>
        </div>
      </div>

      {editingIndex !== null && (
        <div className="admin-hero-editor-card">
          <div className="admin-hero-editor-head">
            <span className="admin-step-editor-label" style={{ marginBottom: 0 }}>
              {editingIndex === -1 ? 'Tambah Hero Banner Baru' : `Edit Banner #${editingIndex + 1}`}
            </span>
            <button
              type="button"
              className="btn-icon-close"
              onClick={closeEditor}
              aria-label="Tutup editor banner"
            >
              <X size={15} />
            </button>
          </div>

          <div className="admin-hero-preview-wrap">
            <div className={`ewl-hero-slide admin-hero-preview-slide ${draft.tone || 'is-cobalt'}`}>
              <div className="ewl-hero-deco-circle a" aria-hidden="true" />
              <div className="ewl-hero-deco-circle b" aria-hidden="true" />
              <div className="ewl-hero-copy">
                <span className="ewl-hero-badge">{(draft.badge || 'INFO').toUpperCase()}</span>
                <div className="ewl-hero-title">
                  {draft.title?.trim() || 'Pratinjau Judul Hero Banner'}
                </div>
                <div className="ewl-hero-sub">
                  {draft.subtitle?.trim() || 'Pratinjau deskripsi singkat banner di aplikasi'}
                </div>
              </div>
              <div className="ewl-hero-visual" aria-hidden="true">
                <div className="ewl-hero-visual-tile">
                  <HeroBannerIcon icon={draft.icon} size={24} strokeWidth={2} />
                </div>
                <span className="ewl-hero-cta-mini">
                  <span>{draft.cta?.trim() || 'Lihat'}</span>
                  <ChevronRight size={12} />
                </span>
              </div>
            </div>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="hero-edit-badge">
                Label Badge Atas
              </label>
              <input
                id="hero-edit-badge"
                type="text"
                maxLength={40}
                className="modern-input"
                placeholder="Contoh: PROMO SPESIAL / CARA PEMAKAIAN"
                value={draft.badge}
                onChange={(e) => setDraft((p) => ({ ...p, badge: e.target.value }))}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="hero-edit-cta">
                Teks Tombol Kanan (CTA)
              </label>
              <input
                id="hero-edit-cta"
                type="text"
                maxLength={32}
                className="modern-input"
                placeholder="Contoh: Lihat Paket"
                value={draft.cta}
                onChange={(e) => setDraft((p) => ({ ...p, cta: e.target.value }))}
              />
            </div>
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="hero-edit-title">
              Judul Banner *
            </label>
            <input
              id="hero-edit-title"
              type="text"
              maxLength={120}
              className="modern-input"
              placeholder="Contoh: Hemat Tagihan Listrik Bulanan"
              value={draft.title}
              onChange={(e) => setDraft((p) => ({ ...p, title: e.target.value }))}
            />
          </div>

          <div className="form-field-group">
            <label className="field-label" htmlFor="hero-edit-sub">
              Subjudul / Deskripsi Singkat
            </label>
            <input
              id="hero-edit-sub"
              type="text"
              maxLength={200}
              className="modern-input"
              placeholder="Penjelasan singkat yang tampil di bawah judul"
              value={draft.subtitle}
              onChange={(e) => setDraft((p) => ({ ...p, subtitle: e.target.value }))}
            />
          </div>

          <div className="form-field-group">
            <span className="field-label">Tema Warna Kartu</span>
            <div className="admin-hero-tone-row">
              {HERO_BANNER_TONES.map((t) => {
                const active = draft.tone === t.id
                return (
                  <button
                    key={t.id}
                    type="button"
                    className={`admin-hero-tone-chip ${active ? 'selected' : ''}`}
                    onClick={() => setDraft((p) => ({ ...p, tone: t.id }))}
                  >
                    <span
                      className="admin-hero-tone-swatch"
                      style={{ backgroundColor: t.color }}
                      aria-hidden="true"
                    />
                    <span>{t.label}</span>
                    {active && <Check size={12} />}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="hero-edit-icon">
                Ikon Banner
              </label>
              <InAppSelect
                id="hero-edit-icon"
                value={draft.icon || 'zap'}
                onChange={(v) => setDraft((p) => ({ ...p, icon: v }))}
                options={HERO_BANNER_ICONS.map((ic) => ({ value: ic.id, label: ic.label }))}
              />
            </div>

            <div className="form-field-group">
              <label className="field-label" htmlFor="hero-edit-audience">
                Target Pengguna
              </label>
              <InAppSelect
                id="hero-edit-audience"
                value={draft.audience || 'all'}
                onChange={(v) => setDraft((p) => ({ ...p, audience: v }))}
                options={HERO_BANNER_AUDIENCES.map((a) => ({ value: a.id, label: a.label }))}
              />
            </div>
          </div>

          <div className="settings-fields-grid">
            <div className="form-field-group">
              <label className="field-label" htmlFor="hero-edit-action">
                Aksi Saat Banner Diklik
              </label>
              <InAppSelect
                id="hero-edit-action"
                value={draft.action_type || 'none'}
                onChange={(v) => setDraft((p) => ({ ...p, action_type: v }))}
                options={HERO_BANNER_ACTIONS.map((a) => ({ value: a.id, label: a.label }))}
              />
            </div>

            {draft.action_type === 'open_url' && (
              <div className="form-field-group">
                <label className="field-label" htmlFor="hero-edit-url">
                  URL Tujuan (https://)
                </label>
                <input
                  id="hero-edit-url"
                  type="url"
                  className="modern-input"
                  placeholder="https://voltku.synemax.web.id/..."
                  value={draft.action_url || ''}
                  onChange={(e) => setDraft((p) => ({ ...p, action_url: e.target.value }))}
                />
              </div>
            )}
          </div>

          {formErr && <p className="admin-field-err">{formErr}</p>}

          <div className="admin-hero-editor-foot">
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              disabled={busy}
              onClick={closeEditor}
            >
              Batal
            </button>
            <button
              type="button"
              className="btn btn-primary btn-compact"
              disabled={busy}
              onClick={handleSaveDraft}
            >
              <Save size={14} />
              <span>{busy ? 'Menyimpan...' : 'Simpan Banner'}</span>
            </button>
          </div>
        </div>
      )}

      {list.length === 0 ? (
        <div className="admin-empty-box" style={{ padding: '22px 16px' }}>
          <Sparkles size={20} style={{ opacity: 0.6, marginBottom: 6 }} />
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Tidak ada hero banner aktif</div>
          <div className="admin-row-sub" style={{ marginBottom: 12 }}>
            Area banner beranda disembunyikan otomatis sampai Anda menambahkan banner baru atau
            memulihkan banner bawaan.
          </div>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            disabled={busy}
            onClick={openCreate}
          >
            <Plus size={14} />
            <span>Tambah Banner Pertama</span>
          </button>
        </div>
      ) : (
        <div className="admin-hero-list">
          {list.map((banner, idx) => {
            const toneMeta =
              HERO_BANNER_TONES.find((t) => t.id === banner.tone) || HERO_BANNER_TONES[1]
            const isActive = banner.enabled !== false
            return (
              <div
                key={banner.id || idx}
                className={`admin-hero-item ${!isActive ? 'is-disabled' : ''}`}
              >
                <div className="admin-hero-item-main">
                  <div
                    className="admin-hero-item-icon"
                    style={{ backgroundColor: toneMeta.color }}
                    aria-hidden="true"
                  >
                    <HeroBannerIcon icon={banner.icon} size={18} strokeWidth={2} />
                  </div>
                  <div className="admin-hero-item-copy">
                    <div className="admin-hero-item-badges">
                      <span className="admin-pill muted">#{idx + 1}</span>
                      {banner.badge && <span className="admin-pill">{banner.badge}</span>}
                      <span className={`admin-pill ${isActive ? 'ok' : 'muted'}`}>
                        {isActive ? 'Aktif' : 'Disembunyikan'}
                      </span>
                      <span className="admin-pill muted">
                        {getHeroBannerAudienceLabel(banner.audience)}
                      </span>
                    </div>
                    <div className="admin-hero-item-title">{banner.title}</div>
                    {banner.subtitle && (
                      <div className="admin-hero-item-sub">{banner.subtitle}</div>
                    )}
                    <div className="admin-hero-item-meta">
                      Aksi: <strong>{getHeroBannerActionLabel(banner.action_type)}</strong> · CTA:{' '}
                      <strong>{banner.cta || 'Lihat'}</strong>
                    </div>
                  </div>
                </div>

                <div className="admin-hero-item-actions">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={isActive}
                    aria-label={`${isActive ? 'Nonaktifkan' : 'Aktifkan'} ${banner.title}`}
                    className={`admin-switch ${isActive ? 'on' : ''}`}
                    disabled={busy}
                    onClick={() => handleToggleEnabled(idx)}
                  >
                    <span className="admin-switch-thumb" />
                  </button>

                  <div className="admin-hero-btn-group">
                    <button
                      type="button"
                      className="btn-icon-close"
                      disabled={busy || idx === 0}
                      aria-label={`Naikkan ${banner.title}`}
                      onClick={() => handleMove(idx, -1)}
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      type="button"
                      className="btn-icon-close"
                      disabled={busy || idx === list.length - 1}
                      aria-label={`Turunkan ${banner.title}`}
                      onClick={() => handleMove(idx, 1)}
                    >
                      <ArrowDown size={14} />
                    </button>
                    <button
                      type="button"
                      className="btn-icon-close"
                      disabled={busy}
                      aria-label={`Edit ${banner.title}`}
                      onClick={() => openEdit(idx)}
                    >
                      <Pencil size={14} />
                    </button>

                    {confirmDeleteIdx === idx ? (
                      <div className="admin-inline-confirm">
                        <button
                          type="button"
                          className="btn btn-danger-solid btn-compact"
                          disabled={busy}
                          onClick={() => handleDelete(idx)}
                        >
                          Hapus
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-compact"
                          disabled={busy}
                          onClick={() => setConfirmDeleteIdx(null)}
                        >
                          Batal
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="btn-icon-close danger"
                        disabled={busy}
                        aria-label={`Hapus ${banner.title}`}
                        onClick={() => setConfirmDeleteIdx(idx)}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

