import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend
} from 'recharts'
import { getStatus, statusColor, statusLabel, SENSORS } from '../sensors'
import AlertLog from './AlertLog'

// ─── Anomaly dot — colored marker on warning/critical points ─────────────────
function AnomalyDot(props) {
  const { cx, cy, payload } = props
  if (!payload || payload.status === 'normal' || payload.status === 'nil') return null
  const color = payload.status === 'critical' ? '#e05555' : '#f0c040'
  return <circle cx={cx} cy={cy} r={5} fill={color} stroke="#0d0f14" strokeWidth={1.5} />
}

// ─── Custom tooltip ───────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label, unit, color }) {
  if (!active || !payload?.length) return null
  const val    = payload[0].value
  const status = payload[0].payload?.status
  const c = status === 'critical' ? '#e05555' : status === 'warning' ? '#f0c040' : color
  return (
    <div className="chart-tooltip">
      <p className="tooltip-time">{label}</p>
      <p className="tooltip-val" style={{ color: c }}>
        {val === null ? '— No signal' : `${val} ${unit}`}
      </p>
      {status && status !== 'normal' && status !== 'nil' && (
        <p className="tooltip-status" style={{ color: c }}>⚠ {statusLabel(status)}</p>
      )}
    </div>
  )
}

// ─── Stats bar ────────────────────────────────────────────────────────────────
function StatsBar({ data, sensor }) {
  const values = data.map(d => d.value).filter(v => v !== null)
  if (values.length === 0) return null
  const min = Math.min(...values).toFixed(2)
  const max = Math.max(...values).toFixed(2)
  const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2)
  const anomalies = data.filter(d => d.status === 'warning' || d.status === 'critical').length
  return (
    <div className="stats-bar">
      <div className="stat-item">
        <span className="stat-label">Min</span>
        <span className="stat-value">{min} <small>{sensor.unit}</small></span>
      </div>
      <div className="stat-item">
        <span className="stat-label">Avg</span>
        <span className="stat-value">{avg} <small>{sensor.unit}</small></span>
      </div>
      <div className="stat-item">
        <span className="stat-label">Max</span>
        <span className="stat-value">{max} <small>{sensor.unit}</small></span>
      </div>
      <div className="stat-item">
        <span className="stat-label">Anomalies</span>
        <span className="stat-value" style={{ color: anomalies > 0 ? '#e05555' : '#2ecc71' }}>
          {anomalies}
        </span>
      </div>
    </div>
  )
}

// ─── IoT Integration placeholder ─────────────────────────────────────────────
function IoTPanel({ sensor }) {
  return (
    <section className="iot-panel">
      <div className="iot-header">
        <span className="iot-icon">🔌</span>
        <h3 className="iot-title">IoT Integration — {sensor.label}</h3>
        <span className="iot-badge">Pending</span>
      </div>
      <div className="iot-body">
        <div className="iot-row">
          <span className="iot-label">Sensor Type</span>
          <span className="iot-val">{sensor.label} Sensor</span>
        </div>
        <div className="iot-row">
          <span className="iot-label">Unit</span>
          <span className="iot-val">{sensor.unit}</span>
        </div>
        <div className="iot-row">
          <span className="iot-label">Normal Range</span>
          <span className="iot-val">{sensor.normal.min} – {sensor.normal.max} {sensor.unit}</span>
        </div>
        <div className="iot-row">
          <span className="iot-label">Warning Range</span>
          <span className="iot-val" style={{ color: '#f0c040' }}>
            {sensor.normal.max} – {sensor.warning.max} {sensor.unit}
          </span>
        </div>
        <div className="iot-row">
          <span className="iot-label">Critical Threshold</span>
          <span className="iot-val" style={{ color: '#e05555' }}>
            &gt; {sensor.warning.max} {sensor.unit}
          </span>
        </div>
        <div className="iot-row">
          <span className="iot-label">Data Feed</span>
          <span className="iot-val iot-pending">WebSocket / MQTT — not connected</span>
        </div>
        <div className="iot-row">
          <span className="iot-label">Status</span>
          <span className="iot-val iot-pending">⏳ Awaiting hardware integration</span>
        </div>
      </div>
      <div className="iot-note">
        Replace <code>generateValue()</code> in <code>sensors.js</code> with your live IoT feed to activate this sensor.
      </div>
    </section>
  )
}

// ─── Main SensorPage ──────────────────────────────────────────────────────────
export default function SensorPage({ sensorKey, data, latestValue, alerts, onClear, clearTime }) {
  const sensor = SENSORS[sensorKey]
  const status = getStatus(latestValue, sensor)
  const color  = statusColor(status)
  const isNil  = status === 'nil'

  return (
    <main className="main sensor-page">

      {/* ── Page title row ── */}
      <div className="page-title-row">
        <div className="page-title-left">
          <span className="page-icon">{sensor.icon}</span>
          <h1 className="page-title">{sensor.label}</h1>
        </div>
        <span className="status-badge-lg" style={{ color, borderColor: color, background: `${color}18` }}>
          {statusLabel(status)}
        </span>
      </div>

      {/* ── Current value ── */}
      <div className="live-value-row">
        {isNil ? (
          <span className="live-value nil-value">—</span>
        ) : (
          <>
            <span className="live-value" style={{ color }}>{latestValue}</span>
            <span className="live-unit">{sensor.unit}</span>
          </>
        )}
        <span className="live-label">Live Reading</span>
      </div>

      {/* ── Stats ── */}
      <StatsBar data={data} sensor={sensor} />

      {/* ── Full chart ── */}
      <section className="chart-section">
        <h2 className="section-title">📈 {sensor.label} — Real-time Chart</h2>
        <div className="chart-legend-row">
          <span className="legend-item legend-warning">── Warning threshold ({sensor.normal.max} {sensor.unit})</span>
          <span className="legend-item legend-critical">── Critical threshold ({sensor.warning.max} {sensor.unit})</span>
        </div>
        {isNil || data.length === 0 ? (
          <div className="nil-chart nil-chart-lg">
            <span>Awaiting IoT signal…</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={data} margin={{ top: 10, right: 24, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#252837" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: '#5a6080' }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11, fill: '#5a6080' }} domain={['auto', 'auto']} width={45} />
              <Tooltip content={<CustomTooltip unit={sensor.unit} color={sensor.color} />} />
              <ReferenceLine y={sensor.normal.max}  label={{ value: 'Warn', fill: '#f0c040', fontSize: 10 }} stroke="#f0c040" strokeDasharray="5 4" strokeWidth={1.2} />
              <ReferenceLine y={sensor.warning.max} label={{ value: 'Crit', fill: '#e05555', fontSize: 10 }} stroke="#e05555" strokeDasharray="5 4" strokeWidth={1.2} />
              <Line
                type="monotone"
                dataKey="value"
                stroke={sensor.color}
                strokeWidth={2.5}
                dot={<AnomalyDot />}
                activeDot={{ r: 5, strokeWidth: 1.5, stroke: '#0d0f14' }}
                isAnimationActive={false}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* ── Alert Log ── */}
      <AlertLog alerts={alerts} onClear={onClear} clearTime={clearTime} />

      {/* ── IoT Integration ── */}
      <IoTPanel sensor={sensor} />

    </main>
  )
}
