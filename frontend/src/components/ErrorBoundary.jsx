import React from 'react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, errorMessage: '' }
  }

  static getDerivedStateFromError(error) {
    return {
      hasError: true,
      errorMessage: error?.message || 'Terjadi kesalahan saat menampilkan halaman.',
    }
  }

  componentDidCatch(error, info) {
    if (typeof console !== 'undefined' && typeof console.error === 'function') {
      console.error('VoltKu ErrorBoundary caught:', error, info)
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback({
          errorMessage: this.state.errorMessage,
          reset: () => {
            this.setState({ hasError: false, errorMessage: '' })
            this.props.onClose?.()
          },
        })
      }
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
            background: '#0f172a',
            color: '#f8fafc',
          }}
        >
          <div
            style={{
              maxWidth: 380,
              width: '100%',
              borderRadius: 16,
              padding: 20,
              background: '#1e293b',
              border: '1px solid #334155',
              textAlign: 'center',
            }}
          >
            <h3 style={{ margin: '0 0 8px', fontSize: 17 }}>Tampilan Gagal Dimuat</h3>
            <p style={{ margin: '0 0 16px', fontSize: 13, color: '#cbd5e1' }}>
              {this.state.errorMessage}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{
                padding: '10px 16px',
                borderRadius: 10,
                border: 0,
                background: '#2563eb',
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Muat Ulang Aplikasi
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

