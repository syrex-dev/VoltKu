import React, { useState, useRef, useEffect } from 'react'
import { Plus, ChevronDown, Check, LayoutGrid } from 'lucide-react'

export function RoomFilterBar({
  rooms = ['Semua'],
  activeRoom = 'Semua',
  onSelectRoom,
  onOpenAddDevice,
  devices = [],
}) {
  const [isOpen, setIsOpen] = useState(false)
  const wrapRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return undefined
    const handlePointerDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    const handleEscape = (e) => {
      if (e.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  const getRoomCount = (room) => {
    if (room === 'Semua') return devices.length
    if (room === 'Lainnya') {
      return devices.filter((d) => !d.location || !d.location.trim()).length
    }
    return devices.filter((d) => (d.location || '').trim() === room).length
  }

  const activeLabel = activeRoom === 'Semua' ? 'Semua Ruangan' : activeRoom

  return (
    <div className="clean-room-bar-row">
      <div className="room-dropdown-wrap" ref={wrapRef}>
        <button
          type="button"
          className={`room-dropdown-trigger ${isOpen ? 'open' : ''}`}
          onClick={() => setIsOpen((prev) => !prev)}
          aria-haspopup="listbox"
          aria-expanded={isOpen}
          aria-label="Pilih Ruangan"
        >
          <LayoutGrid size={15} className="room-dropdown-lead-ico" />
          <span className="room-dropdown-label">{activeLabel}</span>
          <span className="room-dropdown-count num-tabular">{getRoomCount(activeRoom)}</span>
          <span className="header-panel-caret" aria-hidden="true">
            <ChevronDown size={14} />
          </span>
        </button>

        {isOpen && (
          <div className="room-dropdown-popover" role="listbox" aria-label="Daftar Ruangan">
            <div className="header-panel-popover-head">
              <span>Ruangan</span>
              <span className="header-panel-count">{rooms.length}</span>
            </div>
            <div className="header-panel-list">
              {rooms.map((room) => {
                const isSelected = activeRoom === room
                const label = room === 'Semua' ? 'Semua Ruangan' : room
                const count = getRoomCount(room)
                return (
                  <button
                    key={room}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    className={`header-panel-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      onSelectRoom(room)
                      setIsOpen(false)
                    }}
                  >
                    <span className="header-panel-item-copy">
                      <span className="header-panel-item-title">{label}</span>
                    </span>
                    <span className="header-panel-item-right">
                      <span className="header-panel-item-watt num-tabular">{count} panel</span>
                      {isSelected && <Check size={15} className="header-panel-check" />}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {onOpenAddDevice && (
        <button
          type="button"
          data-tour-target="add-panel"
          className="content-add-btn"
          onClick={onOpenAddDevice}
          aria-label="Tambah Panel"
          title="Tambah Panel Listrik Baru"
        >
          <Plus size={15} strokeWidth={2.5} />
          <span>Tambah Panel</span>
        </button>
      )}
    </div>
  )
}
