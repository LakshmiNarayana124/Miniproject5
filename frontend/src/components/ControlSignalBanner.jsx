import { useEffect, useRef, useState } from 'react'
import './ControlSignalBanner.css'
import { t } from '../i18n'
import useLang from '../useLang'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_BASE  = API_BASE.replace(/^http/, 'ws')
const WS_URL   = `${WS_BASE}/stream/status`

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

export default function ControlSignalBanner({ token }) {
  const lang = useLang()
  const [state, setState] = useState({ status: 'NORMAL', intent: 'RUN', alert: null })
  const wsRef = useRef(null)

  useEffect(() => {
    if (!token) return

    const connect = () => {
      const ws = new WebSocket(`${WS_URL}?token=${token}`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          // status stream payload
          if (data.system_status) {
            setState(prev => ({
              ...prev,
              status: data.system_status,
              intent: data.control_intent || 'RUN',
              alert: null,
            }))
          }
          // alert payload
          if (data.type === 'fail_safe' || data.type === 'actuation_failure') {
            setState(prev => ({ ...prev, alert: data }))
          }
        } catch {}
      }

      ws.onclose = () => { setTimeout(connect, 3000) }
      ws.onerror = () => { ws.close() }
    }

    connect()
    return () => { wsRef.current?.close() }
  }, [token])

  const { status, intent, alert } = state
  const isAlert = !!alert || intent === 'SHUTDOWN'
  const color = INTENT_COLOR[intent] || '#94a3b8'

  return (
    <div className={`control-banner ${isAlert ? 'control-banner--alert' : ''}`}
         style={{ borderColor: color }}>
      <span className="control-banner__status">{t('banner_system_label', lang)} <strong>{status}</strong></span>
      <span className="control-banner__intent" style={{ color }}>
        {t(INTENT_KEY[intent] || 'intent_run', lang)}
      </span>
      {alert && (
        <span className="control-banner__alert">
          ⚠ {alert.type === 'fail_safe' ? t('banner_fail_safe', lang) : t('banner_actuation', lang)}
          {alert.detail?.reason ? ` — ${alert.detail.reason}` : ''}
        </span>
      )}
    </div>
  )
}
