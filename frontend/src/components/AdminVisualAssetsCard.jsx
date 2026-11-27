import React, { useState } from 'react'
import { Upload, RotateCcw, Trash2, EyeOff, Image as ImageIcon } from 'lucide-react'
import { compressImageToDataUrl } from '../utils/imageCompress'
import { VISUAL_ASSET_CATALOG, resolveVisualAsset } from '../utils/mascotAssets'

export function AdminVisualAssetsCard({
  visualAssets = {},
  busy = false,
  onUploadAsset,
  onToggleAsset,
  onDeleteAsset,
}) {
  const [activeSlotBusy, setActiveSlotBusy] = useState('')
  const [confirmSlot, setConfirmSlot] = useState('')
  const [localErr, setLocalErr] = useState('')

  const handleFilePicked = async (slot, e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setLocalErr('')
    setActiveSlotBusy(slot)
    try {
      const maxDim = slot === 'pro_banner' ? 1280 : 800
      const compressed = await compressImageToDataUrl(file, {
        maxDimension: maxDim,
        quality: 0.88,
      })
      await onUploadAsset?.(slot, compressed)
    } catch (err) {
      setLocalErr(err?.message || 'Gagal memproses atau mengunggah gambar.')
    } finally {
      setActiveSlotBusy('')
    }
  }

  return (
    <section className="clean-sheet admin-card-block">
      <div className="admin-card-head">
        <div>
          <h3>Kontrol Gambar &amp; Maskot Aplikasi</h3>
          <p className="admin-row-sub">
            Ganti dengan gambar baru, sembunyikan sementara, hapus, atau pulihkan ilustrasi maskot
            bawaan di seluruh halaman Web &amp; APK.
          </p>
        </div>
      </div>

      {localErr && (
        <p className="admin-field-err" style={{ marginBottom: 10 }}>
          {localErr}
        </p>
      )}

      <div className="admin-visual-grid">
        {VISUAL_ASSET_CATALOG.map((item) => {
          const meta = visualAssets?.[item.slot] || { enabled: true, is_custom: false, url: null }
          const isEnabled = meta.enabled !== false
          const isCustom = Boolean(meta.is_custom && meta.url)
          const previewSrc = resolveVisualAsset({ visual_assets: visualAssets }, item.slot)
          const slotBusy = busy || activeSlotBusy === item.slot

          return (
            <div
              key={item.slot}
              className={`admin-visual-card ${!isEnabled ? 'is-disabled' : ''}`}
            >
              <div className="admin-visual-top">
                <div className="admin-visual-preview">
                  {previewSrc ? (
                    <img src={previewSrc} alt={item.label} />
                  ) : (
                    <span className="admin-visual-hidden-ico" aria-hidden="true">
                      <EyeOff size={20} />
                    </span>
                  )}
                </div>

                <div className="admin-visual-copy">
                  <div className="admin-visual-badges">
                    <span className={`admin-pill ${!isEnabled ? 'muted' : isCustom ? 'ok' : ''}`}>
                      {!isEnabled ? 'Disembunyikan' : isCustom ? 'Kustom' : 'Bawaan'}
                    </span>
                  </div>
                  <div className="admin-visual-title">{item.label}</div>
                  <div className="admin-visual-usage">{item.usage}</div>
                </div>
              </div>

              <div className="admin-visual-actions">
                <label className={`btn btn-secondary btn-compact admin-visual-upload-btn ${slotBusy ? 'is-busy' : ''}`}>
                  <Upload size={13} />
                  <span>{activeSlotBusy === item.slot ? 'Mengunggah...' : 'Ganti Gambar'}</span>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    disabled={slotBusy}
                    hidden
                    onChange={(e) => handleFilePicked(item.slot, e)}
                  />
                </label>

                <button
                  type="button"
                  role="switch"
                  aria-checked={isEnabled}
                  aria-label={`${isEnabled ? 'Sembunyikan' : 'Tampilkan'} ${item.label}`}
                  className={`admin-switch ${isEnabled ? 'on' : ''}`}
                  disabled={slotBusy}
                  onClick={() => onToggleAsset?.(item.slot, !isEnabled)}
                >
                  <span className="admin-switch-thumb" />
                </button>
              </div>

              <div className="admin-visual-footer-btns">
                {(isCustom || !isEnabled) && (
                  <button
                    type="button"
                    className="btn btn-secondary btn-compact"
                    disabled={slotBusy}
                    onClick={() => {
                      setConfirmSlot('')
                      onDeleteAsset?.(item.slot, 'reset')
                    }}
                  >
                    <RotateCcw size={12} />
                    <span>Pulihkan Bawaan</span>
                  </button>
                )}

                {isEnabled &&
                  (confirmSlot === item.slot ? (
                    <div className="admin-inline-confirm">
                      <button
                        type="button"
                        className="btn btn-danger-solid btn-compact"
                        disabled={slotBusy}
                        onClick={() => {
                          setConfirmSlot('')
                          onDeleteAsset?.(item.slot, 'disable')
                        }}
                      >
                        Ya, Hapus
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-compact"
                        disabled={slotBusy}
                        onClick={() => setConfirmSlot('')}
                      >
                        Batal
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-secondary btn-compact"
                      disabled={slotBusy}
                      onClick={() => setConfirmSlot(item.slot)}
                    >
                      <Trash2 size={12} />
                      <span>Hapus</span>
                    </button>
                  ))}

                {!isCustom && isEnabled && (
                  <span className="admin-visual-default-hint">
                    <ImageIcon size={12} /> Pakai aset bawaan
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

