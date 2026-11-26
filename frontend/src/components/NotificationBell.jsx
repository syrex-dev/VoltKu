import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import {
  Bell,
  CheckCheck,
  AlertTriangle,
  CheckCircle2,
  Info,
  X,
} from 'lucide-react'

function formatRelativeTime(epochSec) {
  if (!epochSec) return ''
  const diff = Math.max(0, Math.floor(Date.now() / 1000) - Number(epochSec))
  if (diff < 60) return 'baru saja'
  if (diff < 3600) return `${Math.floor(diff / 60)}m lalu`
  if (diff < 86400) return `${Math.floor(diff / 3600)}j lalu`
  return new Date(Number(epochSec) * 1000).toLocaleDateString('id-ID', {
    day: '2-digit',
    month: 'short',
  })
}

export function NotificationBell({
  notifications = [],
  unreadCount = 0,
  onMarkRead,
  onSelectNotification,
}) {
  const [open, setOpen] = useState(false)
  const [filterMode, setFilterMode] = useState('all') // 'all' | 'unread'

  useEffect(() => {
    if (!open) return undefined
    const handleEsc = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handleEsc)
    return () => document.removeEventListener('keydown', handleEsc)
  }, [open])

  const visibleItems =
    filterMode === 'unread'
      ? notifications.filter((item) => !item.is_read)
      : notifications

  const dialogMarkup = open ? (
    <div
      className="modal-overlay pwa-guide-overlay profile-modal-overlay notif-modal-overlay"
      onClick={() => setOpen(false)}
    >
      <div
        className="modal-dialog-modern profile-modal-dialog notif-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Notifikasi VoltKu"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="profile-sticky-topbar">
          <div className="notif-modal-topbar">
            <div className="notif-modal-title-wrap">
              <h2 className="profile-ref-page-title">Notifikasi</h2>
              {unreadCount > 0 && (
                <span className="notif-unread-count-pill num-tabular">
                  {unreadCount} baru
                </span>
              )}
            </div>

            <div className="profile-topbar-right-pair">
              {unreadCount > 0 && onMarkRead && (
                <button
                  type="button"
                  className="header-notif-mark-all"
                  onClick={() => onMarkRead()}
                  title="Tandai semua sudah dibaca"
                >
                  <CheckCheck size={14} />
                  <span>Tandai dibaca</span>
                </button>
              )}
              <button
                type="button"
                className="profile-ref-icon-btn"
                onClick={() => setOpen(false)}
                aria-label="Tutup Notifikasi"
              >
                <X size={17} />
              </button>
            </div>
          </div>

          {notifications.length > 0 && (
            <div className="notif-filter-row" role="tablist" aria-label="Filter notifikasi">
              <button
                type="button"
                role="tab"
                aria-selected={filterMode === 'all'}
                className={`notif-filter-tab ${filterMode === 'all' ? 'active' : ''}`}
                onClick={() => setFilterMode('all')}
              >
                Semua ({notifications.length})
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={filterMode === 'unread'}
                className={`notif-filter-tab ${filterMode === 'unread' ? 'active' : ''}`}
                onClick={() => setFilterMode('unread')}
              >
                Belum Dibaca ({unreadCount})
              </button>
            </div>
          )}
        </div>

        <div className="profile-scroll-region">
          <div className="profile-ref-body notif-modal-body">
            {visibleItems.length === 0 ? (
              <div className="profile-ref-card-group notif-empty-card">
                <span className="notif-empty-icon-circle" aria-hidden="true">
                  <Bell size={24} />
                </span>
                <h3>
                  {filterMode === 'unread'
                    ? 'Semua Notifikasi Sudah Dibaca'
                    : 'Belum Ada Notifikasi Masuk'}
                </h3>
                <p>
                  {filterMode === 'unread'
                    ? 'Tidak ada pesan baru yang belum dibaca saat ini.'
                    : 'Peringatan beban listrik, status panel, dan pembaruan paket Anda akan muncul di sini.'}
                </p>
              </div>
            ) : (
              <div className="profile-ref-card-group">
                {visibleItems.slice(0, 30).map((item) => {
                  const sev = item.severity || 'info'
                  const Icon =
                    sev === 'critical' || sev === 'warning'
                      ? AlertTriangle
                      : sev === 'success'
                        ? CheckCircle2
                        : Info
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={`header-notif-item ${item.is_read ? 'read' : 'unread'}`}
                      onClick={() => {
                        if (!item.is_read && onMarkRead) onMarkRead(item.id)
                        setOpen(false)
                        if (onSelectNotification) onSelectNotification(item)
                      }}
                    >
                      <span className={`header-notif-ico is-${sev}`}>
                        <Icon size={15} />
                      </span>
                      <div className="header-notif-copy">
                        <div className="header-notif-title">
                          <span>{item.title}</span>
                          <small className="num-tabular">{formatRelativeTime(item.created_at)}</small>
                        </div>
                        <p>{item.body}</p>
                      </div>
                      {!item.is_read && <span className="notif-unread-dot" aria-hidden="true" />}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  ) : null

  return (
    <div className="header-notif-wrap">
      <button
        type="button"
        className="header-icon-btn header-notif-btn"
        onClick={() => {
          setFilterMode('all')
          setOpen((prev) => !prev)
        }}
        aria-label="Notifikasi"
        title="Kotak Masuk Notifikasi"
        data-testid="header-notif-btn"
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="header-notif-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
        )}
      </button>

      {dialogMarkup && typeof document !== 'undefined'
        ? createPortal(dialogMarkup, document.body)
        : dialogMarkup}
    </div>
  )
}
