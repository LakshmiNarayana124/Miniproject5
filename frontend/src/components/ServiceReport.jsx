import { useState } from 'react'

// ── IntelliWatch logo for printable report ──
// Uses the official PNG. In the printed/PDF report we embed it via window.location.origin.
const getLogoImg = () =>
  `<img src="${window.location.origin}/intelliwatch-eye-logo-source.png" alt="IntelliWatch" width="72" height="49" style="display:inline-block;object-fit:contain;vertical-align:middle;background:transparent;" />`

// Legacy fallback kept for reference but not used
const LOGO_SVG_UNUSED = `<svg width="62" height="40" viewBox="0 0 186 120" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sr_outerEye" x1="0%" y1="20%" x2="100%" y2="80%">
      <stop offset="0%"   stop-color="#0a1a6e"/>
      <stop offset="40%"  stop-color="#1a3fc4"/>
      <stop offset="70%"  stop-color="#2563eb"/>
      <stop offset="100%" stop-color="#38bdf8"/>
    </linearGradient>
    <linearGradient id="sr_innerLid" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#38bdf8" stop-opacity="0"/>
      <stop offset="30%"  stop-color="#38bdf8"/>
      <stop offset="70%"  stop-color="#93c5fd"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="sr_lowerLid" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="#7c3aed"/>
      <stop offset="50%"  stop-color="#a855f7"/>
      <stop offset="100%" stop-color="#be185d"/>
    </linearGradient>
    <radialGradient id="sr_iris" cx="38%" cy="35%" r="62%">
      <stop offset="0%"   stop-color="#c4b5fd"/>
      <stop offset="25%"  stop-color="#7c3aed"/>
      <stop offset="60%"  stop-color="#4c1d95"/>
      <stop offset="100%" stop-color="#0f0520"/>
    </radialGradient>
    <linearGradient id="sr_gear" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#1d4ed8"/>
      <stop offset="100%" stop-color="#0a1a6e"/>
    </linearGradient>
    <linearGradient id="sr_bar1" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%"   stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#1d4ed8"/>
    </linearGradient>
    <linearGradient id="sr_bar2" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%"   stop-color="#60a5fa"/>
      <stop offset="100%" stop-color="#1e40af"/>
    </linearGradient>
    <linearGradient id="sr_bar3" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%"   stop-color="#93c5fd"/>
      <stop offset="100%" stop-color="#2563eb"/>
    </linearGradient>
  </defs>
  <path d="M4 60 Q20 20 70 14 Q100 10 130 20 Q155 28 182 60 Q155 92 130 100 Q100 110 70 106 Q20 100 4 60Z" fill="#0d1b6e" opacity="0.92"/>
  <path d="M14 60 Q28 30 70 24 Q100 18 128 28 Q150 36 172 60 Q150 84 128 92 Q100 102 70 96 Q28 90 14 60Z" fill="white"/>
  <path d="M4 60 Q20 20 70 14 Q100 10 130 20 Q155 28 182 60" fill="none" stroke="url(#sr_outerEye)" stroke-width="6" stroke-linecap="round"/>
  <path d="M4 60 Q20 100 70 106 Q100 110 130 100 Q155 92 182 60" fill="none" stroke="url(#sr_outerEye)" stroke-width="5" stroke-linecap="round"/>
  <path d="M18 54 Q35 28 70 22 Q100 17 128 30 Q148 38 168 56" fill="none" stroke="url(#sr_innerLid)" stroke-width="2.5" stroke-linecap="round" opacity="0.85"/>
  <path d="M16 64 Q34 92 70 100 Q100 106 128 96 Q152 88 170 68" fill="none" stroke="url(#sr_lowerLid)" stroke-width="4" stroke-linecap="round" opacity="0.9"/>
  <path d="M4 60 L18 50" fill="none" stroke="#0a1a6e" stroke-width="4" stroke-linecap="round"/>
  <circle cx="93" cy="60" r="28" fill="url(#sr_iris)"/>
  <circle cx="93" cy="60" r="28" fill="none" stroke="#6d28d9" stroke-width="1.5" opacity="0.6"/>
  <circle cx="93" cy="60" r="13" fill="#050112"/>
  <circle cx="83" cy="50" r="7" fill="white" fill-opacity="0.65"/>
  <circle cx="98" cy="53" r="3" fill="white" fill-opacity="0.3"/>
  <g transform="translate(148,36)">
    <path d="M-4,-22 L-4,-26 L4,-26 L4,-22 A22,22 0 0,1 10.6,-19.4 L13.4,-22.2 L19.1,-16.5 L16.3,-13.7 A22,22 0 0,1 19.4,-10.6 L23.4,-10.6 L23.4,-2.6 L19.4,-2.6 A22,22 0 0,1 19.4,2.6 L23.4,2.6 L23.4,10.6 L19.4,10.6 A22,22 0 0,1 16.3,13.7 L19.1,16.5 L13.4,22.2 L10.6,19.4 A22,22 0 0,1 4,22 L4,26 L-4,26 L-4,22 A22,22 0 0,1 -10.6,19.4 L-13.4,22.2 L-19.1,16.5 L-16.3,13.7 A22,22 0 0,1 -19.4,10.6 L-23.4,10.6 L-23.4,2.6 L-19.4,2.6 A22,22 0 0,1 -19.4,-2.6 L-23.4,-2.6 L-23.4,-10.6 L-19.4,-10.6 A22,22 0 0,1 -16.3,-13.7 L-19.1,-16.5 L-13.4,-22.2 L-10.6,-19.4 A22,22 0 0,1 -4,-22 Z" fill="url(#sr_gear)" opacity="0.95"/>
    <circle cx="0" cy="0" r="9" fill="white" opacity="0.15"/>
    <circle cx="0" cy="0" r="9" fill="none" stroke="#1d4ed8" stroke-width="1.5"/>
  </g>
  <rect x="128" y="4"  width="9" height="30" rx="2.5" fill="url(#sr_bar1)"/>
  <rect x="140" y="12" width="9" height="22" rx="2.5" fill="url(#sr_bar2)"/>
  <rect x="152" y="18" width="9" height="16" rx="2.5" fill="url(#sr_bar3)"/>
</svg>`

// ── Non-box action button style ──
const linkBtnStyle = {
  background: 'none',
  border: 'none',
  padding: '4px 2px',
  color: 'var(--accent, #60a5fa)',
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
  textDecoration: 'none',
  letterSpacing: '0.01em',
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
}

const dangerBtnStyle = {
  ...linkBtnStyle,
  color: '#f87171',
}

// ── Build printable HTML ──
function buildReportHTML(data, alerts) {
  const rows = alerts.map((a, i) => `
    <tr>
      <td>${a.time ?? '—'}</td>
      <td>${a.label || a.sensor || '—'}</td>
      <td>${a.value !== undefined ? `${a.value} ${a.unit ?? ''}` : a.message ?? '—'}</td>
      <td style="color:${a.status === 'critical' ? '#dc2626' : a.status === 'warning' ? '#d97706' : '#16a34a'};font-weight:600">
        ${a.status?.toUpperCase() ?? '—'}
      </td>
    </tr>`).join('')

  return `<!doctype html>
<html><head><meta charset="utf-8"/>
<title>IntelliWatch Service Report ${data.reportId}</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',Arial,sans-serif;color:#111;background:#fff;padding:28px 36px;font-size:13px}
  .header{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #1d4ed8;padding-bottom:16px;margin-bottom:20px}
  .brand{display:flex;align-items:center;gap:12px}
  .brand h1{font-size:22px;color:#1d4ed8;letter-spacing:1px}
  .brand p{font-size:11px;color:#555;margin-top:2px}
  .heading h2{font-size:16px;text-align:right;color:#111}
  .heading p{font-size:11px;color:#555;text-align:right}
  .meta{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;background:#f1f5f9;border-radius:6px;padding:12px 16px;margin-bottom:20px}
  .meta div strong{display:block;font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px}
  section{margin-bottom:20px}
  h3{font-size:13px;color:#1d4ed8;border-bottom:1px solid #e2e8f0;padding-bottom:4px;margin-bottom:12px}
  .summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}
  .summary div{text-align:center;padding:10px;border:1px solid #e2e8f0;border-radius:6px}
  .summary strong{display:block;font-size:22px;font-weight:700;color:#1d4ed8}
  .summary span{font-size:11px;color:#555}
  table{width:100%;border-collapse:collapse;font-size:12px}
  th{background:#1d4ed8;color:#fff;padding:7px 10px;text-align:left;font-weight:600}
  td{padding:6px 10px;border-bottom:1px solid #e2e8f0}
  tr:nth-child(even) td{background:#f8fafc}
  textarea-val{white-space:pre-wrap;border:1px solid #e2e8f0;border-radius:4px;padding:10px;font-size:12px;min-height:60px;width:100%;display:block;background:#fafafa}
  .sigs{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:16px}
  .sigs div{border-top:1px solid #334155;padding-top:6px;font-size:11px;color:#555;text-align:center}
  footer{margin-top:28px;padding-top:10px;border-top:1px solid #e2e8f0;display:flex;justify-content:space-between;font-size:10px;color:#94a3b8}
  .field-val{font-size:13px;padding:4px 0;border-bottom:1px solid #e2e8f0;min-height:24px;margin-bottom:10px}
  label-name{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:2px}
  @media print{body{padding:12px 18px}}
</style>
</head><body>
<div class="header">
  <div class="brand">
    ${getLogoImg()}
    <div><h1>INTELLIWATCH</h1><p>Real-Time Anomaly Detection &amp; Decision Support System</p></div>
  </div>
  <div class="heading"><h2>Equipment Service Report</h2><p>Alert &amp; Maintenance Record</p></div>
</div>

<div class="meta">
  <div><strong>Report ID</strong>${data.reportId}</div>
  <div><strong>Report Date</strong>${data.reportDate}</div>
  <div><strong>Prepared By</strong>${data.preparedBy || '—'}</div>
</div>

<section>
  <h3>1. Equipment Information</h3>
  <span style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:2px">Equipment / Machine Name</span>
  <div class="field-val">${data.equipment || '—'}</div>
  <span style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:2px">Reporting Period</span>
  <div class="field-val">${data.period || '—'}</div>
</section>

<section>
  <h3>2. Alert Summary</h3>
  <div class="summary">
    <div><strong>${alerts.length}</strong><span>Total Alerts</span></div>
    <div><strong>${alerts.filter(a => a.status === 'warning').length}</strong><span>Warnings</span></div>
    <div><strong>${alerts.filter(a => a.status === 'critical').length}</strong><span>Critical</span></div>
  </div>
  <table><thead><tr><th>Time</th><th>Sensor</th><th>Reading</th><th>Status</th></tr></thead>
  <tbody>${rows}</tbody></table>
</section>

<section>
  <h3>3. Findings / Machine Condition</h3>
  <div class="textarea-val">${data.findings || '—'}</div>
</section>

<section>
  <h3>4. Recommended / Completed Actions</h3>
  <div class="textarea-val">${data.actions || '—'}</div>
</section>

<section>
  <h3>5. Service Notes</h3>
  <div class="textarea-val">${data.notes || '—'}</div>
</section>

<section>
  <h3>6. Review &amp; Sign-off</h3>
  <span style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:2px">Reviewed By</span>
  <div class="field-val">${data.reviewedBy || '—'}</div>
  <div class="sigs">
    <div>Technician Signature</div>
    <div>Reviewer Signature</div>
    <div>Date</div>
  </div>
</section>

<footer>
  <span>${data.reportId}</span>
  <span>INTELLIWATCH</span>
  <span>System-generated report — not a certified inspection or compliance document.</span>
</footer>
</body></html>`
}

// ── Build Word-compatible .doc HTML ──
function buildWordDoc(data, alerts) {
  // Word opens HTML with this MIME type as an editable document
  const html = buildReportHTML(data, alerts)
  return html
    .replace('<html>', '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">')
    .replace('</head>', `<xml><w:WordDocument><w:View>Print</w:View></w:WordDocument></xml></head>`)
}

export default function ServiceReport({ alerts = [] }) {
  const [open, setOpen] = useState(false)
  const [equipment, setEquipment] = useState('')
  const [preparedBy, setPreparedBy] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('iw_user') || '{}').username || ''
    } catch { return '' }
  })
  const [period, setPeriod] = useState('')
  const [findings, setFindings] = useState('')
  const [actions, setActions] = useState('')
  const [notes, setNotes] = useState('')
  const [reviewedBy, setReviewedBy] = useState('')
  const reportDate = new Date().toLocaleDateString()
  const [reportId] = useState(() => `IW-SR-${Date.now().toString().slice(-8)}`)

  const data = { reportId, reportDate, equipment, preparedBy, period, findings, actions, notes, reviewedBy }

  function getHTML() { return buildReportHTML(data, alerts) }

  // Print / PDF via browser print dialog
  function handlePrint() {
    const w = window.open('', '_blank')
    if (!w) { alert('Allow pop-ups to print / save PDF.'); return }
    w.document.open()
    w.document.write(getHTML())
    w.document.close()
    w.onload = () => { w.focus(); w.print() }
  }

  // Direct PDF download (uses print-to-PDF silently where supported)
  function handlePDFDownload() {
    const blob = new Blob([getHTML()], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${reportId}.html`
    a.click()
    URL.revokeObjectURL(url)
    // Open in new tab so user can Ctrl+P → Save as PDF
    const w = window.open(url, '_blank')
    if (w) { setTimeout(() => { w.focus(); w.print() }, 800) }
  }

  // Editable Word .doc download
  function handleWordDownload() {
    const blob = new Blob([buildWordDoc(data, alerts)], {
      type: 'application/msword',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${reportId}.doc`
    a.click()
    URL.revokeObjectURL(url)
  }

  // ── Trigger button — plain text link, no box ──
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        style={{
          background: 'none',
          border: 'none',
          padding: '0 0 0 6px',
          color: 'var(--accent, #60a5fa)',
          fontSize: 13,
          fontWeight: 500,
          cursor: 'pointer',
          letterSpacing: '0.01em',
          opacity: 0.9,
        }}
      >
        📋 Service Report ↗
      </button>
    )
  }

  // ── Report panel ──
  return (
    <div className="iw-report-overlay">
      <div className="iw-report-panel">

        {/* Top action bar — all non-box */}
        <div className="iw-report-actions" style={{ display:'flex', gap:16, alignItems:'center', flexWrap:'wrap', padding:'8px 0 12px' }}>
          <button type="button" style={linkBtnStyle} onClick={handlePrint}>
            🖨️ Print / PDF Preview
          </button>
          <button type="button" style={linkBtnStyle} onClick={handlePDFDownload}>
            ⬇️ Download PDF
          </button>
          <button type="button" style={linkBtnStyle} onClick={handleWordDownload}>
            📝 Download Word (.doc)
          </button>
          <button type="button" style={{ ...dangerBtnStyle, marginLeft:'auto' }} onClick={() => setOpen(false)}>
            ✕ Close
          </button>
        </div>

        <div id="iw-service-report">

          <header className="iw-report-header">
            <div className="iw-report-brand">
              {/* Inline logo — transparent background, no box */}
              <div
                style={{ lineHeight:0 }}
                dangerouslySetInnerHTML={{ __html: LOGO_SVG }}
              />
              <div>
                <h1>INTELLIWATCH</h1>
                <p>Real-Time Anomaly Detection &amp; Decision Support System</p>
              </div>
            </div>
            <div className="iw-report-heading">
              <h2>Equipment Service Report</h2>
              <p>Alert &amp; Maintenance Record</p>
            </div>
          </header>

          <div className="iw-report-meta">
            <div><strong>Report ID</strong><span>{reportId}</span></div>
            <div><strong>Report Date</strong><span>{reportDate}</span></div>
            <div><strong>Prepared By</strong><span>{preparedBy || 'Not specified'}</span></div>
          </div>

          <section className="iw-report-section">
            <h3>1. Equipment Information</h3>
            <div className="iw-report-fields">
              <label>Equipment / Machine Name
                <input value={equipment} onChange={e => setEquipment(e.target.value)} placeholder="Enter equipment name"/>
              </label>
              <label>Reporting Period
                <input value={period} onChange={e => setPeriod(e.target.value)} placeholder="e.g. 01 Nov – 22 Nov 2026"/>
              </label>
              <label>Technician / Prepared By
                <input value={preparedBy} onChange={e => setPreparedBy(e.target.value)} placeholder="Name"/>
              </label>
            </div>
          </section>

          <section className="iw-report-section">
            <h3>2. Alert Summary</h3>
            <div className="iw-report-summary">
              <div><strong>{alerts.length}</strong><span>Total Alerts</span></div>
              <div><strong>{alerts.filter(a => a.status === 'warning').length}</strong><span>Warnings</span></div>
              <div><strong>{alerts.filter(a => a.status === 'critical').length}</strong><span>Critical</span></div>
            </div>
            <table className="iw-report-table">
              <thead><tr><th>Time</th><th>Sensor</th><th>Reading</th><th>Status</th></tr></thead>
              <tbody>
                {alerts.map((alert, i) => (
                  <tr key={alert.id ?? i}>
                    <td>{alert.time ?? '—'}</td>
                    <td>{alert.label || alert.sensor || '—'}</td>
                    <td>{alert.value !== undefined ? `${alert.value} ${alert.unit ?? ''}` : alert.message ?? '—'}</td>
                    <td>{alert.status?.toUpperCase() ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="iw-report-section">
            <h3>3. Findings / Machine Condition</h3>
            <textarea value={findings} onChange={e => setFindings(e.target.value)} placeholder="Record observed machine condition and findings..."/>
          </section>

          <section className="iw-report-section">
            <h3>4. Recommended / Completed Actions</h3>
            <textarea value={actions} onChange={e => setActions(e.target.value)} placeholder="Record inspection, maintenance or corrective actions..."/>
          </section>

          <section className="iw-report-section">
            <h3>5. Service Notes</h3>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Additional service notes..."/>
          </section>

          <section className="iw-report-section">
            <h3>6. Review &amp; Sign-off</h3>
            <label>Reviewed By
              <input value={reviewedBy} onChange={e => setReviewedBy(e.target.value)} placeholder="Reviewer / Maintenance Engineer"/>
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
            <span>System-generated report — not a certified inspection or compliance document.</span>
          </footer>

        </div>
      </div>
    </div>
  )
}
