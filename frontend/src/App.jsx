
import { useState, useEffect, useRef } from 'react'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom'

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
import LoginPage from './components/LoginPage'
import TenderLeaderboard from './components/TenderLeaderboard'
import Chatbot from './components/Chatbot'
import AboutPage from './components/AboutPage'
import MLStatusPanel from './components/MLStatusPanel'
import ControlSignalBanner from './components/ControlSignalBanner'
import UserManagement from './components/UserManagement'
import EquipmentVision from './components/VisionEquipment'

import { t } from './i18n'
import useLang from './useLang'

import {
  recordVisit,
  getLastVisit,
  formatActivity,
} from './activityLog'

import useSensorData from './useSensorData'
import useTokenRefresh from './useTokenRefresh'

import './App.css'


// ==================================================
// CONFIGURATION
// ==================================================

const DEMO_TOKEN = 'demo-offline'

const DEFAULT_OPERATING_MODE = 'iot'

function createEmptySensorAlerts() {
  return {
    vibration: [],
    temperature: [],
    current: [],
  }
}

function createEmptyClearTimes() {
  return {
    vibration: null,
    temperature: null,
    current: null,
  }
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
          ? '\u2014 No signal'
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

function SensorCard({
  sensorKey,
  data = [],
  latestValue,
}) {
  const lang = useLang()
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

  const STATUS_KEYS = {
    normal: 'status_normal',
    warning: 'status_warning',
    critical: 'status_critical',
    uncertain: 'status_uncertain',
    scanning: 'status_scanning',
    ready: 'status_ready',
    nil: 'status_no_data',
    'awaiting-iot': 'status_awaiting',
    'no-recordings': 'status_no_data',
  }

  const statusText = t(
    STATUS_KEYS[status] || 'status_awaiting',
    lang
  )

  return (
    <div className={`sensor-card sensor-${status}`}>

      <div className="card-header">
        <div className="card-title-row">
          <span className="card-icon">
            {sensor.icon}
          </span>

          <h2 className="card-title">
            {sensor.label}
          </h2>
        </div>

        <span
          className="status-badge"
          style={{
            color,
            borderColor: color,
            background: `${color}18`,
          }}
        >
          {statusText}
        </span>
      </div>

      <div className="card-value-row">
        {hasLiveReading ? (
          <>
            <span className="card-value" style={{ color }}>
              {latestValue}
            </span>

            <span className="card-unit">
              {sensor.unit}
            </span>
          </>
        ) : (
          <span className="card-value nil-value">
            &mdash;
          </span>
        )}
      </div>

      <div className="card-thresholds">
        <span>
          {t('normal_range', lang)}: {sensor.normal.min}
          &ndash;{sensor.normal.max} {sensor.unit}
        </span>

        <span>
          {t('warning_range', lang)}: {sensor.normal.max}
          &ndash;{sensor.warning.max} {sensor.unit}
        </span>
      </div>

      <div className="card-chart">
        {!hasLiveReading || data.length === 0 ? (
          <div className="nil-chart">
            <span>{t('awaiting_iot', lang)}</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart
              data={data}
              margin={{
                top: 4,
                right: 8,
                left: -20,
                bottom: 0,
              }}
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
                tick={{
                  fontSize: 10,
                  fill: 'var(--muted)',
                }}
                interval="preserveStartEnd"
                axisLine={false}
                tickLine={false}
              />

              <YAxis
                tick={{
                  fontSize: 10,
                  fill: 'var(--muted)',
                }}
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
// SYSTEM STATUS OVERVIEW
// ==================================================

function SystemStatusOverview({
  systemStatus,
  data,
  connectionStatus,
  operatingMode,
}) {
  const lang = useLang()
  const sensors = Object.keys(SENSORS)

  const statusInfo = {
    normal: {
      icon: '\u2705',
      titleKey: 'sys_overview_normal',
      msgKey: 'sys_msg_normal',
      color: '#22c55e',
    },

    warning: {
      icon: '\u26A0\uFE0F',
      titleKey: 'sys_overview_warning',
      msgKey: 'sys_msg_warning',
      color: '#f59e0b',
    },

    critical: {
      icon: '\uD83D\uDED1',
      titleKey: 'sys_overview_critical',
      msgKey: 'sys_msg_critical',
      color: '#ef4444',
    },

    uncertain: {
      icon: '\uD83D\uDD0D',
      titleKey: 'sys_overview_uncertain',
      msgKey: 'sys_msg_awaiting',
      color: '#a855f7',
    },

    'awaiting-iot': {
      icon: '\uD83D\uDD0C',
      titleKey: 'sys_overview_awaiting',
      msgKey: 'sys_msg_awaiting',
      color: '#94a3b8',
    },
  }

  const info =
    statusInfo[systemStatus] ||
    statusInfo['awaiting-iot']

  const connLabel = {
    live: '\uD83D\uDFE2 Live',
    polling: '\uD83D\uDFE1 Polling',
    connecting: '\uD83D\uDD35 Connecting\u2026',
    offline: '\uD83D\uDD34 Offline',
    demo: '\uD83E\uDDEA Demo Simulation',
    simulation: '\uD83E\uDDEA Simulation',
  }[connectionStatus] || ''

  const sourceLabel =
    operatingMode === 'simulation'
      ? '🧪 Simulation Mode'
      : '🔌 IoT / Hardware Mode'

  return (
    <div
      className={`system-overview${
        systemStatus === 'critical'
          ? ' system-overview-critical'
          : ''
      }`}
      style={{
        borderColor: `${info.color}40`,
        boxShadow: `0 0 24px ${info.color}15`,
      }}
    >
      <div className="system-overview-left">
        <span className="system-overview-icon">
          {info.icon}
        </span>

        <div>
          <h2
            className="system-overview-title"
            style={{ color: info.color }}
          >
            {t(info.titleKey, lang)}
          </h2>

          <p className="system-overview-msg">
            {t(info.msgKey, lang)}

            <span
              style={{
                marginLeft: 10,
                fontSize: '11px',
                opacity: 0.75,
              }}
            >
              {sourceLabel}
              {connLabel ? ` · ${connLabel}` : ''}
            </span>
          </p>
        </div>
      </div>

      <div className="system-overview-sensors">
        {sensors.map(key => {
          const sensor = SENSORS[key]
          const latest = data[key].at(-1)

          const status =
            latest?.status || 'awaiting-iot'

          const color = statusColor(status)

          const statusKey = {
            normal: 'status_normal',
            warning: 'status_warning',
            critical: 'status_critical',
            uncertain: 'status_uncertain',
            nil: 'status_no_data',
            'awaiting-iot': 'status_awaiting',
          }[status] || 'status_awaiting'

          return (
            <div
              key={key}
              className="system-mini-sensor"
              style={{
                borderColor: `${color}30`,
              }}
            >
              <span style={{ fontSize: 18 }}>
                {sensor.icon}
              </span>

              <span className="system-mini-label">
                {sensor.label}
              </span>

              <span
                className="system-mini-status"
                style={{ color }}
              >
                {t(statusKey, lang)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ==================================================
// PAGE TRACKER
// ==================================================

function PageTracker({ user }) {
  const location = useLocation()

  useEffect(() => {
    if (!user?.username) return

    recordVisit(
      user.username,
      user.role,
      location.pathname
    )
  }, [location.pathname, user])

  return null
}


// ==================================================
// LAST SESSION BANNER
// ==================================================

function LastSessionBanner({ user }) {
  const location = useLocation()

  const [last, setLast] = useState(null)
  const [visible, setVisible] = useState(false)

  const shownRef = useRef(false)

  useEffect(() => {
    if (shownRef.current || !user?.username) return

    shownRef.current = true

    const entry = getLastVisit(
      user.username,
      location.pathname
    )

    if (entry) {
      setLast(entry)
      setVisible(true)

      const timer = setTimeout(
        () => setVisible(false),
        6000
      )

      return () => clearTimeout(timer)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!visible || !last) return null

  return (
    <div
      className="last-session-banner"
      role="status"
      aria-live="polite"
    >
      <span className="lsb-icon">
        \uD83D\uDD52
      </span>

      <span className="lsb-text">
        Last session: <strong>{last.label}</strong>
        {' '}&mdash; {formatActivity(last.ts)}
      </span>

      <button
        className="lsb-close"
        onClick={() => setVisible(false)}
        aria-label="Dismiss"
      >
        &times;
      </button>
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
  connectionStatus,
  operatingMode,
}) {
  const statuses = Object.keys(SENSORS).map(
    key => data[key].at(-1)?.status ?? 'awaiting-iot'
  )

  const systemStatus =
    statuses.includes('critical')
      ? 'critical'
      : statuses.includes('warning')
        ? 'warning'
        : statuses.every(
            status => status === 'awaiting-iot'
          )
          ? 'awaiting-iot'
          : statuses.includes('uncertain')
            ? 'uncertain'
            : 'normal'

  return (
    <main className="main">

      <SystemStatusOverview
        systemStatus={systemStatus}
        data={data}
        connectionStatus={connectionStatus}
        operatingMode={operatingMode}
      />

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

      <TenderLeaderboard />

      <MLStatusPanel
        operatingMode={operatingMode}
      />

      <AlertLog
        alerts={alerts}
        onClear={onClear}
        clearTime={clearTime}
        operatingMode={operatingMode}
      />

    </main>
  )
}


// ==================================================
// PROTECTED LAYOUT
// ==================================================

function ProtectedLayout({
  user,
  systemStatus,
  tick,
  isLightMode,
  onToggleTheme,
  onLogout,
  children,
  token,
  operatingMode,
  onOperatingModeChange,
  isDemoSession,
}) {
  return (
    <div className={`app ${isLightMode ? 'light' : ''}`}>

      <Navbar
        systemStatus={systemStatus}
        tick={tick}
        isLightMode={isLightMode}
        onToggleTheme={onToggleTheme}
        user={user}
        onLogout={onLogout}
        operatingMode={operatingMode}
        onOperatingModeChange={onOperatingModeChange}
        isDemoSession={isDemoSession}
      />

      <ControlSignalBanner
        token={token}
        operatingMode={operatingMode}
      />

      <PageTracker user={user} />
      <LastSessionBanner user={user} />

      {children}

      {/* Pass the existing authentication token to Bolt. */}
      <Chatbot
        token={token}
        isDemoSession={isDemoSession}
      />

    </div>
  )
}


// ==================================================
// ROOT APPLICATION
// ==================================================

export default function App() {

  // --------------------------------------------------
  // AUTHENTICATED USER
  // --------------------------------------------------

  const [user, setUser] = useState(() => {
    try {
      const stored = sessionStorage.getItem('iw_user')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })


  // --------------------------------------------------
  // OPERATING MODE
  //
  // IoT / Hardware is always the default.
  // Simulation requires an explicit user selection.
  //
  // Mode is intentionally session-only. Refreshing the
  // page returns to IoT mode rather than silently
  // resuming synthetic readings.
  // --------------------------------------------------

  const [operatingMode, setOperatingMode] = useState(
    DEFAULT_OPERATING_MODE
  )


  // --------------------------------------------------
  // APPLICATION UI STATE
  // --------------------------------------------------

  const [isLightMode, setIsLightMode] = useState(true)
  const [clearTime, setClearTime] = useState(null)

  const [alertsByKey, setAlertsByKey] = useState(
    createEmptySensorAlerts
  )

  const [clearTimes, setClearTimes] = useState(
    createEmptyClearTimes
  )


  // --------------------------------------------------
  // AUTHENTICATION TOKEN
  // --------------------------------------------------

  const token = user
    ? (sessionStorage.getItem('iw_token') || null)
    : null

  const isDemoSession = Boolean(
    token === DEMO_TOKEN ||
    user?.session_mode === 'DEMO'
  )


  // --------------------------------------------------
  // EXPECTED DATA SOURCE
  // --------------------------------------------------

  const expectedAlertSource = isDemoSession
    ? 'offline-demo'
    : operatingMode === 'simulation'
      ? 'simulation'
      : 'hardware'


  // --------------------------------------------------
  // LOGIN
  //
  // Every successful login begins in IoT mode,
  // including a registered account that previously
  // selected Simulation in its earlier session.
  //
  // Offline demo login is independently identified
  // by its demo token.
  // --------------------------------------------------

  function handleLogin(userData) {
    setOperatingMode(DEFAULT_OPERATING_MODE)

    setAlertsByKey(createEmptySensorAlerts())
    setClearTimes(createEmptyClearTimes())
    setClearTime(null)

    setUser(userData)
  }


  // --------------------------------------------------
  // LOGOUT
  // --------------------------------------------------

  function handleLogout() {
    sessionStorage.removeItem('iw_token')
    sessionStorage.removeItem('iw_user')

    setOperatingMode(DEFAULT_OPERATING_MODE)

    setAlertsByKey(createEmptySensorAlerts())
    setClearTimes(createEmptyClearTimes())
    setClearTime(null)

    setUser(null)
  }


  // --------------------------------------------------
  // OPERATING MODE CHANGE
  //
  // Ignore invalid values and ignore mode changes
  // during offline Demo sessions.
  // --------------------------------------------------

  function handleOperatingModeChange(nextMode) {
    if (isDemoSession) return

    if (!['iot', 'simulation'].includes(nextMode)) {
      return
    }

    if (nextMode === operatingMode) return

    setOperatingMode(nextMode)
  }


  // --------------------------------------------------
  // TOKEN REFRESH
  // --------------------------------------------------

  useTokenRefresh(
    (newData) => {
      setUser(prev =>
        prev ? { ...prev, ...newData } : prev
      )
    },
    handleLogout,
  )


  // --------------------------------------------------
  // SENSOR DATA
  //
  // IoT mode:
  //   Authenticated backend connection only.
  //
  // Simulation mode:
  //   Local synthetic readings only.
  //
  // Offline Demo:
  //   Existing local demo token and generator.
  // --------------------------------------------------

  const {
    data,
    alerts: rawAlerts,
    connectionStatus,
    clearAlerts,
  } = useSensorData(
    user ? token : null,
    operatingMode
  )


  // --------------------------------------------------
  // RESET MODE-SPECIFIC ALERT HISTORY
  //
  // Prevent alerts from the previous mode appearing
  // in the newly selected mode.
  // --------------------------------------------------

  useEffect(() => {
    setAlertsByKey(createEmptySensorAlerts())
    setClearTimes(createEmptyClearTimes())
    setClearTime(null)
  }, [operatingMode, token])


  // --------------------------------------------------
  // DISTRIBUTE ALERTS BY SENSOR
  //
  // Only accept alerts originating from the current
  // operating environment.
  // --------------------------------------------------

  useEffect(() => {
    if (!rawAlerts.length) return

    const newest = rawAlerts[0]

    if (!newest?.sensor) return

    if (newest.source !== expectedAlertSource) {
      return
    }

    if (!Object.prototype.hasOwnProperty.call(
      alertsByKey,
      newest.sensor
    )) {
      return
    }

    setAlertsByKey(previous => {
      const bucket = [
        newest,
        ...previous[newest.sensor],
      ]

      return {
        ...previous,
        [newest.sensor]: bucket.slice(0, 100),
      }
    })
  }, [
    rawAlerts,
    expectedAlertSource,
  ])


  // --------------------------------------------------
  // LATEST SENSOR VALUES
  // --------------------------------------------------

  const latest = {
    vibration: data.vibration.at(-1)?.value ?? null,
    temperature: data.temperature.at(-1)?.value ?? null,
    current: data.current.at(-1)?.value ?? null,
  }


  // --------------------------------------------------
  // OVERALL SYSTEM STATUS
  // --------------------------------------------------

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


  // --------------------------------------------------
  // TICK COUNTER
  // --------------------------------------------------

  const totalPoints =
    data.vibration.length +
    data.temperature.length +
    data.current.length


  // --------------------------------------------------
  // CLEAR ALERTS
  // --------------------------------------------------

  function handleHomeClear() {
    clearAlerts()

    setAlertsByKey(createEmptySensorAlerts())

    setClearTime(Date.now())
  }


  function handleSensorClear(key) {
    if (!Object.prototype.hasOwnProperty.call(
      alertsByKey,
      key
    )) {
      return
    }

    setAlertsByKey(previous => ({
      ...previous,
      [key]: [],
    }))

    setClearTimes(previous => ({
      ...previous,
      [key]: Date.now(),
    }))
  }


  // --------------------------------------------------
  // LOGIN SCREEN
  // --------------------------------------------------

  if (!user) {
    return (
      <LoginPage onLogin={handleLogin} />
    )
  }


  // --------------------------------------------------
  // AUTHENTICATED APPLICATION
  // --------------------------------------------------

  return (
    <BrowserRouter>

      <ProtectedLayout
        user={user}
        systemStatus={systemStatus}
        tick={Math.floor(totalPoints / 3)}
        isLightMode={isLightMode}
        onToggleTheme={() => {
          setIsLightMode(previous => !previous)
        }}
        onLogout={handleLogout}
        token={token}
        operatingMode={operatingMode}
        onOperatingModeChange={handleOperatingModeChange}
        isDemoSession={isDemoSession}
      >

        <Routes>

          {/* ----------------------------------------
              HOME DASHBOARD
          ---------------------------------------- */}

          <Route
            path="/"
            element={
              <HomePage
                data={data}
                latest={latest}
                alerts={rawAlerts.filter(
                  alert => alert.source === expectedAlertSource
                )}
                clearTime={clearTime}
                onClear={handleHomeClear}
                connectionStatus={connectionStatus}
                operatingMode={operatingMode}
              />
            }
          />


          {/* ----------------------------------------
              INDIVIDUAL SENSOR PAGES
          ---------------------------------------- */}

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
                  operatingMode={operatingMode}
                />
              }
            />
          ))}


          {/* ----------------------------------------
              SENSOR EXPLORER
          ---------------------------------------- */}

          <Route
            path="/explorer"
            element={<SensorExplorer />}
          />


          {/* ----------------------------------------
              ABOUT
          ---------------------------------------- */}

          <Route
            path="/about"
            element={<AboutPage />}
          />


          {/* ----------------------------------------
              EQUIPMENT VISION
          ---------------------------------------- */}

          <Route
            path="/vision"
            element={<EquipmentVision />}
          />


          {/* ----------------------------------------
              ADMIN USER MANAGEMENT
              Offline demo cannot manage real users.
          ---------------------------------------- */}

          <Route
            path="/admin/users"
            element={
              user.role === 'ADMIN' && !isDemoSession ? (

                <UserManagement
                  token={token}
                  currentUser={user}
                />

              ) : user.role === 'ADMIN' && isDemoSession ? (

                <main className="main">
                  <section className="startup-panel">

                    <div className="startup-panel-header">
                      <span>🧪</span>
                      <span>Administrator Demo</span>
                    </div>

                    <p className="startup-panel-body">
                      This is an offline demonstration session.
                      Real user management, database changes and
                      permission updates are unavailable in Demo mode.
                    </p>

                  </section>
                </main>

              ) : (
                <Navigate to="/" replace />
              )
            }
          />


          {/* ----------------------------------------
              FALLBACK ROUTE
          ---------------------------------------- */}

          <Route
            path="*"
            element={<Navigate to="/" replace />}
          />

        </Routes>

      </ProtectedLayout>

    </BrowserRouter>
  )
}
