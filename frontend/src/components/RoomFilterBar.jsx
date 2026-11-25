import React from 'react'
import { Plus } from 'lucide-react'

export function RoomFilterBar({
  rooms,
  activeRoom,
  onSelectRoom,
  onOpenAddDevice,
}) {
  return (
    <div className="clean-room-bar-row">
      <div className="clean-room-tabs-scroll" role="tablist" aria-label="Ruangan">
        {rooms.map((room) => {
          const isActive = activeRoom === room
          return (
            <button
              key={room}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`clean-room-tab ${isActive ? 'active' : ''}`}
              onClick={() => onSelectRoom(room)}
            >
              <span>{room}</span>
              {isActive && <span className="room-tab-underline" />}
            </button>
          )
        })}
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
