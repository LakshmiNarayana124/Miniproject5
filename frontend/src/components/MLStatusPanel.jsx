
import { useEffect, useState } from 'react'
import { mlEngine } from '../mlEngine'
import { SENSORS } from '../sensors'
import { t } from '../i18n'
import useLang from '../useLang'
import './MLStatusPanel.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Minimal sparkline SVG (accuracy trend, Req 8.6)
function Sparkline({ data }) {
  if (!data || data.length < 2) return <span style={{ color: '#64748b', fontSize: '0.75rem' }}>—</span>
  const vals = data.map(d => d.f1_score)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 0.01
  const w = 80, h = 24
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * w
    const y = h - ((v - min) / range) * h
    return `${x},${y}`
  }).join(' ')
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke="#4f8ef7" strokeWidth="1.5" />
    </svg>
  )
}

// Delegate to global i18n (ml_title, ml_subtitle, etc.)
function tl(key, lang) { return t('ml_' + key, lang) }

function ConfidenceRing({ value }) {
  const r = 18, circ = 2 * Math.PI * r
  const pct = Math.round(value * 100)
  const offset = circ - (pct / 100) * circ
  const color = pct >= 80 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#94a3b8'
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" className="conf-ring">
      <circle cx="22" cy="22" r={r} fill="none" stroke="var(--border)" strokeWidth="3" />
      <circle cx="22" cy="22" r={r} fill="none" stroke={color} strokeWidth="3"
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        style={{ transform: 'rotate(-90deg)', transformOrigin: '22px 22px', transition: 'stroke-dashoffset 0.6s ease' }} />
      <text x="22" y="26" textAnchor="middle" fontSize="11" fontWeight="700" fill={color}>{pct}%</text>
    </svg>
  )
}

function ScoreBar({ score }) {
  const color = score >= 72 ? '#ef4444' : score >= 45 ? '#f59e0b' : '#22c55e'
  return (
    <div className="ml-score-bar-wrap">
      <div className="ml-score-bar-fill" style={{ width: `${score}%`, background: color, transition: 'width 0.5s ease' }} />
      <span className="ml-score-label" style={{ color }}>{Math.round(score)}</span>
    </div>
  )
}

export default function MLStatusPanel({ sensorKey = null }) {
  const lang = useLang()

  // Local (browser-side) mlEngine state
  const [summary, setSummary] = useState(() => mlEngine.getSummary())

  // Backend model status (Req 14.1)
  const [backendStatus, setBackendStatus] = useState(null)
  const [trendData, setTrendData] = useState([])

  useEffect(() => {
    const tick = () => setSummary(mlEngine.getSummary())
    const handle = (e) => { if (!sensorKey || e.detail?.sensorKey === sensorKey) tick() }
    window.addEventListener('iw:ml:update', handle)
    const timer = setInterval(tick, 2000)
    return () => { window.removeEventListener('iw:ml:update', handle); clearInterval(timer) }
  }, [sensorKey])

  // Fetch backend model status (Req 8.6, 14.1) every 30 s
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const token = sessionStorage.getItem('iw_token')
        if (!token || token === 'demo-offline') return
        const r = await fetch(`${API}/models/status`, { headers: { Authorization: `Bearer ${token}` } })
        if (r.ok) setBackendStatus(await r.json())
        const tr = await fetch(`${API}/models/trend/ensemble`, { headers: { Authorization: `Bearer ${token}` } })
        if (tr.ok) { const d = await tr.json(); setTrendData(d.trend || []) }
      } catch {}
    }
    fetchStatus()
    const t = setInterval(fetchStatus, 30000)
    return () => clearInterval(t)
  }, [])

  const keysToShow = sensorKey ? [sensorKey] : Object.keys(SENSORS)
  const allCold = keysToShow.every(k => (summary[k]?.readingCount || 0) === 0)
  const ensembleInfo = backendStatus?.ensemble || null

  return (
    <section className="ml-panel">
      <div className="ml-panel-header">
        <div>
          <h3 className="ml-panel-title">{tl('title', lang)}</h3>
          <p className="ml-panel-sub">{tl('subtitle', lang)}</p>
        </div>
        <span className="ml-live-dot" title="Engine active" />
      </div>

      {/* Backend model info (Req 8.6, 14.1) */}
      {ensembleInfo?.active && (
        <div className="ml-backend-info">
          <span><strong>{tl('version', lang)}:</strong> {ensembleInfo.version}</span>
          {ensembleInfo.training_timestamp && (
            <span><strong>{tl('recalib', lang)}:</strong> {ensembleInfo.training_timestamp.slice(0, 10)}</span>
          )}
          <span><strong>{tl('trend', lang)}:</strong> <Sparkline data={trendData} /></span>
        </div>
      )}

      {allCold ? (
        <p className="ml-cold">{tl('cold', lang)}</p>
      ) : (
        <div className="ml-cards-grid">
          {keysToShow.map(k => {
            const st = summary[k], sens = SENSORS[k]
            if (!st) return null
            const conf = st.confidence ?? 0, score = st.score ?? 0
            const reads = st.readingCount ?? 0
            const acc = st.accuracy ? `${Math.round(st.accuracy * 100)}%` : '—'
            const band = st.learnedNormal
              ? `${st.learnedNormal.min.toFixed(2)} – ${st.learnedNormal.max.toFixed(2)} ${sens.unit}` : '—'
            return (
              <div key={k} className="ml-card">
                <div className="ml-card-top">
                  <span className="ml-card-icon">{sens.icon}</span>
                  <span className="ml-card-label">{sens.label}</span>
                  <ConfidenceRing value={conf} />
                </div>
                <div className="ml-metrics">
                  <div className="ml-metric">
                    <span className="ml-metric-label">{tl('readings', lang)}</span>
                    <span className="ml-metric-val">{reads}</span>
                  </div>
                  <div className="ml-metric">
                    <span className="ml-metric-label">{tl('accuracy', lang)}</span>
                    <span className="ml-metric-val">{acc}</span>
                  </div>
                  <div className="ml-metric ml-metric-full">
                    <span className="ml-metric-label">{tl('score', lang)}</span>
                    <ScoreBar score={score} />
                  </div>
                  <div className="ml-metric ml-metric-full">
                    <span className="ml-metric-label">{tl('learned', lang)}</span>
                    <span className="ml-metric-val ml-metric-band">
                      {reads >= 12 ? band : tl('awaiting', lang)}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}