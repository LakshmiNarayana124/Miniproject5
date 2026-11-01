
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

import {
  statusColor,
  statusLabel,
  SENSORS,
} from '../sensors'

import AlertLog from './AlertLog'

// ==================================================
// ANOMALY DOT
// ==================================================

function AnomalyDot(props) {
  const { cx, cy, payload } = props

  if (!payload || payload.status === 'normal' || payload.status === 'nil') {
    return null
  }

  return (
    <circle
      cx={cx}
      cy={cy}
      r={5}
      fill={statusColor(payload.status)}
      stroke="#0d0f14"
      strokeWidth={1.5}
    />
  )
}

// ==================================================
// CUSTOM TOOLTIP
// ==================================================

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null

  const value = payload[0].value
  const status = payload[0].payload?.status
  const color = statusColor(status)

  return (
    <div className="chart-tooltip">
      <p className="tooltip-time">{label}</p>

      <p className="tooltip-val" style={{ color }}>
        {value === null || value === undefined
          ? '— No signal'
          : `${value} ${unit}`}
      </p>

      {status && status !== 'normal' && (
        <p className="tooltip-status" style={{ color }}>
          {statusLabel(status)}
        </p>
      )}
    </div>
  )
}

// ==================================================
// STARTUP / AWAITING PANEL
// ==================================================

function StartupPanel() {
  return (
    <div
      style={{
        marginTop: 18,
        padding: 18,
        borderRadius: 12,
        border: '1px solid #94a3b855',
        background: 'var(--card, #94a3b810)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          color: 'var(--muted)',
          fontWeight: 600,
        }}
      >
        <span>🔌</span>
        Awaiting IoT Signal
      </div>

      <p
        style={{
          marginTop: 9,
          color: 'var(--muted)',
          fontSize: 13,
          lineHeight: 1.6,
        }}
      >
        IntelliWatch is waiting for real-time sensor readings from
        the IoT hardware. Monitoring and analysis will begin when
        a valid sensor signal is received.
      </p>
    </div>
  )
}

// ==================================================
// IOT INTEGRATION PANEL
// ==================================================

function IoTPanel({ sensor }) {
  return (
    <section className="iot-panel">
      <div className="iot-header">
        <span className="iot-icon">🔌</span>

        <h3 className="iot-title">
          IoT Integration — {sensor.label}
        </h3>

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
          <span className="iot-val">
            {sensor.normal.min} – {sensor.normal.max} {sensor.unit}
          </span>
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
          <span className="iot-val iot-pending">
            WebSocket / MQTT — not connected
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">Status</span>
          <span className="iot-val iot-pending">
            ⏳ Awaiting IoT Signal
          </span>
        </div>
      </div>

      <div className="iot-note">
        Live sensor data has not been received yet.
        Simulated readings are disabled in this monitoring interface.
      </div>
    </section>
  )
}

// ==================================================
// MAIN SENSOR PAGE
// ==================================================

export default function SensorPage({
  sensorKey,
  data = [],
  latestValue = null,
  alerts = [],
  onClear,
  clearTime,
}) {
  const sensor = SENSORS[sensorKey]

  if (!sensor) {
    return (
      <main className="main">
        <p>Sensor not found.</p>
      </main>
    )
  }

  const latestPoint = data.at(-1)

  const hasLiveReading =
    latestValue !== null &&
    latestValue !== undefined &&
    Number.isFinite(Number(latestValue))

  const status = hasLiveReading
    ? latestPoint?.status || 'uncertain'
    : 'awaiting-iot'

  const color = statusColor(status)
  const gradientId = `sensor-page-gradient-${sensorKey}`

  return (
    <main className="main sensor-page">

      {/* Page title */}
      <div className="page-title-row">
        <div className="page-title-left">
          <span className="page-icon">{sensor.icon}</span>
          <h1 className="page-title">{sensor.label}</h1>
        </div>

        <span
          className="status-badge-lg"
          style={{
            color,
            borderColor: color,
            background: `${color}18`,
          }}
        >
          {statusLabel(status)}
        </span>
      </div>

      {/* Current reading */}
      <div className="live-value-row">
        {hasLiveReading ? (
          <>
            <span className="live-value" style={{ color }}>
              {latestValue}
            </span>
            <span className="live-unit">{sensor.unit}</span>
          </>
        ) : (
          <span className="live-value nil-value">—</span>
        )}

        <span className="live-label">Live Reading</span>
      </div>

      {/* Awaiting IoT signal */}
      {!hasLiveReading && <StartupPanel />}

      {/* Actual status explanations */}
      {status === 'warning' && (
        <p style={{ color: '#f0c040', marginTop: 8 }}>
          Reading is above the normal operating range.
          Investigation is recommended.
        </p>
      )}

      {status === 'critical' && (
        <p style={{ color: '#e05555', marginTop: 8 }}>
          Reading has exceeded the critical threshold.
          Immediate inspection is recommended.
        </p>
      )}

      {status === 'normal' && (
        <p style={{ color: '#2ecc71', marginTop: 8 }}>
          Sensor reading is currently within the configured
          normal operating range.
        </p>
      )}

      {status === 'uncertain' && (
        <p style={{ color: '#8b7cf6', marginTop: 8 }}>
          The sensor reading requires further verification.
        </p>
      )}

      {/* Statistics */}
      {hasLiveReading && data.length > 0 && (() => {
        const values = data
          .map(point => Number(point.value))
          .filter(Number.isFinite)

        if (values.length === 0) return null

        const min = Math.min(...values).toFixed(2)
        const max = Math.max(...values).toFixed(2)

        const avg = (
          values.reduce((sum, value) => sum + value, 0) /
          values.length
        ).toFixed(2)

        const anomalies = data.filter(point =>
          ['warning', 'critical'].includes(point.status)
        ).length

        return (
          <div className="stats-bar">
            <div className="stat-item">
              <span className="stat-label">Min</span>
              <span className="stat-value">
                {min} <small>{sensor.unit}</small>
              </span>
            </div>

            <div className="stat-item">
              <span className="stat-label">Avg</span>
              <span className="stat-value">
                {avg} <small>{sensor.unit}</small>
              </span>
            </div>

            <div className="stat-item">
              <span className="stat-label">Max</span>
              <span className="stat-value">
                {max} <small>{sensor.unit}</small>
              </span>
            </div>

            <div className="stat-item">
              <span className="stat-label">Anomalies</span>
              <span
                className="stat-value"
                style={{
                  color: anomalies > 0 ? '#e05555' : '#2ecc71',
                }}
              >
                {anomalies}
              </span>
            </div>
          </div>
        )
      })()}

      {/* Real-time chart */}
      <section className="chart-section">
        <h2 className="section-title">
          📈 {sensor.label} — Real-time Chart
        </h2>

        <div className="chart-legend-row">
          <span className="legend-item legend-warning">
            ── Warning threshold ({sensor.normal.max} {sensor.unit})
          </span>

          <span className="legend-item legend-critical">
            ── Critical threshold ({sensor.warning.max} {sensor.unit})
          </span>
        </div>

        {data.length === 0 ? (
          <div className="nil-chart nil-chart-lg">
            <span>🔌 Awaiting IoT Signal — Chart will appear when live data arrives.</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart
              data={data}
              margin={{ top: 10, right: 24, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient
                  id={gradientId}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="0%"
                    stopColor={sensor.color}
                    stopOpacity={0.38}
                  />

                  <stop
                    offset="65%"
                    stopColor={sensor.color}
                    stopOpacity={0.12}
                  />

                  <stop
                    offset="100%"
                    stopColor={sensor.color}
                    stopOpacity={0.01}
                  />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke="var(--grid)"
                vertical={false}
              />

              <XAxis
                dataKey="time"
                tick={{ fontSize: 11, fill: 'var(--muted)' }}
                interval="preserveStartEnd"
                axisLine={false}
                tickLine={false}
              />

              <YAxis
                tick={{ fontSize: 11, fill: 'var(--muted)' }}
                domain={['auto', 'auto']}
                width={45}
                axisLine={false}
                tickLine={false}
              />

              <Tooltip
                content={
                  <CustomTooltip unit={sensor.unit} />
                }
              />

              <ReferenceLine
                y={sensor.normal.max}
                label={{
                  value: 'Warn',
                  fill: '#f0c040',
                  fontSize: 10,
                }}
                stroke="#f0c040"
                strokeDasharray="5 4"
                strokeWidth={1.2}
              />

              <ReferenceLine
                y={sensor.warning.max}
                label={{
                  value: 'Crit',
                  fill: '#e05555',
                  fontSize: 10,
                }}
                stroke="#e05555"
                strokeDasharray="5 4"
                strokeWidth={1.2}
              />

              <Area
                type="monotone"
                dataKey="value"
                stroke={sensor.color}
                strokeWidth={2.5}
                fill={`url(#${gradientId})`}
                dot={<AnomalyDot />}
                activeDot={{
                  r: 5,
                  strokeWidth: 1.5,
                  stroke: '#ffffff',
                }}
                isAnimationActive={false}
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* Alert log */}
      <AlertLog
        alerts={alerts}
        onClear={onClear}
        clearTime={clearTime}
      />

      {/* IoT integration */}
      <IoTPanel sensor={sensor} />

    </main>
  )
}
