
// ==================================================
// INTELLIWATCH — ADAPTIVE ML ENGINE (Frontend)
// ==================================================
// This is a pure-JS, browser-side adaptive learning
// engine. It does NOT replace the Python/scikit-learn
// model on the Raspberry Pi — it runs in parallel as
// a lightweight anomaly scorer that continuously
// learns from the readings it observes.
//
// APPROACH
// ─────────
// 1. Rolling statistics  — keeps a sliding window of
//    the last N readings per sensor. Computes mean,
//    standard deviation, and percentile ranks.
//
// 2. Dynamic threshold adaptation  — every time a new
//    reading arrives the engine nudges the "learned"
//    normal band using exponential moving averages
//    (EMA). This means the engine naturally follows
//    slow drift (e.g. seasonal temperature baseline
//    shift) without falsely alarming, while still
//    catching sharp spikes.
//
// 3. Anomaly scoring  — produces a score 0-100 for
//    each reading. The score weights:
//      • z-score deviation from learned mean
//      • rate-of-change (delta from previous reading)
//      • consecutive-anomaly streak multiplier
//
// 4. Confidence  — starts low (≤ 5 readings) and
//    grows as more data is observed, reaching full
//    confidence after ~50 readings. Below confidence
//    threshold the engine defers to static thresholds.
//
// 5. Persistence  — the learned model state is saved
//    to localStorage so it survives page reloads and
//    resumes from where it left off.
//
// INTEGRATION
// ───────────
// Call  mlEngine.ingest(sensorKey, value, timestamp)
//       each time a new sensor reading arrives.
// Read  mlEngine.getState(sensorKey)
//       to get { status, score, confidence, learnedNormal }
//
// The engine emits a CustomEvent 'iw:ml:update' on
// window so subscribers (charts, UI) can react.
// ==================================================

const STORAGE_KEY = 'iw_ml_state'

// Window size for rolling stats
const WINDOW_SIZE = 60

// EMA smoothing factor (0 = never adapt, 1 = full replace)
const EMA_ALPHA = 0.04   // slow adaptation — resists temporary spikes

// Minimum readings before we trust our own thresholds
const MIN_CONFIDENCE_READINGS = 12

// Anomaly score thresholds (0–100)
const SCORE_WARNING  = 45
const SCORE_CRITICAL = 72

// ── Persistence helpers ──────────────────────────────────────────────────────
function loadState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveState(state) {
  try {
    // Only persist the learned model — not the raw window (too large)
    const toSave = {}
    for (const [key, s] of Object.entries(state)) {
      toSave[key] = {
        emaMean:      s.emaMean,
        emaStd:       s.emaStd,
        readingCount: s.readingCount,
        lastValue:    s.lastValue,
        streakCount:  s.streakCount,
        learnedNormal:s.learnedNormal,
        accuracy:     s.accuracy,
        correctedCount: s.correctedCount,
      }
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } catch { /* storage full */ }
}

// ── Per-sensor state factory ─────────────────────────────────────────────────
function makeSensorState(persisted = {}) {
  return {
    window:        [],         // rolling raw values
    emaMean:       persisted.emaMean      ?? null,
    emaStd:        persisted.emaStd       ?? null,
    readingCount:  persisted.readingCount ?? 0,
    lastValue:     persisted.lastValue    ?? null,
    streakCount:   persisted.streakCount  ?? 0,
    learnedNormal: persisted.learnedNormal ?? null,  // { min, max }
    accuracy:      persisted.accuracy     ?? 0.5,    // 0–1, starts neutral
    correctedCount:persisted.correctedCount ?? 0,
    // Runtime-only (not persisted)
    lastStatus:    'awaiting-iot',
    lastScore:     0,
    lastTs:        null,
  }
}

// ── Main engine object ────────────────────────────────────────────────────────
const _persisted = loadState()

const _state = {
  vibration:   makeSensorState(_persisted.vibration   || {}),
  temperature: makeSensorState(_persisted.temperature || {}),
  current:     makeSensorState(_persisted.current     || {}),
}

// ── Math helpers ─────────────────────────────────────────────────────────────
function mean(arr) {
  if (!arr.length) return 0
  return arr.reduce((a, b) => a + b, 0) / arr.length
}

function std(arr, m) {
  if (arr.length < 2) return 0
  const mu = m ?? mean(arr)
  const variance = arr.reduce((s, v) => s + (v - mu) ** 2, 0) / arr.length
  return Math.sqrt(variance)
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

// ── Core ingest function ─────────────────────────────────────────────────────
/**
 * Feed a new sensor reading into the engine.
 * @param {string} sensorKey  — 'vibration' | 'temperature' | 'current'
 * @param {number} value      — numeric reading
 * @param {number} [ts]       — epoch ms (defaults to Date.now())
 * @param {object} [staticSensor] — SENSORS[sensorKey] config for fallback thresholds
 * @returns {{ status, score, confidence, learnedNormal, delta }}
 */
function ingest(sensorKey, value, ts = Date.now(), staticSensor = null) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return { status: 'awaiting-iot', score: 0, confidence: 0, learnedNormal: null, delta: 0 }
  }

  const s = _state[sensorKey]
  if (!s) return { status: 'uncertain', score: 0, confidence: 0, learnedNormal: null, delta: 0 }

  // ── 1. Update rolling window ──
  s.window.push(value)
  if (s.window.length > WINDOW_SIZE) s.window.shift()
  s.readingCount++

  // ── 2. Compute current window stats ──
  const wMean = mean(s.window)
  const wStd  = std(s.window, wMean)

  // ── 3. Update EMA (exponential moving average) ──
  if (s.emaMean === null) {
    s.emaMean = wMean
    s.emaStd  = wStd || 0.5  // guard against zero
  } else {
    s.emaMean = EMA_ALPHA * wMean + (1 - EMA_ALPHA) * s.emaMean
    s.emaStd  = EMA_ALPHA * (wStd || 0.5) + (1 - EMA_ALPHA) * s.emaStd
  }

  // Guard std dev floor (avoid div-by-zero)
  const effStd = Math.max(s.emaStd, 0.01)

  // ── 4. Confidence (0–1) ──
  const confidence = clamp(s.readingCount / (MIN_CONFIDENCE_READINGS * 4), 0, 1)

  // ── 5. z-score component ──
  const z = Math.abs(value - s.emaMean) / effStd
  const zScore = clamp(z * 18, 0, 70)   // z=1 → 18pts, z=3 → 54pts, z=4 → 70pts

  // ── 6. Rate-of-change component ──
  const delta = s.lastValue !== null ? Math.abs(value - s.lastValue) : 0
  const roc   = clamp((delta / (effStd + 0.001)) * 15, 0, 30)

  // ── 7. Streak multiplier (persistent anomalies score higher) ──
  const rawScore = zScore + roc
  if (rawScore >= SCORE_WARNING * 0.6) {
    s.streakCount = Math.min(s.streakCount + 1, 10)
  } else {
    s.streakCount = Math.max(s.streakCount - 1, 0)
  }
  const streakBonus = s.streakCount * 2

  // ── 8. Final anomaly score ──
  let score = clamp(rawScore + streakBonus, 0, 100)

  // ── 9. Blend with static thresholds when confidence is low ──
  let status
  if (confidence < 0.3 && staticSensor) {
    // Defer to static thresholds
    if (value > staticSensor.warning.max)       status = 'critical'
    else if (value > staticSensor.normal.max)   status = 'warning'
    else                                         status = 'normal'
    score = status === 'critical' ? 80 : status === 'warning' ? 55 : 15
  } else {
    // Use learned score
    if      (score >= SCORE_CRITICAL) status = 'critical'
    else if (score >= SCORE_WARNING)  status = 'warning'
    else                               status = 'normal'

    // Cross-check with static thresholds (hard ceiling rule):
    // If static says critical, we must also say critical regardless.
    if (staticSensor) {
      if (value > staticSensor.warning.max && status !== 'critical') {
        status = 'critical'
        score  = Math.max(score, SCORE_CRITICAL + 5)
      } else if (value > staticSensor.normal.max && status === 'normal') {
        status = 'warning'
        score  = Math.max(score, SCORE_WARNING + 2)
      }
    }
  }

  // ── 10. Update learned normal band ──
  if (status === 'normal' && s.readingCount >= MIN_CONFIDENCE_READINGS) {
    const band3sig = effStd * 3
    s.learnedNormal = {
      min: Math.max(s.emaMean - band3sig, 0),
      max: s.emaMean + band3sig,
    }
  }

  // ── 11. Update accuracy estimate ──
  // Simple proxy: if status matches the hard static threshold, it's likely correct.
  if (staticSensor && s.readingCount > MIN_CONFIDENCE_READINGS) {
    const staticStatus =
      value > staticSensor.warning.max ? 'critical' :
      value > staticSensor.normal.max  ? 'warning' : 'normal'
    if (status === staticStatus) {
      s.correctedCount++
    }
    s.accuracy = clamp(s.correctedCount / s.readingCount, 0.5, 0.99)
  }

  // ── 12. Store ──
  s.lastValue  = value
  s.lastStatus = status
  s.lastScore  = score
  s.lastTs     = ts

  // Save to localStorage (throttled — every 10 readings)
  if (s.readingCount % 10 === 0) saveState(_state)

  // Emit update event (non-blocking)
  try {
    window.dispatchEvent(new CustomEvent('iw:ml:update', {
      detail: { sensorKey, status, score, confidence, value, ts }
    }))
  } catch { /* SSR / worker context */ }

  return { status, score, confidence, learnedNormal: s.learnedNormal, delta }
}

/**
 * Get current state snapshot for a sensor.
 */
function getState(sensorKey) {
  const s = _state[sensorKey]
  if (!s) return null
  return {
    status:        s.lastStatus,
    score:         s.lastScore,
    confidence:    clamp(s.readingCount / (MIN_CONFIDENCE_READINGS * 4), 0, 1),
    readingCount:  s.readingCount,
    emaMean:       s.emaMean,
    emaStd:        s.emaStd,
    learnedNormal: s.learnedNormal,
    accuracy:      s.accuracy,
    streakCount:   s.streakCount,
  }
}

/**
 * Returns a summary of all sensor model states.
 * Used by the ML panel on dashboards.
 */
function getSummary() {
  return Object.fromEntries(
    Object.keys(_state).map(k => [k, getState(k)])
  )
}

/**
 * Force-reset a sensor's learned model.
 * Called if readings become physically impossible (sensor swap, recalibration).
 */
function resetSensor(sensorKey) {
  _state[sensorKey] = makeSensorState()
  saveState(_state)
}

/**
 * Annotate a historical point as "confirmed anomaly" or "confirmed normal".
 * This is the learning feedback loop — called when a maintenance engineer
 * confirms or dismisses an alert.
 * @param {string} sensorKey
 * @param {'anomaly'|'normal'} label
 */
function feedback(sensorKey, label) {
  const s = _state[sensorKey]
  if (!s) return
  if (label === 'anomaly') {
    // Tighten tolerance slightly — system becomes more sensitive
    s.emaStd = Math.max(s.emaStd * 0.92, 0.01)
  } else {
    // Widen tolerance slightly — reduce false positives
    s.emaStd = s.emaStd * 1.06
  }
  saveState(_state)
}

/**
 * Confidence label for display
 */
function confidenceLabel(c) {
  if (c >= 0.85) return 'High'
  if (c >= 0.5)  return 'Building'
  if (c >= 0.2)  return 'Warming up'
  return 'Cold start'
}

export const mlEngine = { ingest, getState, getSummary, resetSensor, feedback, confidenceLabel }
