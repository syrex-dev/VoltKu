import React, { useState, useMemo } from 'react'
import {
  Search,
  UserPlus,
  Crown,
  Pencil,
  Trash2,
  Eye,
  Copy,
  Cpu,
  Wifi,
  WifiOff,
  X,
  Mail,
  Sparkles,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatDateTimeWIB } from '../utils/formatters'

function UserAvatar({ user }) {
  const [imgErr, setImgErr] = useState(false)
  const initial = (user?.name || user?.email || 'U').charAt(0).toUpperCase()
  if (user?.avatar_url && !imgErr) {
    return (
      <img
        src={user.avatar_url}
        alt={user.name || 'Avatar'}
        className="admin-user-avatar-img"
        referrerPolicy="no-referrer"
        onError={() => setImgErr(true)}
      />
    )
  }
  return <span className="admin-user-avatar-fallback">{initial}</span>
}

function UserDetailModal({
  user,
  ownedDevices,
  busyId,
  defaultPaidName = 'VoltKu Pro',
  onClose,
  onEdit,
  onQuickPro,
}) {
  if (!user) return null
  const isPro = Boolean(user.plan?.is_pro)
  const planLabel = user.plan?.plan_name || (isPro ? 'VoltKu Pro' : 'VoltKu Gratis')
  const isGoogle = (user.auth_provider || '').toLowerCase() === 'google'

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head">
          <div className="admin-user-cell">
            <UserAvatar user={user} />
            <div>
              <h3 className="pwa-guide-title">{user.name}</h3>
              <p className="pwa-guide-sub">{user.email}</p>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <div className="admin-user-detail-grid">
          <div className="admin-user-detail-item">
            <span>Paket Aktif</span>
            <strong style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              {isPro && <Crown size={14} className="plan-pro-crown" />}
              {planLabel}
            </strong>
            <small>
              {isPro
                ? user.plan_expires_at
                  ? `Berlaku s.d. ${formatDateTimeWIB(user.plan_expires_at)}`
                  : 'Aktif Permanen'
                : `Maks. ${user.plan?.limits?.max_devices ?? 1} unit · ${user.plan?.limits?.history_days ?? 3} hr`}
            </small>
          </div>

          <div className="admin-user-detail-item">
            <span>Metode Masuk</span>
            <strong>{isGoogle ? 'Akun Google' : 'Email & Sandi'}</strong>
            <small>Status: {user.is_active ? 'Aktif' : 'Nonaktif'}</small>
          </div>

          <div className="admin-user-detail-item">
            <span>Terdaftar</span>
            <strong className="num-tabular">{formatDateTimeWIB(user.created_at)}</strong>
            <small>ID Pelanggan #{user.id}</small>
          </div>

          <div className="admin-user-detail-item">
            <span>Login Terakhir</span>
            <strong className="num-tabular">
              {user.last_login_at ? formatDateTimeWIB(user.last_login_at) : 'Belum pernah'}
            </strong>
            <small>Ketentuan: {user.terms_version_accepted || 'Belum'}</small>
          </div>
        </div>

        <div style={{ marginTop: 14 }}>
          <div className="pay-methods-head">
            <span className="pay-methods-title">
              Perangkat Dimiliki ({ownedDevices.length} unit)
            </span>
          </div>
          {ownedDevices.length === 0 ? (
            <div className="pay-methods-empty">
              Pelanggan ini belum mengklaim panel listrik apa pun.
            </div>
          ) : (
            <div className="admin-user-dev-list">
              {ownedDevices.map((d) => {
                const isOnline = d.status === 'online'
                return (
                  <div key={d.id} className="admin-user-dev-row">
                    <div>
                      <div className="admin-dev-name">{d.name || d.id}</div>
                      <div className="admin-dev-id num-tabular">
                        {d.id} · {d.location || 'Tanpa ruangan'} · MCB {d.mcb_watt || 2200} W
                      </div>
                    </div>
                    <span className={`admin-pill ${isOnline ? 'ok' : 'muted'}`}>
                      {isOnline ? <Wifi size={12} /> : <WifiOff size={12} />}
                      <span>{isOnline ? 'Online' : 'Offline'}</span>
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="plan-cta-row" style={{ marginTop: 16 }}>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            disabled={busyId === user.id}
            onClick={async () => {
              await onQuickPro(user)
              onClose()
            }}
          >
            <Sparkles size={14} />
            <span>{isPro ? 'Perpanjang +30 Hr' : `Aktifkan ${defaultPaidName} 30 Hr`}</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            onClick={() => {
              onClose()
              onEdit(user)
            }}
          >
            <Pencil size={14} />
            <span>Edit Lengkap</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export function AdminUsersSection({
  users = [],
  devices = [],
  plans = [],
  token,
  onLogout,
  onNotice,
  onReload,
  onOpenCreateUser,
  onOpenEditUser,
  onDeleteUser,
}) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [confirmDeleteId, setConfirmDeleteId] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [copiedId, setCopiedId] = useState(null)
  const [detailUser, setDetailUser] = useState(null)

  const devicesByOwner = useMemo(() => {
    const map = {}
    devices.forEach((d) => {
      if (d.owner_user_id != null) {
        if (!map[d.owner_user_id]) map[d.owner_user_id] = []
        map[d.owner_user_id].push(d)
      }
    })
    return map
  }, [devices])

  const summary = useMemo(() => {
    let pro = 0
    let free = 0
    let active = 0
    let google = 0
    let claimedUnits = 0

    for (const u of users) {
      if (u.plan?.is_pro) pro += 1
      else free += 1
      if (u.is_active) active += 1
      if ((u.auth_provider || '').toLowerCase() === 'google') google += 1
      claimedUnits += Number(u.device_count || 0)
    }

    return {
      total: users.length,
      pro,
      free,
      active,
      inactive: users.length - active,
      google,
      email: users.length - google,
      claimedUnits,
    }
  }, [users])

  const filteredUsers = useMemo(() => {
    const q = search.trim().toLowerCase()
    return users.filter((u) => {
      const isPro = Boolean(u.plan?.is_pro)
      const isGoogle = (u.auth_provider || '').toLowerCase() === 'google'
      if (filter === 'pro' && !isPro) return false
      if (filter === 'free' && isPro) return false
      if (filter === 'inactive' && u.is_active) return false
      if (filter === 'google' && !isGoogle) return false
      if (filter === 'email' && isGoogle) return false
      if (!q) return true
      return (
        (u.name || '').toLowerCase().includes(q) ||
        (u.email || '').toLowerCase().includes(q)
      )
    })
  }, [users, search, filter])

  const handleCopyEmail = async (u) => {
    if (!u.email) return
    try {
      await navigator.clipboard.writeText(u.email)
      setCopiedId(u.id)
      window.setTimeout(() => setCopiedId(null), 1500)
    } catch {
      // Abaikan jika ditolak
    }
  }

  const handleToggleActive = async (u) => {
    setBusyId(u.id)
    if (onNotice) onNotice(null)
    try {
      await apiRequest(
        `/api/admin/users/${u.id}`,
        { method: 'PATCH', body: { is_active: !u.is_active } },
        token,
        onLogout
      )
      if (onNotice) {
        onNotice({
          type: 'success',
          text: !u.is_active
            ? `Akun ${u.name} diaktifkan kembali.`
            : `Akun ${u.name} dinonaktifkan sementara.`,
        })
      }
      if (onReload) await onReload()
    } catch (err) {
      if (onNotice) {
        onNotice({ type: 'error', text: err.message || 'Gagal mengubah status akun.' })
      }
    } finally {
      setBusyId(null)
    }
  }

  const defaultPaidPlan = useMemo(() => {
    return (
      plans.find((p) => p.slug === 'pro' && p.is_active) ||
      plans.find((p) => !p.is_default_free && p.slug !== 'free' && p.is_active) || {
        slug: 'pro',
        name: 'VoltKu Pro',
      }
    )
  }, [plans])

  const handleQuickPro = async (u) => {
    setBusyId(u.id)
    if (onNotice) onNotice(null)
    const targetSlug = u.plan?.is_pro && u.plan_tier ? u.plan_tier : defaultPaidPlan.slug
    const targetName =
      plans.find((p) => p.slug === targetSlug)?.name || u.plan?.plan_name || defaultPaidPlan.name
    try {
      await apiRequest(
        `/api/admin/users/${u.id}`,
        { method: 'PATCH', body: { plan_tier: targetSlug, plan_duration_days: 30 } },
        token,
        onLogout
      )
      if (onNotice) {
        onNotice({
          type: 'success',
          text: `Paket ${targetName} 30 hari diterapkan untuk ${u.name}.`,
        })
      }
      if (onReload) await onReload()
    } catch (err) {
      if (onNotice) {
        onNotice({ type: 'error', text: err.message || 'Gagal memperbarui paket berbayar.' })
      }
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="admin-section-stack tab-pane-fade">
      {/* 1. Ringkasan KPI Pelanggan */}
      <div className="admin-kpi-grid">
        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Total Pengguna</span>
          <strong className="admin-kpi-value num-tabular">{summary.total}</strong>
          <span className="admin-kpi-sub">
            {summary.google} Google · {summary.email} Email
          </span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Status Akun</span>
          <strong className="admin-kpi-value num-tabular brand-emerald-text">{summary.active}</strong>
          <span className="admin-kpi-sub">
            {summary.active} aktif · {summary.inactive} nonaktif
          </span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Pelanggan Pro</span>
          <strong className="admin-kpi-value num-tabular brand-amber-text">{summary.pro}</strong>
          <span className="admin-kpi-sub">{summary.free} pengguna paket Gratis</span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Panel Terklaim</span>
          <strong className="admin-kpi-value num-tabular brand-blue-text">
            {summary.claimedUnits}
          </strong>
          <span className="admin-kpi-sub">Total unit terhubung ke akun</span>
        </div>
      </div>

      {/* 2. Toolbar Pencarian, Filter Cepat & Buat Akun */}
      <div className="clean-sheet admin-users-toolbar-box">
        <div className="admin-toolbar-row">
          <div className="admin-search-wrap">
            <Search size={16} className="admin-search-icon" />
            <input
              type="text"
              className="modern-input admin-search-input"
              placeholder="Cari nama atau email pembeli..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            onClick={onOpenCreateUser}
          >
            <UserPlus size={15} />
            <span>Buat Akun</span>
          </button>
        </div>

        {(() => {
          const userFilters = [
            { id: 'all', label: `Semua (${summary.total})` },
            { id: 'pro', label: `VoltKu Pro (${summary.pro})` },
            { id: 'free', label: `Gratis (${summary.free})` },
            ...(summary.inactive > 0
              ? [{ id: 'inactive', label: `Nonaktif (${summary.inactive})` }]
              : []),
            { id: 'google', label: `Google (${summary.google})` },
            { id: 'email', label: `Email (${summary.email})` },
          ]
          return (
            <div
              className={`admin-pm-filter-tabs is-justified cols-${userFilters.length}`}
              style={{ marginTop: 10 }}
            >
              {userFilters.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`admin-filter-pill ${filter === f.id ? 'active' : ''}`}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )
        })()}
      </div>

      {/* 3. Daftar Pengguna (Desktop & Mobile) */}
      {filteredUsers.length === 0 ? (
        <div className="clean-sheet admin-empty-box">
          Belum ada pengguna terdaftar yang cocok dengan filter ini.
        </div>
      ) : (
        <>
          <div className="clean-sheet admin-table-desktop">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Nama &amp; Email</th>
                  <th>Paket</th>
                  <th>Status</th>
                  <th>Unit</th>
                  <th>Aktivitas</th>
                  <th style={{ textAlign: 'right' }}>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => {
                  const isPro = Boolean(u.plan?.is_pro)
                  const planLabel = u.plan?.plan_name || (isPro ? 'VoltKu Pro' : 'Gratis')
                  const isGoogle = (u.auth_provider || '').toLowerCase() === 'google'
                  return (
                    <tr key={u.id}>
                      <td>
                        <div className="admin-user-cell">
                          <UserAvatar user={u} />
                          <div className="admin-user-ident">
                            <div className="admin-user-name-row">
                              <span className="admin-dev-name">{u.name}</span>
                              <span className={`admin-auth-chip ${isGoogle ? 'google' : 'email'}`}>
                                {!isGoogle && <Mail size={10} />}
                                <span>{isGoogle ? 'Google' : 'Email'}</span>
                              </span>
                            </div>
                            <div className="admin-user-email-row">
                              <span className="admin-dev-id">{u.email}</span>
                              <button
                                type="button"
                                className="admin-pm-copy-btn"
                                onClick={() => handleCopyEmail(u)}
                                title="Salin email"
                              >
                                <Copy size={11} />
                                <span>{copiedId === u.id ? 'Disalin' : 'Salin'}</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td>
                        <span className={`admin-pill ${isPro ? 'pro' : 'muted'}`}>
                          {isPro && <Crown size={12} />}
                          <span>{planLabel}</span>
                        </span>
                        {isPro && (
                          <div className="admin-dev-id num-tabular" style={{ marginTop: 3 }}>
                            {u.plan_expires_at
                              ? `s.d. ${formatDateTimeWIB(u.plan_expires_at)}`
                              : 'Permanen'}
                          </div>
                        )}
                      </td>

                      <td>
                        <div className="admin-user-status-cell">
                          <button
                            type="button"
                            role="switch"
                            aria-checked={Boolean(u.is_active)}
                            aria-label={`Ubah status ${u.name}`}
                            className={`admin-switch is-sm ${u.is_active ? 'on' : ''}`}
                            disabled={busyId === u.id}
                            onClick={() => handleToggleActive(u)}
                          >
                            <span className="admin-switch-thumb" />
                          </button>
                          <span className={`admin-pill ${u.is_active ? 'ok' : 'warn'}`}>
                            {u.is_active ? 'Aktif' : 'Nonaktif'}
                          </span>
                        </div>
                      </td>

                      <td>
                        <button
                          type="button"
                          className="admin-unit-chip num-tabular"
                          onClick={() => setDetailUser(u)}
                          title="Lihat detail & unit milik pengguna"
                        >
                          <Cpu size={12} />
                          <span>{u.device_count} unit</span>
                        </button>
                      </td>

                      <td>
                        <div className="admin-dev-name num-tabular" style={{ fontSize: 12.5 }}>
                          {u.last_login_at ? formatDateTimeWIB(u.last_login_at) : 'Belum login'}
                        </div>
                        <div className="admin-dev-id num-tabular">
                          Daftar: {formatDateTimeWIB(u.created_at)}
                        </div>
                      </td>

                      <td style={{ textAlign: 'right' }}>
                        <div className="admin-row-actions">
                          <button
                            type="button"
                            className="admin-icon-action"
                            title="Detail Akun & Perangkat"
                            onClick={() => setDetailUser(u)}
                          >
                            <Eye size={15} />
                          </button>
                          <button
                            type="button"
                            className="admin-icon-action"
                            title="Edit Akun & Paket"
                            onClick={() => onOpenEditUser(u)}
                          >
                            <Pencil size={15} />
                          </button>
                          {confirmDeleteId === u.id ? (
                            <button
                              type="button"
                              className="btn btn-danger-solid btn-compact"
                              onClick={async () => {
                                await onDeleteUser(u.id)
                                setConfirmDeleteId(null)
                              }}
                            >
                              Hapus?
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="admin-icon-action danger"
                              title="Hapus Akun"
                              onClick={() => setConfirmDeleteId(u.id)}
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
            {filteredUsers.map((u) => {
              const isPro = Boolean(u.plan?.is_pro)
              const planLabel = u.plan?.plan_name || (isPro ? 'VoltKu Pro' : 'Gratis')
              return (
                <div key={u.id} className="clean-sheet admin-device-card-m">
                  <div className="admin-m-top">
                    <div className="admin-user-cell" style={{ minWidth: 0 }}>
                      <UserAvatar user={u} />
                      <div className="admin-m-ident">
                        <div className="admin-dev-name">{u.name}</div>
                        <div className="admin-dev-id">{u.email}</div>
                      </div>
                    </div>
                    <span className={`admin-pill ${isPro ? 'pro' : 'muted'}`}>
                      {isPro && <Crown size={12} />}
                      <span>{planLabel}</span>
                    </span>
                  </div>

                  <div className="admin-m-metrics admin-m-metrics-2col num-tabular">
                    <div>
                      <span>Status &amp; Unit</span>
                      <strong>
                        {u.is_active ? 'Aktif' : 'Nonaktif'} · {u.device_count} unit
                      </strong>
                    </div>
                    <div>
                      <span>Login Terakhir</span>
                      <strong>
                        {u.last_login_at ? formatDateTimeWIB(u.last_login_at) : 'Belum pernah'}
                      </strong>
                    </div>
                  </div>

                  <div className="admin-m-actions admin-m-actions-2col">
                    <button
                      type="button"
                      className="btn btn-secondary btn-compact"
                      onClick={() => setDetailUser(u)}
                    >
                      <Eye size={14} />
                      <span>Detail</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-compact"
                      onClick={() => onOpenEditUser(u)}
                    >
                      <Pencil size={14} />
                      <span>Edit</span>
                    </button>
                    {confirmDeleteId === u.id ? (
                      <button
                        type="button"
                        className="btn btn-danger-solid btn-compact"
                        style={{ gridColumn: 'span 2' }}
                        onClick={async () => {
                          await onDeleteUser(u.id)
                          setConfirmDeleteId(null)
                        }}
                      >
                        <span>Yakin Hapus Akun?</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-compact"
                        style={{ gridColumn: 'span 2' }}
                        onClick={() => setConfirmDeleteId(u.id)}
                      >
                        <Trash2 size={14} />
                        <span>Hapus Akun</span>
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      <UserDetailModal
        user={detailUser}
        ownedDevices={detailUser ? devicesByOwner[detailUser.id] || [] : []}
        busyId={busyId}
        defaultPaidName={defaultPaidPlan.name}
        onClose={() => setDetailUser(null)}
        onEdit={onOpenEditUser}
        onQuickPro={handleQuickPro}
      />
    </div>
  )
}

