
import { formatDateTime } from '../sensors'
import { t } from '../i18n'
import useLang from '../useLang'
import { mlEngine } from '../mlEngine'

// ==================================================
// ALERT ENTRY — with confirm/dismiss feedback buttons
// ==================================================

function AlertEntry({ alert, onFeedback }) {
  const lang = useLang()
  return (
    <div className={`alert-entry alert-${alert.status}`}>
      <span className="alert-dot" />
      <div className="alert-body">
        <span className="alert-sensor">{alert.label || alert.sensor}</span>
        <span className="alert-msg">
          {alert.value !== undefined
            ? `${Number(alert.value).toFixed?.(3) ?? alert.value} ${alert.unit ?? ''} — ${alert.status?.toUpperCase()}`
            : alert.message}
        </span>
      </div>
      <span className="alert-time">{alert.time}</span>
      {/* Feedback buttons — let maintenance engineers confirm/dismiss alerts */}
      {(alert.status === 'warning' || alert.status === 'critical') && (
        <div className="alert-feedback" role="group" aria-label="Feedback">
          <button
            className="alert-fb-btn alert-fb-confirm"
            title="Confirm anomaly"
            aria-label="Confirm anomaly"
            onClick={() => onFeedback?.(alert.sensor, 'anomaly')}
          >✓</button>
          <button
            className="alert-fb-btn alert-fb-dismiss"
            title="Dismiss (false positive)"
            aria-label="Dismiss"
            onClick={() => onFeedback?.(alert.sensor, 'normal')}
          >✕</button>
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
}) {
  const hookLang = useLang()
  const lang = propLang || hookLang

  function handleFeedback(sensorKey, label) {
    // Update the browser-side ML engine
    mlEngine.feedback(sensorKey, label)
    // Post to backend learning endpoint (ADMIN, OPERATOR, and MAINTENANCE_ENGINEER)
    const token = sessionStorage.getItem('iw_token')
    if (token && token !== 'demo-offline') {
      const mlState = mlEngine.getState(sensorKey)
      if (mlState) {
        const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
        fetch(`${API}/learning/label`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            label,
            feature_vector: [mlState.emaMean ?? 0, mlState.emaStd ?? 0, mlState.score ?? 0],
            model_version: 'browser-v1',
          }),
        }).catch(err => console.warn('[AlertLog] label POST failed:', err))
      }
    }
  }

  return (
    <section className="alert-section">
      <div className="alert-header">
        <h2 className="section-title">
          🔔 {t('alert_log', lang)}
          {alerts.length > 0 && (
            <span className="alert-count">{alerts.length}</span>
          )}
        </h2>

        <div className="alert-header-right">
          {clearTime && (
            <span className="cleared-time">
              {t('alert_cleared_at', lang)} {formatDateTime(clearTime)}
            </span>
          )}
          {alerts.length > 0 && (
            <button className="clear-btn" onClick={onClear}>
              {t('alert_clear', lang)}
            </button>
          )}
        </div>
      </div>

      <div className="alert-list">
        {alerts.length === 0 ? (
          <div className="no-alerts">
            <span style={{ display: 'block', marginBottom: 8 }}>
              {t('alert_empty', lang)}
            </span>
            <span style={{ color: 'var(--muted)', fontSize: 13 }}>
              {t('alert_empty_body', lang)}
            </span>
          </div>
        ) : (
          alerts.map(alert => (
            <AlertEntry key={alert.id} alert={alert} onFeedback={handleFeedback} />
          ))
        )}
      </div>
    </section>
  )
}
