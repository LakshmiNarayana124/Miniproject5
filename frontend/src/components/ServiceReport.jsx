import { useState } from 'react'
import { jsPDF } from 'jspdf'
import {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from 'docx'
import './ServiceReport.css'

const DASH = '\u2014'

function safeFileName(value) {
  return String(value || 'IntelliWatch-Service-Report')
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-')
    .replace(/\s+/g, '-')
    .slice(0, 90)
}

function display(value) {
  return value === undefined || value === null || String(value).trim() === ''
    ? DASH
    : String(value)
}

function alertReading(alert) {
  if (alert.value !== undefined && alert.value !== null) {
    return `${alert.value}${alert.unit ? ` ${alert.unit}` : ''}`
  }
  return alert.message || DASH
}

function alertSensor(alert) {
  return alert.label || alert.sensor || DASH
}

function alertStatus(alert) {
  return String(alert.status || DASH).toUpperCase()
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1500)
}

function addPdfText(doc, text, x, y, width, options = {}) {
  const lines = doc.splitTextToSize(String(text), width)
  doc.text(lines, x, y, options)
  return y + lines.length * (options.lineHeight || 5) + 2
}

function ensurePdfSpace(doc, y, needed = 18) {
  if (y + needed > 275) {
    doc.addPage()
    return 18
  }
  return y
}

function pdfSection(doc, title, y) {
  y = ensurePdfSpace(doc, y, 16)
  doc.setFillColor(20, 48, 78)
  doc.roundedRect(14, y - 5, 182, 9, 1.5, 1.5, 'F')
  doc.setTextColor(255, 255, 255)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(10)
  doc.text(title, 18, y + 1)
  doc.setTextColor(35, 48, 62)
  return y + 11
}

function pdfLabelValue(doc, label, value, x, y, width) {
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(8)
  doc.setTextColor(95, 109, 125)
  doc.text(label.toUpperCase(), x, y)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(10)
  doc.setTextColor(35, 48, 62)
  const lines = doc.splitTextToSize(display(value), width)
  doc.text(lines, x, y + 5)
  return y + 5 + lines.length * 4.5 + 5
}

function buildPdf(data) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })
  const pageWidth = 210
  const margin = 14
  const contentWidth = pageWidth - margin * 2
  let y = 18

  doc.setFillColor(15, 38, 65)
  doc.rect(0, 0, pageWidth, 39, 'F')
  doc.setFillColor(43, 153, 184)
  doc.roundedRect(margin, 10, 16, 16, 3, 3, 'F')
  doc.setTextColor(255, 255, 255)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(12)
  doc.text('IW', margin + 8, 20, { align: 'center' })
  doc.setFontSize(17)
  doc.text('INTELLIWATCH', 34, 16)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.text('REAL-TIME ANOMALY DETECTION & DECISION SUPPORT', 34, 22)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(12)
  doc.text('EQUIPMENT SERVICE REPORT', margin, 32)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.text('Maintenance record | Generated report', pageWidth - margin, 32, { align: 'right' })

  y = 47
  doc.setDrawColor(220, 228, 236)
  doc.setFillColor(247, 249, 252)
  doc.roundedRect(margin, y - 4, contentWidth, 23, 2, 2, 'FD')
  pdfLabelValue(doc, 'Report ID', data.reportId, margin + 4, y + 1, 48)
  pdfLabelValue(doc, 'Report Date', data.reportDate, margin + 63, y + 1, 38)
  pdfLabelValue(doc, 'Prepared By', data.preparedBy, margin + 113, y + 1, 55)
  y += 27

  y = pdfSection(doc, '01  EQUIPMENT INFORMATION', y)
  const col = contentWidth / 2
  y = pdfLabelValue(doc, 'Equipment / Machine', data.equipment, margin + 2, y, col - 8)
  const yRight = pdfLabelValue(doc, 'Reporting Period', data.period, margin + col + 2, y - 16, col - 8)
  y = Math.max(y, yRight) + 1

  y = pdfSection(doc, '02  ALERT SUMMARY', y)
  const cards = [
    ['TOTAL ALERTS', data.alerts.length, [28, 91, 128]],
    ['WARNINGS', data.warningCount, [211, 143, 45]],
    ['CRITICAL', data.criticalCount, [190, 62, 67]],
  ]
  const cardGap = 4
  const cardW = (contentWidth - cardGap * 2) / 3
  cards.forEach((card, i) => {
    const x = margin + i * (cardW + cardGap)
    doc.setFillColor(247, 249, 252)
    doc.setDrawColor(225, 231, 238)
    doc.roundedRect(x, y - 2, cardW, 17, 2, 2, 'FD')
    doc.setTextColor(...card[2])
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(15)
    doc.text(String(card[1]), x + 5, y + 6)
    doc.setFontSize(7)
    doc.text(card[0], x + cardW - 4, y + 5, { align: 'right' })
  })
  y += 22

  const tableRows = data.alerts.length
    ? data.alerts.map(a => [display(a.time), alertSensor(a), alertReading(a), alertStatus(a)])
    : [[DASH, 'No alert records', 'No readings', '—']]
  const columns = [
    { title: 'TIME', width: 31 },
    { title: 'SENSOR', width: 48 },
    { title: 'READING / DETAILS', width: 68 },
    { title: 'STATUS', width: 35 },
  ]
  const drawTableHeader = () => {
    doc.setFillColor(231, 238, 245)
    doc.rect(margin, y - 4, contentWidth, 8, 'F')
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(7)
    doc.setTextColor(40, 58, 77)
    let x = margin + 2
    columns.forEach(c => {
      doc.text(c.title, x, y + 1)
      x += c.width
    })
    y += 9
  }
  drawTableHeader()
  tableRows.forEach((row, idx) => {
    const wrapped = row.map((value, i) => doc.splitTextToSize(String(value), columns[i].width - 4))
    const rowHeight = Math.max(8, ...wrapped.map(lines => lines.length * 4 + 3))
    y = ensurePdfSpace(doc, y, rowHeight + 3)
    if (y === 18) drawTableHeader()
    if (idx % 2 === 0) {
      doc.setFillColor(250, 251, 253)
      doc.rect(margin, y - 4, contentWidth, rowHeight, 'F')
    }
    doc.setDrawColor(232, 237, 242)
    doc.line(margin, y + rowHeight - 4, margin + contentWidth, y + rowHeight - 4)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8)
    doc.setTextColor(45, 58, 72)
    let x = margin + 2
    wrapped.forEach((lines, i) => {
      doc.text(lines, x, y)
      x += columns[i].width
    })
    y += rowHeight
  })
  y += 4

  const freeTextSections = [
    ['03  FINDINGS / MACHINE CONDITION', data.findings],
    ['04  RECOMMENDED / COMPLETED ACTIONS', data.actions],
    ['05  SERVICE NOTES', data.notes],
  ]
  freeTextSections.forEach(([title, value]) => {
    y = pdfSection(doc, title, y)
    const content = display(value)
    const lines = doc.splitTextToSize(content, contentWidth - 8)
    const blockHeight = Math.max(14, lines.length * 4.5 + 8)
    y = ensurePdfSpace(doc, y, blockHeight + 3)
    doc.setDrawColor(220, 228, 236)
    doc.setFillColor(252, 253, 254)
    doc.roundedRect(margin, y - 3, contentWidth, blockHeight, 2, 2, 'FD')
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(45, 58, 72)
    doc.text(lines, margin + 4, y + 3)
    y += blockHeight + 4
  })

  y = pdfSection(doc, '06  REVIEW & SIGN-OFF', y)
  y = pdfLabelValue(doc, 'Reviewed By', data.reviewedBy, margin + 2, y, contentWidth - 4)
  y = ensurePdfSpace(doc, y, 24)
  const sigY = y + 10
  const sigW = (contentWidth - 12) / 3
  ;['Technician Signature', 'Reviewer Signature', 'Date'].forEach((label, i) => {
    const x = margin + i * (sigW + 6)
    doc.setDrawColor(155, 169, 183)
    doc.line(x, sigY, x + sigW, sigY)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.setTextColor(95, 109, 125)
    doc.text(label, x, sigY + 5)
  })

  const pageCount = doc.getNumberOfPages()
  for (let page = 1; page <= pageCount; page += 1) {
    doc.setPage(page)
    doc.setDrawColor(220, 228, 236)
    doc.line(margin, 285, pageWidth - margin, 285)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.setTextColor(105, 117, 130)
    doc.text(data.reportId, margin, 290)
    doc.text('System-generated | Not a certified inspection or compliance document', pageWidth / 2, 290, { align: 'center' })
    doc.text(`Page ${page} of ${pageCount}`, pageWidth - margin, 290, { align: 'right' })
  }
  return doc
}

function wordText(text, options = {}) {
  return new Paragraph({
    spacing: { after: options.after ?? 120 },
    alignment: options.alignment,
    children: [
      new TextRun({
        text: String(text ?? DASH),
        bold: options.bold || false,
        color: options.color || '26384A',
        size: options.size || 20,
      }),
    ],
  })
}

function wordSection(title) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 260, after: 120 },
    shading: { type: ShadingType.CLEAR, fill: '16304E' },
    children: [new TextRun({ text: `  ${title}`, bold: true, color: 'FFFFFF', size: 22 })],
  })
}

function wordField(label, value) {
  return new Paragraph({
    spacing: { after: 100 },
    children: [
      new TextRun({ text: `${label}: `, bold: true, color: '526477', size: 20 }),
      new TextRun({ text: display(value), color: '26384A', size: 20 }),
    ],
  })
}

function wordCell(text, header = false) {
  return new TableCell({
    width: { size: 25, type: WidthType.PERCENTAGE },
    shading: header ? { type: ShadingType.CLEAR, fill: 'E7EEF5' } : undefined,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 1, color: 'DCE4EC' },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: 'DCE4EC' },
      left: { style: BorderStyle.SINGLE, size: 1, color: 'DCE4EC' },
      right: { style: BorderStyle.SINGLE, size: 1, color: 'DCE4EC' },
    },
    children: [
      new Paragraph({
        spacing: { before: 60, after: 60 },
        children: [new TextRun({ text: String(text), bold: header, size: 18, color: header ? '16304E' : '26384A' })],
      }),
    ],
  })
}

async function buildWord(data) {
  const alertRows = [
    new TableRow({ tableHeader: true, children: ['Time', 'Sensor', 'Reading / Details', 'Status'].map(t => wordCell(t, true)) }),
    ...(data.alerts.length
      ? data.alerts.map(a => new TableRow({ children: [display(a.time), alertSensor(a), alertReading(a), alertStatus(a)].map(t => wordCell(t)) }))
      : [new TableRow({ children: [DASH, 'No alert records', 'No readings', DASH].map(t => wordCell(t)) })]),
  ]

  const doc = new Document({
    creator: 'IntelliWatch',
    title: 'IntelliWatch Equipment Service Report',
    description: 'Editable equipment service and maintenance report',
    styles: {
      default: {
        document: { run: { font: 'Aptos', size: 20, color: '26384A' } },
        heading1: { run: { font: 'Aptos Display', size: 34, bold: true, color: '16304E' } },
        heading2: { run: { font: 'Aptos Display', size: 22, bold: true, color: 'FFFFFF' } },
      },
    },
    sections: [{
      properties: {
        page: {
          margin: { top: 720, right: 720, bottom: 720, left: 720 },
        },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: `${data.reportId}  |  IntelliWatch  |  Page `, size: 16, color: '708090' }),
              new TextRun({ children: [PageNumber.CURRENT], size: 16, color: '708090' }),
            ],
          })],
        }),
      },
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 80 },
          children: [new TextRun({ text: 'INTELLIWATCH', bold: true, size: 36, color: '16304E' })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 220 },
          children: [new TextRun({ text: 'REAL-TIME ANOMALY DETECTION & DECISION SUPPORT', size: 16, color: '60758A' })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          heading: HeadingLevel.HEADING_1,
          spacing: { after: 220 },
          children: [new TextRun({ text: 'EQUIPMENT SERVICE REPORT', bold: true, size: 30, color: '16304E' })],
        }),
        wordField('Report ID', data.reportId),
        wordField('Report Date', data.reportDate),
        wordField('Prepared By', data.preparedBy),
        wordSection('01  EQUIPMENT INFORMATION'),
        wordField('Equipment / Machine', data.equipment),
        wordField('Reporting Period', data.period),
        wordSection('02  ALERT SUMMARY'),
        wordField('Total Alerts', data.alerts.length),
        wordField('Warnings', data.warningCount),
        wordField('Critical Alerts', data.criticalCount),
        new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: alertRows }),
        wordSection('03  FINDINGS / MACHINE CONDITION'),
        wordText(display(data.findings)),
        wordSection('04  RECOMMENDED / COMPLETED ACTIONS'),
        wordText(display(data.actions)),
        wordSection('05  SERVICE NOTES'),
        wordText(display(data.notes)),
        wordSection('06  REVIEW & SIGN-OFF'),
        wordField('Reviewed By', data.reviewedBy),
        wordText('Technician Signature: ____________________________________'),
        wordText('Reviewer Signature: _____________________________________'),
        wordText('Date: ____________________'),
        wordText('System-generated report — not a certified inspection or compliance document.', { size: 16, color: '708090', after: 0 }),
      ],
    }],
  })
  return Packer.toBlob(doc)
}

export default function ServiceReport({ alerts = [] }) {
  const [open, setOpen] = useState(false)
  const [equipment, setEquipment] = useState('')
  const [preparedBy, setPreparedBy] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('iw_user') || '{}').username || ''
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
  const [reportId] = useState(() => `IW-SR-${Date.now().toString().slice(-8)}`)

  const criticalCount = alerts.filter(alert => alert.status === 'critical').length
  const warningCount = alerts.filter(alert => alert.status === 'warning').length

  function getData() {
    return {
      reportId,
      reportDate,
      preparedBy: preparedBy || 'Not specified',
      equipment,
      period,
      findings,
      actions,
      notes,
      reviewedBy,
      alerts,
      criticalCount,
      warningCount,
    }
  }

  function downloadPdf() {
    try {
      const data = getData()
      const doc = buildPdf(data)
      doc.save(`${safeFileName(data.equipment || data.reportId)}-Service-Report.pdf`)
    } catch (error) {
      console.error('Service report PDF export failed:', error)
      window.alert('PDF could not be generated. Please try again.')
    }
  }

  async function downloadWord() {
    try {
      const data = getData()
      const blob = await buildWord(data)
      downloadBlob(blob, `${safeFileName(data.equipment || data.reportId)}-Service-Report.docx`)
    } catch (error) {
      console.error('Service report Word export failed:', error)
      window.alert('Word document could not be generated. Please try again.')
    }
  }

  function printReport() {
    const report = document.getElementById('iw-service-report')
    if (!report) {
      window.alert('Service report content was not found.')
      return
    }
    const printWindow = window.open('', '_blank')
    if (!printWindow) {
      window.alert('Please allow pop-ups for this site, then try Print Preview again.')
      return
    }

    const clone = report.cloneNode(true)
    clone.querySelectorAll('input').forEach(input => {
      const value = document.createElement('span')
      value.className = 'iw-report-print-value'
      value.textContent = input.value || DASH
      input.replaceWith(value)
    })
    clone.querySelectorAll('textarea').forEach(area => {
      const value = document.createElement('div')
      value.className = 'iw-report-print-value iw-report-print-multiline'
      value.textContent = area.value || DASH
      area.replaceWith(value)
    })
    const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
      .map(style => style.outerHTML)
      .join('\n')

    printWindow.document.open()
    printWindow.document.write(`<!doctype html>
<html><head><meta charset="utf-8"><title>IntelliWatch Service Report</title>
<base href="${window.location.href}">${styles}
<style>
html,body{margin:0!important;padding:0!important;background:#fff!important}
#iw-service-report{display:block!important;width:auto!important;max-width:none!important;margin:0!important;padding:12mm!important}
.iw-report-actions{display:none!important}
@media print{.iw-report-overlay,.iw-report-panel{position:static!important;display:block!important;width:auto!important;height:auto!important;max-height:none!important;overflow:visible!important;padding:0!important;margin:0!important;background:#fff!important;box-shadow:none!important;border:0!important}.iw-report-section,.iw-report-meta,.iw-report-summary,.iw-report-table{break-inside:avoid}}
</style></head><body>${clone.outerHTML}</body></html>`)
    printWindow.document.close()
    printWindow.onload = () => {
      printWindow.focus()
      printWindow.print()
    }
  }

  if (!open) {
    return (
      <button type="button" className="export-btn" onClick={() => setOpen(true)}>
        Service Report
      </button>
    )
  }

  return (
    <div className="iw-report-overlay">
      <div className="iw-report-panel">
        <div className="iw-report-actions">
          <button type="button" className="iw-report-btn iw-report-btn-secondary" onClick={() => setOpen(false)}>Close</button>
          <button type="button" className="iw-report-btn iw-report-btn-secondary" onClick={printReport}>Print Preview</button>
          <button type="button" className="iw-report-btn iw-report-btn-primary" onClick={downloadPdf}>Download PDF</button>
          <button type="button" className="iw-report-btn iw-report-btn-word" onClick={downloadWord}>Download Editable Word</button>
        </div>

        <div id="iw-service-report" className="iw-report-document">
          <header className="iw-report-header">
            <div className="iw-report-brand">
              <div className="iw-report-logo">IW</div>
              <div>
                <h1>INTELLIWATCH</h1>
                <p>Real-Time Anomaly Detection &amp; Decision Support System</p>
              </div>
            </div>
            <div className="iw-report-heading">
              <span className="iw-report-kicker">MAINTENANCE RECORD</span>
              <h2>Equipment Service Report</h2>
              <p>Inspection • Alert review • Corrective action</p>
            </div>
          </header>

          <div className="iw-report-meta">
            <div><strong>Report ID</strong><span>{reportId}</span></div>
            <div><strong>Report Date</strong><span>{reportDate}</span></div>
            <div><strong>Prepared By</strong><span>{preparedBy || 'Not specified'}</span></div>
          </div>

          <section className="iw-report-section">
            <h3><span>01</span> Equipment Information</h3>
            <div className="iw-report-fields">
              <label>Equipment / Machine Name<input value={equipment} onChange={e => setEquipment(e.target.value)} placeholder="Enter equipment name" /></label>
              <label>Reporting Period<input value={period} onChange={e => setPeriod(e.target.value)} placeholder="e.g. 01 Nov – 22 Nov 2026" /></label>
              <label>Technician / Prepared By<input value={preparedBy} onChange={e => setPreparedBy(e.target.value)} placeholder="Name" /></label>
            </div>
          </section>

          <section className="iw-report-section">
            <h3><span>02</span> Alert Summary</h3>
            <div className="iw-report-summary">
              <div className="iw-report-stat"><strong>{alerts.length}</strong><span>Total Alerts</span></div>
              <div className="iw-report-stat iw-report-stat-warning"><strong>{warningCount}</strong><span>Warnings</span></div>
              <div className="iw-report-stat iw-report-stat-critical"><strong>{criticalCount}</strong><span>Critical Alerts</span></div>
            </div>
            <div className="iw-report-table-wrap">
              <table className="iw-report-table">
                <thead><tr><th>Time</th><th>Sensor</th><th>Reading / Details</th><th>Status</th></tr></thead>
                <tbody>
                  {alerts.length ? alerts.map((alert, index) => (
                    <tr key={alert.id ?? index}>
                      <td>{display(alert.time)}</td><td>{alertSensor(alert)}</td><td>{alertReading(alert)}</td><td><span className={`iw-report-status iw-report-status-${String(alert.status || 'unknown').toLowerCase()}`}>{alertStatus(alert)}</span></td>
                    </tr>
                  )) : <tr><td colSpan="4" className="iw-report-empty">No alert records available for this report.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section className="iw-report-section">
            <h3><span>03</span> Findings / Machine Condition</h3>
            <textarea value={findings} onChange={e => setFindings(e.target.value)} placeholder="Record observed machine condition and findings..." />
          </section>
          <section className="iw-report-section">
            <h3><span>04</span> Recommended / Completed Actions</h3>
            <textarea value={actions} onChange={e => setActions(e.target.value)} placeholder="Record inspection, maintenance or corrective actions..." />
          </section>
          <section className="iw-report-section">
            <h3><span>05</span> Service Notes</h3>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Additional service notes..." />
          </section>
          <section className="iw-report-section">
            <h3><span>06</span> Review &amp; Sign-off</h3>
            <label className="iw-report-review-label">Reviewed By<input value={reviewedBy} onChange={e => setReviewedBy(e.target.value)} placeholder="Reviewer / Maintenance Engineer" /></label>
            <div className="iw-report-signatures"><div>Technician Signature</div><div>Reviewer Signature</div><div>Date</div></div>
          </section>
          <footer className="iw-report-footer">
            <span>{reportId}</span><span>INTELLIWATCH</span><span>System-generated report — not a certified inspection or compliance document.</span>
          </footer>
        </div>
      </div>
    </div>
  )
}
