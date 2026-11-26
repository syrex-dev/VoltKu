import React, { useRef, useState, useCallback, useEffect } from 'react'
import { triggerHaptic } from '../utils/userPrefs'

const NODE_COORDS = [
  { id: 0, x: 40, y: 40 },
  { id: 1, x: 120, y: 40 },
  { id: 2, x: 200, y: 40 },
  { id: 3, x: 40, y: 120 },
  { id: 4, x: 120, y: 120 },
  { id: 5, x: 200, y: 120 },
  { id: 6, x: 40, y: 200 },
  { id: 7, x: 120, y: 200 },
  { id: 8, x: 200, y: 200 },
]

// Titik antara yang otomatis ikut terhubung bila garis melewati titik tengah
const MIDPOINT_MAP = {
  '0-2': 1,
  '2-0': 1,
  '0-6': 3,
  '6-0': 3,
  '2-8': 5,
  '8-2': 5,
  '6-8': 7,
  '8-6': 7,
  '0-8': 4,
  '8-0': 4,
  '2-6': 4,
  '6-2': 4,
  '1-7': 4,
  '7-1': 4,
  '3-5': 4,
  '5-3': 4,
}

export function PatternLockGrid({
  minNodes = 4,
  status = 'idle', // 'idle' | 'error' | 'success'
  onComplete,
  disabled = false,
}) {
  const svgRef = useRef(null)
  const [selected, setSelected] = useState([])
  const [isDrawing, setIsDrawing] = useState(false)
  const [pointerPos, setPointerPos] = useState(null)

  useEffect(() => {
    if (status === 'error') {
      const id = window.setTimeout(() => {
        setSelected([])
        setPointerPos(null)
      }, 650)
      return () => window.clearTimeout(id)
    }
    if (status === 'success') {
      const id = window.setTimeout(() => {
        setSelected([])
        setPointerPos(null)
      }, 450)
      return () => window.clearTimeout(id)
    }
    return undefined
  }, [status])

  const clientToSvgPoint = useCallback((clientX, clientY) => {
    const svg = svgRef.current
    if (!svg) return null
    const rect = svg.getBoundingClientRect()
    if (!rect.width || !rect.height) return null
    return {
      x: ((clientX - rect.left) / rect.width) * 240,
      y: ((clientY - rect.top) / rect.height) * 240,
    }
  }, [])

  const findHitNode = useCallback((pt) => {
    if (!pt) return null
    for (const node of NODE_COORDS) {
      const dx = pt.x - node.x
      const dy = pt.y - node.y
      if (dx * dx + dy * dy <= 28 * 28) {
        return node.id
      }
    }
    return null
  }, [])

  const appendNode = useCallback((prevList, nextId) => {
    if (prevList.includes(nextId)) return prevList
    const nextList = [...prevList]
    if (nextList.length > 0) {
      const prevId = nextList[nextList.length - 1]
      const mid = MIDPOINT_MAP[`${prevId}-${nextId}`]
      if (mid !== undefined && !nextList.includes(mid)) {
        nextList.push(mid)
      }
    }
    nextList.push(nextId)
    triggerHaptic(8)
    return nextList
  }, [])

  const finishStroke = useCallback(
    (finalNodes) => {
      setIsDrawing(false)
      setPointerPos(null)
      if (!finalNodes || finalNodes.length === 0) return
      if (onComplete) {
        onComplete(finalNodes)
      }
      if (finalNodes.length < minNodes) {
        window.setTimeout(() => setSelected([]), 450)
      }
    },
    [minNodes, onComplete]
  )

  const handlePointerDown = (e) => {
    if (disabled) return
    e.preventDefault()
    if (e.currentTarget.setPointerCapture) {
      try {
        e.currentTarget.setPointerCapture(e.pointerId)
      } catch {
        // ignore
      }
    }
    const pt = clientToSvgPoint(e.clientX, e.clientY)
    const hitId = findHitNode(pt)
    if (hitId !== null) {
      triggerHaptic(10)
      setSelected([hitId])
      setIsDrawing(true)
      setPointerPos(pt)
    } else {
      setSelected([])
    }
  }

  const handlePointerMove = (e) => {
    if (!isDrawing || disabled) return
    const pt = clientToSvgPoint(e.clientX, e.clientY)
    if (!pt) return
    setPointerPos(pt)
    const hitId = findHitNode(pt)
    if (hitId !== null) {
      setSelected((prev) => appendNode(prev, hitId))
    }
  }

  const handlePointerUp = () => {
    if (!isDrawing) return
    finishStroke(selected)
  }

  const polylinePoints = selected
    .map((id) => {
      const n = NODE_COORDS[id]
      return `${n.x},${n.y}`
    })
    .join(' ')

  const lastNode = selected.length > 0 ? NODE_COORDS[selected[selected.length - 1]] : null
  const isError = status === 'error'
  const isSuccess = status === 'success'

  return (
    <div className={`pattern-grid-shell ${isError ? 'is-error' : ''} ${isSuccess ? 'is-success' : ''}`}>
      <svg
        ref={svgRef}
        viewBox="0 0 240 240"
        className="pattern-grid-svg"
        role="application"
        aria-label="Matriks kunci pola 3x3"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {selected.length >= 2 && (
          <polyline
            points={polylinePoints}
            fill="none"
            className="pattern-line-path"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {isDrawing && lastNode && pointerPos && (
          <line
            x1={lastNode.x}
            y1={lastNode.y}
            x2={pointerPos.x}
            y2={pointerPos.y}
            className="pattern-line-preview"
            strokeLinecap="round"
          />
        )}

        {NODE_COORDS.map((node) => {
          const isActive = selected.includes(node.id)
          const stepNum = selected.indexOf(node.id)
          return (
            <g key={node.id} className="pattern-node-group">
              {isActive && (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={22}
                  className="pattern-node-halo"
                />
              )}
              <circle
                cx={node.x}
                cy={node.y}
                r={18}
                className={`pattern-node-ring ${isActive ? 'is-active' : ''}`}
              />
              <circle
                cx={node.x}
                cy={node.y}
                r={isActive ? 7.5 : 5}
                className={`pattern-node-dot ${isActive ? 'is-active' : ''}`}
              />
              {isActive && stepNum >= 0 && (
                <text
                  x={node.x}
                  y={node.y + 30}
                  textAnchor="middle"
                  className="pattern-node-step"
                >
                  {stepNum + 1}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}


export function AppLockOverlay({
  isOpen,
  userName = 'Pengguna VoltKu',
  userEmail = '',
  onUnlock,
  onResetAndLogout,
  verifyPatternFn,
  appName = 'VoltKu',
  theme = 'light',
  BrandLogoComponent = null,
}) {
  const [status, setStatus] = useState('idle')
  const [message, setMessage] = useState('Gambar pola untuk membuka aplikasi')
  const [attempts, setAttempts] = useState(0)

  if (!isOpen) return null

  const handleComplete = async (nodes) => {
    if (nodes.length < 4) {
      setStatus('error')
      setMessage('Hubungkan minimal 4 titik')
      return
    }
    const ok = await verifyPatternFn(nodes)
    if (ok) {
      setStatus('success')
      setMessage('Pola terverifikasi')
      window.setTimeout(() => {
        setStatus('idle')
        setAttempts(0)
        onUnlock?.()
      }, 280)
    } else {
      const nextAttempts = attempts + 1
      setAttempts(nextAttempts)
      setStatus('error')
      setMessage(`Pola tidak cocok (percobaan ke-${nextAttempts})`)
    }
  }

  return (
    <div className="app-lock-overlay" role="dialog" aria-modal="true" aria-label="Layar Kunci Pola">
      <div className="app-lock-card">
        <div className="app-lock-brand">
          {BrandLogoComponent ? (
            <BrandLogoComponent theme={theme} displayMode="logo_only" appName={appName} variant="compact" />
          ) : (
            <span className="app-lock-brand-fallback">{appName}</span>
          )}
        </div>
        <h2 className="app-lock-title">Aplikasi Terkunci</h2>
        <p className="app-lock-user">
          {userName}
          {userEmail ? ` · ${userEmail}` : ''}
        </p>

        <div className={`app-lock-hint ${status === 'error' ? 'is-error' : status === 'success' ? 'is-success' : ''}`}>
          {message}
        </div>

        <PatternLockGrid status={status} onComplete={handleComplete} />

        {onResetAndLogout && (
          <button type="button" className="app-lock-forgot-btn" onClick={onResetAndLogout}>
            Lupa pola? Keluar &amp; reset kunci lokal
          </button>
        )}
      </div>
    </div>
  )
}
