import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import {
  LayoutDashboard,
  Users,
  Cpu,
  ShieldAlert,
  Sliders,
  ExternalLink,
  LogOut,
  Sun,
  Moon,
  X,
  Save,
  RefreshCw,
  CreditCard,
  Crown,
  MoreHorizontal,
  Check,
  BellRing,
  Trash2,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatTimeWIB } from '../utils/formatters'
import { emitSyncSignal, subscribeSyncSignal } from '../utils/liveSync'
import { BrandLogo } from './BrandLogo'
import { InAppSelect } from './InAppSelect'
import { AdminAppSettingsTab } from './AdminAppSettingsTab'
import { AdminUsersSection } from './AdminUsersSection'
import { AdminDevicesSection } from './AdminDevicesSection'
import { AdminUserModal } from './AdminUserModal'
import { AdminPlansDiscountsSection } from './AdminPlansDiscountsSection'
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
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false)
  const [overview, setOverview] = useState(null)
  const [users, setUsers] = useState([])
  const [devices, setDevices] = useState([])
  const [anomalies, setAnomalies] = useState([])
  const [appSettings, setAppSettings] = useState(null)
  const [consentsData, setConsentsData] = useState(null)
  const [upgradeRequests, setUpgradeRequests] = useState([])
  const [plans, setPlans] = useState([])
  const [discounts, setDiscounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState(null)

  // Filters
  const [anomDeviceFilter, setAnomDeviceFilter] = useState('')
  const [anomSeverityFilter, setAnomSeverityFilter] = useState('')
  const [deletingAnomId, setDeletingAnomId] = useState(null)
  const [confirmAnomId, setConfirmAnomId] = useState(null)
  const [confirmPurgeAnom, setConfirmPurgeAnom] = useState(false)
  const [purgingAnom, setPurgingAnom] = useState(false)

  // Device Edit Modal State
  const [editingDevice, setEditingDevice] = useState(null)
  const [editName, setEditName] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [editMcb, setEditMcb] = useState(2200)
  const [editOwnerId, setEditOwnerId] = useState('0')
  const [editPublicDemo, setEditPublicDemo] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)

  // User Create / Edit Modal State
  const [userModalMode, setUserModalMode] = useState(null) // 'create' | 'edit'
  const [editingUser, setEditingUser] = useState(null)

  const [togglingAccess, setTogglingAccess] = useState(false)
  const [pmSummaryCounts, setPmSummaryCounts] = useState(null)
  const [pmSyncKey, setPmSyncKey] = useState(0)
  const [syncStatus, setSyncStatus] = useState('live')
  const [liveToast, setLiveToast] = useState(null)

  const syncSnapshotRef = useRef(null)
  const loadInFlightRef = useRef(false)
  const toastTimerRef = useRef(null)

  const showAutoResponseToast = useCallback((toastPayload) => {
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current)
    setLiveToast(toastPayload)
    toastTimerRef.current = window.setTimeout(() => {
      setLiveToast(null)
    }, 9000)
  }, [])

  const loadAdminData = useCallback(
    async ({ silent = false } = {}) => {
      if (!token || loadInFlightRef.current) return
      loadInFlightRef.current = true
      if (!silent) {
        setSyncStatus('syncing')
      }
      try {
        const [ov, usrs, devs, anoms, appCfg, consents, upgReqs, admPlans, admDiscounts] =
          await Promise.all([
            apiRequest('/api/admin/overview', {}, token, onLogout),
            apiRequest('/api/admin/users', {}, token, onLogout),
            apiRequest('/api/admin/devices', {}, token, onLogout),
            apiRequest('/api/admin/anomalies?limit=100', {}, token, onLogout),
            apiRequest('/api/admin/app-settings', {}, token, onLogout).catch(() => null),
            apiRequest('/api/admin/consents?limit=100', {}, token, onLogout).catch(() => null),
            apiRequest('/api/admin/upgrade-requests?limit=100', {}, token, onLogout).catch(() => []),
            apiRequest('/api/admin/plans', {}, token, onLogout).catch(() => []),
            apiRequest('/api/admin/discounts', {}, token, onLogout).catch(() => []),
          ])
        setOverview(ov)
        setUsers(usrs || [])
        setDevices(devs || [])
        setAnomalies(anoms || [])
        if (appCfg) setAppSettings(appCfg)
        if (consents) setConsentsData(consents)
        setUpgradeRequests(Array.isArray(upgReqs) ? upgReqs : [])
        setPlans(Array.isArray(admPlans) ? admPlans : [])
        setDiscounts(Array.isArray(admDiscounts) ? admDiscounts : [])
        setSyncStatus('live')
      } catch (err) {
        if (!silent) {
          setNotice({ type: 'error', text: err.message || 'Gagal memuat data Panel Admin.' })
        }
        setSyncStatus('paused')
      } finally {
        loadInFlightRef.current = false
        setLoading(false)
      }
    },
    [token, onLogout]
  )

  const handleAdminMutated = useCallback(
    async ({ reload = true, scope = 'all' } = {}) => {
      emitSyncSignal(scope, { source: 'admin' })
      if (reload) {
        await loadAdminData({ silent: true })
        setPmSyncKey((k) => k + 1)
      }
    },
    [loadAdminData]
  )

  const checkAdminSyncState = useCallback(async () => {
    if (!token || loadInFlightRef.current) return
    try {
      const state = await apiRequest('/api/admin/sync-state', {}, token, onLogout)
      if (!state?.rev) return
      setSyncStatus('live')
      const prev = syncSnapshotRef.current
      syncSnapshotRef.current = state
      if (!prev) return
      if (state.rev !== prev.rev) {
        const prevVerId = prev.latest_verifying?.id ?? null
        const nextVer = state.latest_verifying
        const prevAwaitId = prev.latest_awaiting?.id ?? null
        const nextAwait = state.latest_awaiting

        if (
          nextVer &&
          (nextVer.id !== prevVerId || (state.counts?.verifying ?? 0) > (prev.counts?.verifying ?? 0))
        ) {
          showAutoResponseToast({
            id: `ver-${nextVer.id}-${Date.now()}`,
            kind: 'verifying',
            title: 'Bukti Pembayaran Baru Masuk',
            sub: `${nextVer.user_name} mengunggah bukti untuk ${nextVer.plan_name} (${nextVer.order_code || `#${nextVer.id}`}).`,
            targetTab: 'payments',
          })
        } else if (
          nextAwait &&
          (nextAwait.id !== prevAwaitId || (state.counts?.awaiting ?? 0) > (prev.counts?.awaiting ?? 0))
        ) {
          showAutoResponseToast({
            id: `await-${nextAwait.id}-${Date.now()}`,
            kind: 'awaiting',
            title: 'Tagihan Upgrade Baru Dibuat',
            sub: `${nextAwait.user_name} membuat order ${nextAwait.plan_name} (${nextAwait.order_code || `#${nextAwait.id}`}).`,
            targetTab: 'payments',
          })
        } else if (
          (state.counts?.new_feedback ?? 0) > (prev.counts?.new_feedback ?? 0)
        ) {
          showAutoResponseToast({
            id: `fb-${Date.now()}`,
            kind: 'awaiting',
            title: 'Masukan / Laporan Baru Masuk',
            sub: 'Pelanggan baru saja mengirim rating atau laporan kendala di aplikasi.',
            targetTab: 'settings',
          })
        }

        await loadAdminData({ silent: true })
        if (state.payment_methods_rev !== prev.payment_methods_rev) {
          setPmSyncKey((k) => k + 1)
        }
      }
    } catch {
      setSyncStatus('paused')
    }
  }, [token, onLogout, loadAdminData, showAutoResponseToast])

  useEffect(() => {
    loadAdminData()
    checkAdminSyncState()
  }, [loadAdminData, checkAdminSyncState, refreshSignal])

  useEffect(() => {
    if (!token) return undefined
    let intervalId = null

    const startSync = () => {
      if (intervalId) window.clearInterval(intervalId)
      checkAdminSyncState()
      intervalId = window.setInterval(checkAdminSyncState, 4000)
    }
    const stopSync = () => {
      if (intervalId) {
        window.clearInterval(intervalId)
        intervalId = null
      }
    }
    const handleVisibility = () => {
      if (document.visibilityState === 'hidden') stopSync()
      else startSync()
    }
    const handleFocus = () => checkAdminSyncState()

    if (document.visibilityState !== 'hidden') {
      startSync()
    }
    document.addEventListener('visibilitychange', handleVisibility)
    window.addEventListener('focus', handleFocus)
    const unsubscribeSync = subscribeSyncSignal((sig) => {
      if (sig?.scope === 'admin' || sig?.scope === 'all') {
        checkAdminSyncState()
      }
    })

    return () => {
      stopSync()
      document.removeEventListener('visibilitychange', handleVisibility)
      window.removeEventListener('focus', handleFocus)
      unsubscribeSync()
      if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current)
    }
  }, [token, checkAdminSyncState])

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
      emitSyncSignal('public', { source: 'admin-access' })
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
      await handleAdminMutated()
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
      setNotice({ type: 'success', text: `Perangkat ${devId} dihapus.` })
      await handleAdminMutated()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal menghapus perangkat.' })
    }
  }

  // User Actions
  const openCreateUser = () => {
    setUserModalMode('create')
    setEditingUser(null)
  }

  const openEditUser = (u) => {
    setUserModalMode('edit')
    setEditingUser(u)
  }

  const handleDeleteUser = async (uid) => {
    setNotice(null)
    try {
      await apiRequest(`/api/admin/users/${uid}`, { method: 'DELETE' }, token, onLogout)
      setNotice({ type: 'success', text: 'Akun pengguna dihapus dan unitnya dilepas ke stok.' })
      await handleAdminMutated()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal menghapus akun pengguna.' })
    }
  }

  const handleDeleteSingleAnomaly = async (anomalyId) => {
    setDeletingAnomId(anomalyId)
    setNotice(null)
    try {
      await apiRequest(`/api/admin/anomalies/${anomalyId}`, { method: 'DELETE' }, token, onLogout)
      setConfirmAnomId(null)
      setNotice({ type: 'success', text: 'Catatan anomali berhasil dihapus.' })
      await handleAdminMutated()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal menghapus catatan anomali.' })
    } finally {
      setDeletingAnomId(null)
    }
  }

  const handlePurgeFilteredAnomalies = async () => {
    setPurgingAnom(true)
    setNotice(null)
    try {
      const qs = new URLSearchParams()
      if (anomDeviceFilter) qs.set('device_id', anomDeviceFilter)
      if (anomSeverityFilter) qs.set('severity', anomSeverityFilter)
      const qStr = qs.toString()
      const res = await apiRequest(
        `/api/admin/anomalies${qStr ? `?${qStr}` : ''}`,
        { method: 'DELETE' },
        token,
        onLogout
      )
      setConfirmPurgeAnom(false)
      setNotice({
        type: 'success',
        text: `${res?.deleted ?? 0} catatan anomali dibersihkan sesuai filter.`,
      })
      await handleAdminMutated()
    } catch (err) {
      setNotice({ type: 'error', text: err.message || 'Gagal membersihkan log anomali.' })
    } finally {
      setPurgingAnom(false)
    }
  }

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
    { id: 'plans', label: 'Paket & Diskon', icon: Crown },
    { id: 'devices', label: 'Perangkat', icon: Cpu },
    { id: 'anomalies', label: 'Anomali', icon: ShieldAlert },
    { id: 'settings', label: 'Pengaturan', icon: Sliders },
  ]

  const hasAdminModal = Boolean(editingDevice || userModalMode)

  return (
    <div className={`app-layout admin-shell ${hasAdminModal ? 'has-modal-open' : ''}`}>
      <div className="app-header-wrap clean-header-bar admin-header-bar">
        <div className="container">
          <header className="app-header clean-header-inner admin-header-inner">
            <div className="header-main-row admin-topbar-row">
              <div className="admin-head-left">
                <button
                  type="button"
                  className="header-brand-btn"
                  onClick={() => {
                    setAdminTab('overview')
                    if (typeof window !== 'undefined' && typeof window.scrollTo === 'function') {
                      window.scrollTo({ top: 0, behavior: 'smooth' })
                    }
                  }}
                  aria-label="Kembali ke Ringkasan Admin"
                  title="Ringkasan Admin"
                >
                  <BrandLogo
                    theme={theme}
                    displayMode="logo_only"
                    appName={appSettings?.app_name || 'VoltKu'}
                    variant="compact"
                  />
                </button>
                <span className="admin-brand-divider" aria-hidden="true" />
                <span className="admin-title-badge">Admin</span>
              </div>

              <div className="header-actions admin-head-actions">
                <span
                  className={`admin-live-pill is-${syncStatus}`}
                  title="Sinkronisasi otomatis 2 arah dengan publik aktif"
                >
                  <span className="admin-live-dot" aria-hidden="true" />
                  <span>
                    {syncStatus === 'syncing'
                      ? 'Sync'
                      : syncStatus === 'paused'
                      ? 'Jeda'
                      : 'Live'}
                  </span>
                </span>
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
                <span className="admin-actions-sep" aria-hidden="true" />
                <button
                  type="button"
                  className="header-icon-btn"
                  onClick={() => loadAdminData({ silent: false })}
                  aria-label="Muat Ulang Data Admin"
                  title="Muat ulang data"
                >
                  <RefreshCw size={16} />
                </button>
                <button
                  type="button"
                  className="header-icon-btn"
                  onClick={onToggleTheme}
                  aria-label="Ganti Tema"
                  title={theme === 'dark' ? 'Mode Terang' : 'Mode Gelap'}
                >
                  {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
                </button>
                <button
                  type="button"
                  className="header-icon-btn admin-logout-btn"
                  onClick={onLogout}
                  aria-label="Keluar Admin"
                  title="Keluar Sesi Admin"
                >
                  <LogOut size={16} />
                </button>
              </div>
            </div>

            <nav className="admin-subnav-bar" aria-label="Menu Admin">
              {tabs.map((t) => {
                const Icon = t.icon
                const isActive = adminTab === t.id
                return (
                  <button
                    key={t.id}
                    type="button"
                    className={`admin-nav-tab ${isActive ? 'active' : ''}`}
                    aria-current={isActive ? 'page' : undefined}
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
          </header>
        </div>
      </div>

      <main className="container main-content-wrap has-bottom-nav">
        {liveToast && (
          <div className={`admin-live-toast is-${liveToast.kind}`} role="status">
            <span className="admin-live-toast-ico">
              <BellRing size={16} />
            </span>
            <div className="admin-live-toast-copy">
              <strong>{liveToast.title}</strong>
              <span>{liveToast.sub}</span>
            </div>
            <div className="admin-live-toast-actions">
              {liveToast.targetTab && adminTab !== liveToast.targetTab && (
                <button
                  type="button"
                  className="btn btn-primary btn-compact"
                  onClick={() => {
                    setAdminTab(liveToast.targetTab)
                    setMobileMoreOpen(false)
                    setLiveToast(null)
                  }}
                >
                  Tinjau
                </button>
              )}
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setLiveToast(null)}
                aria-label="Tutup pemberitahuan"
              >
                <X size={15} />
              </button>
            </div>
          </div>
        )}

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
                      <div className="admin-service-item">
                        <span>Email SMTP (Reset Sandi)</span>
                        <span className={`admin-pill ${overview.smtp_configured ? 'ok' : 'warn'}`}>
                          {overview.smtp_configured ? 'Siap' : 'Belum Diatur'}
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
                plans={plans}
                token={token}
                onLogout={onLogout}
                onNotice={setNotice}
                onReload={handleAdminMutated}
                onOpenCreateUser={openCreateUser}
                onOpenEditUser={openEditUser}
                onDeleteUser={handleDeleteUser}
              />
            )}

            {adminTab === 'devices' && (
              <AdminDevicesSection
                devices={devices}
                users={users}
                appName={appSettings?.app_name || 'VoltKu'}
                token={token}
                onLogout={onLogout}
                onNotice={setNotice}
                onReload={handleAdminMutated}
                onOpenAddDevice={onOpenAddDevice}
                onEditDevice={openEditDeviceModal}
                onDeleteDevice={handleDeleteDevice}
              />
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
                      { id: '', label: `Semua (${anomalies.length})` },
                      {
                        id: 'critical',
                        label: `Kritis (${anomalies.filter((a) => (a.severity || '').toLowerCase() === 'critical').length})`,
                      },
                      {
                        id: 'warning',
                        label: `Peringatan (${anomalies.filter((a) => (a.severity || '').toLowerCase() !== 'critical').length})`,
                      },
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

                  {filteredAnomalies.length > 0 && (
                    <div className="admin-inline-actions">
                      {confirmPurgeAnom ? (
                        <div className="admin-inline-confirm">
                          <button
                            type="button"
                            className="btn btn-danger-solid btn-compact"
                            disabled={purgingAnom}
                            onClick={handlePurgeFilteredAnomalies}
                          >
                            {purgingAnom ? 'Membersihkan...' : `Ya, Hapus (${filteredAnomalies.length})`}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-compact"
                            disabled={purgingAnom}
                            onClick={() => setConfirmPurgeAnom(false)}
                          >
                            Batal
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="btn btn-secondary btn-compact"
                          onClick={() => setConfirmPurgeAnom(true)}
                        >
                          <Trash2 size={13} />
                          <span>Bersihkan Filter</span>
                        </button>
                      )}
                    </div>
                  )}
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
                          <div className="anomaly-feed-actions">
                            {confirmAnomId === a.id ? (
                              <div className="admin-inline-confirm">
                                <button
                                  type="button"
                                  className="btn btn-danger-solid btn-compact"
                                  disabled={deletingAnomId === a.id}
                                  onClick={() => handleDeleteSingleAnomaly(a.id)}
                                >
                                  Hapus
                                </button>
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-compact"
                                  onClick={() => setConfirmAnomId(null)}
                                >
                                  Batal
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-secondary btn-compact"
                                aria-label={`Hapus anomali ${a.id}`}
                                onClick={() => setConfirmAnomId(a.id)}
                              >
                                <Trash2 size={13} />
                              </button>
                            )}
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
                  refreshSignal={refreshSignal + pmSyncKey}
                  onMethodsLoaded={setPmSummaryCounts}
                />

                <AdminUpgradeRequestsCard
                  upgradeRequests={upgradeRequests}
                  token={token}
                  onLogout={onLogout}
                  onResolved={handleAdminMutated}
                  onNotice={setNotice}
                />
              </div>
            )}

            {adminTab === 'plans' && (
              <AdminPlansDiscountsSection
                plans={plans}
                discounts={discounts}
                token={token}
                onLogout={onLogout}
                onReload={handleAdminMutated}
                onNotice={setNotice}
              />
            )}

            {adminTab === 'settings' && (
              <AdminAppSettingsTab
                token={token}
                appSettings={appSettings}
                consentsData={consentsData}
                plans={plans}
                users={users}
                commsRefreshKey={refreshSignal + pmSyncKey}
                onOpenPlansTab={() => setAdminTab('plans')}
                onLogout={onLogout}
                onNotice={setNotice}
                onSettingsUpdated={handleAdminMutated}
              />
            )}
          </>
        )}
      </main>

      {/* Mobile Bottom Nav khusus Panel Admin (5 kolom pas layar tanpa terpotong) */}
      {mobileMoreOpen && (
        <div
          className="admin-more-sheet-backdrop"
          onClick={() => setMobileMoreOpen(false)}
          role="presentation"
        >
          <div
            className="admin-more-sheet"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Menu Admin Lainnya"
          >
            <div className="admin-more-sheet-head">
              <span>Menu Lainnya</span>
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setMobileMoreOpen(false)}
                aria-label="Tutup menu"
              >
                <X size={16} />
              </button>
            </div>
            <div className="admin-more-sheet-list">
              {[
                { id: 'devices', label: 'Perangkat', sub: 'Kelola panel ESP32 & stok unit', icon: Cpu },
                { id: 'anomalies', label: 'Anomali', sub: 'Riwayat deteksi & peringatan daya', icon: ShieldAlert },
                { id: 'settings', label: 'Pengaturan', sub: 'Identitas app, legal & freemium', icon: Sliders },
              ].map((item) => {
                const Icon = item.icon
                const isActive = adminTab === item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={`admin-more-item ${isActive ? 'active' : ''}`}
                    onClick={() => {
                      setAdminTab(item.id)
                      setMobileMoreOpen(false)
                      window.scrollTo({ top: 0, behavior: 'smooth' })
                    }}
                  >
                    <span className="admin-more-item-ico">
                      <Icon size={17} />
                    </span>
                    <span className="admin-more-item-copy">
                      <strong>{item.label}</strong>
                      <span>{item.sub}</span>
                    </span>
                    {isActive && <Check size={16} className="brand-blue-text" />}
                  </button>
                )
              })}
              <a
                href="/"
                target="_blank"
                rel="noreferrer"
                className="admin-more-item"
                style={{ textDecoration: 'none' }}
                onClick={() => setMobileMoreOpen(false)}
              >
                <span className="admin-more-item-ico">
                  <ExternalLink size={17} />
                </span>
                <span className="admin-more-item-copy">
                  <strong>Buka Web User</strong>
                  <span>Lihat portal pelanggan di tab baru</span>
                </span>
              </a>
            </div>
          </div>
        </div>
      )}

      <nav className="mobile-bottom-nav" aria-label="Navigasi Panel Admin">
        <div className="bottom-nav-inner">
          {[
            { id: 'overview', label: 'Ringkasan', icon: LayoutDashboard },
            { id: 'users', label: 'Pengguna', icon: Users },
            { id: 'payments', label: 'Bayar', icon: CreditCard, badge: pendingUpgradesCount },
            { id: 'plans', label: 'Paket', icon: Crown },
          ].map((t) => {
            const Icon = t.icon
            const isActive = adminTab === t.id
            return (
              <button
                key={t.id}
                type="button"
                className={`bottom-nav-item ${isActive ? 'active' : ''}`}
                onClick={() => {
                  setMobileMoreOpen(false)
                  setAdminTab(t.id)
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
              >
                <div className="bottom-nav-icon-box">
                  <Icon size={20} className="bottom-nav-icon" />
                  {t.badge > 0 && (
                    <span className="bottom-nav-badge">{t.badge > 9 ? '9+' : t.badge}</span>
                  )}
                </div>
                <span className="bottom-nav-label">{t.label}</span>
              </button>
            )
          })}

          <button
            type="button"
            className={`bottom-nav-item ${
              mobileMoreOpen || ['devices', 'anomalies', 'settings'].includes(adminTab)
                ? 'active'
                : ''
            }`}
            aria-expanded={mobileMoreOpen}
            onClick={() => setMobileMoreOpen((v) => !v)}
          >
            <div className="bottom-nav-icon-box">
              <MoreHorizontal size={20} className="bottom-nav-icon" />
            </div>
            <span className="bottom-nav-label">Lainnya</span>
          </button>
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
                <div className="admin-mcb-presets" aria-label="Preset daya MCB PLN">
                  {[900, 1300, 2200, 3500, 5500].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      className={`admin-mcb-preset-btn num-tabular ${Number(editMcb) === preset ? 'active' : ''}`}
                      onClick={() => setEditMcb(preset)}
                    >
                      {preset} W
                    </button>
                  ))}
                </div>
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
      <AdminUserModal
        mode={userModalMode}
        user={editingUser ? users.find((x) => x.id === editingUser.id) || editingUser : null}
        devices={devices}
        plans={plans}
        appSettings={appSettings}
        token={token}
        onLogout={onLogout}
        onClose={() => setUserModalMode(null)}
        onSaved={handleAdminMutated}
        onNotice={setNotice}
      />
    </div>
  )
}
