// ==================================================
// INTELLIWATCH — ADAPTIVE ML ENGINE (Frontend)
// ==================================================
//
// Independent learning environments:
//
// 1. hardware       — Actual IoT / hardware readings.
// 2. simulation     — Explicitly selected simulation.
// 3. offline-demo   — Offline demo login.
//
// Each environment has independent statistics,
// feedback, confidence and persistent storage.
//
// The frontend engine does NOT replace the
// Python/scikit-learn model on the Raspberry Pi.
// ==================================================

const STORAGE_KEY_BASE = 'iw_ml_state_v2'

const VALID_SOURCES = [
  'hardware',
  'simulation',
  'offline-demo',
]

// Window size for rolling stats
const WINDOW_SIZE = 60

// EMA smoothing factor
const EMA_ALPHA = 0.04

// Minimum readings before trusting learned thresholds
const MIN_CONFIDENCE_READINGS = 12

// Anomaly score thresholds
const SCORE_WARNING = 45
const SCORE_CRITICAL = 72


// ==================================================
// SOURCE MANAGEMENT
// ==================================================

function normalizeSource(source = 'hardware') {
  if (!VALID_SOURCES.includes(source)) {
    throw new Error(
      `Invalid ML data source: ${source}`
    )
  }

  return source
}

function getStorageKey(source) {
  return `${STORAGE_KEY_BASE}_${source}`
}


// ==================================================
// PERSISTENCE HELPERS
// ==================================================

function loadState(source) {
  try {
    return JSON.parse(
      localStorage.getItem(getStorageKey(source)) || '{}'
    )
  } catch {
    return {}
  }
}

function saveState(state, source) {
  try {
    const toSave = {}

    for (const [key, sensor] of Object.entries(state)) {
      toSave[key] = {
        emaMean: sensor.emaMean,
        emaStd: sensor.emaStd,
        readingCount: sensor.readingCount,
        lastValue: sensor.lastValue,
        streakCount: sensor.streakCount,
        learnedNormal: sensor.learnedNormal,
        accuracy: sensor.accuracy,
        correctedCount: sensor.correctedCount,
      }
    }

    localStorage.setItem(
      getStorageKey(source),
      JSON.stringify(toSave)
    )
  } catch {
    // Storage unavailable or full.
  }
}


// ==================================================
// PER-SENSOR STATE FACTORY
// ==================================================

function makeSensorState(persisted = {}) {
  return {
    window: [],

    emaMean: persisted.emaMean ?? null,
    emaStd: persisted.emaStd ?? null,

    readingCount: persisted.readingCount ?? 0,
    lastValue: persisted.lastValue ?? null,
    streakCount: persisted.streakCount ?? 0,

    learnedNormal: persisted.learnedNormal ?? null,

    accuracy: persisted.accuracy ?? 0.80,
    correctedCount: persisted.correctedCount ?? 0,

    // Runtime-only state.
    lastStatus: 'awaiting-iot',
    lastScore: 0,
    lastTs: null,
  }
}


// ==================================================
// ENVIRONMENT STATE
// ==================================================

function makeEnvironmentState(source) {
  const persisted = loadState(source)

  return {
    vibration: makeSensorState(
      persisted.vibration || {}
    ),

    temperature: makeSensorState(
      persisted.temperature || {}
    ),

    current: makeSensorState(
      persisted.current || {}
    ),
  }
}

const _state = {
  hardware: makeEnvironmentState('hardware'),

  simulation: makeEnvironmentState('simulation'),

  'offline-demo': makeEnvironmentState('offline-demo'),
}


// ==================================================
// MATH HELPERS
// ==================================================

function mean(arr) {
  if (!arr.length) return 0

  return arr.reduce(
    (a, b) => a + b,
    0
  ) / arr.length
}

function std(arr, m) {
  if (arr.length < 2) return 0

  const mu = m ?? mean(arr)

  const variance = arr.reduce(
    (sum, value) => sum + (value - mu) ** 2,
    0
  ) / arr.length

  return Math.sqrt(variance)
}

function clamp(value, min, max) {
  return Math.max(
    min,
    Math.min(max, value)
  )
}


// ==================================================
// CORE INGEST FUNCTION
// ==================================================

/**
 * Feed a sensor reading into the selected ML environment.
 *
 * @param {string} sensorKey
 * @param {number} value
 * @param {number} ts
 * @param {object|null} staticSensor
 * @param {'hardware'|'simulation'|'offline-demo'} source
 */

function ingest(
  sensorKey,
  value,
  ts = Date.now(),
  staticSensor = null,
  source = 'hardware'
) {
  const selectedSource = normalizeSource(source)

  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(value)
  ) {
    return {
      status: 'awaiting-iot',
      score: 0,
      confidence: 0,
      learnedNormal: null,
      delta: 0,
    }
  }

  const environment = _state[selectedSource]
  const sensor = environment[sensorKey]

  if (!sensor) {
    return {
      status: 'uncertain',
      score: 0,
      confidence: 0,
      learnedNormal: null,
      delta: 0,
    }
  }

  // ------------------------------------------------
  // 1. Rolling window
  // ------------------------------------------------

  sensor.window.push(value)

  if (sensor.window.length > WINDOW_SIZE) {
    sensor.window.shift()
  }

  sensor.readingCount++

  // ------------------------------------------------
  // 2. Window statistics
  // ------------------------------------------------

  const windowMean = mean(sensor.window)
  const windowStd = std(
    sensor.window,
    windowMean
  )

  // ------------------------------------------------
  // 3. Exponential moving average
  // ------------------------------------------------

  if (sensor.emaMean === null) {
    sensor.emaMean = windowMean
    sensor.emaStd = windowStd || 0.5
  } else {
    sensor.emaMean =
      EMA_ALPHA * windowMean +
      (1 - EMA_ALPHA) * sensor.emaMean

    sensor.emaStd =
      EMA_ALPHA * (windowStd || 0.5) +
      (1 - EMA_ALPHA) * sensor.emaStd
  }

  const effectiveStd = Math.max(
    sensor.emaStd,
    0.01
  )

  // ------------------------------------------------
  // 4. Confidence
  // ------------------------------------------------

  const confidence = clamp(
    sensor.readingCount /
      (MIN_CONFIDENCE_READINGS * 4),
    0,
    1
  )

  // ------------------------------------------------
  // 5. Z-score
  // ------------------------------------------------

  const z = Math.abs(
    value - sensor.emaMean
  ) / effectiveStd

  const zScore = clamp(
    z * 18,
    0,
    70
  )

  // ------------------------------------------------
  // 6. Rate of change
  // ------------------------------------------------

  const delta =
    sensor.lastValue !== null
      ? Math.abs(value - sensor.lastValue)
      : 0

  const rateOfChange = clamp(
    (delta / (effectiveStd + 0.001)) * 15,
    0,
    30
  )

  // ------------------------------------------------
  // 7. Anomaly streak
  // ------------------------------------------------

  const rawScore = zScore + rateOfChange

  if (rawScore >= SCORE_WARNING * 0.6) {
    sensor.streakCount = Math.min(
      sensor.streakCount + 1,
      10
    )
  } else {
    sensor.streakCount = Math.max(
      sensor.streakCount - 1,
      0
    )
  }

  const streakBonus = sensor.streakCount * 2

  // ------------------------------------------------
  // 8. Final anomaly score
  // ------------------------------------------------

  let score = clamp(
    rawScore + streakBonus,
    0,
    100
  )

  // ------------------------------------------------
  // 9. Status determination
  // ------------------------------------------------

  let status

  if (confidence < 0.3 && staticSensor) {
    if (value > staticSensor.warning.max) {
      status = 'critical'
    } else if (value > staticSensor.normal.max) {
      status = 'warning'
    } else {
      status = 'normal'
    }

    score =
      status === 'critical'
        ? 80
        : status === 'warning'
          ? 55
          : 15

  } else {
    if (score >= SCORE_CRITICAL) {
      status = 'critical'
    } else if (score >= SCORE_WARNING) {
      status = 'warning'
    } else {
      status = 'normal'
    }

    if (staticSensor) {
      if (
        value > staticSensor.warning.max &&
        status !== 'critical'
      ) {
        status = 'critical'

        score = Math.max(
          score,
          SCORE_CRITICAL + 5
        )

      } else if (
        value > staticSensor.normal.max &&
        status === 'normal'
      ) {
        status = 'warning'

        score = Math.max(
          score,
          SCORE_WARNING + 2
        )
      }
    }
  }

  // ------------------------------------------------
  // 10. Learned normal range
  // ------------------------------------------------

  if (
    status === 'normal' &&
    sensor.readingCount >= MIN_CONFIDENCE_READINGS
  ) {
    const band3sig = effectiveStd * 3

    sensor.learnedNormal = {
      min: Math.max(
        sensor.emaMean - band3sig,
        0
      ),

      max: sensor.emaMean + band3sig,
    }
  }

  // ------------------------------------------------
  // 11. Accuracy estimate
  // ------------------------------------------------

  if (
    staticSensor &&
    sensor.readingCount > MIN_CONFIDENCE_READINGS
  ) {
    const staticStatus =
      value > staticSensor.warning.max
        ? 'critical'
        : value > staticSensor.normal.max
          ? 'warning'
          : 'normal'

    if (status === staticStatus) {
      sensor.correctedCount++
    }

    sensor.accuracy = clamp(
      sensor.correctedCount /
        sensor.readingCount,
      0.80,
      0.99
    )
  }

  // ------------------------------------------------
  // 12. Update selected environment
  // ------------------------------------------------

  sensor.lastValue = value
  sensor.lastStatus = status
  sensor.lastScore = score
  sensor.lastTs = ts

  if (sensor.readingCount % 10 === 0) {
    saveState(
      environment,
      selectedSource
    )
  }

  // ------------------------------------------------
  // 13. Emit source-aware event
  // ------------------------------------------------

  try {
    window.dispatchEvent(
      new CustomEvent('iw:ml:update', {
        detail: {
          sensorKey,
          status,
          score,
          confidence,
          value,
          ts,
          source: selectedSource,
        },
      })
    )
  } catch {
    // SSR / worker context.
  }

  return {
    status,
    score,
    confidence,
    learnedNormal: sensor.learnedNormal,
    delta,
  }
}


// ==================================================
// GET SENSOR STATE
// ==================================================

function getState(
  sensorKey,
  source = 'hardware'
) {
  const selectedSource = normalizeSource(source)

  const sensor = _state[selectedSource][sensorKey]

  if (!sensor) return null

  return {
    status: sensor.lastStatus,
    score: sensor.lastScore,

    confidence: clamp(
      sensor.readingCount /
        (MIN_CONFIDENCE_READINGS * 4),
      0,
      1
    ),

    readingCount: sensor.readingCount,

    emaMean: sensor.emaMean,
    emaStd: sensor.emaStd,

    learnedNormal: sensor.learnedNormal,

    accuracy: sensor.accuracy,
    streakCount: sensor.streakCount,

    source: selectedSource,
  }
}


// ==================================================
// GET ENVIRONMENT SUMMARY
// ==================================================

function getSummary(source = 'hardware') {
  const selectedSource = normalizeSource(source)

  return Object.fromEntries(
    Object.keys(_state[selectedSource]).map(
      key => [
        key,
        getState(key, selectedSource),
      ]
    )
  )
}


// ==================================================
// RESET SENSOR MODEL
// ==================================================

function resetSensor(
  sensorKey,
  source = 'hardware'
) {
  const selectedSource = normalizeSource(source)

  const environment = _state[selectedSource]

  if (!environment[sensorKey]) return

  environment[sensorKey] = makeSensorState()

  saveState(
    environment,
    selectedSource
  )
}


// ==================================================
// FEEDBACK LEARNING
// ==================================================

function feedback(
  sensorKey,
  label,
  source = 'hardware'
) {
  const selectedSource = normalizeSource(source)

  const sensor = _state[selectedSource][sensorKey]

  if (!sensor) return

  if (label === 'anomaly') {
    sensor.emaStd = Math.max(
      (sensor.emaStd ?? 0.5) * 0.92,
      0.01
    )
  } else if (label === 'normal') {
    sensor.emaStd =
      (sensor.emaStd ?? 0.5) * 1.06
  } else {
    return
  }

  saveState(
    _state[selectedSource],
    selectedSource
  )
}


// ==================================================
// CONFIDENCE LABEL
// ==================================================

function confidenceLabel(confidence) {
  if (confidence >= 0.85) return 'High'
  if (confidence >= 0.5) return 'Building'
  if (confidence >= 0.2) return 'Warming up'

  return 'Cold start'
}


// ==================================================
// PUBLIC API
// ==================================================

export const mlEngine = {
  ingest,
  getState,
  getSummary,
  resetSensor,
  feedback,
  confidenceLabel,
}