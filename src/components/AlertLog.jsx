import { formatDateTime } from '../sensors'

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

export default function AlertLog({ alerts, onClear, clearTime }) {
  return (
    <section className="alert-section">
      <div className="alert-header">
        <h2 className="section-title">
          🔔 Alert Log
          {alerts.length > 0 && <span className="alert-count">{alerts.length}</span>}
        </h2>
        <div className="alert-header-right">
          {clearTime && (
            <span className="cleared-time">Cleared at {formatDateTime(clearTime)}</span>
          )}
          {alerts.length > 0 && (
            <button className="clear-btn" onClick={onClear}>Clear</button>
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
  )
}
