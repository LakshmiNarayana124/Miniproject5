
import { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

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
  SENSORS,
  statusColor,
  statusLabel,
} from './sensors'

import Navbar from './components/Navbar'
import SensorPage from './components/SensorPage'
import AlertLog from './components/AlertLog'
import SensorExplorer from './components/SensorExplorer'

import './App.css'

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

      {status && (
        <p className="tooltip-status" style={{ color }}>
          {statusLabel(status)}
        </p>
      )}
    </div>
  )
}

// ==================================================
// ANOMALY DOT
// ==================================================

function AnomalyDot({ cx, cy, payload }) {
  if (
    !payload ||
    ['normal', 'nil', 'awaiting-iot'].includes(payload.status)
  ) {
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
// SENSOR CARD
// ==================================================

function SensorCard({ sensorKey, data = [], latestValue }) {
  const sensor = SENSORS[sensorKey]
  const latestPoint = data.at(-1)

  const hasLiveReading =
    latestValue !== null &&
    latestValue !== undefined &&
    Number.isFinite(Number(latestValue))

  const status = hasLiveReading
    ? latestPoint?.status || 'uncertain'
    : 'awaiting-iot'

  const color = statusColor(status)
  const gradientId = `dashboard-gradient-${sensorKey}`

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
        {hasLiveReading ? (
          <>
            <span className="card-value" style={{ color }}>
              {latestValue}
            </span>
            <span className="card-unit">{sensor.unit}</span>
          </>
        ) : (
          <span className="card-value nil-value">—</span>
        )}
      </div>

      <div className="card-thresholds">
        <span>
          Normal: {sensor.normal.min}–{sensor.normal.max} {sensor.unit}
        </span>

        <span>
          Warning: {sensor.normal.max}–{sensor.warning.max} {sensor.unit}
        </span>
      </div>

      <div className="card-chart">
        {!hasLiveReading || data.length === 0 ? (
          <div className="nil-chart">
            <span>🔌 Awaiting IoT Signal</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart
              data={data}
              margin={{ top: 4, right: 8, left: -20, bottom: 0 }}
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
                tick={{ fontSize: 10, fill: 'var(--muted)' }}
                interval="preserveStartEnd"
                axisLine={false}
                tickLine={false}
              />

              <YAxis
                tick={{ fontSize: 10, fill: 'var(--muted)' }}
                domain={['auto', 'auto']}
                axisLine={false}
                tickLine={false}
              />

              <Tooltip
                content={<CustomTooltip unit={sensor.unit} />}
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

              <Area
                type="monotone"
                dataKey="value"
                stroke={sensor.color}
                strokeWidth={2.5}
                fill={`url(#${gradientId})`}
                dot={<AnomalyDot />}
                activeDot={{
                  r: 4,
                  strokeWidth: 1.5,
                  stroke: '#ffffff',
                }}
                isAnimationActive={false}
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

// ==================================================
// HOME PAGE
// ==================================================

function HomePage({
  data,
  latest,
  alerts,
  clearTime,
  onClear,
}) {
  return (
    <main className="main">
      {/* Sensor cards */}
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

      {/* Home alert log */}
      <AlertLog
        alerts={alerts}
        onClear={onClear}
        clearTime={clearTime}
      />
    </main>
  )
}

// ==================================================
// ROOT APPLICATION
// ==================================================

export default function App() {
  const emptyData = {
    vibration: [],
    temperature: [],
    current: [],
  }

  // No simulated readings are generated.
  // Histories remain empty until real IoT data is received.
  const [data] = useState(emptyData)

  const [alerts, setAlerts] = useState([])

  const [alertsByKey] = useState({
    vibration: [],
    temperature: [],
    current: [],
  })

  const [clearTime, setClearTime] = useState(null)

  const [clearTimes] = useState({
    vibration: null,
    temperature: null,
    current: null,
  })

  const [isLightMode, setIsLightMode] = useState(true)

  // Latest readings remain null until real sensor data arrives.
  const latest = {
    vibration: data.vibration.at(-1)?.value ?? null,
    temperature: data.temperature.at(-1)?.value ?? null,
    current: data.current.at(-1)?.value ?? null,
  }

  // Determine the overall system status.
  const currentStatuses = Object.keys(SENSORS).map(
    key => data[key].at(-1)?.status ?? 'awaiting-iot'
  )

  const systemStatus =
    currentStatuses.includes('critical')
      ? 'critical'
      : currentStatuses.includes('warning')
        ? 'warning'
        : currentStatuses.includes('uncertain')
          ? 'uncertain'
          : currentStatuses.every(
              status => status === 'awaiting-iot'
            )
            ? 'awaiting-iot'
            : 'normal'

  // Clear home alert log.
  function handleHomeClear() {
    setAlerts([])
    setClearTime(Date.now())
  }

  // Clear sensor-specific alert log.
  function handleSensorClear(key) {
    // Sensor-specific alerts are currently empty because
    // real IoT data has not been connected.
    if (!Object.prototype.hasOwnProperty.call(alertsByKey, key)) {
      return
    }
  }

  return (
    <BrowserRouter>
      <div className={`app ${isLightMode ? 'light' : ''}`}>
        <Navbar
          systemStatus={systemStatus}
          tick={0}
          isLightMode={isLightMode}
          onToggleTheme={() => setIsLightMode(prev => !prev)}
        />

        <Routes>
          {/* Home Dashboard */}
          <Route
            path="/"
            element={
              <HomePage
                data={data}
                latest={latest}
                alerts={alerts}
                clearTime={clearTime}
                onClear={handleHomeClear}
              />
            }
          />

          {/* Dedicated sensor pages */}
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

          {/* 3D Hardware Explorer */}
          <Route
            path="/explorer"
            element={<SensorExplorer />}
          />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
