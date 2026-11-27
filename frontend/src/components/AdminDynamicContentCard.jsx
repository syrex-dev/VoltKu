import React, { useState } from 'react'
import {
  Zap,
  Sparkles,
  Smartphone,
  BookOpen,
  Plus,
  Trash2,
  RotateCcw,
  Save,
} from 'lucide-react'
import { InAppSelect } from './InAppSelect'

export function AdminDynamicContentTab({ appSettings, busy = false, onPersistFields }) {
  const [releaseForm, setReleaseForm] = useState(
    () =>
      appSettings?.app_release || {
        version: 'v2.5.0',
        apk_download_url: '',
        release_notes: '',
        changelog: [],
      }
  )
  const [tariffs, setTariffs] = useState(() => appSettings?.pln_tariffs || [])
  const [prompts, setPrompts] = useState(() => appSettings?.ai_quick_prompts || [])
  const [guide, setGuide] = useState(
    () =>
      appSettings?.usage_guide || {
        pairing_intro_title: '',
        pairing_intro_desc: '',
        usage_intro_title: '',
        usage_intro_desc: '',
        pairing_steps: [],
        usage_cards: [],
      }
  )

  return (
    <div className="admin-section-stack">
      {/* 1. Versi APK, Link Unduhan & Changelog */}
      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>
              <Smartphone size={16} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
              Info Versi APK, Tautan Update &amp; Changelog
            </h3>
            <p className="admin-row-sub">
              Mengatur nomor versi tampil, link unduhan APK terbaru, dan daftar catatan rilis di menu Tentang Aplikasi.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            disabled={busy}
            onClick={() => {
              const defRel = appSettings?.default_app_release
              if (defRel) {
                setReleaseForm(defRel)
                onPersistFields({ app_release: defRel }, 'Info rilis APK dipulihkan ke bawaan.')
              }
            }}
          >
            <RotateCcw size={13} />
            <span>Pulihkan Bawaan</span>
          </button>
        </div>

        <div className="settings-fields-grid">
          <div className="form-field-group">
            <label className="field-label" htmlFor="rel-ver">
              Versi Aplikasi Terbaru
            </label>
            <input
              id="rel-ver"
              type="text"
              className="modern-input num-tabular"
              value={releaseForm.version || ''}
              onChange={(e) => setReleaseForm((p) => ({ ...p, version: e.target.value }))}
            />
          </div>
          <div className="form-field-group">
            <label className="field-label" htmlFor="rel-apk-url">
              Tautan Download APK (Opsional)
            </label>
            <input
              id="rel-apk-url"
              type="url"
              className="modern-input"
              placeholder="https://github.com/.../VoltKu.apk"
              value={releaseForm.apk_download_url || ''}
              onChange={(e) =>
                setReleaseForm((p) => ({ ...p, apk_download_url: e.target.value }))
              }
            />
          </div>
        </div>

        <div className="form-field-group">
          <label className="field-label" htmlFor="rel-notes">
            Catatan Singkat Rilis Terbaru
          </label>
          <input
            id="rel-notes"
            type="text"
            className="modern-input"
            value={releaseForm.release_notes || ''}
            onChange={(e) => setReleaseForm((p) => ({ ...p, release_notes: e.target.value }))}
          />
        </div>

        <div className="pay-methods-head" style={{ marginTop: 8 }}>
          <span className="pay-methods-title">Riwayat Changelog</span>
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            onClick={() =>
              setReleaseForm((p) => ({
                ...p,
                changelog: [
                  { version: 'v2.6.0', date: 'Hari ini', badge: 'Baru', items: ['Pembaruan fitur'] },
                  ...(p.changelog || []),
                ],
              }))
            }
          >
            <Plus size={13} />
            <span>Tambah Rilis</span>
          </button>
        </div>

        <div className="admin-comms-list">
          {(releaseForm.changelog || []).map((rel, idx) => (
            <div key={`${rel.version}-${idx}`} className="admin-comms-card">
              <div className="settings-fields-grid">
                <input
                  type="text"
                  className="modern-input num-tabular"
                  placeholder="Versi (v2.5.0)"
                  value={rel.version || ''}
                  onChange={(e) => {
                    const next = [...releaseForm.changelog]
                    next[idx] = { ...rel, version: e.target.value }
                    setReleaseForm((p) => ({ ...p, changelog: next }))
                  }}
                />
                <input
                  type="text"
                  className="modern-input"
                  placeholder="Tanggal (27 Nov 2026)"
                  value={rel.date || ''}
                  onChange={(e) => {
                    const next = [...releaseForm.changelog]
                    next[idx] = { ...rel, date: e.target.value }
                    setReleaseForm((p) => ({ ...p, changelog: next }))
                  }}
                />
                <input
                  type="text"
                  className="modern-input"
                  placeholder="Badge (Terbaru)"
                  value={rel.badge || ''}
                  onChange={(e) => {
                    const next = [...releaseForm.changelog]
                    next[idx] = { ...rel, badge: e.target.value }
                    setReleaseForm((p) => ({ ...p, changelog: next }))
                  }}
                />
              </div>
              <textarea
                rows={2}
                className="modern-input admin-textarea"
                placeholder="Pisahkan tiap poin pembaruan dengan baris baru"
                value={(rel.items || []).join('\n')}
                onChange={(e) => {
                  const next = [...releaseForm.changelog]
                  next[idx] = {
                    ...rel,
                    items: e.target.value.split('\n').map((s) => s.trim()),
                  }
                  setReleaseForm((p) => ({ ...p, changelog: next }))
                }}
              />
              <div style={{ textAlign: 'right' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  disabled={(releaseForm.changelog || []).length <= 1}
                  onClick={() => {
                    const next = releaseForm.changelog.filter((_, i) => i !== idx)
                    setReleaseForm((p) => ({ ...p, changelog: next }))
                  }}
                >
                  <Trash2 size={12} />
                  <span>Hapus Rilis</span>
                </button>
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            disabled={busy}
            onClick={() =>
              onPersistFields(
                { app_release: releaseForm },
                'Info versi APK & changelog berhasil disimpan.'
              )
            }
          >
            <Save size={14} />
            <span>Simpan Versi &amp; Changelog</span>
          </button>
        </div>
      </section>

      {/* 2. Daftar Preset Golongan Tarif PLN */}
      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>
              <Zap size={16} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
              Preset Golongan Tarif PLN ({tariffs.length} Preset)
            </h3>
            <p className="admin-row-sub">
              Pilihan golongan PLN pada dropdown pelanggan di tab Tarif &amp; Daya.
            </p>
          </div>
          <div className="admin-inline-actions">
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              onClick={() =>
                setTariffs((prev) => [
                  ...prev,
                  {
                    id: `custom-${prev.length + 1}`,
                    category: 'rumah',
                    group: 'Rumah Tangga',
                    label: 'Golongan Baru',
                    tariff_rp: '1444.70',
                  },
                ])
              }
            >
              <Plus size={13} />
              <span>Tambah Preset</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              disabled={busy}
              onClick={() => {
                const defs = appSettings?.default_pln_tariffs
                if (defs) {
                  setTariffs(defs)
                  onPersistFields({ pln_tariffs: defs }, 'Preset tarif PLN dipulihkan ke 24 tarif bawaan.')
                }
              }}
            >
              <RotateCcw size={13} />
              <span>Pulihkan Bawaan</span>
            </button>
          </div>
        </div>

        <div className="admin-comms-list" style={{ maxHeight: 360, overflowY: 'auto' }}>
          {tariffs.map((t, idx) => (
            <div key={`${t.id}-${idx}`} className="admin-tariff-edit-row">
              <InAppSelect
                value={t.category || 'rumah'}
                onChange={(val) => {
                  const next = [...tariffs]
                  next[idx] = { ...t, category: val }
                  setTariffs(next)
                }}
                options={[
                  { value: 'rumah', label: 'Rumah' },
                  { value: 'bisnis', label: 'Bisnis' },
                  { value: 'sosial', label: 'Sosial' },
                  { value: 'lainnya', label: 'Industri & Pem' },
                ]}
              />
              <input
                type="text"
                className="modern-input"
                placeholder="Label (R-1/TR · 1.300 VA)"
                value={t.label || ''}
                onChange={(e) => {
                  const next = [...tariffs]
                  next[idx] = { ...t, label: e.target.value }
                  setTariffs(next)
                }}
              />
              <input
                type="text"
                className="modern-input num-tabular"
                placeholder="Rp/kWh (1444.70)"
                value={t.tariff_rp || ''}
                onChange={(e) => {
                  const next = [...tariffs]
                  next[idx] = { ...t, tariff_rp: e.target.value }
                  setTariffs(next)
                }}
              />
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                disabled={tariffs.length <= 1}
                onClick={() => setTariffs(tariffs.filter((_, i) => i !== idx))}
                aria-label="Hapus preset tarif"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            disabled={busy}
            onClick={() =>
              onPersistFields({ pln_tariffs: tariffs }, 'Daftar preset golongan tarif PLN disimpan.')
            }
          >
            <Save size={14} />
            <span>Simpan Tarif PLN</span>
          </button>
        </div>
      </section>

      {/* 3. Pertanyaan Cepat Asisten AI */}
      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>
              <Sparkles size={16} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
              Pertanyaan Cepat Asisten AI ({prompts.length}/8)
            </h3>
            <p className="admin-row-sub">Chip pertanyaan satu-ketuk di laci Tanya VoltKu.</p>
          </div>
          <div className="admin-inline-actions">
            {prompts.length < 8 && (
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                onClick={() => setPrompts((p) => [...p, 'Ringkasan listrik hari ini?'])}
              >
                <Plus size={13} />
                <span>Tambah</span>
              </button>
            )}
            <button
              type="button"
              className="btn btn-secondary btn-compact"
              disabled={busy}
              onClick={() => {
                const defs = appSettings?.default_ai_quick_prompts
                if (defs) {
                  setPrompts(defs)
                  onPersistFields({ ai_quick_prompts: defs }, 'Prompt AI dipulihkan ke bawaan.')
                }
              }}
            >
              <RotateCcw size={13} />
              <span>Pulihkan</span>
            </button>
          </div>
        </div>

        <div className="admin-comms-list">
          {prompts.map((q, idx) => (
            <div key={idx} className="admin-inline-actions" style={{ width: '100%' }}>
              <input
                type="text"
                className="modern-input"
                style={{ flex: 1 }}
                value={q}
                maxLength={120}
                onChange={(e) => {
                  const next = [...prompts]
                  next[idx] = e.target.value
                  setPrompts(next)
                }}
              />
              <button
                type="button"
                className="btn btn-secondary btn-compact"
                disabled={prompts.length <= 1}
                onClick={() => setPrompts(prompts.filter((_, i) => i !== idx))}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            disabled={busy}
            onClick={() =>
              onPersistFields({ ai_quick_prompts: prompts }, 'Prompt cepat Asisten AI disimpan.')
            }
          >
            <Save size={14} />
            <span>Simpan Prompt AI</span>
          </button>
        </div>
      </section>

      {/* 4. Panduan Cara Pemakaian */}
      <section className="clean-sheet admin-card-block">
        <div className="admin-card-head is-split">
          <div>
            <h3>
              <BookOpen size={16} style={{ verticalAlign: 'text-bottom', marginRight: 6 }} />
              Konten Modal Cara Pemakaian
            </h3>
            <p className="admin-row-sub">
              Teks persiapan pasang panel, 5 langkah pairing, dan penjelasan fitur Pantau &amp; AI.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            disabled={busy}
            onClick={() => {
              const defG = appSettings?.default_usage_guide
              if (defG) {
                setGuide(defG)
                onPersistFields({ usage_guide: defG }, 'Panduan pemakaian dipulihkan ke bawaan.')
              }
            }}
          >
            <RotateCcw size={13} />
            <span>Pulihkan Bawaan</span>
          </button>
        </div>

        <div className="settings-fields-grid">
          <div className="form-field-group">
            <label className="field-label" htmlFor="ug-p-title">
              Judul Kartu Pasang Panel
            </label>
            <input
              id="ug-p-title"
              type="text"
              className="modern-input"
              value={guide.pairing_intro_title || ''}
              onChange={(e) => setGuide((g) => ({ ...g, pairing_intro_title: e.target.value }))}
            />
          </div>
          <div className="form-field-group">
            <label className="field-label" htmlFor="ug-u-title">
              Judul Kartu Pantau &amp; AI
            </label>
            <input
              id="ug-u-title"
              type="text"
              className="modern-input"
              value={guide.usage_intro_title || ''}
              onChange={(e) => setGuide((g) => ({ ...g, usage_intro_title: e.target.value }))}
            />
          </div>
        </div>

        <div className="admin-comms-list">
          {(guide.pairing_steps || []).map((st, idx) => (
            <div key={`ps-${idx}`} className="form-field-group" style={{ marginBottom: 4 }}>
              <label className="field-label" htmlFor={`ug-step-${idx}`}>
                Langkah Pasang {idx + 1}
              </label>
              <input
                id={`ug-step-${idx}`}
                type="text"
                className="modern-input"
                value={st.text || ''}
                onChange={(e) => {
                  const next = [...(guide.pairing_steps || [])]
                  next[idx] = { step: idx + 1, text: e.target.value }
                  setGuide((g) => ({ ...g, pairing_steps: next }))
                }}
              />
            </div>
          ))}
        </div>

        <div className="admin-comms-divider" />

        <div className="admin-comms-list">
          {(guide.usage_cards || []).map((card, idx) => (
            <div key={`uc-${idx}`} className="admin-comms-card">
              <input
                type="text"
                className="modern-input"
                placeholder={`Judul Fitur ${idx + 1}`}
                value={card.title || ''}
                onChange={(e) => {
                  const next = [...(guide.usage_cards || [])]
                  next[idx] = { ...card, title: e.target.value }
                  setGuide((g) => ({ ...g, usage_cards: next }))
                }}
              />
              <textarea
                rows={2}
                className="modern-input admin-textarea"
                placeholder="Deskripsi fitur"
                value={card.desc || ''}
                onChange={(e) => {
                  const next = [...(guide.usage_cards || [])]
                  next[idx] = { ...card, desc: e.target.value }
                  setGuide((g) => ({ ...g, usage_cards: next }))
                }}
              />
            </div>
          ))}
        </div>

        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            disabled={busy}
            onClick={() =>
              onPersistFields({ usage_guide: guide }, 'Konten Panduan Cara Pemakaian disimpan.')
            }
          >
            <Save size={14} />
            <span>Simpan Panduan</span>
          </button>
        </div>
      </section>
    </div>
  )
}

