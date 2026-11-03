
// ==================================================
// INTELLIWATCH - SENSOR CONFIGURATION
// Thresholds follow published industrial standards:
//
// VIBRATION — ISO 10816-3:2009 (Group 2 machines,
//   rigid mounting, 15–75 kW motors):
//   Good / Normal:   0.0 – 2.8 mm/s RMS
//   Satisfactory:    2.8 – 4.5 mm/s RMS   → Warning
//   Unsatisfactory:  4.5 – 7.1 mm/s RMS   → Warning (upper)
//   Unacceptable:    > 7.1 mm/s RMS        → Critical
//   (We use 4.5 as the warning onset and 7.1 as critical)
//
// TEMPERATURE — IEC 60034-1 motor winding classes
//   (Class F insulation, ambient 40 °C):
//   Normal bearing/winding surface: 40 – 80 °C
//   Warning zone:                   80 – 100 °C
//   Critical (risk of insulation breakdown): > 100 °C
//   (Bearing outer-race alarm typically set at 90 °C,
//    shutdown at 100 °C per ISO 10816 supplement)
//
// CURRENT — IEC 60947-4-1 / NEMA MG-1:
//   Rated current (In) for a typical 3-phase 7.5 kW /
//   415 V motor ≈ 15 A. Service Factor 1.15 = 17.25 A.
//   Warning: > 110 % In  → 16.5 A
//   Critical: > 125 % In → 18.75 A  (overload relay trip)
// ==================================================

export const SENSORS = {
  vibration: {
    label: 'Vibration',
    unit: 'mm/s',
    color: '#4f8ef7',
    normal:  { min: 0.0, max: 4.5 },
    warning: { min: 4.5, max: 7.1 },
    base: 2.2,
    noise: 0.3,
    spike: 3.0,
    icon: '📡',
    standard: 'ISO 10816-3:2009',
    // Threshold source documentation (Req 7.3, 7.4)
    source: 'ISO 10816-3:2009',
    equipmentSpecific: false,
  },

  temperature: {
    label: 'Temperature',
    unit: '°C',
    color: '#f97316',
    normal:  { min: 20, max: 80 },
    warning: { min: 80, max: 100 },
    base: 55,
    noise: 1.0,
    spike: 15,
    icon: '🌡️',
    standard: 'IEC 60034-1 (Class F)',
    source: 'IEC 60034-1',
    equipmentSpecific: false,
  },

  current: {
    label: 'Current',
    unit: 'A',
    color: '#2ecc71',
    normal:  { min: 0.0, max: 16.5 },
    warning: { min: 16.5, max: 18.75 },
    base: 12,
    noise: 0.4,
    spike: 4,
    icon: '⚡',
    standard: 'IEC 60947-4-1 / NEMA MG-1',
    source: 'IEC 60947-4-1 / NEMA MG-1',
    equipmentSpecific: false,
  },
}

// ==================================================
// APPLICATION CONFIGURATION
// ==================================================

export const MAX_POINTS = 40
export const CHART_INTERVAL_MS = 3000
export const LOG_INTERVAL_MS = 15000

// Retained for compatibility with startup-related UI logic.
export const MIN_BASELINE_READINGS = 3

// ==================================================
// LIVE SENSOR DATA
// ==================================================

// Simulation has been disabled.
// Real readings must come from the IoT/backend connection.

export function generateValue() {
  return null
}

// ==================================================
// SENSOR STATUS CLASSIFICATION
// ==================================================

export function getStatus(value, sensor) {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
  ) {
    return 'nil'
  }

  if (!sensor) return 'uncertain'

  if (Number(value) > sensor.warning.max) {
    return 'critical'
  }

  if (Number(value) > sensor.normal.max) {
    return 'warning'
  }

  return 'normal'
}

// ==================================================
// STARTUP STATUS
// ==================================================

export function getStartupStatus(history = []) {
  if (!Array.isArray(history) || history.length === 0) {
    return 'awaiting-iot'
  }

  const validReadings = history.filter(point =>
    point &&
    point.value !== null &&
    point.value !== undefined &&
    Number.isFinite(Number(point.value))
  )

  if (validReadings.length === 0) {
    return 'awaiting-iot'
  }

  if (validReadings.length < MIN_BASELINE_READINGS) {
    return 'scanning'
  }

  return 'ready'
}

// ==================================================
// STATUS COLORS
// ==================================================

export function statusColor(status) {
  const colors = {
    normal: '#22c55e',
    warning: '#f59e0b',
    critical: '#ef4444',
    uncertain: '#a855f7',
    scanning: '#3b82f6',
    analysing: '#8b5cf6',
    ready: '#22c55e',
    nil: '#94a3b8',
    'no-recordings': '#94a3b8',
    'awaiting-iot': '#94a3b8',
  }

  return colors[status] || '#94a3b8'
}

// ==================================================
// STATUS LABELS
// ==================================================

export function statusLabel(status) {
  const labels = {
    normal: 'Normal',
    warning: 'Warning',
    critical: 'Critical',
    uncertain: 'Uncertain',
    scanning: 'Initial Scanning',
    analysing: 'Analysing',
    ready: 'Ready',
    nil: 'No Data',
    'no-recordings': 'No Recordings',
    'awaiting-iot': 'Awaiting IoT Signal',
  }

  return labels[status] || 'Unknown'
}

// ==================================================
// TIME FORMATTING — 24-hour format throughout
// ==================================================

export function formatTime(date = new Date()) {
  const d = new Date(date)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function formatDateTime(date = new Date()) {
  const d = new Date(date)
  const pad = n => String(n).padStart(2, '0')
  const months = ['Jan','Feb','Mar','Apr','May','Jun',
                  'Jul','Aug','Sep','Oct','Nov','Dec']
  return `${pad(d.getDate())} ${months[d.getMonth()]} ${d.getFullYear()}  ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
