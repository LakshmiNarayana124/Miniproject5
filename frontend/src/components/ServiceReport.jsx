import { useState } from 'react'

export default function ServiceReport({ alerts = [] }) {
  const [open, setOpen] = useState(false)

  const [equipment, setEquipment] = useState('')

  const [preparedBy, setPreparedBy] = useState(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem('iw_user') || '{}'
      ).username || ''
    } catch {
      return ''
    }
  })

  const [period, setPeriod] = useState('')
  const [findings, setFindings] = useState('')
  const [actions, setActions] = useState('')
  const [notes, setNotes] = useState('')
  const [reviewedBy, setReviewedBy] = useState('')

  const reportDate = new Date().toLocaleDateString()

  const [reportId] = useState(
  () => `IW-SR-${Date.now().toString().slice(-8)}`
)

  const criticalCount = alerts.filter(
    alert => alert.status === 'critical'
  ).length

  const warningCount = alerts.filter(
    alert => alert.status === 'warning'
  ).length

  function printReport() {
    window.print()
  }

  if (!open) {
    return (
      <button
        type="button"
        className="export-btn"
        onClick={() => setOpen(true)}
      >
        Service Report
      </button>
    )
  }

  return (
    <div className="iw-report-overlay">
      <div className="iw-report-panel">

        <div className="iw-report-actions">
          <button
            type="button"
            className="export-btn"
            onClick={() => setOpen(false)}
          >
            Close
          </button>

          <button
            type="button"
            className="export-btn"
            onClick={printReport}
          >
            Print / Save PDF
          </button>
        </div>

        <div id="iw-service-report">

          <header className="iw-report-header">
            <div className="iw-report-brand">
              <div className="iw-report-logo">IW</div>

              <div>
                <h1>INTELLIWATCH</h1>
                <p>
                  Real-Time Anomaly Detection &amp;
                  Decision Support System
                </p>
              </div>
            </div>

            <div className="iw-report-heading">
              <h2>Equipment Service Report</h2>
              <p>Alert &amp; Maintenance Record</p>
            </div>
          </header>

          <div className="iw-report-meta">
            <div>
              <strong>Report ID</strong>
              <span>{reportId}</span>
            </div>

            <div>
              <strong>Report Date</strong>
              <span>{reportDate}</span>
            </div>

            <div>
              <strong>Prepared By</strong>
              <span>{preparedBy || 'Not specified'}</span>
            </div>
          </div>

          <section className="iw-report-section">
            <h3>1. Equipment Information</h3>

            <div className="iw-report-fields">
              <label>
                Equipment / Machine Name
                <input
                  value={equipment}
                  onChange={e => setEquipment(e.target.value)}
                  placeholder="Enter equipment name"
                />
              </label>

              <label>
                Reporting Period
                <input
                  value={period}
                  onChange={e => setPeriod(e.target.value)}
                  placeholder="e.g. 01 Nov – 22 Nov 2026"
                />
              </label>

              <label>
                Technician / Prepared By
                <input
                  value={preparedBy}
                  onChange={e => setPreparedBy(e.target.value)}
                  placeholder="Name"
                />
              </label>
            </div>
          </section>

          <section className="iw-report-section">
            <h3>2. Alert Summary</h3>

            <div className="iw-report-summary">
              <div>
                <strong>{alerts.length}</strong>
                <span>Total Alerts</span>
              </div>

              <div>
                <strong>{warningCount}</strong>
                <span>Warnings</span>
              </div>

              <div>
                <strong>{criticalCount}</strong>
                <span>Critical Alerts</span>
              </div>
            </div>

            <table className="iw-report-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Sensor</th>
                  <th>Reading</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {alerts.map((alert, index) => (
                  <tr key={alert.id ?? index}>
                    <td>{alert.time ?? '—'}</td>

                    <td>
                      {alert.label || alert.sensor || '—'}
                    </td>

                    <td>
                      {alert.value !== undefined
                        ? `${alert.value} ${alert.unit ?? ''}`
                        : alert.message ?? '—'}
                    </td>

                    <td>
                      {alert.status?.toUpperCase() ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="iw-report-section">
            <h3>3. Findings / Machine Condition</h3>

            <textarea
              value={findings}
              onChange={e => setFindings(e.target.value)}
              placeholder="Record observed machine condition and findings..."
            />
          </section>

          <section className="iw-report-section">
            <h3>4. Recommended / Completed Actions</h3>

            <textarea
              value={actions}
              onChange={e => setActions(e.target.value)}
              placeholder="Record inspection, maintenance or corrective actions..."
            />
          </section>

          <section className="iw-report-section">
            <h3>5. Service Notes</h3>

            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Additional service notes..."
            />
          </section>

          <section className="iw-report-section">
            <h3>6. Review &amp; Sign-off</h3>

            <label>
              Reviewed By
              <input
                value={reviewedBy}
                onChange={e => setReviewedBy(e.target.value)}
                placeholder="Reviewer / Maintenance Engineer"
              />
            </label>

            <div className="iw-report-signatures">
              <div>Technician Signature</div>
              <div>Reviewer Signature</div>
              <div>Date</div>
            </div>
          </section>

          <footer className="iw-report-footer">
            <span>{reportId}</span>
            <span>INTELLIWATCH</span>
            <span>
              System-generated report — not a certified
              inspection or compliance document.
            </span>
          </footer>

        </div>
      </div>
    </div>
  )
}