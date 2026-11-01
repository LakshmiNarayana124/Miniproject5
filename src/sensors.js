
// ==================================================
// INTELLIWATCH - SENSOR CONFIGURATION
// ==================================================

export const SENSORS = {
  vibration: {
    label: 'Vibration',
    unit: 'mm/s',
    color: '#4f8ef7',
    normal: { min: 0, max: 5 },
    warning: { min: 5, max: 8 },
    base: 3,
    noise: 0.45,
    spike: 2.5,
    icon: '📡',
  },

  temperature: {
    label: 'Temperature',
    unit: '°C',
    color: '#f97316',
    normal: { min: 20, max: 75 },
    warning: { min: 75, max: 90 },
    base: 55,
    noise: 1.2,
    spike: 8,
    icon: '🌡️',
  },

  current: {
    label: 'Current',
    unit: 'A',
    color: '#2ecc71',
    normal: { min: 0, max: 15 },
    warning: { min: 15, max: 20 },
    base: 10,
    noise: 0.6,
    spike: 3,
    icon: '⚡',
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
// TIME FORMATTING
// ==================================================

export function formatTime(date = new Date()) {
  return new Date(date).toLocaleTimeString('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}

export function formatDateTime(date = new Date()) {
  return new Date(date).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}
