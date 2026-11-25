import React, { useState, useEffect } from 'react'
import { Smartphone, Share, PlusSquare, Laptop, MoreVertical, X, Check } from 'lucide-react'
import { usePwaInstall } from '../hooks/usePwaInstall'
import { isNativeApp } from '../api/client'

const DISMISS_SESSION_KEY = 'ml_pwa_banner_dismissed'

export function PwaInstallPrompt({
  hasBottomNav = false,
  appName = 'VoltKu',
}) {
  const { canInstall, isInstalled, platform, install } = usePwaInstall()
  const [showBanner, setShowBanner] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  const [guideTab, setGuideTab] = useState(platform)
  const [installedToast, setInstalledToast] = useState(false)

  useEffect(() => {
    if (isInstalled || isNativeApp()) {
      setShowBanner(false)
      setShowGuide(false)
      return
    }

    try {
      if (sessionStorage.getItem(DISMISS_SESSION_KEY) === 'true') return
    } catch {
      // Ignore storage read failure
    }

    const timer = setTimeout(() => {
      if (!isInstalled) {
        setShowBanner(true)
      }
    }, 900)

    return () => clearTimeout(timer)
  }, [isInstalled])

  const dismissBanner = () => {
    setShowBanner(false)
    try {
      sessionStorage.setItem(DISMISS_SESSION_KEY, 'true')
    } catch {
      // Ignore
    }
  }

  const closeGuide = () => {
    setShowGuide(false)
  }

  const handleInstallClick = async () => {
    if (isInstalled) {
      dismissBanner()
      return
    }

    if (canInstall) {
      const outcome = await install()
      if (outcome === 'accepted') {
        dismissBanner()
        setInstalledToast(true)
        setTimeout(() => setInstalledToast(false), 2600)
        return
      }
      return
    }

    // Browser tanpa prompt otomatis (mis. iOS Safari / HTTP LAN) -> tampilkan panduan singkat
    setShowBanner(false)
    setGuideTab(platform)
    setShowGuide(true)
  }

  return (
    <>
      {installedToast && (
        <div
          role="status"
          className={`pwa-installed-toast ${hasBottomNav ? 'has-bottom' : ''}`}
        >
          <span className="pwa-toast-check">
            <Check size={14} />
          </span>
          <span>{appName} berhasil dipasang di perangkat</span>
        </div>
      )}

      {showBanner && !isInstalled && !showGuide && (
        <aside
          aria-label={`Pasang ${appName}`}
          className={`pwa-banner-float ${hasBottomNav ? 'has-bottom' : ''}`}
        >
          <img
            src="/pwa-192.png"
            alt={appName}
            className="pwa-banner-icon"
          />
          <div className="pwa-banner-copy">
            <div className="pwa-banner-title">{appName}</div>
            <div className="pwa-banner-sub">Pasang ke layar utama</div>
          </div>
          <div className="pwa-banner-actions">
            <button
              type="button"
              className="pwa-banner-btn"
              onClick={handleInstallClick}
            >
              Pasang
            </button>
            <button
              type="button"
              className="pwa-banner-close"
              onClick={dismissBanner}
              aria-label="Tutup"
            >
              <X size={16} />
            </button>
          </div>
        </aside>
      )}

      {showGuide && !isInstalled && (
        <div className="modal-overlay pwa-guide-overlay" onClick={closeGuide}>
          <div
            className="modal-dialog-modern pwa-guide-sheet"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="pwa-guide-head">
              <div className="pwa-guide-brand">
                <img
                  src="/pwa-192.png"
                  alt="VoltKu"
                  className="pwa-guide-icon"
                />
                <div>
                  <h3 className="pwa-guide-title">Pasang di Layar Utama</h3>
                  <p className="pwa-guide-sub">Ikuti 3 langkah singkat berikut</p>
                </div>
              </div>
              <button
                type="button"
                className="btn-icon-close"
                onClick={closeGuide}
                aria-label="Tutup"
              >
                <X size={18} />
              </button>
            </div>

            <div className="pwa-guide-tabs">
              <button
                type="button"
                className={`pwa-guide-tab ${guideTab === 'android' ? 'active' : ''}`}
                onClick={() => setGuideTab('android')}
              >
                <Smartphone size={14} />
                <span>Android</span>
              </button>
              <button
                type="button"
                className={`pwa-guide-tab ${guideTab === 'ios' ? 'active' : ''}`}
                onClick={() => setGuideTab('ios')}
              >
                <Share size={14} />
                <span>iPhone</span>
              </button>
              <button
                type="button"
                className={`pwa-guide-tab ${guideTab === 'desktop' ? 'active' : ''}`}
                onClick={() => setGuideTab('desktop')}
              >
                <Laptop size={14} />
                <span>Desktop</span>
              </button>
            </div>

            {guideTab === 'android' && (
              <ol className="pwa-guide-steps">
                <li>
                  Buka menu titik tiga (<MoreVertical size={14} style={{ display: 'inline', verticalAlign: 'middle' }} />) di pojok kanan atas Chrome.
                </li>
                <li>
                  Pilih <strong>Tambahkan ke layar utama</strong> atau <strong>Instal aplikasi</strong>.
                </li>
                <li>
                  Ketuk <strong>Instal</strong> untuk menyelesaikan.
                </li>
              </ol>
            )}

            {guideTab === 'ios' && (
              <ol className="pwa-guide-steps">
                <li>
                  Ketuk ikon <strong>Bagikan</strong> (<Share size={14} style={{ display: 'inline', verticalAlign: 'middle' }} />) di bilah bawah Safari.
                </li>
                <li>
                  Pilih <strong>Tambah ke Layar Utama</strong> (<PlusSquare size={14} style={{ display: 'inline', verticalAlign: 'middle' }} />).
                </li>
                <li>
                  Ketuk <strong>Tambah</strong> di pojok kanan atas.
                </li>
              </ol>
            )}

            {guideTab === 'desktop' && (
              <ol className="pwa-guide-steps">
                <li>
                  Klik ikon <strong>Instal</strong> di ujung kanan kolom alamat Chrome atau Edge.
                </li>
                <li>
                  Atau buka menu browser &rarr; <strong>Simpan dan bagikan</strong> &rarr; <strong>Instal VoltKu</strong>.
                </li>
                <li>
                  Klik <strong>Instal</strong> agar terbuka sebagai aplikasi terpisah.
                </li>
              </ol>
            )}

            <div className="pwa-guide-footer">
              <button type="button" className="btn btn-primary" onClick={closeGuide}>
                Mengerti
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
