
import { formatDateTime } from '../sensors'

// ==================================================
// ALERT ENTRY
// ==================================================

function AlertEntry({ alert }) {
  return (
    <div className={`alert-entry alert-${alert.status}`}>
      <span className="alert-dot" />

      <div className="alert-body">
        <span className="alert-sensor">{alert.sensor}</span>
        <span className="alert-msg">{alert.message}</span>
      </div>

      <span className="alert-time">{alert.time}</span>
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
}) {
  return (
    <section className="alert-section">
      <div className="alert-header">
        <h2 className="section-title">
          🔔 Alert Log

          {alerts.length > 0 && (
            <span className="alert-count">
              {alerts.length}
            </span>
          )}
        </h2>

        <div className="alert-header-right">
          {clearTime && (
            <span className="cleared-time">
              Cleared at {formatDateTime(clearTime)}
            </span>
          )}

          {alerts.length > 0 && (
            <button
              className="clear-btn"
              onClick={onClear}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="alert-list">
        {alerts.length === 0 ? (
          <div className="no-alerts">
            <span style={{ display: 'block', marginBottom: 8 }}>
              🔌 Awaiting IoT Signal
            </span>

            <span style={{ color: 'var(--muted)', fontSize: 13 }}>
              Alert monitoring will begin when real sensor data
              is received and analysed by IntelliWatch.
            </span>
          </div>
        ) : (
          alerts.map(alert => (
            <AlertEntry
              key={alert.id}
              alert={alert}
            />
          ))
        )}
      </div>
    </section>
  )
}
