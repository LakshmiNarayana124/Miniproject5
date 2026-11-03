
// ==================================================
// INTELLIWATCH — USER ACTIVITY LOG
// Tracks per-user page visits with timestamps.
// Stored in localStorage, capped at 50 entries.
// Never displayed intrusively — surfaced only when
// the user lands and a previous session exists.
// ==================================================

const MAX_ENTRIES = 50
const STORAGE_KEY = 'iw_activity_log'

// Page labels for display
export const PAGE_LABELS = {
  '/':           'Dashboard',
  '/vibration':  'Vibration',
  '/temperature':'Temperature',
  '/current':    'Current',
  '/explorer':   '3D Lab',
  '/about':      'About',
}

/** Format a timestamp as DD MMM YYYY HH:MM:SS (24h, no AM/PM) */
export function formatActivity(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  const pad = n => String(n).padStart(2, '0')
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${pad(d.getDate())} ${months[d.getMonth()]} ${d.getFullYear()}  ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/** Load entire log from localStorage */
function loadLog() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

/** Persist log */
function saveLog(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(-MAX_ENTRIES)))
  } catch { /* storage full — silently drop */ }
}

/**
 * Record a page visit.
 * @param {string} username
 * @param {string} role
 * @param {string} path  — e.g. '/vibration'
 */
export function recordVisit(username, role, path) {
  if (!username) return
  const entries = loadLog()
  entries.push({
    username,
    role,
    path,
    label: PAGE_LABELS[path] || path,
    ts: Date.now(),
  })
  saveLog(entries)
}

/**
 * Get the last visit entry for a given username,
 * excluding the current path (so it shows "you were last on X").
 */
export function getLastVisit(username, currentPath) {
  if (!username) return null
  const entries = loadLog()
  // Walk backwards to find last entry for this user on a different page
  for (let i = entries.length - 1; i >= 0; i--) {
    const e = entries[i]
    if (e.username === username && e.path !== currentPath) {
      return e
    }
  }
  return null
}

/**
 * Return recent entries for a user (newest first), up to `limit`.
 */
export function getRecentActivity(username, limit = 10) {
  if (!username) return []
  return loadLog()
    .filter(e => e.username === username)
    .slice(-limit)
    .reverse()
}
