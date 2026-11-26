import React, { useState, useRef, useEffect } from 'react'
import {
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  EyeOff,
  LayoutGrid,
  List,
  X,
  Check,
} from 'lucide-react'

export function RoomFilterBar({
  rooms = ['Semua'],
  activeRoom = 'Semua',
  onSelectRoom,
  onOpenAddDevice,
  devices = [],
  viewMode = 'grid',
  onToggleViewMode,
  hideOffline = false,
  onToggleHideOffline,
  searchQuery = '',
  onSearchChange,
  searchOpen = false,
  onToggleSearch,
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuWrapRef = useRef(null)
  const searchInputRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return undefined
    const handlePointerDown = (e) => {
      if (menuWrapRef.current && !menuWrapRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    const handleEscape = (e) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [menuOpen])

  useEffect(() => {
    if (searchOpen && searchInputRef.current) {
      searchInputRef.current.focus()
    }
  }, [searchOpen])

  const getRoomCount = (room) => {
    if (room === 'Semua') return devices.length
    if (room === 'Lainnya') {
      return devices.filter((d) => !d.location || !d.location.trim()).length
    }
    return devices.filter((d) => (d.location || '').trim() === room).length
  }

  return (
    <div className="ewl-room-toolbar-wrap">
      <div className="ewl-room-toolbar">
        {/* Scrollable Room Tabs (eWeLink style with active blue underline) */}
        <div className="clean-room-tabs-scroll" role="tablist" aria-label="Filter Ruangan">
          {rooms.map((room) => {
            const isSelected = activeRoom === room
            const count = getRoomCount(room)
            return (
              <button
                key={room}
                type="button"
                role="tab"
                aria-selected={isSelected}
                className={`clean-room-tab ${isSelected ? 'active' : ''}`}
                onClick={() => onSelectRoom(room)}
              >
                <span>{room}</span>
                {count > 0 && <span className="room-tab-count num-tabular">{count}</span>}
                {isSelected && <span className="room-tab-underline" aria-hidden="true" />}
              </button>
            )
          })}
        </div>

        {/* Right Compact Action Icons + Add Button */}
        <div className="ewl-toolbar-actions">
          {onToggleSearch && (
            <button
              type="button"
              className={`ewl-tool-icon-btn ${searchOpen || searchQuery ? 'active' : ''}`}
              onClick={() => onToggleSearch()}
              aria-label="Cari Perangkat"
              title="Cari Perangkat"
            >
              <Search size={17} />
            </button>
          )}

          <div className="ewl-more-wrap" ref={menuWrapRef}>
            <button
              type="button"
              className={`ewl-tool-icon-btn ${menuOpen || hideOffline ? 'active' : ''}`}
              onClick={() => setMenuOpen((prev) => !prev)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Opsi Tampilan"
              title="Opsi Tampilan & Filter"
            >
              <MoreHorizontal size={18} />
            </button>

            {menuOpen && (
              <div className="ewl-more-popover" role="menu" aria-label="Menu Tampilan">
                {onToggleSearch && (
                  <button
                    type="button"
                    role="menuitem"
                    className="ewl-more-item"
                    onClick={() => {
                      setMenuOpen(false)
                      if (!searchOpen) onToggleSearch()
                    }}
                  >
                    <Search size={16} />
                    <span>Cari Perangkat</span>
                  </button>
                )}

                {onToggleHideOffline && (
                  <button
                    type="button"
                    role="menuitem"
                    className={`ewl-more-item ${hideOffline ? 'is-checked' : ''}`}
                    onClick={() => {
                      onToggleHideOffline()
                      setMenuOpen(false)
                    }}
                  >
                    {hideOffline ? <Eye size={16} /> : <EyeOff size={16} />}
                    <span>{hideOffline ? 'Tampilkan Offline' : 'Sembunyikan Offline'}</span>
                    {hideOffline && <Check size={14} className="ewl-more-check" />}
                  </button>
                )}

                {onToggleViewMode && (
                  <button
                    type="button"
                    role="menuitem"
                    className="ewl-more-item"
                    onClick={() => {
                      onToggleViewMode()
                      setMenuOpen(false)
                    }}
                  >
                    {viewMode === 'grid' ? <List size={16} /> : <LayoutGrid size={16} />}
                    <span>{viewMode === 'grid' ? 'Tampilan Daftar' : 'Tampilan Grid'}</span>
                  </button>
                )}

                {onOpenAddDevice && (
                  <button
                    type="button"
                    role="menuitem"
                    className="ewl-more-item is-accent"
                    onClick={() => {
                      setMenuOpen(false)
                      onOpenAddDevice()
                    }}
                  >
                    <Plus size={16} />
                    <span>Tambah Panel Baru</span>
                  </button>
                )}
              </div>
            )}
          </div>

          {onOpenAddDevice && (
            <button
              type="button"
              data-tour-target="add-panel"
              className="ewl-add-pill"
              onClick={onOpenAddDevice}
              aria-label="Tambah Panel"
              title="Tambah Panel Listrik Baru"
            >
              <Plus size={16} strokeWidth={2.5} />
              <span className="ewl-add-pill-text">Tambah Panel</span>
            </button>
          )}
        </div>
      </div>

      {/* Inline Search Strip */}
      {(searchOpen || searchQuery) && (
        <div className="ewl-search-bar">
          <Search size={15} className="ewl-search-ico" />
          <input
            ref={searchInputRef}
            type="search"
            className="ewl-search-input"
            placeholder="Cari nama panel, kode alat, atau ruangan..."
            value={searchQuery}
            onChange={(e) => onSearchChange?.(e.target.value)}
            aria-label="Cari panel listrik"
          />
          <button
            type="button"
            className="ewl-search-clear"
            aria-label="Tutup pencarian"
            onClick={() => {
              onSearchChange?.('')
              if (searchOpen && onToggleSearch) onToggleSearch(false)
            }}
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  )
}
