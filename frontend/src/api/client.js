// API Client Helper
export async function apiRequest(endpoint, options = {}, token = '', onUnauthorized = null) {
  if (window.location.protocol === 'file:') {
    throw new Error('Dashboard harus dibuka melalui server web (bukan file://).')
  }

  const headers = { ...(options.headers || {}) }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  if (options.body && typeof options.body === 'object') {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }
  options.headers = headers

  try {
    const resp = await fetch(endpoint, options)
    if (resp.status === 401) {
      if (onUnauthorized) onUnauthorized()
      throw new Error('Sesi telah berakhir atau kata sandi salah.')
    }
    if (resp.status === 429) {
      const retryAfter = resp.headers.get('Retry-After') || '30'
      const errData = await resp.json().catch(() => ({}))
      const msg = errData?.error?.message || `Terlalu banyak percobaan. Coba lagi dalam ${retryAfter} detik.`
      throw new Error(msg)
    }
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}))
      const msg = errData?.error?.message || `Error ${resp.status}: Permintaan gagal.`
      throw new Error(msg)
    }
    return await resp.json()
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error('Gagal terhubung ke server backend. Pastikan server aktif di http://localhost:8000')
    }
    throw err
  }
}
