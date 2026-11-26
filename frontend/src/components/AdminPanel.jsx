import React, { useState, useEffect, useCallback, useMemo } from 'react'
import {
  LayoutDashboard,
  Users,
  Cpu,
  ShieldAlert,
  Sliders,
  Plus,
  Search,
  Pencil,
  Trash2,
  ExternalLink,
  LogOut,
  Sun,
  Moon,
  Wifi,
  WifiOff,
  X,
  Save,
  RefreshCw,
  Crown,
  CreditCard,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatNum, formatTimeWIB } from '../utils/formatters'
import { BrandLogo } from './BrandLogo'
import { InAppSelect } from './InAppSelect'
import { AdminAppSettingsTab } from './AdminAppSettingsTab'
import { AdminUsersSection } from './AdminUsersSection'
import {
  AdminPaymentSummaryStrip,
  AdminUpgradeRequestsCard,
  AdminPaymentMethodsCard,
} from './AdminPaymentSection'

export function AdminPanel({
  token,
  theme,
  onToggleTheme,
  onOpenAddDevice,
  onLogout,
  refreshSignal = 0,
}) {
  const [adminTab, setAdminTab] = useState('overview')
  const [overview, setOverview] = useState(null)
  const [users, setUsers] = useState([])
  const [devices, setDevices] = useState([])
  const [anomalies, setAnomalies] = useState([])
  const [appSettings, setAppSettings] = useState(null)
  const [consentsData, setConsentsData] = useState(null)
  const [upgradeRequests, setUpgradeRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState(null)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [anomDeviceFilter, setAnomDeviceFilter] = useState('')
  const [anomSeverityFilter, setAnomSeverityFilter] = useState('')

  // Device Edit Modal State
  const [editingDevice, setEditingDevice] = useState(null)
  const [editName, setEditName] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editMcb, setEditMcb] = useState(2200)
  const [editOwnerId, setEditOwnerId] = useState('0')
  const [editPublicDemo, setEditPublicDemo] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const [confirmDeleteDevId, setConfirmDeleteDevId] = useState('')

  // User Create / Edit Modal State
  const [userModalMode, setUserModalMode] = useState(null) // 'create' | 'edit'
  const [editingUser, setEditingUser] = useState(null)
  const [uName, setUName] = useState('')
  const [uEmail, setUEmail] = useState('')
  const [uPassword, setUPassword] = useState('')
  const [uActive, setUActive] = useState(true)
  const [uPlanTier, setUPlanTier] = useState('free')
  const [uPlanDuration, setUPlanDuration] = useState('keep')
  const [savingUser, setSavingUser] = useState(false)

  const [togglingAccess, setTogglingAccess] = useState(false)
  const [pmSummaryCounts, setPmSummaryCounts] = useState(null)

  const loadAdminData = useCallback(async () => {
    if (!token) return
    try {
      const [ov, usrs, devs, anoms, appCfg, consents, upgReqs] = await Promise.all([
        apiRequest('/api/admin/overview', {}, token, onLogout),
        apiRequest('/api/admin/users', {}, token, onLogout),
        apiRequest('/api/admin/devices', {}, token, onLogout),
        apiRequest('/api/admin/anomalies?limit=100', {}, token, onLogout),
        apiRequest('/api/admin/app-settings', {}, token, onLogout).catch(() => null),
        apiRequest('/api/admin/consents?limit=100', {}, token, onLogout).catch(() => null),
        apiRequest('/api/admin/upgrade-requests?limit=100', {}, token, onLogout).catch(() => []),
      ])
      setOverview(ov)
      setUsers(usrs || [])
      setDevices(devs || [])
      setAnomalies(anoms || [])
      if (appCfg) setAppSettings(appCfg)
      if (consents) setConsentsData(consents)
      setUpgradeRequests(Array.isArray(upgReqs) ? upgReqs : [])
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal memuat data Panel Admin.' })
    } finally {
      setLoading(false)
    }
  }, [token, onLogout])

  useEffect(() => {
    loadAdminData()
  }, [loadAdminData, refreshSignal])

  const handleTogglePublicAccess = async () => {
    if (!overview || togglingAccess) return
    const nextVal = !overview.public_read_enabled
    setTogglingAccess(true)
    setNotice(null)
    try {
      const res = await apiRequest(
        '/api/admin/access',
        { method: 'PATCH', body: { public_read_enabled: nextVal } },
        token,
        onLogout
      )
      setOverview((prev) => (prev ? { ...prev, public_read_enabled: res.public_read_enabled } : prev))
      setNotice({
        type: 'success',
        text: res.public_read_enabled
          ? 'Akses Guest (Tanpa Login) diaktifkan.'
          : 'Akses Guest dimatikan. Pengunjung wajib masuk atau daftar akun.',
      })
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal memperbarui kebijakan akses.' })
    } finally {
      setTogglingAccess(false)
    }
  }

  // Device Actions
  const openEditDeviceModal = (dev) => {
    setEditingDevice(dev)
    setEditName(dev.name || dev.id)
    setEditLocation(dev.location || '')
    setEditMcb(dev.mcb_watt || 2200)
    setEditOwnerId(dev.owner_user_id ? String(dev.owner_user_id) : '0')
    setEditPublicDemo(Boolean(dev.is_public_demo))
  }

  const handleSaveDeviceEdit = async (e) => {
    e.preventDefault()
    if (!editingDevice) return
    setSavingEdit(true)
    setNotice(null)
    try {
      await apiRequest(
        `/api/admin/devices/${editingDevice.id}`,
        {
          method: 'PATCH',
          body: {
            name: editName.trim(),
            location: editLocation.trim(),
            mcb_watt: parseInt(editMcb, 10),
            owner_user_id: parseInt(editOwnerId, 10) || 0,
            is_public_demo: editPublicDemo,
          },
        },
        token,
        onLogout
      )
      setEditingDevice(null)
      setNotice({ type: 'success', text: 'Perangkat diperbarui.' })
      await loadAdminData()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal menyimpan perangkat.' })
    } finally {
      setSavingEdit(false)
    }
  }

  const handleDeleteDevice = async (devId) => {
    setNotice(null)
    try {
      await apiRequest(`/api/devices/${devId}`, { method: 'DELETE' }, token, onLogout)
      setConfirmDeleteDevId('')
      setNotice({ type: 'success', text: `Perangkat ${devId} dihapus.` })
      await loadAdminData()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal menghapus perangkat.' })
    }
  }

  // User Actions
  const openCreateUser = () => {
    setUserModalMode('create')
    setEditingUser(null)
    setUName('')
    setUEmail('')
    setUPassword('')
    setUActive(true)
    setUPlanTier('free')
    setUPlanDuration('0')
  }

  const openEditUser = (u) => {
    setUserModalMode('edit')
    setEditingUser(u)
    setUName(u.name || '')
    setUEmail(u.email || '')
    setUPassword('')
    setUActive(Boolean(u.is_active))
    setUPlanTier(u.plan_tier || 'free')
    setUPlanDuration('keep')
  }

  const handleSaveUser = async (e) => {
    e.preventDefault()
    setSavingUser(true)
    setNotice(null)
    try {
      if (userModalMode === 'create') {
        const body = {
          name: uName.trim(),
          email: uEmail.trim(),
          password: uPassword,
          plan_tier: uPlanTier,
        }
        if (uPlanTier === 'pro' && uPlanDuration !== '0' && Number(uPlanDuration) > 0) {
          body.plan_duration_days = Number(uPlanDuration)
        }
        await apiRequest(
          '/api/admin/users',
          { method: 'POST', body },
          token,
          onLogout
        )
        setNotice({ type: 'success', text: 'Akun pengguna baru berhasil dibuat.' })
      } else if (editingUser) {
        const payload = { name: uName.trim(), is_active: uActive, plan_tier: uPlanTier }
        if (uPassword.trim()) payload.password = uPassword
        if (uPlanTier === 'pro') {
          if (uPlanDuration === '0') {
            payload.clear_plan_expiration = true
          } else if (uPlanDuration !== 'keep' && Number(uPlanDuration) > 0) {
            payload.plan_duration_days = Number(uPlanDuration)
          }
        }
        await apiRequest(
          `/api/admin/users/${editingUser.id}`,
          { method: 'PATCH', body: payload },
          token,
          onLogout
        )
        setNotice({ type: 'success', text: 'Data akun pengguna diperbarui.' })
      }
      setUserModalMode(null)
      await loadAdminData()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal menyimpan akun pengguna.' })
    } finally {
      setSavingUser(false)
    }
  }

  const handleDeleteUser = async (uid) => {
    setNotice(null)
    try {
      await apiRequest(`/api/admin/users/${uid}`, { method: 'DELETE' }, token, onLogout)
      setNotice({ type: 'success', text: 'Akun pengguna dihapus dan unitnya dilepas ke stok.' })
      await loadAdminData()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal menghapus akun pengguna.' })
    }
  }

  const filteredDevices = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return devices.filter((d) => {
      if (statusFilter === 'online' && d.status !== 'online') return false
      if (statusFilter === 'offline' && d.status !== 'offline') return false
      if (statusFilter === 'unclaimed' && d.owner_user_id != null) return false
      if (statusFilter === 'demo' && !d.is_public_demo) return false
      if (!q) return true
      return (
        d.id.toLowerCase().includes(q) ||
        (d.name || '').toLowerCase().includes(q) ||
        (d.location || '').toLowerCase().includes(q) ||
        (d.owner_name || '').toLowerCase().includes(q) ||
        (d.owner_email || '').toLowerCase().includes(q)
      )
    })
  }, [devices, searchQuery, statusFilter])

  const filteredAnomalies = useMemo(() => {
    return anomalies.filter((a) => {
      if (anomDeviceFilter && a.device_id !== anomDeviceFilter) return false
      if (anomSeverityFilter && a.severity !== anomSeverityFilter) return false
      return true
    })
  }, [anomalies, anomDeviceFilter, anomSeverityFilter])

  const deviceNamesById = useMemo(() => {
    const map = {}
    devices.forEach((d) => {
      map[d.id] = d.name || d.id
    })
    return map
  }, [devices])

  const pendingUpgradesCount = upgradeRequests.filter((r) =>
    ['pending', 'awaiting_payment', 'verifying'].includes(r.status)
  ).length

  const tabs = [
    { id: 'overview', label: 'Ringkasan', icon: LayoutDashboard },
    { id: 'users', label: 'Pengguna', icon: Users },
    { id: 'payments', label: 'Pembayaran', icon: CreditCard, badge: pendingUpgradesCount },
    { id: 'devices', label: 'Perangkat', icon: Cpu },
    { id: 'anomalies', label: 'Anomali', icon: ShieldAlert },
    { id: 'settings', label: 'Pengaturan', icon: Sliders },
  ]

  const hasAdminModal = Boolean(editingDevice || userModalMode)

  return (
    <div className={`app-layout admin-shell ${hasAdminModal ? 'has-modal-open' : ''}`}>
      <div className="app-header-wrap clean-header-bar">
        <div className="container">
          <header className="app-header clean-header-inner">
            <div className="header-main-row">
              <div className="admin-head-left">
                <BrandLogo
                  theme={theme}
                  displayMode="logo_only"
                  appName={appSettings?.app_name || 'VoltKu'}
                  variant="compact"
                />
                <span className="admin-title-badge">Admin</span>
                <a
                  href="/"
                  target="_blank"
                  rel="noreferrer"
                  className="desktop-back-btn admin-back-pill"
                  title="Buka Halaman Pembeli"
                >
                  <ExternalLink size={14} />
                  <span>Web User</span>
                </a>
              </div>

              <nav className="desktop-header-nav" aria-label="Menu Admin">
                {tabs.map((t) => {
                  const Icon = t.icon
                  return (
                    <button
                      key={t.id}
                      type="button"
                      className={`desktop-nav-pill ${adminTab === t.id ? 'active' : ''}`}
                      onClick={() => setAdminTab(t.id)}
                    >
                      <Icon size={15} />
                      <span>{t.label}</span>
                      {t.badge > 0 && (
                        <span className="desktop-nav-badge">{t.badge}</span>
                      )}
                    </button>
                  )
                })}
              </nav>

              <div className="header-actions">
                <button
                  type="button"
                  className="header-icon-btn"
                  onClick={loadAdminData}
                  aria-label="Muat Ulang Data Admin"
                  title="Muat ulang data"
                >
                  <RefreshCw size={17} />
                </button>
                <button
                  type="button"
                  className="header-icon-btn"
                  onClick={onToggleTheme}
                  aria-label="Ganti Tema"
                >
                  {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
                </button>
                <button
                  type="button"
                  className="header-icon-btn"
                  onClick={onLogout}
                  aria-label="Keluar Admin"
                  title="Keluar Sesi Admin"
                >
                  <LogOut size={17} />
                </button>
              </div>
            </div>
          </header>
        </div>
      </div>

      <main className="container main-content-wrap has-bottom-nav">
        {notice && (
          <div className={`feedback-msg ${notice.type === 'error' ? 'error' : 'success'}`}>
            {notice.text}
          </div>
        )}

        {loading && !overview ? (
          <div className="clean-sheet admin-empty-box">Memuat data Panel Admin...</div>
        ) : (
          <>
            {adminTab === 'overview' && overview && (
              <div className="admin-section-stack tab-pane-fade">
                <div className="admin-kpi-grid">
                  <div className="clean-sheet admin-kpi-card">
                    <span className="admin-kpi-label">Pengguna (Tenant)</span>
                    <strong className="admin-kpi-value num-tabular">{overview.users_total}</strong>
                    <span className="admin-kpi-sub">
                      {overview.users_active} aktif · {overview.users_pro || 0} Pro
                      {(overview.pending_upgrades || 0) > 0
                        ? ` · ${overview.pending_upgrades} ajuan upgrade`
                        : ''}
                    </span>
                  </div>
                  <div className="clean-sheet admin-kpi-card">
                    <span className="admin-kpi-label">Inventaris Unit</span>
                    <strong className="admin-kpi-value num-tabular">{overview.devices_total}</strong>
                    <span className="admin-kpi-sub">
                      {overview.devices_claimed} diklaim · {overview.devices_unclaimed} stok
                    </span>
                  </div>
                  <div className="clean-sheet admin-kpi-card">
                    <span className="admin-kpi-label">Unit Online</span>
                    <strong className="admin-kpi-value num-tabular brand-blue-text">
                      {overview.devices_online}
                    </strong>
                    <span className="admin-kpi-sub">
                      {overview.devices_public_demo} perangkat Guest
                    </span>
                  </div>
                  <div className="clean-sheet admin-kpi-card">
                    <span className="admin-kpi-label">Anomali (7 Hari)</span>
                    <strong className="admin-kpi-value num-tabular">{overview.anomalies_7d}</strong>
                    <span className="admin-kpi-sub">Tarif dasar Rp {overview.tariff_rp}</span>
                  </div>
                </div>

                <div className="admin-two-col">
                  <section className="clean-sheet admin-card-block">
                    <div className="admin-card-head">
                      <h3>Akses Guest (Tanpa Login)</h3>
                    </div>
                    <div className="admin-toggle-row">
                      <div>
                        <div className="admin-row-title">Izinkan Akses Guest Tanpa Login</div>
                        <div className="admin-row-sub">
                          {overview.public_read_enabled
                            ? 'Guest dapat melihat perangkat publik secara read-only. Perangkat milik akun pembeli tetap privat.'
                            : 'Halaman utama ditutup untuk Guest. Pengunjung wajib masuk atau daftar akun.'}
                        </div>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={overview.public_read_enabled}
                        className={`admin-switch ${overview.public_read_enabled ? 'on' : ''}`}
                        onClick={handleTogglePublicAccess}
                        disabled={togglingAccess}
                      >
                        <span className="admin-switch-thumb" />
                      </button>
                    </div>
                  </section>

                  <section className="clean-sheet admin-card-block">
                    <div className="admin-card-head">
                      <h3>Status Layanan Server</h3>
                    </div>
                    <div className="admin-service-list">
                      <div className="admin-service-item">
                        <span>Broker MQTT</span>
                        <span className={`admin-pill ${overview.mqtt_connected ? 'ok' : 'warn'}`}>
                          {overview.mqtt_connected ? 'Terhubung' : 'Terputus'}
                        </span>
                      </div>
                      <div className="admin-service-item">
                        <span>Worker Telemetri</span>
                        <span className={`admin-pill ${overview.ingest_worker_alive ? 'ok' : 'warn'}`}>
                          {overview.ingest_worker_alive ? 'Aktif' : 'Berhenti'}
                        </span>
                      </div>
                      <div className="admin-service-item">
                        <span>Antrean Data Masuk</span>
                        <span className="num-tabular">{overview.ingest_queue_size} pesan</span>
                      </div>
                      <div className="admin-service-item">
                        <span>Scheduler Laporan</span>
                        <span className={`admin-pill ${overview.scheduler_enabled ? 'ok' : 'muted'}`}>
                          {overview.scheduler_enabled ? 'Aktif' : 'Nonaktif'}
                        </span>
                      </div>
                      <div className="admin-service-item">
                        <span>Bot Telegram</span>
                        <span className={`admin-pill ${overview.bot_configured ? 'ok' : 'muted'}`}>
                          {overview.bot_configured ? 'Siap' : 'Belum Diatur'}
                        </span>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
            )}

            {adminTab === 'users' && (
              <AdminUsersSection
                users={users}
                devices={devices}
                token={token}
                onLogout={onLogout}
                onNotice={setNotice}
                onReload={loadAdminData}
                onOpenCreateUser={openCreateUser}
                onOpenEditUser={openEditUser}
                onDeleteUser={handleDeleteUser}
              />
            )}

            {adminTab === 'devices' && (
              <div className="admin-section-stack tab-pane-fade">
                <div className="clean-sheet admin-toolbar-card">
                  <div className="admin-search-wrap">
                    <Search size={16} className="admin-search-icon" />
                    <input
                      type="text"
                      className="modern-input admin-search-input"
                      placeholder="Cari ID, nama alat, atau pemilik..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </div>
                  <div className="admin-toolbar-right">
                    <div className="admin-filter-pills">
                      {[
                        { id: 'all', label: 'Semua' },
                        { id: 'online', label: 'Online' },
                        { id: 'unclaimed', label: 'Stok' },
                        { id: 'demo', label: 'Guest' },
                      ].map((f) => (
                        <button
                          key={f.id}
                          type="button"
                          className={`admin-chip-btn ${statusFilter === f.id ? 'active' : ''}`}
                          onClick={() => setStatusFilter(f.id)}
                        >
                          {f.label}
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="btn btn-primary btn-compact"
                      onClick={onOpenAddDevice}
                    >
                      <Plus size={15} />
                      <span>Tambah Unit</span>
                    </button>
                  </div>
                </div>

                {filteredDevices.length === 0 ? (
                  <div className="clean-sheet admin-empty-box">
                    Tidak ada perangkat yang cocok dengan filter saat ini.
                  </div>
                ) : (
                  <>
                    <div className="clean-sheet admin-table-desktop">
                      <table className="admin-table">
                        <thead>
                          <tr>
                            <th>Perangkat</th>
                            <th>Pemilik (Tenant)</th>
                            <th>Status</th>
                            <th>Daya / Tegangan</th>
                            <th>MCB</th>
                            <th style={{ textAlign: 'right' }}>Aksi</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredDevices.map((d) => {
                            const online = d.status === 'online'
                            const watts = d.latest?.p
                            const volts = d.latest?.v
                            return (
                              <tr key={d.id}>
                                <td>
                                  <div className="admin-dev-name">
                                    {d.name || d.id}{' '}
                                    {d.is_public_demo && (
                                      <span className="admin-demo-badge">Guest</span>
                                    )}
                                  </div>
                                  <div className="admin-dev-id num-tabular">
                                    {d.id} · {d.location || 'Tanpa ruangan'}
                                  </div>
                                </td>
                                <td>
                                  {d.owner_name ? (
                                    <div>
                                      <div className="admin-dev-name">{d.owner_name}</div>
                                      <div className="admin-dev-id">{d.owner_email}</div>
                                    </div>
                                  ) : (
                                    <span className="admin-pill muted">Stok (Belum Diklaim)</span>
                                  )}
                                </td>
                                <td>
                                  <span className={`admin-pill ${online ? 'ok' : 'muted'}`}>
                                    {online ? 'Online' : 'Offline'}
                                  </span>
                                </td>
                                <td className="num-tabular">
                                  {watts !== undefined ? `${formatNum(watts, 0)} W` : '—'}
                                  {volts !== undefined ? ` · ${formatNum(volts, 0)} V` : ''}
                                </td>
                                <td className="num-tabular">{d.mcb_watt} W</td>
                                <td>
                                  <div className="admin-row-actions">
                                    <button
                                      type="button"
                                      className="admin-icon-action"
                                      title="Atur Pemilik & Metadata"
                                      onClick={() => openEditDeviceModal(d)}
                                    >
                                      <Pencil size={15} />
                                    </button>
                                    {confirmDeleteDevId === d.id ? (
                                      <button
                                        type="button"
                                        className="btn btn-danger-solid btn-compact"
                                        onClick={() => handleDeleteDevice(d.id)}
                                      >
                                        Hapus?
                                      </button>
                                    ) : (
                                      <button
                                        type="button"
                                        className="admin-icon-action danger"
                                        title="Hapus Perangkat"
                                        onClick={() => setConfirmDeleteDevId(d.id)}
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
                      {filteredDevices.map((d) => {
                        const online = d.status === 'online'
                        const watts = d.latest?.p
                        const volts = d.latest?.v
                        const rssi = d.latest?.rssi
                        return (
                          <div key={d.id} className="clean-sheet admin-device-card-m">
                            <div className="admin-m-top">
                              <div className="admin-m-ident">
                                <div className="admin-dev-name">
                                  {d.name || d.id}{' '}
                                  {d.is_public_demo && (
                                    <span className="admin-demo-badge">Guest</span>
                                  )}
                                </div>
                                <div className="admin-dev-id num-tabular">
                                  {d.id} · {d.owner_name ? `Milik ${d.owner_name}` : 'Stok Belum Diklaim'}
                                </div>
                              </div>
                              <span className={`admin-pill ${online ? 'ok' : 'muted'}`}>
                                {online ? <Wifi size={12} /> : <WifiOff size={12} />}
                                <span>{online ? 'Online' : 'Offline'}</span>
                              </span>
                            </div>

                            <div className="admin-m-metrics num-tabular">
                              <div>
                                <span>Daya</span>
                                <strong>{watts !== undefined ? `${formatNum(watts, 0)} W` : '--'}</strong>
                              </div>
                              <div>
                                <span>Tegangan</span>
                                <strong>{volts !== undefined ? `${formatNum(volts, 0)} V` : '--'}</strong>
                              </div>
                              <div>
                                <span>MCB</span>
                                <strong>{d.mcb_watt} W</strong>
                              </div>
                              <div>
                                <span>Sinyal</span>
                                <strong>{rssi !== undefined ? `${rssi} dBm` : '--'}</strong>
                              </div>
                            </div>

                            <div className="admin-m-actions admin-m-actions-2col">
                              <button
                                type="button"
                                className="btn btn-secondary btn-compact"
                                onClick={() => openEditDeviceModal(d)}
                              >
                                <Pencil size={14} />
                                <span>Atur / Pemilik</span>
                              </button>
                              {confirmDeleteDevId === d.id ? (
                                <button
                                  type="button"
                                  className="btn btn-danger-solid btn-compact"
                                  onClick={() => handleDeleteDevice(d.id)}
                                >
                                  <span>Yakin Hapus</span>
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  className="btn btn-danger-ghost btn-compact"
                                  onClick={() => setConfirmDeleteDevId(d.id)}
                                >
                                  <Trash2 size={14} />
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
              </div>
            )}

            {adminTab === 'anomalies' && (
              <div className="admin-section-stack tab-pane-fade">
                <div className="clean-sheet admin-toolbar-card">
                  <div style={{ minWidth: 220, flex: '1 1 220px' }}>
                    <InAppSelect
                      id="admin-anom-dev-filter"
                      value={anomDeviceFilter}
                      onChange={setAnomDeviceFilter}
                      ariaLabel="Filter Perangkat"
                      options={[
                        { value: '', label: 'Semua Perangkat' },
                        ...devices.map((d) => ({
                          value: d.id,
                          label: d.name || d.id,
                        })),
                      ]}
                    />
                  </div>

                  <div className="admin-filter-pills">
                    {[
                      { id: '', label: 'Semua' },
                      { id: 'critical', label: 'Critical' },
                      { id: 'warning', label: 'Warning' },
                    ].map((s) => (
                      <button
                        key={s.id || 'all'}
                        type="button"
                        className={`admin-chip-btn ${anomSeverityFilter === s.id ? 'active' : ''}`}
                        onClick={() => setAnomSeverityFilter(s.id)}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>

                {filteredAnomalies.length === 0 ? (
                  <div className="clean-sheet admin-empty-box">
                    Tidak ada anomali pada filter ini.
                  </div>
                ) : (
                  <div className="clean-sheet admin-anomaly-list">
                    {filteredAnomalies.map((a) => {
                      const sev = (a.severity || '').toLowerCase()
                      const isCrit = sev === 'critical'
                      return (
                        <div key={a.id} className="anomaly-feed-row">
                          <div className={`anomaly-feed-icon ${isCrit ? 'crit' : 'warn'}`}>
                            <ShieldAlert size={16} />
                          </div>
                          <div className="anomaly-feed-body">
                            <div className="anomaly-feed-top">
                              <span className="anomaly-feed-msg">{a.message}</span>
                              <span className={`severity-tag-soft ${isCrit ? 'crit' : 'warn'}`}>
                                {isCrit ? 'Penting' : 'Peringatan'}
                              </span>
                            </div>
                            <div className="anomaly-feed-meta">
                              <span className="anomaly-device-tag">
                                {deviceNamesById[a.device_id] || a.device_id}
                              </span>
                              <span className="num-tabular">{formatTimeWIB(a.ts)}</span>
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {adminTab === 'payments' && (
              <div className="admin-section-stack tab-pane-fade">
                <AdminPaymentSummaryStrip
                  upgradeRequests={upgradeRequests}
                  methodsCount={pmSummaryCounts}
                />

                <AdminPaymentMethodsCard
                  token={token}
                  onLogout={onLogout}
                  onNotice={setNotice}
                  refreshSignal={refreshSignal}
                  onMethodsLoaded={setPmSummaryCounts}
                />

                <AdminUpgradeRequestsCard
                  upgradeRequests={upgradeRequests}
                  token={token}
                  onLogout={onLogout}
                  onResolved={loadAdminData}
                  onNotice={setNotice}
                />
              </div>
            )}

            {adminTab === 'settings' && (
              <AdminAppSettingsTab
                token={token}
                appSettings={appSettings}
                consentsData={consentsData}
                onLogout={onLogout}
                onNotice={setNotice}
                onSettingsUpdated={async () => {
                  await loadAdminData()
                }}
              />
            )}
          </>
        )}
      </main>

      {/* Mobile Bottom Nav khusus Panel Admin */}
      <nav className="mobile-bottom-nav" aria-label="Navigasi Panel Admin">
        <div className="bottom-nav-inner">
          {tabs.map((t) => {
            const Icon = t.icon
            const isActive = adminTab === t.id
            return (
              <button
                key={t.id}
                type="button"
                className={`bottom-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => {
                  setAdminTab(t.id)
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                <div className="bottom-nav-icon-box">
                  <Icon size={20} className="bottom-nav-icon" />
                </div>
                <span className="bottom-nav-label">{t.label}</span>
              </button>
            )
          })}
        </div>
      </nav>

      {/* Modal Edit Perangkat & Pemilik */}
      {editingDevice && (
        <div className="modal-overlay pwa-guide-overlay" onClick={() => setEditingDevice(null)}>
          <div className="modal-dialog-modern pwa-guide-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="pwa-guide-head">
              <div>
                <h3 className="pwa-guide-title">Atur Perangkat</h3>
                <p className="pwa-guide-sub num-tabular">{editingDevice.id}</p>
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setEditingDevice(null)}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSaveDeviceEdit}>
              <div className="form-field-group">
                <label className="field-label" htmlFor="admin-edit-name">
                  Nama Perangkat
                </label>
                <input
                  id="admin-edit-name"
                  type="text"
                  className="modern-input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  required
                />
              </div>
              <div className="form-field-group">
                <label className="field-label" htmlFor="admin-edit-loc">
                  Ruangan / Lokasi
                </label>
                <input
                  id="admin-edit-loc"
                  type="text"
                  className="modern-input"
                  value={editLocation}
                  onChange={(e) => setEditLocation(e.target.value)}
                  placeholder="Contoh: Panel Utama"
                />
              </div>
              <div className="form-field-group">
                <label className="field-label" htmlFor="admin-edit-mcb">
                  Batas MCB (Watt)
                </label>
                <input
                  id="admin-edit-mcb"
                  type="number"
                  className="modern-input num-tabular"
                  min="100"
                  max="25000"
                  value={editMcb}
                  onChange={(e) => setEditMcb(e.target.value)}
                  required
                />
              </div>
              <div className="form-field-group">
                <label className="field-label" htmlFor="admin-edit-owner">
                  Pemilik Akun (Tenant)
                </label>
                <InAppSelect
                  id="admin-edit-owner"
                  value={editOwnerId}
                  onChange={setEditOwnerId}
                  ariaLabel="Pemilik Akun (Tenant)"
                  options={[
                    { value: '0', label: '— Stok / Belum Diklaim —' },
                    ...users.map((u) => ({
                      value: String(u.id),
                      label: `${u.name} (${u.email})`,
                    })),
                  ]}
                />
              </div>
              <label className="admin-checkbox-row">
                <input
                  type="checkbox"
                  checked={editPublicDemo}
                  onChange={(e) => setEditPublicDemo(e.target.checked)}
                />
                <span>Tampilkan untuk Guest (Tanpa Login)</span>
              </label>

              <div className="pwa-guide-footer" style={{ gap: 8, marginTop: 16 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setEditingDevice(null)}
                >
                  Batal
                </button>
                <button type="submit" className="btn btn-primary" disabled={savingEdit}>
                  <Save size={15} />
                  <span>{savingEdit ? 'Menyimpan...' : 'Simpan'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Buat / Edit Tenant User */}
      {userModalMode && (
        <div className="modal-overlay pwa-guide-overlay" onClick={() => setUserModalMode(null)}>
          <div className="modal-dialog-modern pwa-guide-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="pwa-guide-head">
              <div>
                <h3 className="pwa-guide-title">
                  {userModalMode === 'create' ? 'Buat Akun Pembeli' : 'Edit Akun Pembeli'}
                </h3>
                {editingUser && <p className="pwa-guide-sub">{editingUser.email}</p>}
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setUserModalMode(null)}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSaveUser}>
              <div className="form-field-group">
                <label className="field-label" htmlFor="admin-user-name">
                  Nama Lengkap
                </label>
                <input
                  id="admin-user-name"
                  type="text"
                  className="modern-input"
                  value={uName}
                  onChange={(e) => setUName(e.target.value)}
                  required
                />
              </div>
              {userModalMode === 'create' && (
                <div className="form-field-group">
                  <label className="field-label" htmlFor="admin-user-email">
                    Email
                  </label>
                  <input
                    id="admin-user-email"
                    type="email"
                    className="modern-input"
                    value={uEmail}
                    onChange={(e) => setUEmail(e.target.value)}
                    required
                  />
                </div>
              )}
              <div className="form-field-group">
                <label className="field-label" htmlFor="admin-user-pass">
                  {userModalMode === 'create'
                    ? 'Kata Sandi Awal'
                    : 'Kata Sandi Baru (kosongkan jika tetap)'}
                </label>
                <input
                  id="admin-user-pass"
                  type="password"
                  className="modern-input"
                  value={uPassword}
                  onChange={(e) => setUPassword(e.target.value)}
                  minLength={userModalMode === 'create' ? 6 : undefined}
                  required={userModalMode === 'create'}
                />
              </div>
              <div className="form-field-group">
                <label className="field-label" htmlFor="admin-user-plan">
                  Paket Langganan
                </label>
                <InAppSelect
                  id="admin-user-plan"
                  value={uPlanTier}
                  onChange={setUPlanTier}
                  options={[
                    { value: 'free', label: appSettings?.free_plan_name || 'VoltKu Gratis' },
                    { value: 'pro', label: appSettings?.pro_plan_name || 'VoltKu Pro' },
                  ]}
                />
              </div>

              {uPlanTier === 'pro' && (
                <div className="form-field-group">
                  <label className="field-label" htmlFor="admin-user-duration">
                    Masa Aktif Pro
                  </label>
                  <InAppSelect
                    id="admin-user-duration"
                    value={uPlanDuration}
                    onChange={setUPlanDuration}
                    options={[
                      ...(userModalMode === 'edit'
                        ? [{ value: 'keep', label: 'Pertahankan masa aktif saat ini' }]
                        : []),
                      { value: '30', label: '+ 30 Hari (1 Bulan)' },
                      { value: '90', label: '+ 90 Hari (3 Bulan)' },
                      { value: '365', label: '+ 365 Hari (1 Tahun)' },
                      { value: '0', label: 'Permanen (Tanpa Kedaluwarsa)' },
                    ]}
                  />
                </div>
              )}

              {userModalMode === 'edit' && (
                <label className="admin-checkbox-row">
                  <input
                    type="checkbox"
                    checked={uActive}
                    onChange={(e) => setUActive(e.target.checked)}
                  />
                  <span>Akun Aktif (boleh login ke dashboard)</span>
                </label>
              )}

              <div className="pwa-guide-footer" style={{ gap: 8, marginTop: 16 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setUserModalMode(null)}
                >
                  Batal
                </button>
                <button type="submit" className="btn btn-primary" disabled={savingUser}>
                  <Save size={15} />
                  <span>{savingUser ? 'Menyimpan...' : 'Simpan'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
