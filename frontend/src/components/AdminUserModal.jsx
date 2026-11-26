import React, { useState, useEffect, useMemo } from 'react'
import {
  X,
  Save,
  Eye,
  EyeOff,
  Mail,
  Send,
  Crown,
  Cpu,
  Plus,
  Unlink,
  ShieldCheck,
  User as UserIcon,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatDateTimeWIB } from '../utils/formatters'
import { InAppSelect } from './InAppSelect'

export function AdminUserModal({
  mode,
  user,
  devices = [],
  plans = [],
  appSettings,
  token,
  onLogout,
  onClose,
  onSaved,
  onNotice,
}) {
  const isEdit = mode === 'edit' && Boolean(user)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [isActive, setIsActive] = useState(true)
  const [planTier, setPlanTier] = useState('free')
  const [planDuration, setPlanDuration] = useState('keep')
  const [customDays, setCustomDays] = useState('30')
  const [saving, setSaving] = useState(false)
  const [sendingReset, setSendingReset] = useState(false)
  const [assignDeviceId, setAssignDeviceId] = useState('')
  const [deviceBusyId, setDeviceBusyId] = useState('')
  const [localMsg, setLocalMsg] = useState(null)

  useEffect(() => {
    if (!mode) return
    setLocalMsg(null)
    setShowPass(false)
    setPassword('')
    if (mode === 'edit' && user) {
      setName(user.name || '')
      setEmail(user.email || '')
      setIsActive(Boolean(user.is_active))
      setPlanTier(user.plan_tier || 'free')
      setPlanDuration('keep')
    } else {
      setName('')
      setEmail('')
      setIsActive(true)
      setPlanTier('free')
      setPlanDuration('0')
    }
  }, [mode, user])

  const ownedDevices = useMemo(() => {
    if (!isEdit || !user) return []
    return devices.filter((d) => d.owner_user_id === user.id)
  }, [devices, isEdit, user])

  const unclaimedDevices = useMemo(() => {
    return devices.filter((d) => d.owner_user_id == null)
  }, [devices])

  useEffect(() => {
    if (unclaimedDevices.length > 0 && !unclaimedDevices.some((d) => d.id === assignDeviceId)) {
      setAssignDeviceId(unclaimedDevices[0].id)
    } else if (unclaimedDevices.length === 0) {
      setAssignDeviceId('')
    }
  }, [unclaimedDevices, assignDeviceId])

  const planOptions = useMemo(() => {
    if (Array.isArray(plans) && plans.length > 0) {
      return plans.map((p) => ({
        value: p.slug,
        label: p.is_active ? p.name : `${p.name} (Nonaktif)`,
      }))
    }
    return [
      { value: 'free', label: appSettings?.free_plan_name || 'VoltKu Gratis' },
      { value: 'pro', label: appSettings?.pro_plan_name || 'VoltKu Pro' },
    ]
  }, [plans, appSettings])

  const selectedPlanObj = useMemo(
    () => (Array.isArray(plans) ? plans.find((p) => p.slug === planTier) : null),
    [plans, planTier]
  )
  const isSelectedPaid = selectedPlanObj ? !selectedPlanObj.is_default_free : planTier !== 'free'

  if (!mode) return null

  const isProCurrent = Boolean(user?.plan?.is_pro)
  const isGoogle = (user?.auth_provider || '').toLowerCase() === 'google'

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setLocalMsg(null)
    if (onNotice) onNotice(null)

    const durationValue = planDuration === 'custom' ? Number(customDays || 0) : Number(planDuration)

    try {
      if (!isEdit) {
        const body = {
          name: name.trim(),
          email: email.trim(),
          password,
          plan_tier: planTier,
        }
        if (isSelectedPaid && planDuration !== '0' && durationValue > 0) {
          body.plan_duration_days = durationValue
        }
        await apiRequest('/api/admin/users', { method: 'POST', body }, token, onLogout)
        if (onNotice) onNotice({ type: 'success', text: 'Akun pengguna baru berhasil dibuat.' })
      } else {
        const payload = {
          name: name.trim(),
          email: email.trim(),
          is_active: isActive,
          plan_tier: planTier,
        }
        if (password.trim()) {
          payload.password = password
        }
        if (isSelectedPaid) {
          if (planDuration === '0') {
            payload.clear_plan_expiration = true
          } else if (planDuration !== 'keep' && durationValue > 0) {
            payload.plan_duration_days = durationValue
          }
        }
        await apiRequest(
          `/api/admin/users/${user.id}`,
          { method: 'PATCH', body: payload },
          token,
          onLogout
        )
        if (onNotice) {
          onNotice({ type: 'success', text: `Perubahan akun ${name.trim()} disimpan.` })
        }
      }
      onClose()
      if (onSaved) await onSaved()
    } catch (err) {
      setLocalMsg({ type: 'error', text: err.message || 'Gagal menyimpan data akun.' })
    } finally {
      setSaving(false)
    }
  }

  const handleSendResetEmail = async () => {
    if (!isEdit || !user) return
    setSendingReset(true)
    setLocalMsg(null)
    try {
      const res = await apiRequest(
        `/api/admin/users/${user.id}/send-reset-link`,
        { method: 'POST', body: {} },
        token,
        onLogout
      )
      setLocalMsg({
        type: res.smtp_configured ? 'success' : 'error',
        text: res.message,
      })
    } catch (err) {
      setLocalMsg({ type: 'error', text: err.message || 'Gagal mengirim tautan reset.' })
    } finally {
      setSendingReset(false)
    }
  }

  const handleAssignDevice = async () => {
    if (!isEdit || !user || !assignDeviceId) return
    setDeviceBusyId(assignDeviceId)
    setLocalMsg(null)
    try {
      await apiRequest(
        `/api/admin/devices/${assignDeviceId}`,
        { method: 'PATCH', body: { owner_user_id: user.id } },
        token,
        onLogout
      )
      setLocalMsg({
        type: 'success',
        text: `Unit ${assignDeviceId} berhasil dipasangkan ke akun ${user.name}.`,
      })
      if (onSaved) await onSaved()
    } catch (err) {
      setLocalMsg({ type: 'error', text: err.message || 'Gagal memasangkan unit.' })
    } finally {
      setDeviceBusyId('')
    }
  }

  const handleUnlinkDevice = async (devId) => {
    if (!isEdit || !user) return
    setDeviceBusyId(devId)
    setLocalMsg(null)
    try {
      await apiRequest(
        `/api/admin/devices/${devId}`,
        { method: 'PATCH', body: { owner_user_id: 0 } },
        token,
        onLogout
      )
      setLocalMsg({
        type: 'success',
        text: `Unit ${devId} dilepas kembali ke inventaris stok.`,
      })
      if (onSaved) await onSaved()
    } catch (err) {
      setLocalMsg({ type: 'error', text: err.message || 'Gagal melepas unit.' })
    } finally {
      setDeviceBusyId('')
    }
  }

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head">
          <div>
            <h3 className="pwa-guide-title">
              {isEdit ? 'Kelola & Edit Akun Pembeli' : 'Buat Akun Pembeli Baru'}
            </h3>
            <p className="pwa-guide-sub">
              {isEdit
                ? 'Ubah identitas/email, bantu reset sandi, atur paket Pro, atau pasangkan unit alat.'
                : 'Daftarkan akun pembeli baru beserta paket awal dan kata sandi.'}
            </p>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        {isEdit && user && (
          <div className="admin-user-banner">
            <div className="admin-user-banner-left">
              <span className="admin-user-avatar-fallback">
                {(user.name || user.email || 'U').charAt(0).toUpperCase()}
              </span>
              <div>
                <div className="admin-user-name-row">
                  <strong>{user.name}</strong>
                  <span className={`admin-auth-chip ${isGoogle ? 'google' : 'email'}`}>
                    {isGoogle ? 'Google' : 'Email'}
                  </span>
                </div>
                <div className="admin-dev-id num-tabular">
                  ID #{user.id} · Daftar {formatDateTimeWIB(user.created_at)}
                </div>
              </div>
            </div>
            <span className={`admin-pill ${isProCurrent ? 'pro' : 'muted'}`}>
              {isProCurrent && <Crown size={12} />}
              <span>{user.plan?.plan_name || (isProCurrent ? 'VoltKu Pro' : 'Gratis')}</span>
            </span>
          </div>
        )}

        {localMsg && (
          <div className={`feedback-msg ${localMsg.type === 'error' ? 'error' : 'success'}`}>
            {localMsg.text}
          </div>
        )}

        <form onSubmit={handleSubmit} className="admin-modal-stack">
          {/* 1. Identitas & Email */}
          <div className="admin-modal-section">
            <div className="admin-modal-sec-head">
              <UserIcon size={14} />
              <span>1. Identitas &amp; Email Akun</span>
            </div>
            <div className="settings-fields-grid">
              <div className="form-field-group" style={{ marginBottom: 0 }}>
                <label className="field-label" htmlFor="admin-user-name">
                  Nama Lengkap
                </label>
                <input
                  id="admin-user-name"
                  type="text"
                  className="modern-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="form-field-group" style={{ marginBottom: 0 }}>
                <label className="field-label" htmlFor="admin-user-email">
                  Alamat Email Login
                </label>
                <input
                  id="admin-user-email"
                  type="email"
                  className="modern-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>
          </div>

          {/* 2. Keamanan & Kata Sandi */}
          <div className="admin-modal-section">
            <div className="admin-modal-sec-head">
              <ShieldCheck size={14} />
              <span>2. Keamanan &amp; Reset Kata Sandi</span>
            </div>
            <div className="form-field-group" style={{ marginBottom: isEdit ? 10 : 0 }}>
              <label className="field-label" htmlFor="admin-user-pass">
                {isEdit ? 'Setel Kata Sandi Baru Secara Manual (Opsional)' : 'Kata Sandi Awal'}
              </label>
              <div className="admin-pass-wrap">
                <input
                  id="admin-user-pass"
                  type={showPass ? 'text' : 'password'}
                  className="modern-input"
                  placeholder={isEdit ? 'Kosongkan jika tidak ingin mengubah sandi' : 'Minimal 6 karakter'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={isEdit ? undefined : 6}
                  required={!isEdit}
                />
                <button
                  type="button"
                  className="admin-pass-eye"
                  onClick={() => setShowPass((v) => !v)}
                  aria-label="Tampilkan atau sembunyikan kata sandi"
                >
                  {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {isEdit && (
              <div className="admin-reset-assist-row">
                <div className="admin-dev-id" style={{ flex: 1 }}>
                  <Mail size={13} style={{ verticalAlign: 'middle', marginRight: 5 }} />
                  Atau biarkan pembeli menyetel ulang sandinya sendiri via tautan aman (berlaku 30 menit):
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-compact"
                  disabled={sendingReset || !user?.is_active}
                  onClick={handleSendResetEmail}
                >
                  <Send size={13} />
                  <span>{sendingReset ? 'Mengirim...' : 'Kirim Link Reset ke Email'}</span>
                </button>
              </div>
            )}
          </div>

          {/* 3. Paket Langganan */}
          <div className="admin-modal-section">
            <div className="admin-modal-sec-head">
              <Crown size={14} />
              <span>3. Paket Langganan &amp; Masa Aktif</span>
            </div>
            <div className="settings-fields-grid">
              <div className="form-field-group" style={{ marginBottom: 0 }}>
                <label className="field-label" htmlFor="admin-user-plan">
                  Paket Langganan
                </label>
                <InAppSelect
                  id="admin-user-plan"
                  value={planTier}
                  onChange={setPlanTier}
                  options={planOptions}
                />
              </div>

              {isSelectedPaid && (
                <div className="form-field-group" style={{ marginBottom: 0 }}>
                  <label className="field-label" htmlFor="admin-user-duration">
                    Masa Aktif Paket Berbayar
                  </label>
                  <InAppSelect
                    id="admin-user-duration"
                    value={planDuration}
                    onChange={setPlanDuration}
                    options={[
                      ...(isEdit
                        ? [{ value: 'keep', label: 'Pertahankan masa aktif saat ini' }]
                        : []),
                      { value: '7', label: '+ 7 Hari (Trial)' },
                      { value: '30', label: '+ 30 Hari (1 Bulan)' },
                      { value: '90', label: '+ 90 Hari (3 Bulan)' },
                      { value: '365', label: '+ 365 Hari (1 Tahun)' },
                      { value: 'custom', label: 'Atur Jumlah Hari Kustom...' },
                      { value: '0', label: 'Permanen (Tanpa Kedaluwarsa)' },
                    ]}
                  />
                </div>
              )}
            </div>

            {isSelectedPaid && planDuration === 'custom' && (
              <div className="form-field-group" style={{ marginTop: 10, marginBottom: 0 }}>
                <label className="field-label" htmlFor="admin-user-custom-days">
                  Tambah / Set Durasi Paket (Hari)
                </label>
                <input
                  id="admin-user-custom-days"
                  type="number"
                  min={1}
                  max={3650}
                  className="modern-input num-tabular"
                  value={customDays}
                  onChange={(e) => setCustomDays(e.target.value)}
                />
              </div>
            )}

            {isEdit && user?.plan_tier && user.plan_tier !== 'free' && (
              <div className="admin-dev-id num-tabular" style={{ marginTop: 8 }}>
                Masa aktif saat ini:{' '}
                <strong>
                  {user.plan_expires_at ? formatDateTimeWIB(user.plan_expires_at) : 'Permanen'}
                </strong>
              </div>
            )}
          </div>

          {/* 4. Pasangkan / Lepas Unit Panel Listrik */}
          {isEdit && (
            <div className="admin-modal-section">
              <div className="admin-modal-sec-head">
                <Cpu size={14} />
                <span>4. Unit Panel Listrik Pembeli ({ownedDevices.length} unit)</span>
              </div>

              {ownedDevices.length === 0 ? (
                <div className="admin-dev-id" style={{ marginBottom: 10 }}>
                  Akun ini belum memiliki unit alat. Pasangkan unit dari stok di bawah jika perlu.
                </div>
              ) : (
                <div className="admin-user-dev-list" style={{ marginBottom: 10 }}>
                  {ownedDevices.map((d) => (
                    <div key={d.id} className="admin-user-dev-row">
                      <div>
                        <div className="admin-dev-name">{d.name || d.id}</div>
                        <div className="admin-dev-id num-tabular">
                          {d.id} · {d.status === 'online' ? 'Online' : 'Offline'}
                        </div>
                      </div>
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-compact"
                        disabled={deviceBusyId === d.id}
                        onClick={() => handleUnlinkDevice(d.id)}
                      >
                        <Unlink size={13} />
                        <span>{deviceBusyId === d.id ? '...' : 'Lepas'}</span>
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {unclaimedDevices.length > 0 && (
                <div className="admin-user-assign-row">
                  <div style={{ flex: 1, minWidth: 180 }}>
                    <InAppSelect
                      id="admin-assign-device"
                      value={assignDeviceId}
                      onChange={setAssignDeviceId}
                      options={unclaimedDevices.map((d) => ({
                        value: d.id,
                        label: `${d.name || d.id} (${d.id})`,
                      }))}
                    />
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    disabled={!assignDeviceId || Boolean(deviceBusyId)}
                    onClick={handleAssignDevice}
                  >
                    <Plus size={14} />
                    <span>Pasangkan Unit</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* 5. Hak Akses Login */}
          {isEdit && (
            <div className="admin-modal-section">
              <div className="admin-toggle-row">
                <div>
                  <div className="admin-row-title">Izinkan Akun Login ke Dashboard</div>
                  <div className="admin-row-sub">
                    {isActive
                      ? 'Aktif: pembeli dapat masuk dan memantau panel listriknya.'
                      : 'Ditangguhkan: pembeli langsung ditolak saat mencoba masuk atau memakai API.'}
                  </div>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={isActive}
                  className={`admin-switch ${isActive ? 'on' : ''}`}
                  onClick={() => setIsActive((v) => !v)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>
            </div>
          )}

          <div className="pwa-guide-footer" style={{ gap: 8, marginTop: 4 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Batal
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              <Save size={15} />
              <span>{saving ? 'Menyimpan...' : 'Simpan Perubahan'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

