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
import MLStatusPanel from './MLStatusPanel'
import useRUL from '../useRUL'

import { t } from '../i18n'
import useLang from '../useLang'


// ==================================================
// ANOMALY DOT
// ==================================================

function AnomalyDot(props) {
  const { cx, cy, payload } = props

  if (
    !payload ||
    [
      'normal',
      'nil',
      'awaiting-iot',
    ].includes(payload.status)
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
// CUSTOM TOOLTIP
// ==================================================

function CustomTooltip({ active, payload, label, unit }) {
  const lang = useLang()

  if (!active || !payload?.length) return null

  const value = payload[0].value
  const status = payload[0].payload?.status
  const color = statusColor(status)

  return (
    <div className="chart-tooltip">

      <p className="tooltip-time">
        {label}
      </p>

      <p
        className="tooltip-val"
        style={{ color }}
      >
        {value === null || value === undefined
          ? '— No signal'
          : `${value} ${unit}`}
      </p>

      {status && status !== 'normal' && (
        <p
          className="tooltip-status"
          style={{ color }}
        >
          {statusLabel(status, lang)}
        </p>
      )}

    </div>
  )
}


// ==================================================
// ACTION BANNER
// ==================================================

function ActionBanner({ status, lang }) {
  if (
    !status ||
    status === 'awaiting-iot' ||
    status === 'nil'
  ) {
    return null
  }

  const configs = {
    critical: {
      title: t('action_critical_title', lang),
      body: t('action_critical_body', lang),
      bg: '#ef444412',
      border: '#ef444440',
      color: '#ef4444',
      icon: '🛑',
      pulse: true,
    },

    warning: {
      title: t('action_warning_title', lang),
      body: t('action_warning_body', lang),
      bg: '#f59e0b10',
      border: '#f59e0b35',
      color: '#f59e0b',
      icon: '⚠️',
      pulse: false,
    },

    normal: {
      title: t('action_normal_title', lang),
      body: t('action_normal_body', lang),
      bg: '#22c55e0d',
      border: '#22c55e30',
      color: '#22c55e',
      icon: '✅',
      pulse: false,
    },

    uncertain: {
      title: '🔍 Verifying Sensor Data',
      body: 'Readings are being cross-checked against known baselines. Stand by.',
      bg: '#a855f710',
      border: '#a855f730',
      color: '#a855f7',
      icon: '🔍',
      pulse: false,
    },
  }

  const config = configs[status]

  if (!config) return null

  return (
    <div
      className={`action-banner${
        config.pulse ? ' action-banner-pulse' : ''
      }`}
      style={{
        background: config.bg,
        borderColor: config.border,
        '--banner-color': config.color,
      }}
    >

      <div className="action-banner-header">

        <span className="action-banner-icon">
          {config.icon}
        </span>

        <span
          className="action-banner-title"
          style={{ color: config.color }}
        >
          {config.title}
        </span>

      </div>

      <p className="action-banner-body">
        {config.body}
      </p>

    </div>
  )
}


// ==================================================
// STARTUP / AWAITING PANEL
// ==================================================

function StartupPanel({ lang }) {
  return (
    <div className="startup-panel">

      <div className="startup-panel-header">
        <span>🔌</span>
        <span>{t('awaiting_iot', lang)}</span>
      </div>

      <p className="startup-panel-body">
        {t('awaiting_iot_body', lang)}
      </p>

    </div>
  )
}


// ==================================================
// IOT INTEGRATION PANEL
// ==================================================

function IoTPanel({ sensor, lang }) {
  return (
    <section className="iot-panel">

      <div className="iot-header">

        <span className="iot-icon">
          🔌
        </span>

        <h3 className="iot-title">
          {t('iot_panel_title', lang)} — {sensor.label}
        </h3>

        <span className="iot-badge">
          {t('iot_pending', lang)}
        </span>

      </div>

      <div className="iot-body">

        <div className="iot-row">
          <span className="iot-label">
            {t('iot_sensor_type', lang)}
          </span>

          <span className="iot-val">
            {sensor.label} Sensor
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            {t('iot_unit', lang)}
          </span>

          <span className="iot-val">
            {sensor.unit}
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            {t('iot_normal_range', lang)}
          </span>

          <span className="iot-val">
            {sensor.normal.min} – {sensor.normal.max} {sensor.unit}
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            {t('iot_warn_range', lang)}
          </span>

          <span
            className="iot-val"
            style={{ color: '#f0c040' }}
          >
            {sensor.normal.max} – {sensor.warning.max} {sensor.unit}
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            {t('iot_crit_thresh', lang)}
          </span>

          <span
            className="iot-val"
            style={{ color: '#e05555' }}
          >
            &gt; {sensor.warning.max} {sensor.unit}
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            {t('iot_data_feed', lang)}
          </span>

          <span className="iot-val iot-pending">
            {t('iot_not_connected', lang)}
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            Status
          </span>

          <span className="iot-val iot-pending">
            {t('iot_awaiting_sig', lang)}
          </span>
        </div>

      </div>

      <div className="iot-note">
        {t('iot_note', lang)}
      </div>

    </section>
  )
}


// ==================================================
// SIMULATION INFORMATION PANEL
// ==================================================

function SimulationPanel({ sensor }) {
  return (
    <section className="iot-panel">

      <div className="iot-header">

        <span className="iot-icon">
          🧪
        </span>

        <h3 className="iot-title">
          Simulation Mode — {sensor.label}
        </h3>

        <span
          className="iot-badge"
          style={{
            background: '#3b82f615',
            color: '#60a5fa',
            borderColor: '#3b82f640',
          }}
        >
          SIMULATED
        </span>

      </div>

      <div className="iot-body">

        <div className="iot-row">
          <span className="iot-label">
            Data source
          </span>

          <span className="iot-val">
            Local simulation generator
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            Sensor
          </span>

          <span className="iot-val">
            {sensor.label}
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            Measurement unit
          </span>

          <span className="iot-val">
            {sensor.unit}
          </span>
        </div>

        <div className="iot-row">
          <span className="iot-label">
            Hardware connection
          </span>

          <span className="iot-val iot-pending">
            Not used in this mode
          </span>
        </div>

      </div>

      <div className="iot-note">
        Synthetic readings are generated for demonstration
        and testing only. They are not actual equipment
        measurements and are isolated from hardware learning
        and backend equipment history.
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
  operatingMode = 'iot',
}) {
  const lang = useLang()

  const mlSource =
    operatingMode === 'simulation' ? 'simulation' :
    sessionStorage.getItem('iw_token') === 'demo-offline' ? 'offline-demo' :
    'hardware'

  const rul = useRUL(mlSource)

  const sensor = SENSORS[sensorKey]

  if (!sensor) {
    return (
      <main className="main">
        <p>Sensor not found.</p>
      </main>
    )
  }

  const isSimulation = operatingMode === 'simulation'

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

          <span className="page-icon">
            {sensor.icon}
          </span>

          <h1 className="page-title">
            {sensor.label}
          </h1>

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


      {/* Data source indication */}

      <div
        style={{
          fontSize: 12,
          color: isSimulation ? '#60a5fa' : 'var(--muted)',
          fontWeight: 600,
        }}
      >
        {isSimulation
          ? '🧪 SIMULATION DATA'
          : '🔌 IoT / HARDWARE MODE'}
      </div>


      {/* Current reading */}

      <div className="live-value-row">

        {hasLiveReading ? (
          <>
            <span
              className="live-value"
              style={{ color }}
            >
              {latestValue}
            </span>

            <span className="live-unit">
              {sensor.unit}
            </span>
          </>
        ) : (
          <span className="live-value nil-value">
            —
          </span>
        )}

        <span className="live-label">
          {t('live_reading', lang)}
        </span>

      </div>


      {/* Action banner */}

      <ActionBanner
        status={hasLiveReading ? status : null}
        lang={lang}
      />


      {/* RUL / Maintenance window estimate */}

      {rul.status !== 'cold' && rul.status !== 'stable' && (
        <div
          className="rul-banner"
          style={{
            background:
              rul.status === 'imminent' || rul.status === 'exceeded'
                ? '#ef444412'
                : rul.status === 'soon'
                ? '#f59e0b10'
                : '#3b82f610',
            borderColor:
              rul.status === 'imminent' || rul.status === 'exceeded'
                ? '#ef444440'
                : rul.status === 'soon'
                ? '#f59e0b35'
                : '#3b82f640',
          }}
        >
          <span className="rul-icon">
            {rul.status === 'imminent' || rul.status === 'exceeded'
              ? '🔴'
              : rul.status === 'soon'
              ? '🟡'
              : '🔵'}
          </span>
          <div className="rul-body">
            <span className="rul-title"
              style={{
                color:
                  rul.status === 'imminent' || rul.status === 'exceeded'
                    ? '#ef4444'
                    : rul.status === 'soon'
                    ? '#f59e0b'
                    : '#60a5fa',
              }}
            >
              {rul.status === 'exceeded'
                ? 'Critical threshold exceeded'
                : rul.status === 'imminent'
                ? `Maintenance required within ~${rul.hoursUntilCritical}h`
                : rul.status === 'soon'
                ? `Maintenance recommended within ~${rul.hoursUntilCritical}h`
                : `Projected maintenance window: ~${rul.hoursUntilCritical}h`}
            </span>
            <span className="rul-sub">
              {rul.dominantSensor
                ? `Trend on ${SENSORS[rul.dominantSensor]?.label ?? rul.dominantSensor} · ISO 13381-1 RUL estimate · ${rul.confidence}% confidence`
                : `ISO 13381-1 RUL estimate · ${rul.confidence}% confidence`}
            </span>
          </div>
        </div>
      )}


      {/* Awaiting hardware */}

      {!hasLiveReading && !isSimulation && (
        <StartupPanel lang={lang} />
      )}


      {/* Statistics */}

      {hasLiveReading && data.length > 0 && (() => {
        const values = data
          .map(point => Number(point.value))
          .filter(Number.isFinite)

        if (!values.length) return null

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
              <span className="stat-label">
                {t('stat_min', lang)}
              </span>

              <span className="stat-value">
                {min} <small>{sensor.unit}</small>
              </span>
            </div>

            <div className="stat-item">
              <span className="stat-label">
                {t('stat_avg', lang)}
              </span>

              <span className="stat-value">
                {avg} <small>{sensor.unit}</small>
              </span>
            </div>

            <div className="stat-item">
              <span className="stat-label">
                {t('stat_max', lang)}
              </span>

              <span className="stat-value">
                {max} <small>{sensor.unit}</small>
              </span>
            </div>

            <div className="stat-item">
              <span className="stat-label">
                {t('stat_anomalies', lang)}
              </span>

              <span
                className="stat-value"
                style={{
                  color: anomalies > 0
                    ? '#e05555'
                    : '#2ecc71',
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
          📈 {sensor.label} — {t('chart_title', lang)}
        </h2>

        <div className="chart-legend-row">

          <span className="legend-item legend-warning">
            ── {t('warn_threshold', lang)} ({sensor.normal.max} {sensor.unit})
          </span>

          <span className="legend-item legend-critical">
            ── {t('crit_threshold', lang)} ({sensor.warning.max} {sensor.unit})
          </span>

        </div>

        {data.length === 0 ? (
          <div className="nil-chart nil-chart-lg">
            <span>
              {t('chart_awaiting', lang)}
            </span>
          </div>
        ) : (
          <ResponsiveContainer
            width="100%"
            height={320}
          >
            <AreaChart
              data={data}
              margin={{
                top: 10,
                right: 24,
                left: 0,
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
                  fontSize: 11,
                  fill: 'var(--muted)',
                }}
                interval="preserveStartEnd"
                axisLine={false}
                tickLine={false}
              />

              <YAxis
                tick={{
                  fontSize: 11,
                  fill: 'var(--muted)',
                }}
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
                  value: 'W',
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
                  value: 'C',
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


      {/* Sensor-specific ML state */}

      <MLStatusPanel
        sensorKey={sensorKey}
        operatingMode={operatingMode}
      />


      {/* Alert log */}

      <AlertLog
        alerts={alerts}
        onClear={onClear}
        clearTime={clearTime}
        lang={lang}
        operatingMode={operatingMode}
      />


      {/* Mode-specific information */}

      {isSimulation ? (
        <SimulationPanel sensor={sensor} />
      ) : (
        <IoTPanel
          sensor={sensor}
          lang={lang}
        />
      )}

    </main>
  )
}