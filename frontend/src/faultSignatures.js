// ==================================================
// INTELLIWATCH — FAULT SIGNATURE LIBRARY
//
// Maps multi-sensor patterns to named industrial
// fault classes using rules derived from:
//   - ISO 10816-3 vibration severity zones
//   - IEC 60034-1 thermal insulation classes
//   - IEEE 1159 power quality / motor current
//   - ISO 13373-1 condition monitoring practices
//
// Each rule scores 0-100 for how well the current
// sensor state matches the fault pattern.  The
// highest-scoring match above MIN_CONFIDENCE is
// returned.  Below that threshold the result is
// 'nominal' (no fault signature detected).
//
// This is intentionally rule-based so it works
// entirely in the browser without model files.
// The Python backend's DetectionTrace adds
// fault_hint from the same logic server-side.
// ==================================================

const MIN_CONFIDENCE = 32   // below this → no match reported

// Fault catalogue
// Each entry has:
//   id         – machine-readable key
//   label      – display name
//   severity   – 'low' | 'medium' | 'high'
//   standard   – normative reference shown in UI
//   description – one-line plain language meaning
//   match(v,t,c,mlV,mlT,mlC) – returns 0-100 confidence
//     v  = vibration mm/s   (null if unavailable)
//     t  = temperature °C
//     c  = current A
//     mlV/mlT/mlC = mlEngine state objects for each sensor
const FAULT_CATALOGUE = [
  {
    id: 'bearing_wear',
    label: 'Bearing Wear',
    severity: 'high',
    standard: 'ISO 10816-3 / ISO 13373-1',
    description: 'Progressive rolling-element bearing degradation. Elevated vibration with stable or mildly elevated temperature and current.',
    match(v, t, c, mlV) {
      if (v === null) return 0
      // Vibration elevated into warning/critical zone
      let score = 0
      if (v > 7.1)      score += 55
      else if (v > 4.5) score += 40
      else if (v > 3.5) score += 20
      else return 0
      // Streak bonus — persistent anomaly is a bearing signature
      if (mlV?.streakCount >= 4) score += 20
      else if (mlV?.streakCount >= 2) score += 10
      // Temperature: bearings run warm but rarely critical at onset
      if (t !== null && t > 100) score -= 10   // too hot → more likely thermal
      if (t !== null && t > 80 && t <= 100) score += 8
      // Current stable (bearing wear does not immediately load current)
      if (c !== null && c < 16.5) score += 7
      return Math.min(score, 95)
    },
  },
  {
    id: 'mechanical_imbalance',
    label: 'Mechanical Imbalance',
    severity: 'medium',
    standard: 'ISO 10816-3',
    description: 'Rotating mass imbalance causing sinusoidal vibration at 1× running frequency. Vibration elevated, temperature and current near-normal.',
    match(v, t, c, mlV) {
      if (v === null) return 0
      let score = 0
      if (v > 4.5 && v <= 10) score += 45
      else if (v > 2.8 && v <= 4.5) score += 25
      else return 0
      // Imbalance is consistent — streak grows steadily
      if (mlV?.streakCount >= 3 && mlV?.streakCount < 8) score += 18
      // Temperature should be close to normal
      if (t !== null && t < 80) score += 10
      else if (t !== null && t >= 80) score -= 8
      // Current near rated (imbalance loads shaft, not winding)
      if (c !== null && c > 12 && c < 16.5) score += 10
      return Math.min(score, 90)
    },
  },
  {
    id: 'thermal_overload',
    label: 'Thermal Overload',
    severity: 'high',
    standard: 'IEC 60034-1 Class F',
    description: 'Winding or bearing temperature exceeds safe operating limit. Likely caused by overloading, blocked ventilation, or coolant failure.',
    match(v, t, c, _mlV, mlT) {
      if (t === null) return 0
      let score = 0
      if (t > 100)     score += 60
      else if (t > 85) score += 40
      else if (t > 80) score += 20
      else return 0
      // Sustained high temperature (streak)
      if (mlT?.streakCount >= 3) score += 20
      // High current → overload rather than ventilation blockage
      if (c !== null && c > 16.5) score += 12
      // Vibration can be normal during thermal event
      if (v !== null && v < 4.5) score += 5
      return Math.min(score, 95)
    },
  },
  {
    id: 'electrical_overload',
    label: 'Electrical Overload',
    severity: 'high',
    standard: 'IEC 60947-4-1 / NEMA MG-1',
    description: 'Motor drawing current above service factor limit. Indicates excessive mechanical load, phase imbalance, or starting condition.',
    match(v, t, c, _mlV, _mlT, mlC) {
      if (c === null) return 0
      let score = 0
      if (c > 18.75)     score += 60
      else if (c > 16.5) score += 40
      else if (c > 15)   score += 15
      else return 0
      if (mlC?.streakCount >= 3) score += 20
      // High current + high temperature is a compound overload
      if (t !== null && t > 80) score += 12
      // Vibration may be elevated due to load stress
      if (v !== null && v > 4.5) score += 8
      return Math.min(score, 95)
    },
  },
  {
    id: 'misalignment',
    label: 'Shaft Misalignment',
    severity: 'medium',
    standard: 'ISO 10816-3 / ISO 13373-1',
    description: 'Coupling or shaft misalignment generates vibration at 1× and 2× running frequency with possible axial component and mild current fluctuation.',
    match(v, t, c, mlV) {
      if (v === null) return 0
      let score = 0
      if (v > 4.5 && v <= 9) score += 38
      else if (v > 3.0 && v <= 4.5) score += 20
      else return 0
      // Misalignment appears suddenly (rate of change high)
      if (mlV?.lastDelta !== undefined && mlV.lastDelta > 0.5) score += 15
      // Current slightly elevated (additional mechanical load)
      if (c !== null && c > 14 && c <= 18) score += 12
      // Temperature mildly elevated from coupling friction
      if (t !== null && t > 65 && t < 90) score += 10
      return Math.min(score, 85)
    },
  },
  {
    id: 'mechanical_looseness',
    label: 'Mechanical Looseness',
    severity: 'medium',
    standard: 'ISO 13373-1',
    description: 'Loose mounting bolts or structural looseness. Vibration typically erratic with high peak-to-trough variation.',
    match(v, t, c, mlV) {
      if (v === null) return 0
      let score = 0
      if (v > 4.5) score += 30
      else if (v > 3.0) score += 15
      else return 0
      // Looseness is intermittent → std deviation large relative to mean
      const emaM = mlV?.emaMean ?? 0
      const emaS = mlV?.emaStd ?? 0
      if (emaM > 0 && emaS / emaM > 0.3) score += 25
      // Current and temperature near-normal
      if (c !== null && c < 16.5) score += 8
      if (t !== null && t < 80) score += 8
      return Math.min(score, 80)
    },
  },
  {
    id: 'compound_fault',
    label: 'Compound Fault',
    severity: 'high',
    standard: 'ISO 10816-3 / IEC 60034-1',
    description: 'Multiple sensors simultaneously in abnormal zones. Likely combined mechanical and thermal stress — requires immediate inspection.',
    match(v, t, c) {
      let zones = 0
      if (v !== null && v > 4.5)  zones++
      if (t !== null && t > 80)   zones++
      if (c !== null && c > 16.5) zones++
      if (zones < 2) return 0
      let score = zones === 3 ? 85 : 60
      if (v !== null && v > 7.1)  score += 8
      if (t !== null && t > 100)  score += 8
      if (c !== null && c > 18.75) score += 8
      return Math.min(score, 98)
    },
  },
]

// Severity colour tokens (consistent with status colours in sensors.js)
export const FAULT_SEVERITY_COLOR = {
  high:   '#ef4444',
  medium: '#f59e0b',
  low:    '#22c55e',
}

/**
 * Classify the current sensor readings against the fault catalogue.
 *
 * @param {object} readings  { vibration, temperature, current } — numeric or null
 * @param {object} mlStates  { vibration, temperature, current } — mlEngine state objects
 * @returns {{ id, label, severity, standard, description, confidence } | null}
 *   The best-matching fault, or null when no pattern exceeds MIN_CONFIDENCE.
 */
export function classifyFaultType(readings = {}, mlStates = {}) {
  const v = readings.vibration  ?? null
  const t = readings.temperature ?? null
  const c = readings.current     ?? null

  const mlV = mlStates.vibration   ?? null
  const mlT = mlStates.temperature ?? null
  const mlC = mlStates.current     ?? null

  let best = null
  let bestScore = MIN_CONFIDENCE - 1

  for (const fault of FAULT_CATALOGUE) {
    const score = fault.match(v, t, c, mlV, mlT, mlC)
    if (score > bestScore) {
      bestScore = score
      best = fault
    }
  }

  if (!best) return null

  return {
    id:          best.id,
    label:       best.label,
    severity:    best.severity,
    standard:    best.standard,
    description: best.description,
    confidence:  Math.round(bestScore),
  }
}

/**
 * Run classifyFaultType against a single sensor's ML state only.
 * Used by MLStatusPanel to show per-card fault hints.
 */
export function classifyFaultForSensor(sensorKey, value, mlState) {
  const readings = { vibration: null, temperature: null, current: null }
  const states   = { vibration: null, temperature: null, current: null }

  if (value !== null && value !== undefined) {
    readings[sensorKey] = value
  }
  if (mlState) {
    states[sensorKey] = mlState
  }

  return classifyFaultType(readings, states)
}
