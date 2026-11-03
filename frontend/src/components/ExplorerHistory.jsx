import { useEffect, useState } from 'react'
import { t } from '../i18n'
import useLang from '../useLang'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const IS_SECURE = API.startsWith('https')

/**
 * ExplorerHistory — side panel showing past workspace states and classifications.
 * Req 6.3: reverse-chronological list.
 * Req 6.4: replay action restores placedComponents from stored arrangement.
 */
export default function ExplorerHistory({ onReplay, token }) {
  const lang = useLang()
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    if (!token) return
    setLoading(true)
    try {
      const r = await fetch(`${API}/explorer/history?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (r.ok) setEntries(await r.json())
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [token])

  const replay = async (entry) => {
    if (!onReplay) return
    let arrangement = null
    try {
      const r = await fetch(`${API}/explorer/history/${entry.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (r.ok) {
        const detail = await r.json()
        if (detail.arrangement_json) {
          arrangement = JSON.parse(detail.arrangement_json)
        }
      }
    } catch {}
    onReplay({ entry, arrangement })
  }

  return (
    <div className="explorer-history">
      <div className="explorer-history__header">
        <span>
          {IS_SECURE && <span title={t('https_secure', lang)} style={{ marginRight: 4, color: '#22c55e' }}>🔒</span>}
          {t('hist_title', lang)}
        </span>
        <button onClick={load} title={t('hist_refresh', lang)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: '1rem' }}>⟳</button>
      </div>
      {loading && <p style={{ color: '#64748b', padding: '8px', fontSize: '0.78rem' }}>{t('hist_loading', lang)}</p>}
      {!loading && entries.length === 0 && (
        <p style={{ color: '#64748b', padding: '8px', fontSize: '0.78rem' }}>{t('hist_empty', lang)}</p>
      )}
      <ul className="explorer-history__list">
        {entries.map(e => (
          <li key={e.id} className={`explorer-history__item explorer-history__item--${e.entry_type}`}>
            <div className="explorer-history__meta">
              <span className="explorer-history__type">{e.entry_type === 'classification' ? '🤖' : '📐'}</span>
              <span className="explorer-history__time">{e.timestamp?.slice(0, 19).replace('T', ' ')}</span>
            </div>
            {e.classification_label && (
              <div className="explorer-history__label">
                {e.classification_label}
                {e.confidence != null && ` (${Math.round(e.confidence * 100)}%)`}
              </div>
            )}
            {e.entry_type === 'workspace_state' && (
              <button
                className="explorer-history__replay"
                onClick={() => replay(e)}
                title={t('hist_replay_title', lang)}
              >
                {t('hist_replay', lang)}
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
