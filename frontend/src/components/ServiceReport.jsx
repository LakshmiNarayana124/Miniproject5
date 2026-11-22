import React from 'react'

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') {
    return '\u2014'
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }

  return String(value)
}

export default function ServiceReport({ alerts = [] }) {
  function handlePrintReport() {
    if (!Array.isArray(alerts) || alerts.length === 0) {
      window.alert('There are no alerts to include in the report.')
      return
    }

    const username = (() => {
      try {
        return JSON.parse(
          sessionStorage.getItem('iw_user') || '{}'
        ).username || 'User'
      } catch {
        return 'User'
      }
    })()

    const generatedAt = new Date().toLocaleString()

    const rows = alerts.map((alert, index) => {
      const time = formatValue(alert.time ?? alert.timestamp)
      const sensor = formatValue(alert.sensor)
      const value = formatValue(alert.value)
      const unit = formatValue(alert.unit)
      const status = formatValue(alert.status)
      const score = formatValue(alert.score)
      const source = formatValue(alert.source)

      return `
        <tr>
          <td>${index + 1}</td>
          <td>${escapeHtml(time)}</td>
          <td>${escapeHtml(sensor)}</td>
          <td>${escapeHtml(value)} ${escapeHtml(unit)}</td>
          <td>${escapeHtml(status)}</td>
          <td>${escapeHtml(score)}</td>
          <td>${escapeHtml(source)}</td>
        </tr>
      `
    }).join('')

    const reportHtml = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <title>IntelliWatch Service Report</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            color: #172033;
            margin: 28px;
          }

          h1 {
            margin-bottom: 4px;
          }

          .subtitle {
            color: #5b6475;
            margin-bottom: 24px;
          }

          .summary {
            display: flex;
            gap: 24px;
            margin: 20px 0;
          }

          .summary div {
            border: 1px solid #d8dee9;
            padding: 12px 16px;
            border-radius: 8px;
          }

          table {
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
          }

          th, td {
            border: 1px solid #d8dee9;
            padding: 8px;
            text-align: left;
            overflow-wrap: anywhere;
          }

          th {
            background: #eef2f7;
          }

          footer {
            margin-top: 24px;
            color: #687386;
            font-size: 10px;
          }

          @media print {
            body {
              margin: 12mm;
            }

            button {
              display: none;
            }

            thead {
              display: table-header-group;
            }

            tr {
              page-break-inside: avoid;
            }
          }
        </style>
      </head>
      <body>
        <h1>IntelliWatch</h1>
        <div class="subtitle">Equipment Alert Service Report</div>

        <div>
          <strong>Generated:</strong> ${escapeHtml(generatedAt)}<br>
          <strong>Prepared for:</strong> ${escapeHtml(username)}<br>
          <strong>Alert count:</strong> ${alerts.length}
        </div>

        <div class="summary">
          <div>
            <strong>Total Alerts</strong><br>
            ${alerts.length}
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Timestamp</th>
              <th>Sensor</th>
              <th>Value</th>
              <th>Status</th>
              <th>ML Score</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>

        <footer>
          This report contains the alert records available in the current
          IntelliWatch session. It is an exported operational record and
          does not independently certify equipment condition or compliance.
        </footer>

        <script>
          window.addEventListener('load', function () {
            setTimeout(function () {
              window.print()
            }, 300)
          })
        </script>
      </body>
      </html>
    `

    const printWindow = window.open(
      '',
      '_blank',
      'width=1100,height=800'
    )

    if (!printWindow) {
      window.alert(
        'The report window was blocked. Allow pop-ups for IntelliWatch and try again.'
      )
      return
    }

    printWindow.document.open()
    printWindow.document.write(reportHtml)
    printWindow.document.close()
  }

  return (
    <button
      className="export-btn"
      type="button"
      onClick={handlePrintReport}
      title="Print or save alert service report as PDF"
    >
      Service Report / PDF
    </button>
  )
}