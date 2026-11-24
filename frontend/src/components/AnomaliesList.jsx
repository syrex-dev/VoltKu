import React from 'react'
import { AlertCircle, ShieldAlert, CheckCircle2 } from 'lucide-react'
import { formatDateTimeWIB } from '../utils/formatters'

export function AnomaliesList({ anomalies }) {
  return (
    <section className="section-block">
      <div className="card">
        <div className="chart-header">
          <div className="chart-title-wrap">
            <ShieldAlert size={20} className="text-warning" />
            <h3 className="chart-title">Riwayat Peringatan & Anomali (7 Hari Terakhir)</h3>
          </div>
        </div>
        <div className="anomalies-container">
          {!anomalies || anomalies.length === 0 ? (
            <div className="anomalies-empty">
              <CheckCircle2 size={24} className="text-success" />
              <p>Tidak ada anomali atau peringatan terdeteksi dalam 7 hari terakhir.</p>
            </div>
          ) : (
            <div className="anomalies-list">
              {anomalies.map((item) => (
                <div key={item.id || `${item.ts}-${item.type}`} className="anomaly-item">
                  <div className="anomaly-left">
                    <span className="anomaly-message">{item.message || item.type}</span>
                    <span className="anomaly-time">{formatDateTimeWIB(item.ts)} WIB</span>
                  </div>
                  <span
                    className={`badge ${
                      item.severity === 'critical' ? 'badge-offline' : 'badge-warning'
                    }`}
                  >
                    {item.severity.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
