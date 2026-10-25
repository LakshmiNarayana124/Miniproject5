
 // ─── Shared sensor config & helpers ─────────────────────────────────────────

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

export const MAX_POINTS = 40
export const CHART_INTERVAL_MS = 3000
export const LOG_INTERVAL_MS = 15000

// IoT integration pending.
// Return null until actual sensor data is received.
export function generateValue(sensor) {
  return null
}

export function getStatus(value, sensor) {
  if (value === null || value === undefined) return 'nil'
  if (value > sensor.warning.max) return 'critical'
  if (value > sensor.normal.max) return 'warning'
  return 'normal'
}

export function statusColor(status) {
  if (status === 'critical') return '#e05555'
  if (status === 'warning') return '#f0c040'
  if (status === 'nil') return '#4a5070'
  return '#2ecc71'
}

export function statusLabel(status) {
  if (status === 'critical') return 'CRITICAL'
  if (status === 'warning') return 'WARNING'
  if (status === 'nil') return 'NO SIGNAL'
  return 'NORMAL'
}

export function formatTime(ts) {
  const d = new Date(ts)

  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

export function formatDateTime(ts) {
  const d = new Date(ts)

  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  })
}
