import React, { useState } from 'react'
import { ShieldCheck, FileText, ArrowLeft, Check } from 'lucide-react'

export function TermsAgreementModal({
  isOpen,
  isUpdate = false,
  readOnly = false,
  termsVersion = '2026-11-v1',
  initialDoc = null,
  onAgree,
  onDecline,
  onClose,
}) {
  const [activeDoc, setActiveDoc] = useState(initialDoc)

  if (!isOpen) return null

  const title = isUpdate
    ? 'Pembaruan Kebijakan Penting'
    : 'Syarat Penggunaan & Kebijakan Privasi'

  return (
    <div
      className="modal-overlay app-terms-overlay"
      onClick={readOnly && onClose ? onClose : undefined}
    >
      <div
        className="app-dialog-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        {!activeDoc ? (
          <>
            <div className="app-dialog-body">
              <div className="app-dialog-badge-icon">
                <ShieldCheck size={24} />
              </div>
              <h2 id="terms-modal-title" className="app-dialog-title">
                {title}
              </h2>
              <p className="app-dialog-copy">
                VoltKu menjaga keamanan dan privasi data kelistrikan Anda. Syarat Penggunaan
                dan Kebijakan Privasi menjelaskan bagaimana data sensor meter, preferensi
                tarif PLN, serta identitas akun (termasuk Login Google) dikelola dan
                dilindungi.
              </p>
              <p className="app-dialog-copy">
                Dengan mengetuk <strong>[Setuju]</strong>, Anda menyatakan telah membaca,
                memahami, dan menyetujui seluruh ketentuan versi <code>{termsVersion}</code>.
              </p>

              <div className="app-dialog-links-row">
                <button
                  type="button"
                  className="app-link-btn"
                  onClick={() => setActiveDoc('terms')}
                >
                  Syarat Penggunaan
                </button>
                <span className="app-link-sep">&amp;</span>
                <button
                  type="button"
                  className="app-link-btn"
                  onClick={() => setActiveDoc('privacy')}
                >
                  Kebijakan Privasi
                </button>
              </div>
            </div>

            {readOnly ? (
              <div className="app-dialog-single-footer">
                <button type="button" className="app-dialog-action-agree" onClick={onClose}>
                  <Check size={16} />
                  <span>Tutup</span>
                </button>
              </div>
            ) : (
              <div className="app-dialog-split-footer">
                <button type="button" className="app-dialog-action-exit" onClick={onDecline}>
                  Keluar
                </button>
                <button type="button" className="app-dialog-action-agree" onClick={onAgree}>
                  Setuju
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="app-doc-reader">
            <div className="app-doc-header">
              <button
                type="button"
                className="btn-icon-close"
                onClick={() => setActiveDoc(null)}
                aria-label="Kembali"
              >
                <ArrowLeft size={18} />
              </button>
              <h3>
                {activeDoc === 'terms' ? 'Syarat Penggunaan VoltKu' : 'Kebijakan Privasi VoltKu'}
              </h3>
              <span className="app-doc-version">{termsVersion}</span>
            </div>

            <div className="app-doc-scroll">
              {activeDoc === 'terms' ? (
                <>
                  <h4>1. Ruang Lingkup Layanan</h4>
                  <p>
                    VoltKu menyediakan pemantauan daya, tegangan, arus, histori pemakaian kWh,
                    perkiraan biaya listrik, serta peringatan anomali berbasis perangkat IoT
                    ESP32 &amp; PZEM-004T.
                  </p>
                  <h4>2. Akun &amp; Kepemilikan Perangkat</h4>
                  <p>
                    Pengguna bertanggung jawab menjaga kerahasiaan akun email/Google dan
                    perangkat yang diklaim pada akun masing-masing. Mode Guest hanya
                    menampilkan panel publik demo secara read-only.
                  </p>
                  <h4>3. Batasan Tanggung Jawab</h4>
                  <p>
                    Estimasi tagihan PLN bersifat informatif berdasarkan tarif yang diatur
                    pengguna dan kalibrasi sensor. VoltKu tidak memutus atau mengendalikan
                    beban listrik AC secara sepihak.
                  </p>
                </>
              ) : (
                <>
                  <h4>1. Data yang Dikumpulkan</h4>
                  <p>
                    Saat mendaftar dengan Email atau Akun Google, VoltKu menyimpan nama,
                    alamat email terverifikasi, foto profil opsional, dan daftar ID panel
                    listrik milik Anda di database MySQL server Anda.
                  </p>
                  <h4>2. Data Telemetri &amp; Wi-Fi Perangkat</h4>
                  <p>
                    Kredensial Wi-Fi rumah disimpan secara lokal di memori NVS perangkat ESP32
                    dan tidak dikirim ke server publik mana pun.
                  </p>
                  <h4>3. Kontrol &amp; Penghapusan</h4>
                  <p>
                    Anda dapat menghapus perangkat atau meminta pengelola menonaktifkan akun
                    kapan saja. Sesi token disimpan secara aman di perangkat Anda agar nyaman
                    digunakan di Web maupun aplikasi Android (.apk).
                  </p>
                </>
              )}
            </div>

            <div className="app-doc-footer">
              <button
                type="button"
                className="btn btn-primary"
                style={{ width: '100%' }}
                onClick={() => setActiveDoc(null)}
              >
                <FileText size={16} />
                <span>Mengerti &amp; Kembali</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

