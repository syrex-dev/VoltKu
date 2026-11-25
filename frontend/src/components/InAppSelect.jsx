import React, { useState, useRef, useEffect } from 'react'
import { ChevronDown, Check } from 'lucide-react'

export function InAppSelect({
  id,
  value,
  onChange,
  options = [],
  placeholder = 'Pilih opsi...',
  ariaLabel,
  disabled = false,
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef(null)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    menuRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    const handleOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    const handleEsc = (e) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [open])

  const selectedOpt = options.find((opt) => String(opt.value) === String(value))

  return (
    <div className="inapp-select-wrap" ref={containerRef}>
      <button
        id={id}
        type="button"
        className={`modern-input inapp-select-trigger ${open ? 'is-open' : ''}`}
        onClick={() => {
          if (!disabled) setOpen((prev) => !prev)
        }}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        disabled={disabled}
      >
        <span className="inapp-select-val">
          {selectedOpt ? selectedOpt.label : placeholder}
        </span>
        <ChevronDown
          size={16}
          className={`inapp-select-arrow ${open ? 'rotated' : ''}`}
        />
      </button>

      {open && (
        <div
          ref={menuRef}
          className="inapp-select-menu"
          role="listbox"
          aria-label={ariaLabel || placeholder}
        >
          {options.map((opt) => {
            const active = String(opt.value) === String(value)
            return (
              <button
                key={String(opt.value)}
                type="button"
                role="option"
                aria-selected={active}
                className={`inapp-select-option ${active ? 'active' : ''}`}
                onClick={() => {
                  onChange(String(opt.value))
                  setOpen(false)
                }}
              >
                <span className="inapp-select-option-text">{opt.label}</span>
                {active && <Check size={15} className="inapp-select-check" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
