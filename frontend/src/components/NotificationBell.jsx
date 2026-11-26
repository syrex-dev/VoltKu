import React, { useState, useRef, useEffect } from 'react'
import { Bell, CheckCheck, AlertTriangle, CheckCircle2, Info } from 'lucide-react'

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
  const wrapRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const handleOutside = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleOutside)
    return () => document.removeEventListener('mousedown', handleOutside)
  }, [open])

  return (
    <div className="header-notif-wrap" ref={wrapRef}>
      <button
        type="button"
        className="header-icon-btn header-notif-btn"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="Notifikasi"
        title="Kotak Masuk Notifikasi"
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="header-notif-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <div className="header-notif-popover" role="dialog" aria-label="Notifikasi VoltKu">
          <div className="header-notif-head">
            <span>Notifikasi {unreadCount > 0 ? `(${unreadCount})` : ''}</span>
            {unreadCount > 0 && onMarkRead && (
              <button
                type="button"
                className="header-notif-mark-all"
                onClick={() => onMarkRead()}
              >
                <CheckCheck size={13} />
                <span>Tandai dibaca</span>
              </button>
            )}
          </div>

          <div className="header-notif-list">
            {notifications.length === 0 ? (
              <div className="header-notif-empty">Belum ada notifikasi masuk.</div>
            ) : (
              notifications.slice(0, 15).map((item) => {
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
                        <small>{formatRelativeTime(item.created_at)}</small>
                      </div>
                      <p>{item.body}</p>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
