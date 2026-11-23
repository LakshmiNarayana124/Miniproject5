import { useState } from 'react'
import { formatDateTime } from '../sensors'
import { t } from '../i18n'
import useLang from '../useLang'
import { mlEngine } from '../mlEngine'
import ServiceReport from './ServiceReport'
const DEMO_TOKEN = 'demo-offline'

const API = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '')


// ==================================================
// DATA SOURCE
// ==================================================

function getFeedbackSource(alertSource, operatingMode, token) {
  if (token === DEMO_TOKEN) {
    return 'offline-demo'
  }

  if (
    ['hardware', 'simulation', 'offline-demo'].includes(alertSource)
  ) {
    return alertSource
  }

  return operatingMode === 'simulation'
    ? 'simulation'
    : 'hardware'
}


// ==================================================
// ALERT ENTRY — CONFIRM / DISMISS FEEDBACK
// ==================================================

function AlertEntry({ alert, onFeedback, onDismiss }) {
  const lang = useLang()

  return (
    <div className={`alert-entry alert-${alert.status}`}>
      <span className="alert-dot" />

      <div className="alert-body">
        <span className="alert-sensor">
          {alert.label || alert.sensor}
        </span>

        <span className="alert-msg">
          {alert.value !== undefined
            ? `${Number(alert.value).toFixed?.(3) ?? alert.value} ${alert.unit ?? ''} — ${alert.status?.toUpperCase()}`
            : alert.message}
        </span>
      </div>

      <span className="alert-time">
        {alert.time}
      </span>

      {(
        alert.status === 'warning' ||
        alert.status === 'critical'
      ) && (
        <div
          className="alert-feedback"
          role="group"
          aria-label="Feedback"
        >
          <button
            className="alert-fb-btn alert-fb-confirm"
            title="Confirm anomaly"
            aria-label="Confirm anomaly"
            onClick={() => onFeedback?.(
              alert.sensor || alert.label || 'unknown',
              'anomaly',
              alert.source
            )}
            type="button"
          >
            ✓
          </button>

          <button
            className="alert-fb-btn alert-fb-dismiss"
            title="Dismiss (false positive)"
            aria-label="Dismiss"
            onClick={() => onDismiss?.(alert)}
            type="button"
          >
            ✕
          </button>
        </div>
      )}
    </div>
  )
}


// ==================================================
// ALERT LOG
// ==================================================

export default function AlertLog({
  alerts = [],
  onClear,
  clearTime,
  lang: propLang,
  operatingMode = 'iot',
}) {
  const hookLang = useLang()
  const lang = propLang || hookLang
  const [dismissedAlertIds, setDismissedAlertIds] = useState(() => new Set())
  const visibleAlerts = alerts.filter(alert => !dismissedAlertIds.has(String(alert.id)))


  // ==================================================
  // FEEDBACK HANDLING
  // ==================================================

  function handleFeedback(
    sensorKey,
    label,
    alertSource
  ) {
    const token = sessionStorage.getItem('iw_token')

    let storedUser = null

    try {
      storedUser = JSON.parse(
        sessionStorage.getItem('iw_user') || 'null'
      )
    } catch {
      storedUser = null
    }

    const source = getFeedbackSource(
      alertSource,
      operatingMode,
      token
    )

    // Update only the selected learning environment.
    mlEngine.feedback(
      sensorKey,
      label,
      source
    )

    // Offline Demo and restricted demo sessions
    // remain completely local.
    if (
      !token ||
      token === DEMO_TOKEN ||
      storedUser?.session_mode === 'DEMO'
    ) {
      return
    }

    // Simulation feedback must never enter the
    // backend operational learning system.
    if (source !== 'hardware') {
      return
    }

    const mlState = mlEngine.getState(
      sensorKey,
      'hardware'
    )

    if (!mlState) return

    // Only registered online hardware sessions
    // can submit feedback to backend learning.
    fetch(`${API}/learning/label`, {
      method: 'POST',

      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },

      body: JSON.stringify({
        label,

        feature_vector: [
          mlState.emaMean ?? 0,
          mlState.emaStd ?? 0,
          mlState.score ?? 0,
        ],

        model_version: 'browser-v1',
      }),

    }).catch(error => {
      console.warn(
        '[AlertLog] Online label submission failed:',
        error
      )
    })
  }


  // ==================================================
  // RENDER
  // ==================================================

  return (
    <section className="alert-section">

      <div className="alert-header">
        <h2 className="section-title">
          🔔 {t('alert_log', lang)}

          {visibleAlerts.length > 0 && (
            <span className="alert-count">
              {visibleAlerts.length}
            </span>
          )}
        </h2>

        <div className="alert-header-right">
          {clearTime && (
            <span className="cleared-time">
              {t('alert_cleared_at', lang)}{' '}
              {formatDateTime(clearTime)}
            </span>
          )}

          {visibleAlerts.length > 0 && (
            <button
              className="clear-btn"
              onClick={onClear}
              type="button"
            >
              {t('alert_clear', lang)}
            </button>
          )}
	  <ServiceReport alerts={alerts} />
        </div>
      </div>

      <div className="alert-list">
        {visibleAlerts.length === 0 ? (
          <div className="no-alerts">
            <span
              style={{
                display: 'block',
                marginBottom: 8,
              }}
            >
              {t('alert_empty', lang)}
            </span>

            <span
              style={{
                color: 'var(--muted)',
                fontSize: 13,
              }}
            >
              {t('alert_empty_body', lang)}
            </span>
          </div>
        ) : (
          visibleAlerts.map(alert => (
            <AlertEntry
              key={alert.id}
              alert={alert}
              onFeedback={handleFeedback}
              onDismiss={alert => {
                handleFeedback(alert.sensor || alert.label || 'unknown', 'normal', alert.source)
                setDismissedAlertIds(prev => {
                  const next = new Set(prev)
                  next.add(String(alert.id))
                  return next
                })
              }}
            />
          ))
        )}
      </div>

    </section>
  )
}
