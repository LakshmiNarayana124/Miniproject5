// ==================================================
// useTokenRefresh — auto-refresh JWT before expiry
// ==================================================
// Reads the token from sessionStorage, decodes the
// exp claim, and POSTs to /auth/refresh ≈5 min before
// expiry so monitoring sessions never silently drop.
// ==================================================

import { useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Refresh 5 minutes before expiry
const REFRESH_BUFFER_MS = 5 * 60 * 1000

function parseJwtExp(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

/**
 * @param {Function} onRefresh  — called with the new user object when
 *                                the token is successfully refreshed.
 * @param {Function} onExpired  — called when refresh fails (logs out).
 */
export default function useTokenRefresh(onRefresh, onExpired) {
  const timerRef = useRef(null)

  useEffect(() => {
    function schedule() {
      const token = sessionStorage.getItem('iw_token')
      if (!token || token === 'demo-offline') return

      const exp = parseJwtExp(token)
      if (!exp) return

      const now      = Date.now()
      const msLeft   = exp - now
      const fireIn   = Math.max(msLeft - REFRESH_BUFFER_MS, 10_000) // at least 10 s

      clearTimeout(timerRef.current)
      timerRef.current = setTimeout(async () => {
        try {
          const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
          })
          if (!res.ok) throw new Error('refresh failed')
          const data = await res.json()
          sessionStorage.setItem('iw_token', data.access_token)
          sessionStorage.setItem('iw_user', JSON.stringify({
            username:  data.username,
            full_name: data.full_name,
            role:      data.role,
            user_id:   data.user_id,
          }))
          onRefresh?.({ ...data })
          schedule()  // schedule the next refresh
        } catch {
          // Token could not be refreshed — log the user out
          sessionStorage.removeItem('iw_token')
          sessionStorage.removeItem('iw_user')
          onExpired?.()
        }
      }, fireIn)
    }

    schedule()
    return () => clearTimeout(timerRef.current)
  }, [onRefresh, onExpired])
}
