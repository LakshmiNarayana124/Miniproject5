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

function AlertEntry({ alert, onFeedback }) {
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
              alert.sensor,
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
            onClick={() => onFeedback?.(
              alert.sensor,
              'normal',
              alert.source
            )}
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
  // EXPORT — CSV + JSON (ISO traceability)
  // Implements IEC 62443 / ISO 55000 audit trail
  // export.  No backend round-trip; runs entirely
  // in the browser using the Blob / anchor trick.
  // ==================================================

  function exportAlerts() {
    if (!alerts.length) return

    const ts   = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    const user = (() => {
      try { return JSON.parse(sessionStorage.getItem('iw_user') || '{}').username || 'unknown' }
      catch { return 'unknown' }
    })()

    // ---- CSV ----
    const csvHeader = 'timestamp,sensor,value,unit,status,ml_score,model_version,source\n'
    const csvRows = alerts.map(a => [
      a.time ?? '',
      a.sensor ?? '',
      a.value !== undefined ? a.value : '',
      a.unit   ?? '',
      a.status ?? '',
      a.score  !== undefined ? a.score  : '',
      a.model_version ?? 'browser-v1',
      a.source  ?? '',
    ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')

    const csvBlob = new Blob(
      [csvHeader + csvRows],
      { type: 'text/csv;charset=utf-8;' }
    )
    const csvUrl = URL.createObjectURL(csvBlob)
    const csvLink = document.createElement('a')
    csvLink.href = csvUrl
    csvLink.download = `IntelliWatch_AlertLog_${user}_${ts}.csv`
    csvLink.click()
    URL.revokeObjectURL(csvUrl)

    // ---- JSON ----
    const jsonPayload = {
      export_timestamp: new Date().toISOString(),
      exported_by: user,
      standard: 'IEC 62443 / ISO 55000 audit trail',
      model_version: 'browser-v1',
      alert_count: alerts.length,
      alerts,
    }
    const jsonBlob = new Blob(
      [JSON.stringify(jsonPayload, null, 2)],
      { type: 'application/json' }
    )
    const jsonUrl = URL.createObjectURL(jsonBlob)
    const jsonLink = document.createElement('a')
    jsonLink.href = jsonUrl
    jsonLink.download = `IntelliWatch_AlertLog_${user}_${ts}.json`
    jsonLink.click()
    URL.revokeObjectURL(jsonUrl)
  }


  // ==================================================
  // RENDER
  // ==================================================

  return (
    <section className="alert-section">

      <div className="alert-header">
        <h2 className="section-title">
          🔔 {t('alert_log', lang)}

          {alerts.length > 0 && (
            <span className="alert-count">
              {alerts.length}
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

          {alerts.length > 0 && (
            <>
              <button
                className="export-btn"
                onClick={exportAlerts}
                type="button"
                title="Export alert log as CSV + JSON (IEC 62443 audit trail)"
              >
                ⬇ Export
              </button>
	      <ServiceReport alerts={alerts} />
              <button
                className="clear-btn"
                onClick={onClear}
                type="button"
              >
                {t('alert_clear', lang)}
              </button>
            </>
          )}
        </div>
      </div>

      <div className="alert-list">
        {alerts.length === 0 ? (
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
          alerts.map(alert => (
            <AlertEntry
              key={alert.id}
              alert={alert}
              onFeedback={handleFeedback}
            />
          ))
        )}
      </div>

    </section>
  )
}