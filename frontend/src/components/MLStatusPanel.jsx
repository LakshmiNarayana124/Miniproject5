import { useEffect, useState } from 'react'

import { mlEngine } from '../mlEngine'
import { SENSORS } from '../sensors'
import { t } from '../i18n'
import useLang from '../useLang'
import { classifyFaultForSensor, FAULT_SEVERITY_COLOR } from '../faultSignatures'

import './MLStatusPanel.css'


const API = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '')

const DEMO_TOKEN = 'demo-offline'


// ==================================================
// DATA SOURCE
// ==================================================

function getMlSource(operatingMode, token) {
  if (token === DEMO_TOKEN) {
    return 'offline-demo'
  }

  return operatingMode === 'simulation'
    ? 'simulation'
    : 'hardware'
}


// ==================================================
// MINIMAL SPARKLINE SVG
// ==================================================

function Sparkline({ data }) {
  if (!data || data.length < 2) {
    return (
      <span style={{ color: '#64748b', fontSize: '0.75rem' }}>
        —
      </span>
    )
  }

  const vals = data.map(d => d.f1_score)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 0.01

  const w = 80
  const h = 24

  const pts = vals.map((value, index) => {
    const x = (index / (vals.length - 1)) * w
    const y = h - ((value - min) / range) * h

    return `${x},${y}`
  }).join(' ')

  return (
    <svg
      width={w}
      height={h}
      style={{ display: 'block' }}
    >
      <polyline
        points={pts}
        fill="none"
        stroke="#4f8ef7"
        strokeWidth="1.5"
      />
    </svg>
  )
}


// ==================================================
// INTERNATIONALIZATION
// ==================================================

function tl(key, lang) {
  return t(`ml_${key}`, lang)
}


// ==================================================
// CONFIDENCE RING
// ==================================================

function ConfidenceRing({ value }) {
  const r = 18
  const circ = 2 * Math.PI * r
  const pct = Math.round(value * 100)
  const offset = circ - (pct / 100) * circ

  const color =
    pct >= 80
      ? '#22c55e'
      : pct >= 40
        ? '#f59e0b'
        : '#94a3b8'

  return (
    <svg
      width="44"
      height="44"
      viewBox="0 0 44 44"
      className="conf-ring"
    >
      <circle
        cx="22"
        cy="22"
        r={r}
        fill="none"
        stroke="var(--border)"
        strokeWidth="3"
      />

      <circle
        cx="22"
        cy="22"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{
          transform: 'rotate(-90deg)',
          transformOrigin: '22px 22px',
          transition: 'stroke-dashoffset 0.6s ease',
        }}
      />

      <text
        x="22"
        y="26"
        textAnchor="middle"
        fontSize="11"
        fontWeight="700"
        fill={color}
      >
        {pct}%
      </text>
    </svg>
  )
}


// ==================================================
// ANOMALY SCORE BAR
// ==================================================

function ScoreBar({ score }) {
  const color =
    score >= 72
      ? '#ef4444'
      : score >= 45
        ? '#f59e0b'
        : '#22c55e'

  return (
    <div className="ml-score-bar-wrap">
      <div
        className="ml-score-bar-fill"
        style={{
          width: `${score}%`,
          background: color,
          transition: 'width 0.5s ease',
        }}
      />

      <span
        className="ml-score-label"
        style={{ color }}
      >
        {Math.round(score)}
      </span>
    </div>
  )
}


// ==================================================
// ML STATUS PANEL
// ==================================================

export default function MLStatusPanel({
  sensorKey = null,
  operatingMode = 'iot',
}) {
  const lang = useLang()

  const token = sessionStorage.getItem('iw_token')

  const source = getMlSource(
    operatingMode,
    token
  )

  // Keep the snapshot tagged with its source.
  // This prevents displaying the previous mode's
  // readings during a mode transition.
  const [summarySnapshot, setSummarySnapshot] = useState(
    () => ({
      source,
      values: mlEngine.getSummary(source),
    })
  )

  const summary =
    summarySnapshot.source === source
      ? summarySnapshot.values
      : mlEngine.getSummary(source)

  // Backend model information is available only
  // for authenticated IoT / Hardware sessions.
  const [backendStatus, setBackendStatus] = useState(null)
  const [trendData, setTrendData] = useState([])


  // ==================================================
  // LOCAL ML ENGINE UPDATES
  // ==================================================

  useEffect(() => {
    const refreshSummary = () => {
      setSummarySnapshot({
        source,
        values: mlEngine.getSummary(source),
      })
    }

    const handleUpdate = event => {
      if (event.detail?.source !== source) {
        return
      }

      if (
        sensorKey &&
        event.detail?.sensorKey !== sensorKey
      ) {
        return
      }

      refreshSummary()
    }

    refreshSummary()

    window.addEventListener(
      'iw:ml:update',
      handleUpdate
    )

    const timer = setInterval(
      refreshSummary,
      2000
    )

    return () => {
      window.removeEventListener(
        'iw:ml:update',
        handleUpdate
      )

      clearInterval(timer)
    }
  }, [sensorKey, source])


  // ==================================================
  // BACKEND MODEL STATUS
  //
  // Only IoT / Hardware mode fetches backend model
  // information. Simulation and offline Demo remain
  // completely independent of backend ML status.
  // ==================================================

  useEffect(() => {
    if (
      source !== 'hardware' ||
      !token ||
      token === DEMO_TOKEN
    ) {
      setBackendStatus(null)
      setTrendData([])
      return
    }

    let cancelled = false
    let activeController = null

    const fetchStatus = async () => {
      if (cancelled) return

      const controller = new AbortController()
      activeController = controller

      const headers = {
        Authorization: `Bearer ${token}`,
      }

      try {
        const response = await fetch(
          `${API}/models/status`,
          {
            method: 'GET',
            cache: 'no-store',
            headers,
            signal: controller.signal,
          }
        )

        if (cancelled) return

        if (response.ok) {
          setBackendStatus(
            await response.json()
          )
        } else {
          setBackendStatus(null)
        }

        const trendResponse = await fetch(
          `${API}/models/trend/ensemble`,
          {
            method: 'GET',
            cache: 'no-store',
            headers,
            signal: controller.signal,
          }
        )

        if (cancelled) return

        if (trendResponse.ok) {
          const result = await trendResponse.json()

          setTrendData(
            Array.isArray(result.trend)
              ? result.trend
              : []
          )
        }

      } catch {
        if (!cancelled) {
          setBackendStatus(null)
          setTrendData([])
        }
      }
    }

    fetchStatus()

    const timer = setInterval(
      fetchStatus,
      30000
    )

    return () => {
      cancelled = true

      clearInterval(timer)

      if (activeController) {
        activeController.abort()
      }
    }
  }, [source, token])


  // ==================================================
  // DISPLAY DATA
  // ==================================================

  const keysToShow = sensorKey
    ? [sensorKey]
    : Object.keys(SENSORS)

  const allCold = keysToShow.every(
    key => (summary[key]?.readingCount || 0) === 0
  )

  const ensembleInfo = backendStatus?.ensemble || null

  return (
    <section className="ml-panel">

      <div className="ml-panel-header">

        <div>
          <h3 className="ml-panel-title">
            {tl('title', lang)}
          </h3>

          <p className="ml-panel-sub">
            {tl('subtitle', lang)}
          </p>
        </div>

        <span
          className="ml-live-dot"
          title={`${source} learning environment`}
        />

      </div>


      {/* Backend model information — IoT only */}

      {source === 'hardware' && ensembleInfo?.active && (
        <div className="ml-backend-info">

          <span>
            <strong>{tl('version', lang)}:</strong>
            {' '}
            {ensembleInfo.version}
          </span>

          {ensembleInfo.training_timestamp && (
            <span>
              <strong>{tl('recalib', lang)}:</strong>
              {' '}
              {ensembleInfo.training_timestamp.slice(0, 10)}
            </span>
          )}

          <span>
            <strong>{tl('trend', lang)}:</strong>
            {' '}
            <Sparkline data={trendData} />
          </span>

        </div>
      )}


      {/* Cold-start state */}

      {allCold ? (

        <p className="ml-cold">
          {tl('cold', lang)}
        </p>

      ) : (

        <div className="ml-cards-grid">

          {keysToShow.map(key => {

            const state = summary[key]
            const sensor = SENSORS[key]

            if (!state || !sensor) return null

            const confidence = readings > 0 ? (state.confidence ?? 0) : 0
            const score = readings > 0 ? (state.score ?? 0) : 0
            const readings = state.readingCount ?? 0

            const accuracy = readings >= 12 && state.accuracy != null
              ? `${Math.round(state.accuracy * 100)}%`
              : 'Calibrating…'

            const band = state.learnedNormal
              ? `${state.learnedNormal.min.toFixed(2)} – ${state.learnedNormal.max.toFixed(2)} ${sensor.unit}`
              : '—'

            const faultHint = classifyFaultForSensor(
              key,
              state.lastValue ?? null,
              state
            )

            return (
              <div
                key={key}
                className="ml-card"
              >

                <div className="ml-card-top">

                  <span className="ml-card-icon">
                    {sensor.icon}
                  </span>

                  <span className="ml-card-label">
                    {sensor.label}
                  </span>

                  <ConfidenceRing value={confidence} />

                </div>


                <div className="ml-metrics">

                  <div className="ml-metric">
                    <span className="ml-metric-label">
                      {tl('readings', lang)}
                    </span>

                    <span className="ml-metric-val">
                      {readings}
                    </span>
                  </div>


                  <div className="ml-metric">
                    <span className="ml-metric-label">
                      {tl('accuracy', lang)}
                    </span>

                    <span className="ml-metric-val">
                      {accuracy}
                    </span>
                  </div>


                  <div className="ml-metric ml-metric-full">
                    <span className="ml-metric-label">
                      {tl('score', lang)}
                    </span>

                    <ScoreBar score={score} />
                  </div>


                  <div className="ml-metric ml-metric-full">
                    <span className="ml-metric-label">
                      {tl('learned', lang)}
                    </span>

                    <span className="ml-metric-val ml-metric-band">
                      {readings >= 12
                        ? band
                        : tl('awaiting', lang)}
                    </span>
                  </div>

                  {faultHint && (
                    <div className="ml-metric ml-metric-full ml-fault-hint">
                      <span className="ml-metric-label">
                        Fault signature
                      </span>
                      <span
                        className="ml-fault-chip"
                        style={{
                          borderColor: `${FAULT_SEVERITY_COLOR[faultHint.severity]}60`,
                          background:  `${FAULT_SEVERITY_COLOR[faultHint.severity]}12`,
                          color:        FAULT_SEVERITY_COLOR[faultHint.severity],
                        }}
                        title={`${faultHint.description} (${faultHint.standard}) — ${faultHint.confidence}% match`}
                      >
                        {faultHint.label}
                        <span className="ml-fault-conf">
                          {faultHint.confidence}%
                        </span>
                      </span>
                    </div>
                  )}

                </div>

              </div>
            )
          })}

        </div>
      )}

    </section>
  )
}