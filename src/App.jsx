
import { useState, useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'
import {
  SENSORS, MAX_POINTS, CHART_INTERVAL_MS, LOG_INTERVAL_MS,
  generateValue, getStatus, statusColor, statusLabel,
  formatTime, formatDateTime
} from './sensors'
import Navbar from './components/Navbar'
import SensorPage from './components/SensorPage'
import './App.css'

// ─── Custom Dot ───────────────────────────────────────────────────────────────
function AnomalyDot(props) {
  const { cx, cy, payload } = props

  if (!payload || payload.status === 'normal' || payload.status === 'nil') {
    return null
  }

  const color = payload.status === 'critical' ? '#e05555' : '#f0c040'

  return (
    <circle
      cx={cx}
      cy={cy}
      r={5}
      fill={color}
      stroke="#0d0f14"
      strokeWidth={1.5}
    />
  )
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────
function CustomTooltip({ active, payload, label, unit, color }) {
  if (!active || !payload?.length) return null

  const val = payload[0].value
  const status = payload[0].payload?.status
  const c =
    status === 'critical'
      ? '#e05555'
      : status === 'warning'
        ? '#f0c040'
        : color

  return (
    <div className="chart-tooltip">
      <p className="tooltip-time">{label}</p>

      <p className="tooltip-val" style={{ color: c }}>
        {val === null ? '— No signal' : `${val} ${unit}`}
      </p>

      {status && status !== 'normal' && status !== 'nil' && (
        <p className="tooltip-status" style={{ color: c }}>
          ⚠ {statusLabel(status)}
        </p>
      )}
    </div>
  )
}

// ─── Alert Entry ──────────────────────────────────────────────────────────────
function AlertEntry({ alert }) {
  const statusColors = {
    normal: '#2ecc71',
    warning: '#f0c040',
    critical: '#e05555',
    nil: '#4a5070',
  }

  const color = statusColors[alert.status] || '#4a5070'

  return (
    <div className={`alert-entry alert-${alert.status}`}>
      <span className="alert-dot" />

      <div className="alert-body">
        <span className="alert-sensor">{alert.sensor}</span>
        <span className="alert-msg">{alert.message}</span>
      </div>

      <span className="alert-time" style={{ color }}>
        {alert.time}
      </span>
    </div>
  )
}

// ─── Sensor Card (homepage) ───────────────────────────────────────────────────
function SensorCard({ sensorKey, data, latestValue }) {
  const sensor = SENSORS[sensorKey]
  const status = getStatus(latestValue, sensor)
  const color = statusColor(status)
  const isNil = status === 'nil'

  return (
    <div className={`sensor-card sensor-${status}`}>
      <div className="card-header">
        <div className="card-title-row">
          <span className="card-icon">{sensor.icon}</span>
          <h2 className="card-title">{sensor.label}</h2>
        </div>

        <span
          className="status-badge"
          style={{
            color,
            borderColor: color,
            background: `${color}18`,
          }}
        >
          {statusLabel(status)}
        </span>
      </div>

      <div className="card-value-row">
        {isNil ? (
          <span className="card-value nil-value">—</span>
        ) : (
          <>
            <span className="card-value" style={{ color }}>
              {latestValue}
            </span>
            <span className="card-unit">{sensor.unit}</span>
          </>
        )}
      </div>

      <div className="card-thresholds">
        <span>
          Normal: &lt; {sensor.normal.max} {sensor.unit}
        </span>
        <span>
          Warning: {sensor.normal.max}–{sensor.warning.max} {sensor.unit}
        </span>
      </div>

      <div className="card-chart">
        {isNil || data.length === 0 ? (
          <div className="nil-chart">
            <span>Awaiting IoT signal…</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={140}>
            <LineChart
              data={data}
              margin={{ top: 4, right: 8, left: -20, bottom: 0 }}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#252837"
              />

              <XAxis
                dataKey="time"
                tick={{ fontSize: 10, fill: '#5a6080' }}
                interval="preserveStartEnd"
              />

              <YAxis
                tick={{ fontSize: 10, fill: '#5a6080' }}
                domain={['auto', 'auto']}
              />

              <Tooltip
                content={
                  <CustomTooltip
                    unit={sensor.unit}
                    color={sensor.color}
                  />
                }
              />

              <ReferenceLine
                y={sensor.normal.max}
                stroke="#f0c040"
                strokeDasharray="4 4"
                strokeWidth={1}
              />

              <ReferenceLine
                y={sensor.warning.max}
                stroke="#e05555"
                strokeDasharray="4 4"
                strokeWidth={1}
              />

              <Line
                type="monotone"
                dataKey="value"
                stroke={sensor.color}
                strokeWidth={2}
                dot={<AnomalyDot />}
                activeDot={{
                  r: 4,
                  strokeWidth: 1.5,
                  stroke: '#0d0f14',
                }}
                isAnimationActive={false}
                connectNulls={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

// ─── Home Page (original dashboard) ──────────────────────────────────────────
function HomePage({
  data,
  latest,
  alerts,
  clearTime,
  onClear,
  tick,
  systemStatus,
}) {
  return (
    <main className="main">
      <section className="sensors-grid">
        {Object.keys(SENSORS).map(key => (
          <SensorCard
            key={key}
            sensorKey={key}
            data={data[key]}
            latestValue={latest[key]}
          />
        ))}
      </section>

      <section className="alert-section">
        <div className="alert-header">
          <h2 className="section-title">
            🔔 Alert Log
            {alerts.length > 0 && (
              <span className="alert-count">{alerts.length}</span>
            )}
          </h2>

          <div className="alert-header-right">
            {clearTime && (
              <span className="cleared-time">
                Cleared at {formatDateTime(clearTime)}
              </span>
            )}

            {alerts.length > 0 && (
              <button className="clear-btn" onClick={onClear}>
                Clear
              </button>
            )}
          </div>
        </div>

        <div className="alert-list">
          {alerts.length === 0 ? (
            <div className="no-alerts">
              👁️ Watching… Connect IoT sensors to begin receiving data.
            </div>
          ) : (
            alerts.map(a => <AlertEntry key={a.id} alert={a} />)
          )}
        </div>
      </section>
    </main>
  )
}

// ─── Root App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [data, setData] = useState({
    vibration: [],
    temperature: [],
    current: [],
  })

  const [alerts, setAlerts] = useState([])
  const [alertsByKey, setAlertsByKey] = useState({
    vibration: [],
    temperature: [],
    current: [],
  })

  const [clearTime, setClearTime] = useState(null)

  const [clearTimes, setClearTimes] = useState({
    vibration: null,
    temperature: null,
    current: null,
  })

  const [tick, setTick] = useState(0)
  const [isLightMode, setIsLightMode] = useState(true)

  const lastLogTime = useRef({
    vibration: 0,
    temperature: 0,
    current: 0,
  })

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      const timeLabel = formatTime(now)

      const nextData = {}
      const newAlerts = []
      const newAlertsByKey = {
        vibration: [],
        temperature: [],
        current: [],
      }

      for (const key of Object.keys(SENSORS)) {
        const sensor = SENSORS[key]
        const value = generateValue(sensor)
        const status = getStatus(value, sensor)

        const point = {
          time: timeLabel,
          value,
          status,
        }

        const timeSinceLast = now - lastLogTime.current[key]
        const isAnomaly =
          status === 'warning' || status === 'critical'

        const shouldLog =
          status !== 'nil' &&
          (isAnomaly || timeSinceLast >= LOG_INTERVAL_MS)

        if (shouldLog) {
          if (!isAnomaly) {
            lastLogTime.current[key] = now
          }

          const entry = {
            id: `${key}-${now}-${Math.random()}`,
            sensor: sensor.label,
            status,
            message: `${value} ${sensor.unit} — ${statusLabel(status)}`,
            time: timeLabel,
          }

          newAlerts.push(entry)
          newAlertsByKey[key].push(entry)
        }

        nextData[key] = point
      }

      setData(prev => {
        const next = {}

        for (const key of Object.keys(SENSORS)) {
          next[key] = [
            ...prev[key],
            nextData[key],
          ].slice(-MAX_POINTS)
        }

        return next
      })

      if (newAlerts.length > 0) {
        setAlerts(prev => [
          ...newAlerts,
          ...prev,
        ].slice(0, 100))

        setAlertsByKey(prev => {
          const next = {}

          for (const key of Object.keys(SENSORS)) {
            next[key] =
              newAlertsByKey[key].length > 0
                ? [
                    ...newAlertsByKey[key],
                    ...prev[key],
                  ].slice(0, 100)
                : prev[key]
          }

          return next
        })
      }

      setTick(t => t + 1)
    }, CHART_INTERVAL_MS)

    return () => clearInterval(interval)
  }, [])

  const latest = {
    vibration: data.vibration.at(-1)?.value ?? null,
    temperature: data.temperature.at(-1)?.value ?? null,
    current: data.current.at(-1)?.value ?? null,
  }

  const systemStatus = Object.keys(SENSORS).some(
    key => getStatus(latest[key], SENSORS[key]) === 'critical'
  )
    ? 'critical'
    : Object.keys(SENSORS).some(
        key => getStatus(latest[key], SENSORS[key]) === 'warning'
      )
      ? 'warning'
      : Object.keys(SENSORS).every(
          key => getStatus(latest[key], SENSORS[key]) === 'nil'
        )
        ? 'nil'
        : 'normal'

  function handleHomeClear() {
    setAlerts([])
    setClearTime(Date.now())
  }

  function handleSensorClear(key) {
    setAlertsByKey(prev => ({
      ...prev,
      [key]: [],
    }))

    setClearTimes(prev => ({
      ...prev,
      [key]: Date.now(),
    }))
  }

  return (
    <BrowserRouter>
      <div className={`app ${isLightMode ? 'light' : ''}`}>
        <Navbar
          systemStatus={systemStatus}
          tick={tick}
          isLightMode={isLightMode}
          onToggleTheme={() => setIsLightMode(prev => !prev)}
        />

        <Routes>
          <Route
            path="/"
            element={
              <HomePage
                data={data}
                latest={latest}
                alerts={alerts}
                clearTime={clearTime}
                onClear={handleHomeClear}
                tick={tick}
                systemStatus={systemStatus}
              />
            }
          />

          {Object.keys(SENSORS).map(key => (
            <Route
              key={key}
              path={`/${key}`}
              element={
                <SensorPage
                  sensorKey={key}
                  data={data[key]}
                  latestValue={latest[key]}
                  alerts={alertsByKey[key]}
                  onClear={() => handleSensorClear(key)}
                  clearTime={clearTimes[key]}
                />
              }
            />
          ))}
        </Routes>
      </div>
    </BrowserRouter>
  )
}
