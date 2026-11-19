
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  SENSORS,
  MAX_POINTS,
  CHART_INTERVAL_MS,
  getStatus,
  formatTime,
} from './sensors'

import { mlEngine } from './mlEngine'


const API_BASE = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '')

const WS_BASE = API_BASE.replace(/^http/, 'ws')

const MAX_ALERTS = 200
const DEMO_TOKEN = 'demo-offline'

const EMPTY_DATA = {
  vibration: [],
  temperature: [],
  current: [],
}

const EXPECTED_SOURCES = [
  'hardware',
  'simulation',
  'offline-demo',
]

const VALID_QUALITIES = new Set([
  'GOOD',
  'VALID',
  'WARNING',
  'DEGRADED',
  'ERROR',
  'UNAVAILABLE',
])

const WARNING_QUALITIES = new Set([
  'WARNING',
  'DEGRADED',
])

const UNAVAILABLE_QUALITIES = new Set([
  'ERROR',
  'UNAVAILABLE',
])


// ==================================================
// EMPTY DATA FACTORY
// ==================================================

function createEmptyData() {
  return {
    vibration: [],
    temperature: [],
    current: [],
  }
}


// ==================================================
// TIMESTAMP NORMALIZATION
// ==================================================

function normalizeTimestamp(payload) {
  const rawTimestamp =
    payload.ts ??
    payload.timestamp ??
    Date.now()

  const timestamp = Number(rawTimestamp)

  if (Number.isFinite(timestamp)) {
    return timestamp < 1e12
      ? timestamp * 1000
      : timestamp
  }

  const parsedTimestamp = Date.parse(rawTimestamp)

  return Number.isFinite(parsedTimestamp)
    ? parsedTimestamp
    : Date.now()
}


// ==================================================
// SOURCE NORMALIZATION
// ==================================================

function normalizeSource(source) {
  return EXPECTED_SOURCES.includes(source)
    ? source
    : 'hardware'
}


// ==================================================
// STATUS NORMALIZATION
// ==================================================

function normalizeStatus(value) {
  if (value && typeof value === 'object') {
    value =
      value.status ??
      value.state ??
      value.assessment ??
      value.condition
  }

  if (typeof value !== 'string') return null

  const status = value.trim().toLowerCase()

  if (
    ['normal', 'warning', 'critical'].includes(status)
  ) {
    return status
  }

  if (
    ['good', 'valid', 'healthy'].includes(status)
  ) {
    return 'normal'
  }

  if (status === 'degraded') {
    return 'warning'
  }

  if (
    [
      'unavailable',
      'awaiting-iot',
      'awaiting_iot',
      'no_data',
      'nil',
      'error',
      'invalid',
    ].includes(status)
  ) {
    return 'awaiting-iot'
  }

  return status || null
}


function getBackendSensorStatus(assessment, key) {
  const statuses = assessment?.sensor_statuses

  if (!statuses || typeof statuses !== 'object') {
    return null
  }

  return normalizeStatus(
    statuses[key] ?? statuses[key.toUpperCase()]
  )
}


// ==================================================
// SENSOR POINT CREATION
// ==================================================

function makePoint(
  key,
  raw,
  timestamp,
  assessment,
  source
) {
  const sensor = SENSORS[key]

  const value = raw?.value ?? null

  const numericValue =
    value === null || value === undefined
      ? null
      : Number(value)

  const hasValidValue =
    numericValue !== null &&
    Number.isFinite(numericValue)

  const quality = String(
    raw?.quality ?? 'GOOD'
  ).toUpperCase()

  const backendStatus = getBackendSensorStatus(
    assessment,
    key
  )

  let status

  // Missing or explicitly invalid measurements must never
  // be shown as normal, even if an older assessment exists.
  if (
    !hasValidValue ||
    UNAVAILABLE_QUALITIES.has(quality) ||
    !VALID_QUALITIES.has(quality)
  ) {
    status = 'awaiting-iot'

  // A valid backend assessment takes priority over local
  // threshold calculation.
  } else if (backendStatus !== null) {
    status = backendStatus

  // Warning/degraded measurements remain visible with
  // their actual numeric values.
  } else if (WARNING_QUALITIES.has(quality)) {
    status = 'warning'

  // GOOD and VALID readings use the configured sensor thresholds.
  } else {
    status = getStatus(
      numericValue,
      sensor
    )
  }

  return {
    ts: timestamp,
    value: hasValidValue ? numericValue : null,
    status,
    time: formatTime(new Date(timestamp)),
    source,
  }
}


function appendPoint(previous, point) {
  const next = [...previous, point]

  return next.length > MAX_POINTS
    ? next.slice(-MAX_POINTS)
    : next
}


// ==================================================
// LOCAL SIMULATION VALUE GENERATOR
//
// Used only for:
// 1. Explicit online Simulation mode.
// 2. Existing offline Demo login.
//
// Never used as a substitute for hardware readings.
// ==================================================

function generateLocalValue(sensor, timestamp) {
  const base = Number(sensor?.base)

  if (!Number.isFinite(base)) {
    return null
  }

  const configuredNoise = Number(sensor?.noise)
  const configuredSpike = Number(sensor?.spike)

  const noise = Number.isFinite(configuredNoise)
    ? Math.abs(configuredNoise)
    : 0

  const spike = Number.isFinite(configuredSpike)
    ? Math.abs(configuredSpike)
    : 0

  const randomNoise =
    (Math.random() * 2 - 1) * noise

  const drift =
    Math.sin(timestamp / 27000) *
    noise *
    0.35

  const anomaly =
    Math.random() < 0.015
      ? spike * 2
      : 0

  const value = Math.max(
    0,
    base + randomNoise + drift + anomaly
  )

  return Number(value.toFixed(2))
}


// ==================================================
// MAIN SENSOR DATA HOOK
// ==================================================

/**
 * @param {string|null} token
 * @param {'iot'|'simulation'} operatingMode
 *
 * Behaviour:
 *
 * Registered account + IoT:
 *   Backend WebSocket and HTTP polling fallback.
 *
 * Registered account + Simulation:
 *   Local synthetic readings.
 *   No sensor API or WebSocket requests.
 *
 * Offline demo token:
 *   Local demo readings only.
 *   No backend requests.
 *
 * No token:
 *   No sensor acquisition.
 */

export default function useSensorData(
  token,
  operatingMode = 'iot'
) {
  const [data, setData] = useState(createEmptyData)
  const [alerts, setAlerts] = useState([])

  const [connectionStatus, setConnectionStatus] =
    useState('offline')

  const wsRef = useRef(null)
  const pollRef = useRef(null)
  const retryRef = useRef(null)

  const retryCount = useRef(0)
  const lastAlertStatus = useRef({})
  const pollingInProgress = useRef(false)


  // ==================================================
  // PROCESS SENSOR PAYLOAD
  // ==================================================

  const processPayload = useCallback((
    payload,
    source = 'hardware'
  ) => {
    if (!payload || typeof payload !== 'object') {
      return
    }

    const selectedSource = normalizeSource(source)

    const timestamp = normalizeTimestamp(payload)

    const assessment = payload.assessment ?? null

    const points = {}
    const newAlerts = []

    for (const key of Object.keys(SENSORS)) {
      const raw = payload[key]

      if (!raw || typeof raw !== 'object') {
        continue
      }

      const point = makePoint(
        key,
        raw,
        timestamp,
        assessment,
        selectedSource
      )

      points[key] = point

      if (
        point.value !== null &&
        Number.isFinite(point.value)
      ) {
        mlEngine.ingest(
          key,
          point.value,
          timestamp,
          SENSORS[key],
          selectedSource
        )
      }

      const previous = lastAlertStatus.current[key]

      if (
        point.status === 'warning' ||
        point.status === 'critical'
      ) {
        if (previous !== point.status) {
          newAlerts.push({
            id: `${key}-${timestamp}-${Math.random()}`,
            sensor: key,
            label: SENSORS[key].label,
            status: point.status,
            value: point.value,
            unit: SENSORS[key].unit,
            time: point.time,
            source: selectedSource,
          })
        }

        lastAlertStatus.current[key] = point.status

      } else if (
        point.status === 'normal' ||
        point.status === 'awaiting-iot'
      ) {
        lastAlertStatus.current[key] = point.status
      }
    }

    if (Object.keys(points).length > 0) {
      setData(previous => {
        const next = { ...previous }

        for (const [key, point] of Object.entries(points)) {
          next[key] = appendPoint(
            previous[key] ?? [],
            point
          )
        }

        return next
      })
    }

    if (newAlerts.length > 0) {
      setAlerts(previous =>
        [
          ...newAlerts.reverse(),
          ...previous,
        ].slice(0, MAX_ALERTS)
      )
    }
  }, [])


  // ==================================================
  // GENERATE LOCAL SIMULATION PAYLOAD
  // ==================================================

  const generateLocalPayload = useCallback((
    source
  ) => {
    const selectedSource = normalizeSource(source)

    if (
      selectedSource !== 'simulation' &&
      selectedSource !== 'offline-demo'
    ) {
      return
    }

    const timestamp = Date.now()

    const payload = {
      ts: timestamp,
    }

    for (const key of Object.keys(SENSORS)) {
      payload[key] = {
        value: generateLocalValue(
          SENSORS[key],
          timestamp
        ),

        quality: 'GOOD',

        metadata: {
          source: selectedSource,

          measurement_type:
            selectedSource === 'simulation'
              ? 'simulated_frontend'
              : 'offline_demo',
        },
      }
    }

    processPayload(
      payload,
      selectedSource
    )
  }, [processPayload])


  // ==================================================
  // STOP BACKEND POLLING
  // ==================================================

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])


  // ==================================================
  // CLOSE WEBSOCKET
  // ==================================================

  const closeWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen = null
      wsRef.current.onmessage = null
      wsRef.current.onerror = null
      wsRef.current.onclose = null

      try {
        wsRef.current.close()
      } catch {
        // Ignore already-closed sockets.
      }

      wsRef.current = null
    }
  }, [])


  // ==================================================
  // STOP RETRIES
  // ==================================================

  const stopRetry = useCallback(() => {
    if (retryRef.current) {
      clearTimeout(retryRef.current)
      retryRef.current = null
    }

    retryCount.current = 0
  }, [])


  // ==================================================
  // BACKEND POLLING
  //
  // Used only by registered users in IoT mode.
  // ==================================================

  const startPolling = useCallback(() => {
    if (!token || token === DEMO_TOKEN) return

    if (pollRef.current) return

    setConnectionStatus('polling')

    const poll = async () => {
      if (pollingInProgress.current) return

      pollingInProgress.current = true

      try {
        const response = await fetch(
          `${API_BASE}/sensors/all`,
          {
            method: 'GET',

            cache: 'no-store',

            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        )

        if (!response.ok) {
          setConnectionStatus('offline')
          return
        }

        const payload = await response.json()

        processPayload(
          payload,
          'hardware'
        )

        setConnectionStatus(
          payload.status === 'unavailable'
            ? 'awaiting-iot'
            : 'polling'
        )

      } catch {
        setConnectionStatus('offline')

      } finally {
        pollingInProgress.current = false
      }
    }

    poll()

    pollRef.current = setInterval(
      poll,
      CHART_INTERVAL_MS
    )
  }, [token, processPayload])


  // ==================================================
  // WEBSOCKET CONNECTION
  //
  // Used only by registered users in IoT mode.
  // ==================================================

  const connectWS = useCallback(() => {
    if (!token || token === DEMO_TOKEN) {
      setConnectionStatus('offline')
      return
    }

    try {
      const url =
        `${WS_BASE}/stream/sensors?token=${encodeURIComponent(token)}`

      const ws = new WebSocket(url)

      wsRef.current = ws

      ws.onopen = () => {
        setConnectionStatus('live')

        retryCount.current = 0

        stopPolling()
      }

      ws.onmessage = event => {
        try {
          const payload = JSON.parse(event.data)

          processPayload(
            payload,
            'hardware'
          )

          if (payload.status === 'unavailable') {
            setConnectionStatus('awaiting-iot')
          } else {
            setConnectionStatus('live')
          }

        } catch {
          // Ignore malformed WebSocket messages.
        }
      }

      ws.onerror = () => {
        startPolling()
      }

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null
        }

        startPolling()

        const delay = Math.min(
          2000 * 2 ** retryCount.current,
          30000
        )

        retryCount.current++

        clearTimeout(retryRef.current)

        retryRef.current = setTimeout(
          connectWS,
          delay
        )
      }

    } catch {
      startPolling()
    }
  }, [
    token,
    processPayload,
    startPolling,
    stopPolling,
  ])


  // ==================================================
  // SESSION AND OPERATING MODE MANAGEMENT
  // ==================================================

  useEffect(() => {
    const isOfflineDemo = token === DEMO_TOKEN

    const selectedSource = isOfflineDemo
      ? 'offline-demo'
      : operatingMode === 'simulation'
        ? 'simulation'
        : 'hardware'

    // ------------------------------------------------
    // Reset previous connections and timers.
    // ------------------------------------------------

    stopPolling()
    stopRetry()
    closeWebSocket()

    pollingInProgress.current = false
    lastAlertStatus.current = {}

    setData(createEmptyData())
    setAlerts([])

    // ------------------------------------------------
    // No authenticated session.
    // ------------------------------------------------

    if (!token) {
      setConnectionStatus('offline')

      return () => {
        stopPolling()
        stopRetry()
        closeWebSocket()
      }
    }

    // ------------------------------------------------
    // Offline demo session.
    //
    // No backend requests.
    // ------------------------------------------------

    if (isOfflineDemo) {
      setConnectionStatus('demo')

      generateLocalPayload('offline-demo')

      const demoInterval = setInterval(
        () => generateLocalPayload('offline-demo'),
        CHART_INTERVAL_MS
      )

      return () => {
        clearInterval(demoInterval)

        stopPolling()
        stopRetry()
        closeWebSocket()
      }
    }

    // ------------------------------------------------
    // Explicit online Simulation mode.
    //
    // No backend sensor API requests.
    // No sensor WebSocket.
    // No hardware commands.
    // ------------------------------------------------

    if (selectedSource === 'simulation') {
      setConnectionStatus('simulation')

      generateLocalPayload('simulation')

      const simulationInterval = setInterval(
        () => generateLocalPayload('simulation'),
        CHART_INTERVAL_MS
      )

      return () => {
        clearInterval(simulationInterval)

        stopPolling()
        stopRetry()
        closeWebSocket()
      }
    }

    // ------------------------------------------------
    // Default online IoT / Hardware mode.
    //
    // Never generates local synthetic readings.
    // ------------------------------------------------

    setConnectionStatus('connecting')

    connectWS()

    return () => {
      stopPolling()
      stopRetry()
      closeWebSocket()
    }

  }, [
    token,
    operatingMode,
    connectWS,
    generateLocalPayload,
    stopPolling,
    stopRetry,
    closeWebSocket,
  ])


  // ==================================================
  // CLEAR ALERTS
  // ==================================================

  const clearAlerts = useCallback(() => {
    setAlerts([])
  }, [])


  return {
    data,
    alerts,
    connectionStatus,
    clearAlerts,
  }
}
