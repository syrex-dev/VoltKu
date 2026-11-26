import { useEffect, useState } from 'react'
import { buildApiUrl } from '../api/client'

/**
 * Mengambil gambar privat dari endpoint yang membutuhkan header Bearer JWT
 * dan mengubahnya menjadi Object URL lokal agar token tidak pernah bocor di URL.
 */
export function useAuthImage(endpoint, token, enabled = true) {
  const [imageUrl, setImageUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!enabled || !endpoint || !token) {
      setImageUrl('')
      setLoading(false)
      setError('')
      return undefined
    }

    let cancelled = false
    let objectUrl = ''
    const controller = new AbortController()

    setLoading(true)
    setError('')

    fetch(buildApiUrl(endpoint), {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async (resp) => {
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`)
        }
        return resp.blob()
      })
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setImageUrl(objectUrl)
      })
      .catch((err) => {
        if (cancelled || err?.name === 'AbortError') return
        setError('Foto bukti pembayaran belum tersedia.')
        setImageUrl('')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
      controller.abort()
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [endpoint, token, enabled])

  return { imageUrl, loading, error }
}

