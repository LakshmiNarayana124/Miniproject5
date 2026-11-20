// ==================================================
// INTELLIWATCH — REMAINING USEFUL LIFE (RUL) HOOK
//
// Estimates the time until the anomaly score is
// projected to cross the CRITICAL threshold (72)
// based on a linear regression over the recent
// score history held by the ML engine.
//
// Method
// ------
// The mlEngine emits 'iw:ml:update' events each
// time a reading is ingested.  This hook maintains
// a rolling window of (timestamp, score) pairs per
// sensor and fits a least-squares slope to them.
// A positive slope that would cross SCORE_CRITICAL
// within a finite horizon produces an estimate;
// otherwise the status is 'stable'.
//
// Output states
// -------------
//   stable      – score flat or falling
//   warning     – crossing predicted < 72 h
//   soon        – crossing predicted < 24 h
//   imminent    – crossing predicted < 4 h
//   exceeded    – score already above critical
//   cold        – not enough data to estimate
//
// References
// ----------
// ISO 13381-1:2015 — Condition monitoring and
// diagnostics: prognostics (RUL concept).
// ==================================================

import { useEffect, useRef, useState } from 'react'
import { mlEngine } from './mlEngine'

const SCORE_CRITICAL = 72
const WINDOW_SIZE    = 40   // score history points
const MIN_POINTS     = 8    // minimum before regression

// ms horizons
const H_IMMINENT = 4  * 60 * 60 * 1000
const H_SOON     = 24 * 60 * 60 * 1000
const H_WARNING  = 72 * 60 * 60 * 1000

/**
 * Least-squares linear slope over (x, y) pairs.
 * Returns { slope, intercept }.
 */
function linearRegression(pairs) {
  const n = pairs.length
  if (n < 2) return { slope: 0, intercept: pairs[0]?.[1] ?? 0 }

  let sumX = 0, sumY = 0, sumXX = 0, sumXY = 0
  for (const [x, y] of pairs) {
    sumX  += x
    sumY  += y
    sumXX += x * x
    sumXY += x * y
  }

  const denom = n * sumXX - sumX * sumX
  if (denom === 0) return { slope: 0, intercept: sumY / n }

  const slope     = (n * sumXY - sumX * sumY) / denom
  const intercept = (sumY - slope * sumX) / n
  return { slope, intercept }
}

/**
 * useRUL — returns the worst-case RUL estimate across
 * the sensors that are actively receiving readings.
 *
 * @param {'hardware'|'simulation'|'offline-demo'} source
 * @returns {{
 *   status: 'stable'|'warning'|'soon'|'imminent'|'exceeded'|'cold',
 *   hoursUntilCritical: number|null,
 *   dominantSensor: string|null,
 *   confidence: number,
 * }}
 */
export default function useRUL(source = 'hardware') {
  // histories: { [sensorKey]: Array<[ts, score]> }
  const historiesRef = useRef({
    vibration:   [],
    temperature: [],
    current:     [],
  })

  const [result, setResult] = useState({
    status: 'cold',
    hoursUntilCritical: null,
    dominantSensor: null,
    confidence: 0,
  })

  useEffect(() => {
    // Reset histories when source changes
    historiesRef.current = {
      vibration:   [],
      temperature: [],
      current:     [],
    }

    function handleUpdate(event) {
      const { sensorKey, score, source: evtSource } = event.detail ?? {}
      if (evtSource !== source) return
      if (!sensorKey || score === undefined) return

      const hist = historiesRef.current
      if (!hist[sensorKey]) return

      hist[sensorKey].push([Date.now(), score])
      if (hist[sensorKey].length > WINDOW_SIZE) {
        hist[sensorKey].shift()
      }

      recalculate()
    }

    function recalculate() {
      const hist = historiesRef.current
      let worstHours = Infinity
      let worstSensor = null
      let totalPoints = 0
      let anyExceeded = false
      let dominantConf = 0

      for (const [key, pairs] of Object.entries(hist)) {
        if (pairs.length === 0) continue
        totalPoints += pairs.length

        const latestScore = pairs[pairs.length - 1][1]

        if (latestScore >= SCORE_CRITICAL) {
          anyExceeded = true
          worstSensor = key
          continue
        }

        if (pairs.length < MIN_POINTS) continue

        // Normalise timestamps to seconds from first point
        const t0 = pairs[0][0]
        const normalised = pairs.map(([ts, sc]) => [(ts - t0) / 1000, sc])

        const { slope, intercept } = linearRegression(normalised)

        if (slope <= 0) continue   // flat or improving

        // Time (seconds) until score reaches SCORE_CRITICAL
        const secsUntil = (SCORE_CRITICAL - intercept) / slope
        if (secsUntil <= 0) continue   // already in the past

        const msUntil = secsUntil * 1000
        const hoursUntil = msUntil / (60 * 60 * 1000)

        if (msUntil < worstHours) {
          worstHours  = msUntil
          worstSensor = key
          // Confidence: more points + steeper slope = higher confidence
          dominantConf = Math.min(
            Math.round((pairs.length / WINDOW_SIZE) * 100),
            95
          )
        }
      }

      if (totalPoints < MIN_POINTS) {
        setResult({ status: 'cold', hoursUntilCritical: null, dominantSensor: null, confidence: 0 })
        return
      }

      if (anyExceeded && worstSensor) {
        setResult({ status: 'exceeded', hoursUntilCritical: 0, dominantSensor: worstSensor, confidence: 95 })
        return
      }

      if (worstHours === Infinity) {
        setResult({ status: 'stable', hoursUntilCritical: null, dominantSensor: null, confidence: dominantConf })
        return
      }

      const h = worstHours / (60 * 60 * 1000)
      const status =
        worstHours <= H_IMMINENT ? 'imminent' :
        worstHours <= H_SOON    ? 'soon'     :
        worstHours <= H_WARNING ? 'warning'  :
        'stable'

      setResult({
        status,
        hoursUntilCritical: Math.round(h * 10) / 10,
        dominantSensor: worstSensor,
        confidence: dominantConf,
      })
    }

    window.addEventListener('iw:ml:update', handleUpdate)

    // Seed from current engine state on mount
    const summary = mlEngine.getSummary(source)
    for (const [key, state] of Object.entries(summary)) {
      if (state?.score > 0) {
        historiesRef.current[key].push([Date.now(), state.score])
      }
    }
    recalculate()

    return () => window.removeEventListener('iw:ml:update', handleUpdate)
  }, [source])

  return result
}
