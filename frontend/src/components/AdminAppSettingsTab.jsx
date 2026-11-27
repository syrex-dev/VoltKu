import React, { useState, useEffect, useRef } from 'react'
import {
  Store,
  Palette,
  Lock,
  ShieldCheck,
  Sliders,
  Save,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  CheckCircle2,
  Clock,
  Globe,
  UserCheck,
  Crown,
  ArrowRight,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatTimeWIB, formatRp } from '../utils/formatters'
import { InAppSelect } from './InAppSelect'

const SUB_TABS = [
  { id: 'identitas', label: '1. Identitas & Brand', icon: Store },
  { id: 'tampilan', label: '2. Tampilan & Panduan', icon: Palette },
  { id: 'akses', label: '3. Akses & Login', icon: Lock },
  { id: 'legal', label: '4. Legal & Audit', icon: ShieldCheck },
  { id: 'operasional', label: '5. Operasional & Dukungan', icon: Sliders },
  { id: 'freemium', label: '6. Paket & Freemium', icon: Crown },
]

const VIA_LABELS = {
  register: 'Registrasi Email',
  login: 'Login Email',
  google: 'Akun Google',
  reconsent: 'Persetujuan Ulang',
  guest: 'Tamu (Guest)',
}

export function AdminAppSettingsTab({
  token,
  appSettings,
  consentsData,
  plans = [],
  onOpenPlansTab = null,
  onLogout,
  onSettingsUpdated,
  onNotice,
}) {
  const [subTab, setSubTab] = useState('identitas')
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)
  const navRef = useRef(null)

  useEffect(() => {
    if (appSettings) {
      setForm({ ...appSettings })
    }
  }, [appSettings])

  const updateScrollArrows = () => {
    const el = navRef.current
    if (!el) return
    setCanScrollLeft(el.scrollLeft > 4)
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4)
  }

  useEffect(() => {
    updateScrollArrows()
    window.addEventListener('resize', updateScrollArrows)
    return () => window.removeEventListener('resize', updateScrollArrows)
  }, [subTab])

  if (!form) {
    return <div className="clean-sheet admin-empty-box">Memuat pengaturan aplikasi...</div>
  }

  const updateField = (key, val) => {
    setForm((prev) => ({ ...prev, [key]: val }))
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    if (onNotice) onNotice(null)
    try {
      const payload = {
        app_name: (form.app_name || '').trim() || 'VoltKu',
        app_tagline: (form.app_tagline || '').trim(),
        navbar_brand_display: form.navbar_brand_display || 'logo_only',
        announcement_active: Boolean(form.announcement_active),
        announcement_text: (form.announcement_text || '').trim(),
        announcement_url: (form.announcement_url || '').trim(),
        default_theme: form.default_theme || 'light',
        onboarding_enabled: Boolean(form.onboarding_enabled),
        onboarding_step1_title: (form.onboarding_step1_title || '').trim(),
        onboarding_step1_desc: (form.onboarding_step1_desc || '').trim(),
        onboarding_step2_title: (form.onboarding_step2_title || '').trim(),
        onboarding_step2_desc: (form.onboarding_step2_desc || '').trim(),
        onboarding_step3_title: (form.onboarding_step3_title || '').trim(),
        onboarding_step3_desc: (form.onboarding_step3_desc || '').trim(),
        public_read_enabled: Boolean(form.public_read_enabled),
        registration_enabled: Boolean(form.registration_enabled),
        google_auth_enabled: Boolean(form.google_auth_enabled),
        google_client_id: (form.google_client_id || '').trim(),
        google_android_client_id: (form.google_android_client_id || '').trim(),
        require_terms_consent: Boolean(form.require_terms_consent),
        terms_version: (form.terms_version || '').trim(),
        privacy_version: (form.terms_version || '').trim(),
        legal_updated_at: (form.legal_updated_at || '').trim(),
        terms_title: (form.terms_title || '').trim(),
        terms_content: form.terms_content || '',
        privacy_title: (form.privacy_title || '').trim(),
        privacy_content: form.privacy_content || '',
        support_whatsapp: (form.support_whatsapp || '').trim(),
        support_telegram: (form.support_telegram || '').trim(),
        support_email: (form.support_email || '').trim(),
        freemium_enabled: Boolean(form.freemium_enabled),
        free_plan_name: (form.free_plan_name || '').trim() || 'VoltKu Gratis',
        free_max_devices: Math.max(1, parseInt(form.free_max_devices, 10) || 1),
        free_history_days: Math.max(1, parseInt(form.free_history_days, 10) || 3),
        free_forecast_enabled: Boolean(form.free_forecast_enabled),
        free_export_enabled: Boolean(form.free_export_enabled),
        pro_plan_name: (form.pro_plan_name || '').trim() || 'VoltKu Pro',
        pro_monthly_price_rp: Math.max(0, parseInt(form.pro_monthly_price_rp, 10) || 0),
        pro_yearly_price_rp: Math.max(0, parseInt(form.pro_yearly_price_rp, 10) || 0),
        pro_max_devices:
          form.pro_max_devices === '' || form.pro_max_devices === null
            ? 10
            : parseInt(form.pro_max_devices, 10),
        pro_history_days: Math.max(1, parseInt(form.pro_history_days, 10) || 90),
        upgrade_instructions: (form.upgrade_instructions || '').trim(),
        tariff_rp: String(form.tariff_rp || '1444.70').trim(),
        power_limit_w: parseInt(form.power_limit_w, 10) || 2200,
        alert_cooldown_min: parseInt(form.alert_cooldown_min, 10) || 30,
        extra_percent: parseFloat(form.extra_percent) || 0,
        report_hour: parseInt(form.report_hour, 10) || 21,
        report_timezone: form.report_timezone || 'Asia/Jakarta',
        report_enabled: Boolean(form.report_enabled),
      }
      const updated = await apiRequest(
        '/api/admin/app-settings',
        { method: 'PATCH', body: payload },
        token,
        onLogout
      )
      setForm(updated)
      if (onNotice) {
        onNotice({ type: 'success', text: 'Seluruh pengaturan aplikasi berhasil disimpan.' })
      }
      if (onSettingsUpdated) await onSettingsUpdated(updated)
    } catch (err) {
      if (onNotice) {
        onNotice({ type: 'error', text: err.message || 'Gagal menyimpan pengaturan aplikasi.' })
      }
    } finally {
      setSaving(false)
    }
  }

  const handleBumpTermsVersion = () => {
    const today = new Date().toISOString().slice(0, 10)
    const cur = form.terms_version || ''
    const suffixMatch = cur.match(/-r(\d+)$/)
    const nextRev = suffixMatch ? Number(suffixMatch[1]) + 1 : 2
    const nextVer = `${today}-r${nextRev}`
    updateField('terms_version', nextVer)
    const months = [
      'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
      'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
    ]
    const now = new Date()
    updateField(
      'legal_updated_at',
      `${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`
    )
  }

  return (
    <div className="admin-section-stack tab-pane-fade">
      {/* Sub-Tabs Horizontal Scrollable ala DigiPoint / SynemaX */}
      <div className="admin-subtabs-shell">
        {canScrollLeft && (
          <button
            type="button"
            className="admin-subtab-arrow left"
            onClick={() => navRef.current?.scrollBy({ left: -220, behavior: 'smooth' })}
            aria-label="Geser tab ke kiri"
          >
            <ChevronLeft size={16} />
          </button>
        )}

        <nav
          ref={navRef}
          className="admin-subtabs-scroll"
          onScroll={updateScrollArrows}
          aria-label="Kategori Pengaturan Aplikasi"
        >
          {SUB_TABS.map((t) => {
            const Icon = t.icon
            const active = subTab === t.id
            return (
              <button
                key={t.id}
                type="button"
                className={`admin-subtab-pill ${active ? 'active' : ''}`}
                onClick={() => setSubTab(t.id)}
              >
                <Icon size={15} />
                <span>{t.label}</span>
              </button>
            )
          })}
        </nav>

        {canScrollRight && (
          <button
            type="button"
            className="admin-subtab-arrow right"
            onClick={() => navRef.current?.scrollBy({ left: 220, behavior: 'smooth' })}
            aria-label="Geser tab ke kanan"
          >
            <ChevronRight size={16} />
          </button>
        )}
      </div>

      <form onSubmit={handleSave} className="admin-section-stack">
        {subTab === 'identitas' && (
          <>
            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head">
                <h3>Identitas &amp; Brand Aplikasi</h3>
              </div>

              <div className="settings-fields-grid">
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-app-name">
                    Nama Aplikasi
                  </label>
                  <input
                    id="cfg-app-name"
                    type="text"
                    className="modern-input"
                    value={form.app_name || ''}
                    onChange={(e) => updateField('app_name', e.target.value)}
                    required
                  />
                </div>

                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-brand-display">
                    Tampilan Logo di Navbar
                  </label>
                  <InAppSelect
                    id="cfg-brand-display"
                    value={form.navbar_brand_display || 'logo_only'}
                    onChange={(v) => updateField('navbar_brand_display', v)}
                    options={[
                      { value: 'logo_only', label: 'Logo SVG Resmi Saja (Rekomendasi)' },
                      { value: 'logo_text', label: 'Ikon Petir + Nama Aplikasi Teks' },
                      { value: 'text_only', label: 'Nama Aplikasi Teks Saja' },
                    ]}
                  />
                </div>
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="cfg-app-tagline">
                  Tagline / Subjudul Layar Masuk &amp; Tentang
                </label>
                <input
                  id="cfg-app-tagline"
                  type="text"
                  className="modern-input"
                  value={form.app_tagline || ''}
                  onChange={(e) => updateField('app_tagline', e.target.value)}
                />
              </div>
            </section>

            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head">
                <h3>Banner Pengumuman Atas</h3>
              </div>

              <div className="admin-toggle-row" style={{ marginBottom: 14 }}>
                <div>
                  <div className="admin-row-title">Tampilkan Strip Pengumuman Global</div>
                  <div className="admin-row-sub">
                    Muncul tipis di bawah navbar Web &amp; APK untuk info pemeliharaan atau rilis.
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(form.announcement_active)}
                  className={`admin-switch ${form.announcement_active ? 'on' : ''}`}
                  onClick={() => updateField('announcement_active', !form.announcement_active)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>

              <div className="settings-fields-grid">
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-ann-text">
                    Teks Pengumuman
                  </label>
                  <input
                    id="cfg-ann-text"
                    type="text"
                    className="modern-input"
                    placeholder="Contoh: Pemeliharaan server pukul 23:00 WIB"
                    value={form.announcement_text || ''}
                    onChange={(e) => updateField('announcement_text', e.target.value)}
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-ann-url">
                    Tautan Opsional (URL)
                  </label>
                  <input
                    id="cfg-ann-url"
                    type="url"
                    className="modern-input"
                    placeholder="https://..."
                    value={form.announcement_url || ''}
                    onChange={(e) => updateField('announcement_url', e.target.value)}
                  />
                </div>
              </div>
            </section>
          </>
        )}

        {subTab === 'tampilan' && (
          <section className="clean-sheet admin-card-block">
            <div className="admin-card-head">
              <h3>Tampilan Default &amp; Panduan Awal Pengguna</h3>
            </div>

            <div className="form-field-group" style={{ maxWidth: 340 }}>
              <label className="field-label" htmlFor="cfg-default-theme">
                Tema Bawaan Pengunjung Baru
              </label>
              <InAppSelect
                id="cfg-default-theme"
                value={form.default_theme || 'light'}
                onChange={(v) => updateField('default_theme', v)}
                options={[
                  { value: 'light', label: 'Mode Terang (Light)' },
                  { value: 'dark', label: 'Mode Gelap (Dark)' },
                  { value: 'system', label: 'Ikuti Tema Perangkat (System)' },
                ]}
              />
            </div>

            <div className="admin-toggle-row" style={{ margin: '16px 0' }}>
              <div>
                <div className="admin-row-title">Aktifkan Panduan Awal Aplikasi</div>
                <div className="admin-row-sub">
                  Menampilkan lembar pengenalan 3 langkah yang bersih untuk pengguna baru.
                </div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={Boolean(form.onboarding_enabled)}
                className={`admin-switch ${form.onboarding_enabled ? 'on' : ''}`}
                onClick={() => updateField('onboarding_enabled', !form.onboarding_enabled)}
              >
                <span className="admin-switch-thumb" />
              </button>
            </div>

            {[1, 2, 3].map((step) => (
              <div key={step} className="admin-step-editor-box">
                <div className="admin-step-editor-label">Langkah Panduan {step}</div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor={`cfg-step${step}-title`}>
                    Judul Langkah {step}
                  </label>
                  <input
                    id={`cfg-step${step}-title`}
                    type="text"
                    className="modern-input"
                    value={form[`onboarding_step${step}_title`] || ''}
                    onChange={(e) => updateField(`onboarding_step${step}_title`, e.target.value)}
                  />
                </div>
                <div className="form-field-group" style={{ marginBottom: 0 }}>
                  <label className="field-label" htmlFor={`cfg-step${step}-desc`}>
                    Deskripsi Langkah {step}
                  </label>
                  <textarea
                    id={`cfg-step${step}-desc`}
                    rows={2}
                    className="modern-input admin-textarea"
                    value={form[`onboarding_step${step}_desc`] || ''}
                    onChange={(e) => updateField(`onboarding_step${step}_desc`, e.target.value)}
                  />
                </div>
              </div>
            ))}
          </section>
        )}

        {subTab === 'akses' && (
          <>
            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head">
                <h3>Kebijakan Akses &amp; Autentikasi</h3>
              </div>

              <div className="admin-toggle-row">
                <div>
                  <div className="admin-row-title">Izinkan Akses Mode Tamu (Guest) Tanpa Login</div>
                  <div className="admin-row-sub">
                    Guest hanya melihat unit yang Anda tandai Demo Publik secara read-only.
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(form.public_read_enabled)}
                  className={`admin-switch ${form.public_read_enabled ? 'on' : ''}`}
                  onClick={() => updateField('public_read_enabled', !form.public_read_enabled)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>

              <div className="admin-toggle-row" style={{ marginTop: 14 }}>
                <div>
                  <div className="admin-row-title">Izinkan Pendaftaran Akun Mandiri</div>
                  <div className="admin-row-sub">
                    Jika dimatikan, hanya akun yang dibuat pengelola dari tab Pengguna yang dapat masuk.
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(form.registration_enabled)}
                  className={`admin-switch ${form.registration_enabled ? 'on' : ''}`}
                  onClick={() => updateField('registration_enabled', !form.registration_enabled)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>

              <div className="admin-toggle-row" style={{ marginTop: 14, marginBottom: 14 }}>
                <div>
                  <div className="admin-row-title">Aktifkan Login dengan Google</div>
                  <div className="admin-row-sub">
                    Memungkinkan pengguna masuk satu ketuk memakai akun Google di Web &amp; APK.
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(form.google_auth_enabled)}
                  className={`admin-switch ${form.google_auth_enabled ? 'on' : ''}`}
                  onClick={() => updateField('google_auth_enabled', !form.google_auth_enabled)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>

              <div className="settings-fields-grid">
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-google-cid">
                    Google OAuth Client ID (Web &amp; APK)
                  </label>
                  <input
                    id="cfg-google-cid"
                    type="text"
                    className="modern-input"
                    placeholder={
                      form.effective_google_client_id
                        ? `Aktif (dari .env): ${form.effective_google_client_id}`
                        : 'xxx.apps.googleusercontent.com'
                    }
                    value={form.google_client_id || ''}
                    onChange={(e) => updateField('google_client_id', e.target.value)}
                  />
                  <small className="field-hint">
                    Kosongkan untuk memakai Client ID dari environment server. Di Google Cloud
                    Console (Web client), wajib isi{' '}
                    <strong>Authorized redirect URIs</strong> dengan{' '}
                    <code>{typeof window !== 'undefined' ? `${window.location.origin}/` : 'https://voltku.synemax.web.id/'}</code>
                    {' '}agar login Web tidak terkena <code>redirect_uri_mismatch</code>.
                  </small>
                </div>

                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-google-android-cid">
                    Google Client ID Khusus Android (Opsional)
                  </label>
                  <input
                    id="cfg-google-android-cid"
                    type="text"
                    className="modern-input"
                    placeholder="Kosongkan jika sama dengan Web Client ID"
                    value={form.google_android_client_id || ''}
                    onChange={(e) => updateField('google_android_client_id', e.target.value)}
                  />
                </div>
              </div>
            </section>
          </>
        )}

        {subTab === 'legal' && (
          <>
            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head">
                <h3>Syarat Penggunaan &amp; Kebijakan Privasi</h3>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  onClick={handleBumpTermsVersion}
                >
                  <RefreshCw size={14} />
                  <span>Naikkan Versi (Wajib Setuju Ulang)</span>
                </button>
              </div>

              <div className="admin-toggle-row" style={{ marginBottom: 14 }}>
                <div>
                  <div className="admin-row-title">Wajibkan Persetujuan User &amp; Tamu</div>
                  <div className="admin-row-sub">
                    Menyimpan stempel waktu &amp; versi ke tabel <code>terms_consents</code> setiap user menyetujui.
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(form.require_terms_consent)}
                  className={`admin-switch ${form.require_terms_consent ? 'on' : ''}`}
                  onClick={() => updateField('require_terms_consent', !form.require_terms_consent)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>

              <div className="settings-fields-grid">
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-terms-ver">
                    Versi Ketentuan Aktif
                  </label>
                  <input
                    id="cfg-terms-ver"
                    type="text"
                    className="modern-input num-tabular"
                    value={form.terms_version || ''}
                    onChange={(e) => updateField('terms_version', e.target.value)}
                    required
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-legal-updated">
                    Tanggal Pembaruan Tampil
                  </label>
                  <input
                    id="cfg-legal-updated"
                    type="text"
                    className="modern-input"
                    value={form.legal_updated_at || ''}
                    onChange={(e) => updateField('legal_updated_at', e.target.value)}
                  />
                </div>
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="cfg-terms-title">
                  Judul Syarat Penggunaan
                </label>
                <input
                  id="cfg-terms-title"
                  type="text"
                  className="modern-input"
                  value={form.terms_title || ''}
                  onChange={(e) => updateField('terms_title', e.target.value)}
                  required
                />
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="cfg-terms-content">
                  Isi Dokumen Syarat Penggunaan
                </label>
                <textarea
                  id="cfg-terms-content"
                  rows={8}
                  className="modern-input admin-textarea"
                  value={form.terms_content || ''}
                  onChange={(e) => updateField('terms_content', e.target.value)}
                  required
                />
                <small className="field-hint">
                  Pisahkan tiap pasal dengan baris kosong agar otomatis rapi saat dibaca user.
                </small>
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="cfg-privacy-title">
                  Judul Kebijakan Privasi
                </label>
                <input
                  id="cfg-privacy-title"
                  type="text"
                  className="modern-input"
                  value={form.privacy_title || ''}
                  onChange={(e) => updateField('privacy_title', e.target.value)}
                  required
                />
              </div>

              <div className="form-field-group">
                <label className="field-label" htmlFor="cfg-privacy-content">
                  Isi Dokumen Kebijakan Privasi
                </label>
                <textarea
                  id="cfg-privacy-content"
                  rows={8}
                  className="modern-input admin-textarea"
                  value={form.privacy_content || ''}
                  onChange={(e) => updateField('privacy_content', e.target.value)}
                  required
                />
              </div>
            </section>

            {consentsData && (
              <section className="clean-sheet admin-card-block">
                <div className="admin-card-head">
                  <h3>Audit Persetujuan Pengguna &amp; Tamu</h3>
                  <span className="admin-pill ok">
                    Versi Aktif: {consentsData.current_terms_version}
                  </span>
                </div>

                <div className="admin-consent-summary">
                  <div className="admin-consent-stat">
                    <CheckCircle2 size={16} className="brand-emerald-text" />
                    <span>
                      <strong>{consentsData.users_agreed_current}</strong> /{' '}
                      {consentsData.users_total} akun telah setuju versi terbaru
                    </span>
                  </div>
                  <div className="admin-consent-stat">
                    <Clock size={16} />
                    <span>
                      <strong>{consentsData.users_pending_or_outdated}</strong> akun menunggu
                      persetujuan ulang
                    </span>
                  </div>
                </div>

                {consentsData.items?.length === 0 ? (
                  <div className="admin-empty-box" style={{ padding: '18px 0' }}>
                    Belum ada catatan persetujuan yang tersimpan.
                  </div>
                ) : (
                  <div className="admin-table-scroll">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>Subjek (Akun / ID Tamu)</th>
                          <th>Jalur</th>
                          <th>Versi</th>
                          <th>Waktu (WIB)</th>
                          <th>Alamat IP</th>
                        </tr>
                      </thead>
                      <tbody>
                        {consentsData.items.slice(0, 40).map((item) => (
                          <tr key={item.id}>
                            <td>
                              {item.user_id ? (
                                <div className="admin-consent-subject">
                                  <UserCheck size={14} className="brand-blue-text" />
                                  <div>
                                    <div className="admin-dev-name">{item.user_name || 'Akun'}</div>
                                    <div className="admin-dev-id">{item.email}</div>
                                  </div>
                                </div>
                              ) : (
                                <div className="admin-consent-subject">
                                  <Globe size={14} />
                                  <div>
                                    <div className="admin-dev-name">Sesi Tamu</div>
                                    <div className="admin-dev-id num-tabular">
                                      {item.client_id || 'Anonim'}
                                    </div>
                                  </div>
                                </div>
                              )}
                            </td>
                            <td>
                              <span className="admin-pill muted">
                                {VIA_LABELS[item.accepted_via] || item.accepted_via}
                              </span>
                            </td>
                            <td>
                              <span
                                className={`admin-pill ${item.is_current_version ? 'ok' : 'warn'}`}
                              >
                                {item.terms_version}
                              </span>
                            </td>
                            <td className="num-tabular">{formatTimeWIB(item.accepted_at)}</td>
                            <td className="num-tabular">{item.ip_address || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )}
          </>
        )}

        {subTab === 'operasional' && (
          <>
            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head">
                <h3>Default Kelistrikan Global &amp; Jadwal Rekap</h3>
              </div>

              <div className="settings-fields-grid">
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-op-tariff">
                    Tarif Dasar PLN Global (Rp/kWh)
                  </label>
                  <input
                    id="cfg-op-tariff"
                    type="text"
                    className="modern-input num-tabular"
                    value={form.tariff_rp || ''}
                    onChange={(e) => updateField('tariff_rp', e.target.value)}
                    required
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-op-mcb">
                    Batas Daya Peringatan Default (Watt)
                  </label>
                  <input
                    id="cfg-op-mcb"
                    type="number"
                    min="100"
                    max="25000"
                    className="modern-input num-tabular"
                    value={form.power_limit_w ?? 2200}
                    onChange={(e) => updateField('power_limit_w', e.target.value)}
                    required
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-op-cooldown">
                    Jeda Cooldown Alarm (Menit)
                  </label>
                  <input
                    id="cfg-op-cooldown"
                    type="number"
                    min="5"
                    max="1440"
                    className="modern-input num-tabular"
                    value={form.alert_cooldown_min ?? 30}
                    onChange={(e) => updateField('alert_cooldown_min', e.target.value)}
                    required
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-op-extra">
                    PPJ / Biaya Tambahan (%)
                  </label>
                  <input
                    id="cfg-op-extra"
                    type="number"
                    min="0"
                    step="0.1"
                    className="modern-input num-tabular"
                    value={form.extra_percent ?? 0}
                    onChange={(e) => updateField('extra_percent', e.target.value)}
                    required
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-op-hour">
                    Jam Rekap Laporan Harian
                  </label>
                  <input
                    id="cfg-op-hour"
                    type="number"
                    min="0"
                    max="23"
                    className="modern-input num-tabular"
                    value={form.report_hour ?? 21}
                    onChange={(e) => updateField('report_hour', e.target.value)}
                    required
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-op-timezone">
                    Zona Waktu Rekap Default
                  </label>
                  <InAppSelect
                    id="cfg-op-timezone"
                    value={form.report_timezone || 'Asia/Jakarta'}
                    onChange={(val) => updateField('report_timezone', val)}
                    ariaLabel="Zona Waktu Rekap Default"
                    options={[
                      { value: 'Asia/Jakarta', label: 'WIB (Asia/Jakarta · UTC+7)' },
                      { value: 'Asia/Makassar', label: 'WITA (Asia/Makassar · UTC+8)' },
                      { value: 'Asia/Jayapura', label: 'WIT (Asia/Jayapura · UTC+9)' },
                    ]}
                  />
                </div>
              </div>

              <div className="admin-toggle-row">
                <div>
                  <div className="admin-row-title">Aktifkan Jadwal Rekap Harian</div>
                  <div className="admin-row-sub">
                    Mengirim ringkasan pemakaian harian otomatis sesuai jam &amp; zona waktu di atas.
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(form.report_enabled)}
                  className={`admin-switch ${form.report_enabled ? 'on' : ''}`}
                  onClick={() => updateField('report_enabled', !form.report_enabled)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>
            </section>

            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head">
                <h3>Kontak Dukungan &amp; Bantuan Pelanggan</h3>
              </div>
              <div className="settings-fields-grid">
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-sup-wa">
                    Nomor WhatsApp Admin
                  </label>
                  <input
                    id="cfg-sup-wa"
                    type="text"
                    className="modern-input num-tabular"
                    placeholder="Contoh: 6281234567890"
                    value={form.support_whatsapp || ''}
                    onChange={(e) => updateField('support_whatsapp', e.target.value)}
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-sup-tg">
                    Username Telegram Dukungan
                  </label>
                  <input
                    id="cfg-sup-tg"
                    type="text"
                    className="modern-input"
                    placeholder="Contoh: @voltku_support"
                    value={form.support_telegram || ''}
                    onChange={(e) => updateField('support_telegram', e.target.value)}
                  />
                </div>
                <div className="form-field-group">
                  <label className="field-label" htmlFor="cfg-sup-email">
                    Email Dukungan
                  </label>
                  <input
                    id="cfg-sup-email"
                    type="email"
                    className="modern-input"
                    placeholder="support@voltku.synemax.web.id"
                    value={form.support_email || ''}
                    onChange={(e) => updateField('support_email', e.target.value)}
                  />
                </div>
              </div>
            </section>
          </>
        )}

        {subTab === 'freemium' && (
          <>
            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head">
                <h3>Pengaturan Model Bisnis Freemium</h3>
              </div>

              <div className="admin-toggle-row" style={{ marginBottom: 14 }}>
                <div>
                  <div className="admin-row-title">Aktifkan Pembatasan Paket (Freemium)</div>
                  <div className="admin-row-sub">
                    Jika aktif, pengguna baru masuk ke paket Gratis sesuai kuota panel &amp;
                    riwayat masing-masing paket. Jika dimatikan, seluruh pengguna otomatis terbuka
                    penuh.
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={Boolean(form.freemium_enabled)}
                  className={`admin-switch ${form.freemium_enabled ? 'on' : ''}`}
                  onClick={() => updateField('freemium_enabled', !form.freemium_enabled)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>

              <div className="form-field-group" style={{ marginTop: 8, marginBottom: 0 }}>
                <label className="field-label" htmlFor="cfg-upg-inst">
                  Instruksi Pembayaran / Konfirmasi Upgrade (Ditampilkan ke Pelanggan)
                </label>
                <textarea
                  id="cfg-upg-inst"
                  rows={3}
                  className="modern-input admin-textarea"
                  placeholder="Contoh: Transfer QRIS / BCA ... lalu klik ajukan & konfirmasi ke WhatsApp admin."
                  value={form.upgrade_instructions || ''}
                  onChange={(e) => updateField('upgrade_instructions', e.target.value)}
                />
              </div>
            </section>

            <section className="clean-sheet admin-card-block">
              <div className="admin-card-head is-split">
                <div>
                  <h3>Katalog Paket, Harga Promo &amp; Kode Kupon</h3>
                  <p className="admin-row-sub">
                    Pengelolaan daftar paket (Gratis/Pro/Kustom), harga coret, kuota fitur, dan
                    kode voucher dikelola penuh di tab <strong>Paket &amp; Diskon</strong>.
                  </p>
                </div>
                {onOpenPlansTab && (
                  <button
                    type="button"
                    className="btn btn-primary btn-compact"
                    onClick={onOpenPlansTab}
                  >
                    <Crown size={14} />
                    <span>Kelola Paket &amp; Diskon</span>
                    <ArrowRight size={14} />
                  </button>
                )}
              </div>

              {plans.length > 0 && (
                <div className="admin-plan-summary-strip num-tabular">
                  {plans.map((p) => (
                    <div key={p.id || p.slug} className="admin-plan-mini-chip">
                      <strong>{p.name}</strong>
                      <span>
                        {p.is_default_free
                          ? 'Gratis'
                          : `${formatRp(p.effective_monthly_price_rp)}/bln`}
                      </span>
                      {p.promo_active && <span className="admin-pill warn">Promo</span>}
                      {!p.is_active && <span className="admin-pill muted">Nonaktif</span>}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        <div className="admin-sticky-save-bar">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={16} />
            <span>{saving ? 'Menyimpan Semua Pengaturan...' : 'Simpan Pengaturan Aplikasi'}</span>
          </button>
        </div>
      </form>
    </div>
  )
}

