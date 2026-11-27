import React, { useState, useEffect, useRef } from 'react'
import { Send, X } from 'lucide-react'
import { apiRequest } from '../api/client'
import mascotAvatarImg from '../assets/mascot/voltku-avatar.jpg'
import mascotAnalyzeImg from '../assets/mascot/voltku-analyze.jpg'

const QUICK_PROMPTS = [
  'Berapa biaya listrik hari ini?',
  'Jam berapa paling boros?',
  'Berapa proyeksi tagihan bulan ini?',
  'Apakah ada anomali minggu ini?',
]

const TOOL_LABELS = {
  list_devices: 'Daftar Panel',
  get_summary: 'Ringkasan',
  get_current: 'Daya Live',
  get_forecast: 'Proyeksi',
  get_hourly_profile: 'Profil Jam',
  compare_periods: 'Perbandingan',
  get_anomalies: 'Anomali',
}

export function AiChatWidget({ token, onUnauthorized, hidden = false }) {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (!isOpen || !token || historyLoaded) return
    apiRequest('/api/chat/history?limit=12', {}, token, onUnauthorized)
      .then((rows) => {
        if (Array.isArray(rows) && rows.length > 0) {
          const hist = []
          rows.forEach((r) => {
            hist.push({ id: `q-${r.id}`, role: 'user', text: r.question })
            hist.push({
              id: `a-${r.id}`,
              role: 'assistant',
              text: r.answer,
              tools: r.tools_used || [],
            })
          })
          setMessages(hist)
        }
        setHistoryLoaded(true)
      })
      .catch(() => setHistoryLoaded(true))
  }, [isOpen, token, historyLoaded, onUnauthorized])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, isOpen, sending])

  useEffect(() => {
    const handleOpenEvent = () => setIsOpen(true)
    window.addEventListener('voltku:open-ai-chat', handleOpenEvent)
    return () => window.removeEventListener('voltku:open-ai-chat', handleOpenEvent)
  }, [])

  if (!token || hidden) return null

  const sendQuestion = async (rawText) => {
    const q = (rawText ?? input).trim()
    if (!q || sending) return
    const tempId = Date.now()
    setMessages((prev) => [...prev, { id: `u-${tempId}`, role: 'user', text: q }])
    if (!rawText) setInput('')
    setSending(true)
    try {
      const res = await apiRequest(
        '/api/chat',
        { method: 'POST', body: { question: q } },
        token,
        onUnauthorized
      )
      setMessages((prev) => [
        ...prev,
        {
          id: `b-${tempId}`,
          role: 'assistant',
          text: res?.answer || 'Tidak ada jawaban.',
          tools: res?.tools_used || [],
        },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${tempId}`,
          role: 'assistant',
          text: err?.message || 'Gagal menghubungi asisten AI.',
          isError: true,
        },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {!isOpen && (
        <button
          type="button"
          className="ai-chat-fab"
          onClick={() => setIsOpen(true)}
          aria-label="Buka Asisten Energi VoltKu"
          title="Asisten Energi VoltKu"
        >
          <span className="ai-chat-fab-avatar" aria-hidden="true">
            <img src={mascotAvatarImg} alt="" />
          </span>
          <span>Tanya VoltKu</span>
        </button>
      )}

      {isOpen && (
        <div className="ai-chat-drawer" role="dialog" aria-label="Asisten Energi VoltKu">
          <div className="ai-chat-header">
            <div className="ai-chat-title">
              <span className="ai-chat-header-avatar" aria-hidden="true">
                <img src={mascotAvatarImg} alt="" />
              </span>
              <div>
                <strong>Asisten Energi VoltKu</strong>
                <span className="ai-chat-sub">Analisa pemakaian &amp; tagihan berbasis data riil</span>
              </div>
            </div>
            <button
              type="button"
              className="ai-chat-close"
              onClick={() => setIsOpen(false)}
              aria-label="Tutup Asisten AI"
            >
              <X size={18} />
            </button>
          </div>

          <div className="ai-chat-body" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="ai-chat-empty">
                <div className="ai-chat-empty-illus" aria-hidden="true">
                  <img src={mascotAnalyzeImg} alt="" />
                </div>
                <p>Tanyakan pemakaian kWh, jam paling boros, proyeksi tagihan, atau anomali panel Anda.</p>
                <div className="ai-chat-chips">
                  {QUICK_PROMPTS.map((qp) => (
                    <button
                      key={qp}
                      type="button"
                      className="ai-chat-chip"
                      onClick={() => sendQuestion(qp)}
                    >
                      {qp}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => (
              <div
                key={m.id}
                className={`ai-chat-bubble ${m.role === 'user' ? 'user' : 'bot'} ${m.isError ? 'err' : ''}`}
              >
                <div className="ai-chat-text">{m.text}</div>
                {Array.isArray(m.tools) && m.tools.length > 0 && (
                  <div className="ai-chat-tools">
                    {[...new Set(m.tools)].map((t) => TOOL_LABELS[t] || t).join(' · ')}
                  </div>
                )}
              </div>
            ))}

            {sending && (
              <div className="ai-chat-bubble bot is-typing" role="status" aria-label="AI sedang mengetik">
                <div className="ai-typing-wave" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <form
            className="ai-chat-form"
            onSubmit={(e) => {
              e.preventDefault()
              sendQuestion()
            }}
          >
            <input
              type="text"
              className="ai-chat-input"
              placeholder="Tulis pertanyaan listrik Anda..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              maxLength={500}
              disabled={sending}
            />
            <button
              type="submit"
              className="ai-chat-send"
              disabled={sending || !input.trim()}
              aria-label="Kirim pertanyaan"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
    </>
  )
}

