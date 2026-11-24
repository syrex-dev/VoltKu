import React from 'react'
import { ShieldAlert, ShieldCheck, AlertCircle } from 'lucide-react'
import { formatDateTimeWIB } from '../utils/formatters'

export function AnomaliesList({ anomalies }) {
  return (
    <section className="section-block">
      <div className="card">
        <div className="section-header">
          <div className="section-title">
            <ShieldAlert size={15} className="text-warning" /> Riwayat Deteksi Anomali & Peringatan (7 Hari)
          </div>
        </div>

        {!anomalies || anomalies.length === 0 ? (
          <div className="empty-healthy-card">
            <div className="healthy-icon-wrap">
              <ShieldCheck size={26} />
            </div>
            <div style={{ fontWeight: 600, color: '#f8fafc' }}>Kondisi Kelistrikan Normal</div>
            <div style={{ fontSize: 12 }}>Tidak ada deviasi daya, lonjakan, atau anomali dalam 7 hari terakhir.</div>
          </div>
        ) : (
          <div className="anomalies-list-modern">
            {anomalies.map((item) => {
              const isCrit = item.severity === 'critical'
              return (
                <div key={item.id || `${item.ts}-${item.type}`} className="anomaly-row">
                  <div className="anomaly-left-col">
                    <div className={`anomaly-icon-badge ${isCrit ? 'critical' : 'warning'}`}>
                      <AlertCircle size={18} />
                    </div>
                    <div className="anomaly-content">
                      <div className="anomaly-title">{item.message || item.type}</div>
                      <div className="anomaly-time-str num-tabular">
                        {formatDateTimeWIB(item.ts)} WIB
                      </div>
                    </div>
                  </div>
                  <span className={isCrit ? 'pill-critical' : 'pill-warning'}>
                    {item.severity.toUpperCase()}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}
