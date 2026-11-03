// ==================================================
// useSensorData — live sensor data hook
// ==================================================
// Opens a WebSocket to ws://[host]/stream/sensors and
// pushes incoming readings into the shared `data` state.
//
// Falls back to HTTP polling every CHART_INTERVAL_MS if
// the WebSocket is unavailable (offline / demo mode).
//
// Usage:
//   const { data, alerts, connectionStatus } = useSensorData(token)
//
// Returns:
//   data            — { vibration: [...], temperature: [...], current: [...] }
//   alerts          — flat array of alert objects (newest first, capped at 200)
//   connectionStatus — 'connecting' | 'live' | 'polling' | 'offline'
// ==================================================

import { useState, useEffect, useRef, useCallback } from 'react'
import { SENSORS, MAX_POINTS, CHART_INTERVAL_MS, getStatus, formatTime } from './sensors'
import { mlEngine } from './mlEngine'

const API_BASE  = import.meta.env.VITE_API_URL  || 'http://localhost:8000'
const WS_BASE   = API_BASE.replace(/^http/, 'ws')
const MAX_ALERTS = 200

function makePoint(sensorKey, raw, ts) {
  const value  = raw?.value ?? null
  const sensor = SENSORS[sensorKey]
  const status = getStatus(value, sensor)
  return { ts, value, status, time: formatTime(new Date(ts)) }
}

function appendPoint(arr, point) {
  const next = [...arr, point]
  return next.length > MAX_POINTS ? next.slice(next.length - MAX_POINTS) : next
}

function maybeAlert(sensorKey, point, setAlerts) {
  const { status, value, time } = point
  if (status === 'critical' || status === 'warning') {
    const sensor = SENSORS[sensorKey]
    setAlerts(prev => {
      const entry = {
        id:     Date.now() + Math.random(),
        sensor: sensorKey,
        label:  sensor.label,
        status,
        value,
        unit:   sensor.unit,
        time,
      }
      const next = [entry, ...prev]
      return next.length > MAX_ALERTS ? next.slice(0, MAX_ALERTS) : next
    })
  }
}

export default function useSensorData(token) {
  const emptyData = { vibration: [], temperature: [], current: [] }
  const [data,             setData]             = useState(emptyData)
  const [alerts,           setAlerts]           = useState([])
  const [connectionStatus, setConnectionStatus] = useState('connecting')

  const wsRef      = useRef(null)
  const pollRef    = useRef(null)
  const retryRef   = useRef(null)
  const retryCount = useRef(0)

  const processPayload = useCallback((payload) => {
    const ts = payload.ts || Date.now()
    setData(prev => {
      const next = { ...prev }
      for (const key of Object.keys(SENSORS)) {
        const raw   = payload[key]
        if (!raw) continue
        const point = makePoint(key, raw, ts)
        next[key]   = appendPoint(prev[key], point)
        // Feed browser-side ML engine
        if (point.value !== null && Number.isFinite(Number(point.value))) {
          mlEngine.ingest(key, Number(point.value), ts, SENSORS[key])
        }
        maybeAlert(key, point, setAlerts)
      }
      return next
    })
  }, [])

  // ── HTTP polling fallback ──────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    if (pollRef.current) return
    setConnectionStatus('polling')
    async function poll() {
      try {
        const headers = token && token !== 'demo-offline'
          ? { Authorization: `Bearer ${token}` }
          : {}
        const res = await fetch(`${API_BASE}/sensors/all`, { headers })
        if (res.ok) {
          const json = await res.json()
          // Normalise AllSensorsData shape to the flat shape our code expects
          const payload = {
            ts:          json.ts || (json.timestamp ? json.timestamp * 1000 : Date.now()),
            vibration:   json.vibration,
            temperature: json.temperature,
            current:     json.current,
          }
          processPayload(payload)
        }
      } catch {
        setConnectionStatus('offline')
      }
    }
    poll()
    pollRef.current = setInterval(poll, CHART_INTERVAL_MS)
  }, [token, processPayload])

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  // ── WebSocket connection ───────────────────────────────────────────────────
  const connectWS = useCallback(() => {
    if (!token || token === 'demo-offline') {
      // Demo / offline mode — use polling instead (no auth needed for demo)
      startPolling()
      return
    }

    const url = `${WS_BASE}/stream/sensors?token=${encodeURIComponent(token)}`
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionStatus('live')
      retryCount.current = 0
      stopPolling()
    }

    ws.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data)
        processPayload(payload)
      } catch { /* malformed frame */ }
    }

    ws.onerror = () => {
      // Switch to polling while we wait to retry
      startPolling()
    }

    ws.onclose = () => {
      wsRef.current = null
      startPolling()
      // Exponential back-off retry (max 30 s)
      const delay = Math.min(2000 * 2 ** retryCount.current, 30000)
      retryCount.current++
      retryRef.current = setTimeout(connectWS, delay)
    }
  }, [token, processPayload, startPolling, stopPolling])

  useEffect(() => {
    connectWS()
    return () => {
      clearTimeout(retryRef.current)
      stopPolling()
      if (wsRef.current) {
        wsRef.current.onclose = null  // prevent auto-retry on unmount
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connectWS, stopPolling])

  const clearAlerts = useCallback(() => setAlerts([]), [])

  return { data, alerts, connectionStatus, clearAlerts }
}
