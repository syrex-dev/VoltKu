import React, { useState, useRef, useEffect } from 'react'
import { Radio, ChevronDown, Check, Cpu } from 'lucide-react'

export function CustomDeviceSelector({ devices, activeDeviceId, onSelectDevice }) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)

  const activeDevice = devices.find((d) => d.id === activeDeviceId)

  // Close when clicked outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen])

  const handleSelect = (id) => {
    onSelectDevice(id)
    setIsOpen(false)
  }

  return (
    <div className="custom-dropdown-container" ref={dropdownRef}>
      <button
        type="button"
        className={`custom-dropdown-trigger ${isOpen ? 'active' : ''}`}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="dropdown-trigger-label">
          <Radio size={13} className="trigger-icon" /> Perangkat:
        </span>
        <span className="dropdown-trigger-value">
          {activeDevice ? (activeDevice.name || activeDevice.id) : 'Pilih Perangkat'}
        </span>
        {activeDevice && (
          <span className="dropdown-trigger-mcb">{activeDevice.mcb_watt} W</span>
        )}
        <ChevronDown size={14} className={`dropdown-chevron ${isOpen ? 'rotate' : ''}`} />
      </button>

      {isOpen && (
        <div className="custom-dropdown-popover" role="listbox">
          <div className="dropdown-popover-header">
            <span>Daftar Sensor Perangkat</span>
            <span className="dropdown-badge-count">{devices.length}</span>
          </div>

          <div className="dropdown-popover-list">
            {devices.length === 0 ? (
              <div className="dropdown-item-empty">Tidak ada perangkat terdaftar</div>
            ) : (
              devices.map((device) => {
                const isSelected = device.id === activeDeviceId
                return (
                  <div
                    key={device.id}
                    className={`custom-dropdown-item ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleSelect(device.id)}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <div className="item-icon-box">
                      <Cpu size={16} />
                    </div>
                    <div className="item-info">
                      <span className="item-name">{device.name || device.id}</span>
                      <span className="item-id-sub">{device.id}</span>
                    </div>
                    <div className="item-end">
                      <span className="item-mcb-pill">{device.mcb_watt} W</span>
                      {isSelected && <Check size={16} className="item-check-icon" />}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
