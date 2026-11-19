import { useEffect, useRef, useState } from 'react'
import './ControlSignalBanner.css'
import { t } from '../i18n'
import useLang from '../useLang'

const API_BASE = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '')

const WS_BASE = API_BASE.replace(/^http/, 'ws')
const WS_URL = `${WS_BASE}/stream/status`
const DEMO_TOKEN = 'demo-offline'

const INTENT_COLOR = {
  SHUTDOWN: '#ef4444',
  DE_RATE: '#f59e0b',
  RUN: '#22c55e',
}

const INTENT_KEY = {
  SHUTDOWN: 'intent_shutdown',
  DE_RATE: 'intent_de_rate',
  RUN: 'intent_run',
}

export default function ControlSignalBanner({
  token,
  operatingMode = 'iot',
}) {
  const lang = useLang()

  const [state, setState] = useState({
    status: 'NORMAL',
    intent: 'RUN',
    alert: null,
  })

  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  useEffect(() => {
    let disposed = false

    function closeConnection() {
      clearTimeout(reconnectRef.current)
      reconnectRef.current = null

      if (wsRef.current) {
        const ws = wsRef.current

        wsRef.current = null
        ws.onopen = null
        ws.onmessage = null
        ws.onerror = null
        ws.onclose = null

        ws.close()
      }
    }

    // No authenticated session.
    if (!token) {
      closeConnection()

      setState({
        status: 'NORMAL',
        intent: 'RUN',
        alert: null,
      })

      return () => {
        disposed = true
        closeConnection()
      }
    }

    // Offline demo session: no backend connection.
    if (token === DEMO_TOKEN) {
      closeConnection()

      setState({
        status: 'DEMO',
        intent: 'RUN',
        alert: null,
      })

      return () => {
        disposed = true
        closeConnection()
      }
    }

    // Simulation mode: never connect to live backend status.
    if (operatingMode === 'simulation') {
      closeConnection()

      setState({
        status: 'SIMULATION',
        intent: 'RUN',
        alert: null,
      })

      return () => {
        disposed = true
        closeConnection()
      }
    }

    // Registered account in IoT mode.
    setState({
      status: 'NORMAL',
      intent: 'RUN',
      alert: null,
    })

    function scheduleReconnect() {
      if (disposed) return

      clearTimeout(reconnectRef.current)

      reconnectRef.current = setTimeout(connect, 3000)
    }

    function connect() {
      if (disposed) return

      try {
        const ws = new WebSocket(
          `${WS_URL}?token=${encodeURIComponent(token)}`
        )

        wsRef.current = ws

        ws.onmessage = (event) => {
          if (disposed) return

          try {
            const data = JSON.parse(event.data)

            // System status payload.
            if (data.system_status) {
              setState(previous => ({
                ...previous,
                status: data.system_status,
                intent: data.control_intent || 'RUN',
                alert: null,
              }))
            }

            // Fail-safe and actuation failure payload.
            if (
              data.type === 'fail_safe' ||
              data.type === 'actuation_failure'
            ) {
              setState(previous => ({
                ...previous,
                alert: data,
              }))
            }
          } catch {
            // Ignore malformed WebSocket messages.
          }
        }

        ws.onclose = () => {
          if (wsRef.current === ws) {
            wsRef.current = null
          }

          scheduleReconnect()
        }

        ws.onerror = () => {
          ws.close()
        }
      } catch {
        scheduleReconnect()
      }
    }

    connect()

    return () => {
      disposed = true
      closeConnection()
    }
  }, [token, operatingMode])

  const { status, intent, alert } = state

  const isAlert =
    !!alert || intent === 'SHUTDOWN'

  const color =
    INTENT_COLOR[intent] || '#94a3b8'

  return (
    <div
      className={`control-banner${isAlert ? ' control-banner--alert' : ''}`}
      style={{ borderColor: color }}
    >
      <span className="control-banner__status">
        {t('banner_system_label', lang)}{' '}
        <strong>{status}</strong>
      </span>

      <span
        className="control-banner__intent"
        style={{ color }}
      >
        {t(INTENT_KEY[intent] || 'intent_run', lang)}
      </span>

      {alert && (
        <span className="control-banner__alert">
          ⚠{' '}
          {alert.type === 'fail_safe'
            ? t('banner_fail_safe', lang)
            : t('banner_actuation', lang)}

          {alert.detail?.reason
            ? ` — ${alert.detail.reason}`
            : ''}
        </span>
      )}
    </div>
  )
}