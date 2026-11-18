// ==================================================
// useTokenRefresh — auto-refresh JWT before expiry
// ==================================================
//
// Reads the token from sessionStorage, decodes the
// exp claim, and POSTs to /auth/refresh approximately
// 5 minutes before expiry.
//
// Demo sessions are excluded completely.
// ==================================================

import { useEffect, useRef } from 'react'

const API_BASE =
  import.meta.env.VITE_API_URL || 'http://localhost:8000'

const DEMO_TOKEN = 'demo-offline'

// Refresh 5 minutes before expiry.
const REFRESH_BUFFER_MS = 5 * 60 * 1000


// ==================================================
// JWT EXPIRY PARSER
// ==================================================

function parseJwtExp(token) {
  try {
    const payloadPart = token.split('.')[1]

    if (!payloadPart) return null

    const base64 = payloadPart
      .replace(/-/g, '+')
      .replace(/_/g, '/')

    const padded = base64.padEnd(
      Math.ceil(base64.length / 4) * 4,
      '='
    )

    const payload = JSON.parse(atob(padded))

    return payload.exp
      ? payload.exp * 1000
      : null
  } catch {
    return null
  }
}


// ==================================================
// TOKEN REFRESH HOOK
// ==================================================

export default function useTokenRefresh(onRefresh, onExpired) {
  const timerRef = useRef(null)

  // Keep the latest callbacks without resetting the
  // refresh timer on every parent component render.
  const callbacksRef = useRef({
    onRefresh,
    onExpired,
  })

  callbacksRef.current = {
    onRefresh,
    onExpired,
  }

  // Read the current token during render.
  // The effect is restarted only when the token changes.
  const token =
    sessionStorage.getItem('iw_token')


  useEffect(() => {
    let cancelled = false

    async function refresh(currentToken) {
      if (cancelled) return

      try {
        const res = await fetch(
          `${API_BASE}/auth/refresh`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${currentToken}`,
            },
          }
        )

        if (!res.ok) {
          throw new Error('Token refresh failed.')
        }

        const data = await res.json()

        if (cancelled) return

        const refreshedUser = {
          username: data.username,
          full_name: data.full_name,
          role: data.role,
          account_role: data.account_role || data.role,
          is_restricted_session: !!data.is_restricted_session,
          user_id: data.user_id,
          session_mode: 'ONLINE',
        }

        sessionStorage.setItem(
          'iw_token',
          data.access_token
        )

        sessionStorage.setItem(
          'iw_user',
          JSON.stringify(refreshedUser)
        )

        callbacksRef.current.onRefresh?.({
          ...data,
          ...refreshedUser,
        })

      } catch {
        if (cancelled) return

        // The registered session cannot continue
        // when its token cannot be refreshed.
        sessionStorage.removeItem('iw_token')
        sessionStorage.removeItem('iw_user')

        callbacksRef.current.onExpired?.()
      }
    }


    function schedule(currentToken) {
      clearTimeout(timerRef.current)
      timerRef.current = null

      // Offline demo has no JWT and must never call
      // the authentication refresh endpoint.
      if (!currentToken || currentToken === DEMO_TOKEN) {
        return
      }

      const exp = parseJwtExp(currentToken)

      if (!exp) return

      const now = Date.now()
      const msLeft = exp - now

      // Keep a minimum 10-second delay.
      const fireIn = Math.max(
        msLeft - REFRESH_BUFFER_MS,
        10_000
      )

      timerRef.current = setTimeout(() => {
        refresh(currentToken)
      }, fireIn)
    }


    schedule(token)

    return () => {
      cancelled = true
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [token])
}