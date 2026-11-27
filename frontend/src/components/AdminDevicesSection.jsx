import React, { useState, useMemo } from 'react'
import {
  Search,
  Plus,
  Cpu,
  Wifi,
  WifiOff,
  Copy,
  Eye,
  Pencil,
  Trash2,
  X,
  Activity,
  ShieldAlert,
  Globe,
  UserCheck,
  Package,
  Gauge,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { formatDateTimeWIB, formatNum, formatTimeWIB } from '../utils/formatters'

function getSignalInfo(rssi) {
  if (rssi == null || Number.isNaN(Number(rssi))) {
    return { label: 'Tidak ada data', tone: 'muted' }
  }
  const val = Number(rssi)
  if (val >= -65) return { label: `${val} dBm · Kuat`, tone: 'ok' }
  if (val >= -80) return { label: `${val} dBm · Cukup`, tone: 'warn' }
  return { label: `${val} dBm · Lemah`, tone: 'danger' }
}

function getMcbLoadInfo(watts, mcbWatt) {
  const cap = Number(mcbWatt) || 2200
  if (watts == null || Number.isNaN(Number(watts))) {
    return { pct: 0, tone: 'ok', hasData: false }
  }
  const pct = Math.min(100, Math.max(0, Math.round((Number(watts) / cap) * 100)))
  let tone = 'ok'
  if (pct >= 90) tone = 'danger'
  else if (pct >= 75) tone = 'warn'
  return { pct, tone, hasData: true }
}

function DeviceDetailModal({
  device,
  busyId,
  copiedId,
  onCopyId,
  onToggleDemo,
  onEdit,
  onClose,
}) {
  if (!device) return null
  const isOnline = device.status === 'online'
  const latest = device.latest || null
  const watts = latest?.p
  const volts = latest?.v
  const amps = latest?.i
  const pf = latest?.pf
  const freq = latest?.f
  const energy = latest?.e
  const rssiInfo = getSignalInfo(latest?.rssi)
  const loadInfo = getMcbLoadInfo(watts, device.mcb_watt)

  return (
    <div className="modal-overlay pwa-guide-overlay" onClick={onClose}>
      <div
        className="modal-dialog-modern pwa-guide-sheet plan-modal-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pwa-guide-head">
          <div className="admin-user-cell">
            <div className={`admin-dev-icon-box ${isOnline ? 'online' : 'offline'}`}>
              <Cpu size={18} />
            </div>
            <div>
              <h3 className="pwa-guide-title">{device.name || device.id}</h3>
              <div className="admin-user-email-row" style={{ marginTop: 2 }}>
                <span className="pwa-guide-sub num-tabular">{device.id}</span>
                <button
                  type="button"
                  className="admin-pm-copy-btn"
                  onClick={() => onCopyId(device.id)}
                  title="Salin ID Perangkat"
                >
                  <Copy size={11} />
                  <span>{copiedId === device.id ? 'Disalin' : 'Salin ID'}</span>
                </button>
              </div>
            </div>
          </div>
          <button type="button" className="btn-icon-close" onClick={onClose} aria-label="Tutup">
            <X size={18} />
          </button>
        </div>

        <div className="admin-user-detail-grid">
          <div className="admin-user-detail-item">
            <span>Status Perangkat</span>
            <strong className={isOnline ? 'brand-emerald-text' : ''}>
              {isOnline ? 'Online' : 'Offline'}
            </strong>
            <small className="num-tabular">
              {device.last_seen_at
                ? `Terakhir aktif: ${formatDateTimeWIB(device.last_seen_at)}`
                : 'Belum pernah mengirim data'}
            </small>
          </div>

          <div className="admin-user-detail-item">
            <span>Pemilik (Tenant)</span>
            <strong>{device.owner_name || 'Stok Belum Diklaim'}</strong>
            <small>{device.owner_email || 'Siap diklaim pelanggan atau ditetapkan admin'}</small>
          </div>

          <div className="admin-user-detail-item">
            <span>Ruangan &amp; Akses Guest</span>
            <strong>{device.location || 'Tanpa ruangan'}</strong>
            <small>
              {device.is_public_demo
                ? 'Ditampilkan di Mode Guest (Demo Publik)'
                : 'Khusus akun pemilik (Privat)'}
            </small>
          </div>

          <div className="admin-user-detail-item">
            <span>Statistik Database</span>
            <strong className="num-tabular">
              {Number(device.readings_count || 0).toLocaleString('id-ID')} pembacaan
            </strong>
            <small className="num-tabular">
              {device.anomalies_7d || 0} anomali dalam 7 hari terakhir
            </small>
          </div>
        </div>

        <div className="admin-modal-section" style={{ marginTop: 14 }}>
          <div className="admin-modal-sec-head">
            <Activity size={14} className="brand-blue-text" />
            <span>Telemetri Listrik Terakhir</span>
          </div>

          {!latest ? (
            <div className="pay-methods-empty">
              Unit ini belum memiliki catatan telemetri dari sensor ESP32.
            </div>
          ) : (
            <>
              <div className="admin-dev-telemetry-grid num-tabular">
                <div className="admin-dev-tel-cell">
                  <span>Daya Aktif</span>
                  <strong>{watts !== undefined ? `${formatNum(watts, 1)} W` : '—'}</strong>
                </div>
                <div className="admin-dev-tel-cell">
                  <span>Tegangan</span>
                  <strong>{volts !== undefined ? `${formatNum(volts, 1)} V` : '—'}</strong>
                </div>
                <div className="admin-dev-tel-cell">
                  <span>Arus Listrik</span>
                  <strong>{amps !== undefined ? `${formatNum(amps, 2)} A` : '—'}</strong>
                </div>
                <div className="admin-dev-tel-cell">
                  <span>Faktor Daya</span>
                  <strong>{pf !== undefined ? formatNum(pf, 2) : '—'}</strong>
                </div>
                <div className="admin-dev-tel-cell">
                  <span>Frekuensi</span>
                  <strong>{freq !== undefined ? `${formatNum(freq, 1)} Hz` : '—'}</strong>
                </div>
                <div className="admin-dev-tel-cell">
                  <span>Total Energi</span>
                  <strong>{energy !== undefined ? `${formatNum(energy, 2)} kWh` : '—'}</strong>
                </div>
              </div>

              <div className="admin-dev-mcb-detail">
                <div className="admin-dev-mcb-top num-tabular">
                  <span>
                    Beban MCB ({formatNum(watts ?? 0, 0)} / {device.mcb_watt} W)
                  </span>
                  <strong>{loadInfo.pct}%</strong>
                </div>
                <div className="admin-mcb-bar-track">
                  <div
                    className={`admin-mcb-bar-fill ${loadInfo.tone}`}
                    style={{ width: `${loadInfo.pct}%` }}
                  />
                </div>
                <div className="admin-dev-signal-note num-tabular">
                  Kualitas Wi-Fi sensor: <strong>{rssiInfo.label}</strong>
                </div>
              </div>
            </>
          )}
        </div>

        <div className="plan-cta-row" style={{ marginTop: 16 }}>
          <button
            type="button"
            className="btn btn-secondary btn-compact"
            disabled={busyId === device.id}
            onClick={async () => {
              await onToggleDemo(device)
              onClose()
            }}
          >
            <Globe size={14} />
            <span>{device.is_public_demo ? 'Matikan Mode Guest' : 'Jadikan Demo Guest'}</span>
          </button>
          <button
            type="button"
            className="btn btn-primary btn-compact"
            onClick={() => {
              onClose()
              onEdit(device)
            }}
          >
            <Pencil size={14} />
            <span>Atur Perangkat &amp; Pemilik</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export function AdminDevicesSection({
  devices = [],
  token,
  onLogout,
  onNotice,
  onReload,
  onOpenAddDevice,
  onEditDevice,
  onDeleteDevice,
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [confirmDeleteDevId, setConfirmDeleteDevId] = useState('')
  const [copiedId, setCopiedId] = useState('')
  const [busyId, setBusyId] = useState('')
  const [detailDevice, setDetailDevice] = useState(null)

  const summary = useMemo(() => {
    let online = 0
    let claimed = 0
    let demo = 0
    let totalWatts = 0
    let anomalies7d = 0

    for (const d of devices) {
      if (d.status === 'online') {
        online += 1
        if (d.latest?.p != null) {
          totalWatts += Number(d.latest.p) || 0
        }
      }
      if (d.owner_user_id != null) claimed += 1
      if (d.is_public_demo) demo += 1
      anomalies7d += Number(d.anomalies_7d || 0)
    }

    return {
      total: devices.length,
      online,
      offline: devices.length - online,
      claimed,
      unclaimed: devices.length - claimed,
      demo,
      totalWatts,
      anomalies7d,
    }
  }, [devices])

  const filteredDevices = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return devices.filter((d) => {
      if (statusFilter === 'online' && d.status !== 'online') return false
      if (statusFilter === 'offline' && d.status !== 'offline') return false
      if (statusFilter === 'claimed' && d.owner_user_id == null) return false
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

  const handleCopyDeviceId = async (devId) => {
    if (!devId) return
    try {
      await navigator.clipboard.writeText(devId)
      setCopiedId(devId)
      window.setTimeout(() => setCopiedId(''), 1500)
    } catch {
      // Abaikan jika clipboard diblokir
    }
  }

  const handleTogglePublicDemo = async (dev) => {
    setBusyId(dev.id)
    if (onNotice) onNotice(null)
    try {
      const nextVal = !dev.is_public_demo
      await apiRequest(
        `/api/admin/devices/${dev.id}`,
        { method: 'PATCH', body: { is_public_demo: nextVal } },
        token,
        onLogout
      )
      if (onNotice) {
        onNotice({
          type: 'success',
          text: nextVal
            ? `${dev.name || dev.id} kini tampil di Mode Guest (Demo Publik).`
            : `${dev.name || dev.id} dilepas dari Mode Guest.`,
        })
      }
      if (onReload) await onReload()
    } catch (err) {
      if (onNotice) {
        onNotice({ type: 'error', text: err.message || 'Gagal mengubah akses Demo Guest.' })
      }
    } finally {
      setBusyId('')
    }
  }

  return (
    <div className="admin-section-stack tab-pane-fade">
      {/* 1. Ringkasan KPI Perangkat */}
      <div className="admin-kpi-grid">
        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Total Perangkat</span>
          <strong className="admin-kpi-value num-tabular">{summary.total}</strong>
          <span className="admin-kpi-sub">
            {summary.claimed} terklaim · {summary.unclaimed} stok
          </span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Unit Online</span>
          <strong className="admin-kpi-value num-tabular brand-emerald-text">
            {summary.online}
          </strong>
          <span className="admin-kpi-sub">
            {summary.offline > 0
              ? `${summary.offline} unit sedang offline`
              : 'Semua unit terhubung'}
          </span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Total Beban Aktif</span>
          <strong className="admin-kpi-value num-tabular brand-blue-text">
            {formatNum(summary.totalWatts, 0)} W
          </strong>
          <span className="admin-kpi-sub">
            Dari {summary.online} sensor online saat ini
          </span>
        </div>

        <div className="clean-sheet admin-kpi-card">
          <span className="admin-kpi-label">Demo Guest &amp; Anomali</span>
          <strong
            className={`admin-kpi-value num-tabular ${summary.anomalies7d > 0 ? 'brand-amber-text' : ''}`}
          >
            {summary.demo} unit
          </strong>
          <span className="admin-kpi-sub">
            {summary.anomalies7d} anomali tercatat 7 hari terakhir
          </span>
        </div>
      </div>

      {/* 2. Toolbar Pencarian & Filter Pil */}
      <div className="clean-sheet admin-users-toolbar-box">
        <div className="admin-toolbar-row">
          <div className="admin-search-wrap">
            <Search size={16} className="admin-search-icon" />
            <input
              type="text"
              className="modern-input admin-search-input"
              placeholder="Cari ID perangkat, nama unit, ruangan, atau pemilik..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
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

        {(() => {
          const deviceFilters = [
            { id: 'all', label: `Semua (${summary.total})` },
            { id: 'online', label: `Online (${summary.online})` },
            ...(summary.offline > 0
              ? [{ id: 'offline', label: `Offline (${summary.offline})` }]
              : []),
            { id: 'claimed', label: `Terklaim (${summary.claimed})` },
            { id: 'unclaimed', label: `Stok (${summary.unclaimed})` },
            { id: 'demo', label: `Demo Guest (${summary.demo})` },
          ]
          return (
            <div
              className={`admin-pm-filter-tabs is-justified cols-${deviceFilters.length}`}
              style={{ marginTop: 10 }}
            >
              {deviceFilters.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`admin-filter-pill ${statusFilter === f.id ? 'active' : ''}`}
                  onClick={() => setStatusFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )
        })()}
      </div>

      {/* 3. Daftar Perangkat (Desktop & Mobile) */}
      {filteredDevices.length === 0 ? (
        <div className="clean-sheet admin-empty-box">
          Tidak ada perangkat yang cocok dengan filter atau pencarian saat ini.
        </div>
      ) : (
        <>
          <div className="clean-sheet admin-table-desktop">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Perangkat</th>
                  <th>Pemilik (Tenant)</th>
                  <th>Status &amp; Sinyal</th>
                  <th>Beban &amp; MCB</th>
                  <th>Demo Guest</th>
                  <th style={{ textAlign: 'right' }}>Aksi</th>
                </tr>
              </thead>
              <tbody>
                {filteredDevices.map((d) => {
                  const online = d.status === 'online'
                  const watts = d.latest?.p
                  const volts = d.latest?.v
                  const rssiInfo = getSignalInfo(d.latest?.rssi)
                  const loadInfo = getMcbLoadInfo(watts, d.mcb_watt)
                  const anomCount = Number(d.anomalies_7d || 0)

                  return (
                    <tr key={d.id}>
                      <td>
                        <div className="admin-user-cell">
                          <div className={`admin-dev-icon-box ${online ? 'online' : 'offline'}`}>
                            <Cpu size={16} />
                          </div>
                          <div className="admin-user-ident">
                            <div className="admin-user-name-row">
                              <span className="admin-dev-name">{d.name || d.id}</span>
                              {d.is_public_demo && <span className="admin-demo-badge">Guest</span>}
                              {anomCount > 0 && (
                                <span
                                  className="admin-pill warn"
                                  title={`${anomCount} anomali dalam 7 hari terakhir`}
                                >
                                  <ShieldAlert size={11} />
                                  <span>{anomCount}</span>
                                </span>
                              )}
                            </div>
                            <div className="admin-user-email-row">
                              <span className="admin-dev-id num-tabular">
                                {d.id} · {d.location || 'Tanpa ruangan'}
                              </span>
                              <button
                                type="button"
                                className="admin-pm-copy-btn"
                                onClick={() => handleCopyDeviceId(d.id)}
                                title="Salin ID perangkat"
                              >
                                <Copy size={11} />
                                <span>{copiedId === d.id ? 'Disalin' : 'Salin'}</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      </td>

                      <td>
                        {d.owner_name ? (
                          <div>
                            <div className="admin-user-name-row">
                              <UserCheck size={13} className="brand-blue-text" />
                              <span className="admin-dev-name" style={{ fontSize: 13.5 }}>
                                {d.owner_name}
                              </span>
                            </div>
                            <div className="admin-dev-id">{d.owner_email}</div>
                          </div>
                        ) : (
                          <button
                            type="button"
                            className="admin-unit-chip"
                            onClick={() => onEditDevice(d)}
                            title="Tetapkan pemilik akun untuk perangkat stok ini"
                          >
                            <Package size={12} />
                            <span>Stok · Tetapkan</span>
                          </button>
                        )}
                      </td>

                      <td>
                        <span className={`admin-pill ${online ? 'ok' : 'muted'}`}>
                          {online ? <Wifi size={12} /> : <WifiOff size={12} />}
                          <span>{online ? 'Online' : 'Offline'}</span>
                        </span>
                        <div className="admin-dev-id num-tabular" style={{ marginTop: 4 }}>
                          {online
                            ? rssiInfo.label
                            : d.last_seen_at
                              ? `Terakhir ${formatTimeWIB(d.last_seen_at)}`
                              : 'Belum aktif'}
                        </div>
                      </td>

                      <td>
                        <div className="admin-dev-mcb-cell num-tabular">
                          <div className="admin-dev-mcb-values">
                            <strong>{watts !== undefined ? `${formatNum(watts, 0)} W` : '—'}</strong>
                            <span>
                              {volts !== undefined ? `${formatNum(volts, 0)} V · ` : ''}
                              MCB {d.mcb_watt} W
                            </span>
                          </div>
                          {loadInfo.hasData && (
                            <div className="admin-mcb-bar-track is-sm" title={`Beban ${loadInfo.pct}% dari MCB`}>
                              <div
                                className={`admin-mcb-bar-fill ${loadInfo.tone}`}
                                style={{ width: `${loadInfo.pct}%` }}
                              />
                            </div>
                          )}
                        </div>
                      </td>

                      <td>
                        <div className="admin-user-status-cell">
                          <button
                            type="button"
                            role="switch"
                            aria-checked={Boolean(d.is_public_demo)}
                            aria-label={`Mode Guest untuk ${d.name || d.id}`}
                            className={`admin-switch is-sm ${d.is_public_demo ? 'on' : ''}`}
                            disabled={busyId === d.id}
                            onClick={() => handleTogglePublicDemo(d)}
                          >
                            <span className="admin-switch-thumb" />
                          </button>
                          <span className={`admin-pill ${d.is_public_demo ? 'ok' : 'muted'}`}>
                            {d.is_public_demo ? 'Publik' : 'Privat'}
                          </span>
                        </div>
                      </td>

                      <td style={{ textAlign: 'right' }}>
                        <div className="admin-row-actions">
                          <button
                            type="button"
                            className="admin-icon-action"
                            title="Lihat Telemetri & Detail"
                            onClick={() => setDetailDevice(d)}
                          >
                            <Eye size={15} />
                          </button>
                          <button
                            type="button"
                            className="admin-icon-action"
                            title="Atur Pemilik & Metadata"
                            onClick={() => onEditDevice(d)}
                          >
                            <Pencil size={15} />
                          </button>
                          {confirmDeleteDevId === d.id ? (
                            <button
                              type="button"
                              className="btn btn-danger-solid btn-compact"
                              onClick={async () => {
                                await onDeleteDevice(d.id)
                                setConfirmDeleteDevId('')
                              }}
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
              const loadInfo = getMcbLoadInfo(watts, d.mcb_watt)
              return (
                <div key={d.id} className="clean-sheet admin-device-card-m">
                  <div className="admin-m-top">
                    <div className="admin-user-cell" style={{ minWidth: 0 }}>
                      <div className={`admin-dev-icon-box ${online ? 'online' : 'offline'}`}>
                        <Cpu size={16} />
                      </div>
                      <div className="admin-m-ident">
                        <div className="admin-dev-name">
                          {d.name || d.id}{' '}
                          {d.is_public_demo && <span className="admin-demo-badge">Guest</span>}
                        </div>
                        <div className="admin-dev-id num-tabular">
                          {d.id} · {d.owner_name ? `Milik ${d.owner_name}` : 'Stok Belum Diklaim'}
                        </div>
                      </div>
                    </div>
                    <span className={`admin-pill ${online ? 'ok' : 'muted'}`}>
                      {online ? <Wifi size={12} /> : <WifiOff size={12} />}
                      <span>{online ? 'Online' : 'Offline'}</span>
                    </span>
                  </div>

                  {loadInfo.hasData && (
                    <div className="admin-dev-mcb-cell num-tabular">
                      <div className="admin-dev-mcb-top" style={{ fontSize: 11.5 }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <Gauge size={12} /> Beban MCB
                        </span>
                        <span>
                          {loadInfo.pct}% dari {d.mcb_watt} W
                        </span>
                      </div>
                      <div className="admin-mcb-bar-track is-sm">
                        <div
                          className={`admin-mcb-bar-fill ${loadInfo.tone}`}
                          style={{ width: `${loadInfo.pct}%` }}
                        />
                      </div>
                    </div>
                  )}

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
                      onClick={() => setDetailDevice(d)}
                    >
                      <Eye size={14} />
                      <span>Detail</span>
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-compact"
                      onClick={() => onEditDevice(d)}
                    >
                      <Pencil size={14} />
                      <span>Atur</span>
                    </button>
                    {confirmDeleteDevId === d.id ? (
                      <button
                        type="button"
                        className="btn btn-danger-solid btn-compact"
                        style={{ gridColumn: 'span 2' }}
                        onClick={async () => {
                          await onDeleteDevice(d.id)
                          setConfirmDeleteDevId('')
                        }}
                      >
                        <span>Yakin Hapus Unit?</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-danger-ghost btn-compact"
                        style={{ gridColumn: 'span 2' }}
                        onClick={() => setConfirmDeleteDevId(d.id)}
                      >
                        <Trash2 size={14} />
                        <span>Hapus Perangkat</span>
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      <DeviceDetailModal
        device={detailDevice}
        busyId={busyId}
        copiedId={copiedId}
        onCopyId={handleCopyDeviceId}
        onToggleDemo={handleTogglePublicDemo}
        onEdit={onEditDevice}
        onClose={() => setDetailDevice(null)}
      />
    </div>
  )
}

