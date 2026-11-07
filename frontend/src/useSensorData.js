
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  SENSORS,
  MAX_POINTS,
  CHART_INTERVAL_MS,
  getStatus,
  formatTime,
} from './sensors'
import { mlEngine } from './mlEngine'

const API_BASE =
  import.meta.env.VITE_API_URL || 'http://localhost:8000'

const WS_BASE = API_BASE.replace(/^http/, 'ws')
const MAX_ALERTS = 200

const EMPTY_DATA = {
  vibration: [],
  temperature: [],
  current: [],
}

function normalizeTimestamp(payload) {
  const timestamp = Number(
    payload.ts ?? payload.timestamp ?? Date.now()
  )

  if (!Number.isFinite(timestamp)) return Date.now()

  return timestamp < 1e12 ? timestamp * 1000 : timestamp
}

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

  if (['normal', 'warning', 'critical'].includes(status)) {
    return status
  }

  return status || null
}

function getBackendSensorStatus(assessment, key) {
  const statuses = assessment?.sensor_statuses

  if (!statuses || typeof statuses !== 'object') return null

  return normalizeStatus(
    statuses[key] ?? statuses[key.toUpperCase()]
  )
}

function makePoint(key, raw, timestamp, assessment) {
  const value = raw?.value ?? null
  const sensor = SENSORS[key]

  const backendStatus = getBackendSensorStatus(
    assessment,
    key
  )

  return {
    ts: timestamp,
    value,
    status: backendStatus ?? getStatus(value, sensor),
    time: formatTime(new Date(timestamp)),
  }
}

function appendPoint(previous, point) {
  const next = [...previous, point]

  return next.length > MAX_POINTS
    ? next.slice(-MAX_POINTS)
    : next
}

export default function useSensorData(token) {
  const [data, setData] = useState(EMPTY_DATA)
  const [alerts, setAlerts] = useState([])
  const [connectionStatus, setConnectionStatus] =
    useState('connecting')

  const wsRef = useRef(null)
  const pollRef = useRef(null)
  const retryRef = useRef(null)
  const retryCount = useRef(0)
  const lastAlertStatus = useRef({})
  const pollingInProgress = useRef(false)

  const processPayload = useCallback((payload) => {
    if (!payload || typeof payload !== 'object') return

    const timestamp = normalizeTimestamp(payload)
    const assessment = payload.assessment ?? null

    const points = {}
    const newAlerts = []

    for (const key of Object.keys(SENSORS)) {
      const raw = payload[key]

      if (!raw || typeof raw !== 'object') continue

      const point = makePoint(
        key,
        raw,
        timestamp,
        assessment
      )

      points[key] = point

      if (
        point.value !== null &&
        Number.isFinite(Number(point.value))
      ) {
        mlEngine.ingest(
          key,
          Number(point.value),
          timestamp,
          SENSORS[key]
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
          })
        }

        lastAlertStatus.current[key] = point.status
      } else if (point.status === 'normal') {
        lastAlertStatus.current[key] = 'normal'
      }
    }

    if (Object.keys(points).length > 0) {
      setData((previous) => {
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
      setAlerts((previous) =>
        [...newAlerts.reverse(), ...previous].slice(
          0,
          MAX_ALERTS
        )
      )
    }
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(() => {
    if (pollRef.current) return

    setConnectionStatus('polling')

    const poll = async () => {
      if (pollingInProgress.current) return

      pollingInProgress.current = true

      try {
        const headers =
          token && token !== 'demo-offline'
            ? { Authorization: `Bearer ${token}` }
            : {}

        const response = await fetch(
          `${API_BASE}/sensors/all`,
          { headers }
        )

        if (!response.ok) {
          setConnectionStatus('offline')
          return
        }

        const payload = await response.json()

        processPayload(payload)
        setConnectionStatus('polling')
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

  const connectWS = useCallback(() => {
    if (!token || token === 'demo-offline') {
      startPolling()
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

      ws.onmessage = (event) => {
        try {
          processPayload(JSON.parse(event.data))
        } catch {
          // Ignore malformed WebSocket messages.
        }
      }

      ws.onerror = () => {
        startPolling()
      }

      ws.onclose = () => {
        wsRef.current = null
        startPolling()

        const delay = Math.min(
          2000 * 2 ** retryCount.current,
          30000
        )

        retryCount.current += 1

        clearTimeout(retryRef.current)

        retryRef.current = setTimeout(
          connectWS,
          delay
        )
      }
    } catch {
      startPolling()
    }
  }, [token, processPayload, startPolling, stopPolling])

  useEffect(() => {
    connectWS()

    return () => {
      clearTimeout(retryRef.current)
      stopPolling()

      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connectWS, stopPolling])

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
