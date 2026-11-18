
import { useState, useEffect, useRef } from 'react'
import './LoginPage.css'

import {
  isFirebaseConfigured,
  firebaseAuth,
} from '../firebase.js'

// Firebase auth methods — imported lazily-ish via static import but only
// called when isFirebaseConfigured is true, so they don't crash when Firebase
// is not configured (they just never execute).
import {
  GoogleAuthProvider,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  RecaptchaVerifier,
  signInWithPhoneNumber,
} from 'firebase/auth'

const API = (
  import.meta.env.VITE_API_URL || 'http://localhost:8000'
).trim().replace(/\/+$/, '')

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

const DEMO_TOKEN = 'demo-offline'
const INTERNET_CHECK_URL =
  import.meta.env.VITE_INTERNET_CHECK_URL ||
  'https://www.gstatic.com/generate_204'

const AVAILABILITY_TIMEOUT_MS = 3500

// ─────────────────────────────────────────────────────────────────────────────
// 1. HELPERS
// ─────────────────────────────────────────────────────────────────────────────

function isBrowserOnline() {
  return typeof navigator === 'undefined' || navigator.onLine
}

function getLoginErrorMessage(data, fallback) {
  if (typeof data?.detail === 'string' && data.detail.trim()) {
    return data.detail
  }

  if (Array.isArray(data?.detail)) {
    const messages = data.detail
      .map(item => item?.msg)
      .filter(message => typeof message === 'string')

    if (messages.length > 0) {
      return messages.join('; ')
    }
  }

  if (
    data?.detail &&
    typeof data.detail === 'object' &&
    typeof data.detail.message === 'string'
  ) {
    return data.detail.message
  }

  if (typeof data?.message === 'string' && data.message.trim()) {
    return data.message
  }

  return fallback
}

function saveSession(token, user) {
  if (
    typeof token !== 'string' ||
    !token.trim() ||
    !user ||
    typeof user !== 'object'
  ) {
    throw new Error('Invalid authentication session.')
  }

  const serializedUser = JSON.stringify(user)

  try {
    sessionStorage.setItem('iw_token', token)
    sessionStorage.setItem('iw_user', serializedUser)
  } catch (error) {
    // Do not leave an incomplete session behind.
    try {
      sessionStorage.removeItem('iw_token')
      sessionStorage.removeItem('iw_user')
    } catch (cleanupError) {
      console.warn(
        '[IntelliWatch] Session cleanup failed:',
        cleanupError
      )
    }

    throw error
  }
}

function clearSavedSession() {
  try {
    sessionStorage.removeItem('iw_token')
    sessionStorage.removeItem('iw_user')
  } catch (error) {
    console.warn(
      '[IntelliWatch] Unable to clear stored session:',
      error
    )
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// 2a. FIREBASE ERROR TRANSLATION + TOKEN EXCHANGE
// ─────────────────────────────────────────────────────────────────────────────

function firebaseErrorMessage(err, fallback) {
  const code = err?.code || ''
  const map = {
    'auth/billing-not-enabled':
      'Phone authentication requires upgrading to the Firebase Blaze (pay-as-you-go) plan. Upgrade at console.firebase.google.com → Usage and billing.',
    'auth/configuration-not-found':
      'Google sign-in is not enabled yet. Enable it in Firebase Console → Authentication → Sign-in method.',
    'auth/operation-not-allowed':
      'This sign-in method is not enabled. Enable it in Firebase Console → Authentication.',
    'auth/invalid-phone-number':
      'Invalid phone number. Use international format, e.g. +14155551234.',
    'auth/too-many-requests':
      'Too many attempts. Please wait a few minutes and try again.',
    'auth/captcha-check-failed':
      'reCAPTCHA verification failed. Please try again.',
    'auth/invalid-verification-code':
      'Invalid OTP code. Check the 6-digit code and try again.',
    'auth/code-expired':
      'The OTP code has expired. Request a new one.',
    'auth/network-request-failed':
      'Network error. Check your internet connection and try again.',
    'auth/popup-blocked':
      'Sign-in popup was blocked. Please allow popups for this site.',
    'auth/popup-closed-by-user':
      'Sign-in was cancelled. Please try again.',
    'auth/unauthorized-domain':
      'This domain is not authorized. Add it in Firebase Console → Authentication → Authorized domains.',
  }
  return map[code] || err?.message || fallback
}


async function exchangeFirebaseToken(idToken, requestedRole) {
  // Use a 15-second timeout — the backend verifies the Firebase ID token
  // with Google's servers, which can take several seconds on first call.
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 15000)

  try {
    const response = await fetch(`${API}/auth/firebase-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id_token: idToken,
        requested_role: requestedRole,
      }),
      signal: controller.signal,
    })

    const text = await response.text()
    let data = {}
    if (text.trim()) {
      try { data = JSON.parse(text) } catch {}
    }

    if (!response.ok) {
      throw new Error(getLoginErrorMessage(data, `Firebase login failed (HTTP ${response.status}).`))
    }

    return data
  } finally {
    clearTimeout(timeout)
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// 2b. GOOGLE SIGN-IN SVG LOGO
// ─────────────────────────────────────────────────────────────────────────────

function GoogleLogo() {
  return (
    <svg className="google-signin-icon" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.2l6.7-6.7C35.8 2.5 30.2 0 24 0 14.7 0 6.8 5.4 2.9 13.3l7.8 6C12.4 13.2 17.7 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.5 24.5c0-1.7-.2-3.3-.5-4.9H24v9.3h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9C43.9 37.6 46.5 31.5 46.5 24.5z"/>
      <path fill="#FBBC05" d="M10.7 28.7A14.5 14.5 0 0 1 9.5 24c0-1.6.3-3.2.7-4.7l-7.8-6A23.9 23.9 0 0 0 0 24c0 3.9.9 7.5 2.5 10.7l8.2-6z"/>
      <path fill="#34A853" d="M24 48c6.2 0 11.4-2 15.1-5.5l-7.6-5.9C29.5 38.5 27 39.5 24 39.5c-6.3 0-11.6-3.7-13.3-9.3l-8.2 6C6.8 42.6 14.7 48 24 48z"/>
    </svg>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 2c. FIREBASE ROLE PICKER
//
// Shown after Firebase authentication succeeds so the user can select which
// IntelliWatch role to log in with. Only Operator and Engineer are available
// via open Firebase sign-in — Admin requires an invitation token.
// ─────────────────────────────────────────────────────────────────────────────

function FirebaseRolePicker({ onSelect, loading }) {
  const roles = [
    { key: 'OPERATOR', icon: '📊', label: 'Operator' },
    { key: 'MAINTENANCE_ENGINEER', icon: '🔧', label: 'Engineer' },
  ]

  return (
    <div className="firebase-role-pick">
      <p className="firebase-role-pick-title">Select your role to continue</p>
      <div className="firebase-role-pick-btns">
        {roles.map(r => (
          <button
            key={r.key}
            type="button"
            className="firebase-role-btn"
            onClick={() => onSelect(r.key)}
            disabled={loading}
          >
            <span className="firebase-role-btn-icon">{r.icon}</span>
            {r.label}
          </button>
        ))}
      </div>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 2d. GOOGLE SIGN-IN PANEL
// ─────────────────────────────────────────────────────────────────────────────

function GoogleSignInPanel({ onLogin, onError, loading, setLoading, timezone, selectedRole }) {
  const [idToken, setIdToken] = useState(null)
  const [displayName, setDisplayName] = useState('')

  // Detect redirect result on mount (for browsers that blocked popup)
  useEffect(() => {
    if (!firebaseAuth) return
    getRedirectResult(firebaseAuth)
      .then(async result => {
        if (!result?.user) return
        const token = await result.user.getIdToken()
        setIdToken(token)
        setDisplayName(result.user.displayName || result.user.email || '')
        // Auto-exchange token with the selected role
        await doRoleLogin(token)
      })
      .catch(() => {})
  }, [])

  async function doRoleLogin(token) {
    setLoading(true)
    onError('')
    try {
      const data = await exchangeFirebaseToken(token, selectedRole)
      if (
        typeof data.access_token !== 'string' ||
        typeof data.username !== 'string' ||
        typeof data.role !== 'string'
      ) {
        throw new Error('The server returned an incomplete login response.')
      }
      const sessionUser = {
        username: data.username,
        full_name: data.full_name || data.username,
        role: data.role,
        account_role: data.account_role || data.role,
        is_restricted_session: !!data.is_restricted_session,
        is_demo_session: false,
        user_id: data.user_id,
        session_mode: 'ONLINE',
        timezone,
      }
      saveSession(data.access_token, sessionUser)
      onLogin({ ...data, is_demo_session: false, session_mode: 'ONLINE', timezone })
    } catch (err) {
      onError(firebaseErrorMessage(err, 'Google login failed. Please try again.'))
      setIdToken(null)
      setLoading(false)
    }
  }

  async function handleGoogleSignIn() {
    if (!firebaseAuth) return
    onError('')

    try {
      const provider = new GoogleAuthProvider()
      provider.setCustomParameters({ prompt: 'select_account' })

      let result
      try {
        result = await signInWithPopup(firebaseAuth, provider)
      } catch (popupError) {
        if (
          popupError.code === 'auth/popup-blocked' ||
          popupError.code === 'auth/popup-closed-by-user'
        ) {
          await signInWithRedirect(firebaseAuth, provider)
          return
        }
        throw popupError
      }

      const token = await result.user.getIdToken()
      setIdToken(token)
      setDisplayName(result.user.displayName || result.user.email || '')
      await doRoleLogin(token)
    } catch (err) {
      onError(firebaseErrorMessage(err, 'Google sign-in failed. Please try again.'))
      setLoading(false)
    }
  }

  const roleLabel = selectedRole === 'MAINTENANCE_ENGINEER' ? '🔧 Engineer' : '📊 Operator'

  return (
    <div className="phone-otp-wrap">
      <button
        type="button"
        className="google-signin-btn"
        onClick={handleGoogleSignIn}
        disabled={loading}
      >
        {loading ? <span className="login-spinner" /> : <GoogleLogo />}
        Sign in as {roleLabel}
      </button>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 2e. PHONE + OTP PANEL
// ─────────────────────────────────────────────────────────────────────────────

function PhoneOtpPanel({ onLogin, onError, loading, setLoading, timezone, selectedRole }) {
  const [step, setStep] = useState('phone') // 'phone' | 'otp'
  const [phonePrefix, setPhonePrefix] = useState('+91')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [otp, setOtp] = useState('')
  const [confirmationResult, setConfirmationResult] = useState(null)
  const [countdown, setCountdown] = useState(0)

  const recaptchaRef = useRef(null)
  const timerRef = useRef(null)

  function startCountdown(secs) {
    setCountdown(secs)
    clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { clearInterval(timerRef.current); return 0 }
        return prev - 1
      })
    }, 1000)
  }

  useEffect(() => () => clearInterval(timerRef.current), [])

  function getRecaptchaVerifier() {
    if (!recaptchaRef.current && firebaseAuth) {
      recaptchaRef.current = new RecaptchaVerifier(
        firebaseAuth,
        'recaptcha-container',
        { size: 'invisible', 'expired-callback': () => { recaptchaRef.current = null } }
      )
      // Explicitly render — required in Firebase modular SDK v9+
      recaptchaRef.current.render().catch(() => {})
    }
    return recaptchaRef.current
  }

  async function handleSendOtp(e) {
    e && e.preventDefault()
    if (!firebaseAuth) return

    const fullNumber = phonePrefix.trim() + phoneNumber.trim()
    if (phoneNumber.trim().length < 5) {
      onError('Enter a valid phone number (without country code).')
      return
    }

    setLoading(true)
    onError('')

    try {
      const verifier = getRecaptchaVerifier()
      const result = await signInWithPhoneNumber(firebaseAuth, fullNumber, verifier)
      setConfirmationResult(result)
      setStep('otp')
      startCountdown(60)
    } catch (err) {
      recaptchaRef.current = null
      onError(firebaseErrorMessage(err, 'Failed to send OTP. Check the phone number and try again.'))
    } finally {
      setLoading(false)
    }
  }

  async function handleVerifyOtp(e) {
    e && e.preventDefault()
    if (!confirmationResult) return

    if (otp.trim().length < 4) {
      onError('Enter the OTP sent to your phone.')
      return
    }

    setLoading(true)
    onError('')

    try {
      const userCredential = await confirmationResult.confirm(otp.trim())
      const token = await userCredential.user.getIdToken()

      // Immediately exchange the token — role comes from the subrole tabs
      setLoading(true)
      const data = await exchangeFirebaseToken(token, selectedRole)
      if (
        typeof data.access_token !== 'string' ||
        typeof data.username !== 'string' ||
        typeof data.role !== 'string'
      ) {
        throw new Error('The server returned an incomplete login response.')
      }
      const sessionUser = {
        username: data.username,
        full_name: data.full_name || data.username,
        role: data.role,
        account_role: data.account_role || data.role,
        is_restricted_session: !!data.is_restricted_session,
        is_demo_session: false,
        user_id: data.user_id,
        session_mode: 'ONLINE',
        timezone,
      }
      saveSession(data.access_token, sessionUser)
      onLogin({ ...data, is_demo_session: false, session_mode: 'ONLINE', timezone })
    } catch (err) {
      onError(firebaseErrorMessage(err, 'OTP verification failed. Check the code and try again.'))
      setLoading(false)
    }
  }

  // Invisible reCAPTCHA anchor — must be in the DOM before signInWithPhoneNumber
  const recaptchaContainer = <div id="recaptcha-container" />

  if (step === 'otp') {
    return (
      <form className="phone-otp-wrap" onSubmit={handleVerifyOtp} noValidate>
        {recaptchaContainer}
        <div className="otp-info">
          OTP sent to <strong>{phonePrefix} {phoneNumber}</strong>. Enter the 6-digit code below.
        </div>
        <div className="login-field">
          <label className="login-label" htmlFor="otp-code">Verification Code</label>
          <div className="otp-input-wrap">
            <input
              id="otp-code"
              className="otp-input"
              type="tel"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              placeholder="000000"
              value={otp}
              onChange={e => setOtp(e.target.value.replace(/\D/g, ''))}
              autoComplete="one-time-code"
              disabled={loading}
              autoFocus
            />
            <button
              type="button"
              className="otp-resend-btn"
              disabled={loading || countdown > 0}
              onClick={() => { setOtp(''); handleSendOtp() }}
            >
              {countdown > 0 ? `Resend (${countdown}s)` : 'Resend'}
            </button>
          </div>
        </div>
        <button
          className="login-btn"
          type="submit"
          disabled={loading || otp.length < 4}
        >
          {loading ? <span className="login-spinner" /> : 'Verify OTP'}
        </button>
        <button
          type="button"
          className="login-extra-btn"
          style={{ marginTop: 4, textAlign: 'center' }}
          onClick={() => { setStep('phone'); setOtp(''); onError('') }}
        >
          ← Change number
        </button>
      </form>
    )
  }

  // step === 'phone'
  return (
    <form className="phone-otp-wrap" onSubmit={handleSendOtp} noValidate>
      {recaptchaContainer}
      <div className="login-field">
        <label className="login-label" htmlFor="phone-number">Phone Number</label>
        <div className="phone-input-row">
          <select
            className="phone-country-code login-input"
            value={phonePrefix}
            onChange={e => setPhonePrefix(e.target.value)}
            disabled={loading}
            aria-label="Country code"
          >
            <option value="+91">🇮🇳 +91 India</option>
            <option value="+1">🇺🇸 +1 USA/Canada</option>
            <option value="+44">🇬🇧 +44 UK</option>
            <option value="+61">🇦🇺 +61 Australia</option>
            <option value="+49">🇩🇪 +49 Germany</option>
            <option value="+33">🇫🇷 +33 France</option>
            <option value="+81">🇯🇵 +81 Japan</option>
            <option value="+82">🇰🇷 +82 South Korea</option>
            <option value="+65">🇸🇬 +65 Singapore</option>
            <option value="+971">🇦🇪 +971 UAE</option>
            <option value="+966">🇸🇦 +966 Saudi Arabia</option>
            <option value="+92">🇵🇰 +92 Pakistan</option>
            <option value="+880">🇧🇩 +880 Bangladesh</option>
            <option value="+94">🇱🇰 +94 Sri Lanka</option>
            <option value="+977">🇳🇵 +977 Nepal</option>
            <option value="+55">🇧🇷 +55 Brazil</option>
            <option value="+52">🇲🇽 +52 Mexico</option>
            <option value="+7">🇷🇺 +7 Russia</option>
            <option value="+86">🇨🇳 +86 China</option>
            <option value="+27">🇿🇦 +27 South Africa</option>
            <option value="+234">🇳🇬 +234 Nigeria</option>
          </select>
          <div className="login-input-wrap phone-number-input">
            <span className="login-input-icon">📱</span>
            <input
              id="phone-number"
              className="login-input"
              type="tel"
              inputMode="tel"
              placeholder="e.g. 9876543210"
              value={phoneNumber}
              onChange={e => setPhoneNumber(e.target.value.replace(/[^\d\s\-().]/g, ''))}
              autoComplete="tel-national"
              disabled={loading}
            />
          </div>
        </div>
      </div>
      <div className="otp-info">
        Select your country code, then enter your phone number. A 6-digit code will be sent via SMS.
      </div>
      <button
        className="login-btn"
        type="submit"
        disabled={loading || phoneNumber.trim().length < 5}
      >
        {loading ? <span className="login-spinner" /> : 'Send OTP'}
      </button>
    </form>
  )
}



// ─────────────────────────────────────────────────────────────────────────────
// 2. CONNECTION DETECTION
//
// Online mode requires BOTH:
//   1. Internet connectivity.
//   2. IntelliWatch backend availability.
//
// If either is unavailable, the application enters demo fallback mode.
// ─────────────────────────────────────────────────────────────────────────────

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController()

  const timeout = setTimeout(
    () => controller.abort(),
    AVAILABILITY_TIMEOUT_MS
  )

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    })
  } finally {
    clearTimeout(timeout)
  }
}

async function checkInternetAvailability() {
  if (!isBrowserOnline()) return false

  try {
    await fetchWithTimeout(INTERNET_CHECK_URL, {
      method: 'GET',
      mode: 'no-cors',
      cache: 'no-store',
    })

    return true
  } catch {
    return false
  }
}

async function checkBackendAvailability() {
  try {
    const response = await fetchWithTimeout(
      `${API}/auth/registration-status`,
      {
        method: 'GET',
        cache: 'no-store',
      }
    )

    if (!response.ok) {
      return {
        available: false,
        registrationEnabled: false,
      }
    }

    const data = await response.json()

    return {
      available: true,
      registrationEnabled: !!data.registration_enabled,
    }
  } catch {
    return {
      available: false,
      registrationEnabled: false,
    }
  }
}

async function detectAvailability() {
  const [internetAvailable, backend] = await Promise.all([
    checkInternetAvailability(),
    checkBackendAvailability(),
  ])

  return {
    checked: true,
    internetAvailable,
    backendAvailable: backend.available,
    onlineMode: backend.available,
    registrationEnabled: backend.registrationEnabled,
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// 3. PASSWORD VISIBILITY ICON
// ─────────────────────────────────────────────────────────────────────────────

function PasswordVisibilityIcon({ visible, size = 18 }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {visible ? (
        <>
          <path d="M3 3l18 18" />
          <path d="M10.6 10.6a2 2 0 002.8 2.8" />
          <path d="M9.9 5.2A10.8 10.8 0 0112 5c6.4 0 10 7 10 7a15.5 15.5 0 01-3.1 3.8" />
          <path d="M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7a10.5 10.5 0 004-.8" />
        </>
      ) : (
        <>
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
          <circle cx="12" cy="12" r="3" />
        </>
      )}
    </svg>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 4. PASSWORD STRENGTH
// ─────────────────────────────────────────────────────────────────────────────

function PasswordStrength({ password }) {
  if (!password) return null

  const score = [
    password.length >= 12,
    /[A-Z]/.test(password),
    /[a-z]/.test(password),
    /\d/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length

  const labels = ['', 'Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong']
  const colors = ['', '#ef4444', '#f59e0b', '#eab308', '#22c55e', '#10b981']

  return (
    <div className="pw-strength">
      <div className="pw-bars">
        {[1, 2, 3, 4, 5].map(i => (
          <div
            key={i}
            className="pw-bar"
            style={{
              background: i <= score ? colors[score] : '#252837',
            }}
          />
        ))}
      </div>

      <span className="pw-label" style={{ color: colors[score] }}>
        {labels[score]}
      </span>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 5. ADMIN REGISTER MODAL
// ─────────────────────────────────────────────────────────────────────────────

function AdminRegisterModal({ onClose, onDone }) {
  const [form, setForm] = useState({
    username: '',
    full_name: '',
    password: '',
    confirmPw: '',
    invite_token: '',
  })

  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (
      !form.username.trim() ||
      !form.full_name.trim() ||
      !form.password ||
      !form.invite_token.trim()
    ) {
      setError('Please fill in all required fields.')
      return
    }

    if (form.password.length < 12) {
      setError('Password must be at least 12 characters long.')
      return
    }

    if (form.password !== form.confirmPw) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)

    try {
      const r = await fetch(`${API}/auth/register-admin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username.trim(),
          full_name: form.full_name.trim(),
          password: form.password,
          invite_token: form.invite_token.trim(),
        }),
      })

      const d = await r.json().catch(() => ({}))

      if (!r.ok) {
        setError(
          getLoginErrorMessage(d, 'Admin registration failed.')
        )
        return
      }

      setSuccess(d.invited_by || '—')
    } catch (error) {
      console.error(
        '[IntelliWatch] Admin registration failed:',
        error
      )

      setError('Unable to connect to the server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Admin Registration</span>

          <button
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
            type="button"
          >
            &times;
          </button>
        </div>

        {success ? (
          <div className="modal-success">
            <span className="modal-success-icon">✅</span>

            <p>
              Administrator account created by <strong>{success}</strong>.
            </p>

            <p className="modal-success-sub">
              You can now sign in using your administrator credentials.
            </p>

            <button className="login-btn" onClick={onDone} type="button">
              Done
            </button>
          </div>
        ) : (
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div className="modal-notice">
              Administrator registration requires a valid invitation token.
            </div>

            <div className="login-form-row">
              <div className="login-field">
                <label className="login-label" htmlFor="ar-user">
                  Username
                </label>

                <div className="login-input-wrap">
                  <span className="login-input-icon">👤</span>

                  <input
                    id="ar-user"
                    className="login-input"
                    type="text"
                    placeholder="Choose a username"
                    value={form.username}
                    onChange={e =>
                      setForm(f => ({ ...f, username: e.target.value }))
                    }
                    autoComplete="off"
                    disabled={loading}
                    spellCheck={false}
                  />
                </div>
              </div>

              <div className="login-field">
                <label className="login-label" htmlFor="ar-name">
                  Full Name
                </label>

                <div className="login-input-wrap">
                  <span className="login-input-icon">🎭</span>

                  <input
                    id="ar-name"
                    className="login-input"
                    type="text"
                    placeholder="Enter your full name"
                    value={form.full_name}
                    onChange={e =>
                      setForm(f => ({ ...f, full_name: e.target.value }))
                    }
                    autoComplete="off"
                    disabled={loading}
                  />
                </div>
              </div>
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="ar-pw">
                Password{' '}
                <span className="login-label-hint">
                  (Minimum 12 characters)
                </span>
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>

                <input
                  id="ar-pw"
                  className="login-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder="Create a strong password"
                  value={form.password}
                  onChange={e =>
                    setForm(f => ({ ...f, password: e.target.value }))
                  }
                  autoComplete="new-password"
                  disabled={loading}
                />

                <button
                  type="button"
                  className="login-eye-btn"
                  onClick={() => setShowPw(v => !v)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  <PasswordVisibilityIcon visible={showPw} />
                </button>
              </div>

              <PasswordStrength password={form.password} />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="ar-pw2">
                Confirm Password
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>

                <input
                  id="ar-pw2"
                  className="login-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder="Re-enter your password"
                  value={form.confirmPw}
                  onChange={e =>
                    setForm(f => ({ ...f, confirmPw: e.target.value }))
                  }
                  autoComplete="new-password"
                  disabled={loading}
                />
              </div>

              {form.confirmPw && form.password !== form.confirmPw && (
                <span className="login-field-err">
                  Passwords do not match.
                </span>
              )}
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="ar-tok">
                Invitation Token
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔑</span>

                <input
                  id="ar-tok"
                  className="login-input"
                  type="text"
                  placeholder="Enter invitation token"
                  value={form.invite_token}
                  onChange={e =>
                    setForm(f => ({ ...f, invite_token: e.target.value }))
                  }
                  autoComplete="off"
                  disabled={loading}
                  spellCheck={false}
                />
              </div>
            </div>

            {error && <div className="login-error">⚠️ {error}</div>}

            <button
              className="login-btn login-btn--admin-purple"
              type="submit"
              disabled={loading || form.password !== form.confirmPw}
            >
              {loading ? (
                <span className="login-spinner" />
              ) : (
                'Create Administrator Account'
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 6. FORGOT PASSWORD MODAL
// ─────────────────────────────────────────────────────────────────────────────

function ForgotModal({ onClose }) {
  const [step, setStep] = useState('request')
  const [username, setUsername] = useState('')
  const [token, setToken] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleRequest(e) {
    e.preventDefault()
    setError('')

    if (!username.trim()) {
      setError('Please enter your username.')
      return
    }

    setLoading(true)

    try {
      const r = await fetch(`${API}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim() }),
      })

      const d = await r.json().catch(() => ({}))

      if (!r.ok) {
        setError(
          getLoginErrorMessage(d, 'Unable to process your request.')
        )
        return
      }

      if (d.reset_token) {
        setInfo(
          `Reset Token: ${d.reset_token}\n\nKeep this token secure and use it to reset your password.`
        )
      } else {
        setInfo(d.note || d.message || '')
      }

      setStep('reset')
    } catch (error) {
      console.error(
        '[IntelliWatch] Password-reset request failed:',
        error
      )

      setError('Unable to connect to the server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleReset(e) {
    e.preventDefault()
    setError('')

    if (!token.trim()) {
      setError('Please enter the reset token.')
      return
    }

    if (newPw.length < 12) {
      setError('Password must be at least 12 characters long.')
      return
    }

    if (newPw !== confirmPw) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)

    try {
      const r = await fetch(`${API}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: token.trim(),
          new_password: newPw,
        }),
      })

      const d = await r.json().catch(() => ({}))

      if (!r.ok) {
        setError(
          getLoginErrorMessage(d, 'Password reset failed.')
        )
        return
      }

      setDone(true)
    } catch (error) {
      console.error(
        '[IntelliWatch] Password reset failed:',
        error
      )

      setError('Unable to connect to the server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Reset Password</span>

          <button
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
            type="button"
          >
            &times;
          </button>
        </div>

        {done ? (
          <div className="modal-success">
            <span className="modal-success-icon">✅</span>
            <p>Your password has been updated successfully.</p>

            <button
              className="login-btn"
              onClick={onClose}
              style={{ marginTop: 12 }}
              type="button"
            >
              Done
            </button>
          </div>
        ) : step === 'request' ? (
          <form className="login-form" onSubmit={handleRequest} noValidate>
            <p className="login-fp-desc">
              Enter your username to request a password reset.
            </p>

            <div className="login-field">
              <label className="login-label" htmlFor="fp-u">
                Username
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">👤</span>

                <input
                  id="fp-u"
                  className="login-input"
                  type="text"
                  placeholder="Enter your username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  disabled={loading}
                  spellCheck={false}
                />
              </div>
            </div>

            {error && <div className="login-error">⚠️ {error}</div>}
            {info && <div className="login-info">{info}</div>}

            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? (
                <span className="login-spinner" />
              ) : (
                'Get Reset Token'
              )}
            </button>
          </form>
        ) : (
          <form className="login-form" onSubmit={handleReset} noValidate>
            {info && (
              <div className="login-info login-info--token">
                <pre>{info}</pre>
              </div>
            )}

            <div className="login-field">
              <label className="login-label" htmlFor="fp-tok">
                Reset Token
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🎫</span>

                <input
                  id="fp-tok"
                  className="login-input"
                  type="text"
                  placeholder="Paste your reset token"
                  value={token}
                  onChange={e => setToken(e.target.value)}
                  disabled={loading}
                  spellCheck={false}
                />
              </div>
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="fp-pw">
                New Password
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>

                <input
                  id="fp-pw"
                  className="login-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder="Enter your new password"
                  value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  autoComplete="new-password"
                  disabled={loading}
                />

                <button
                  type="button"
                  className="login-eye-btn"
                  onClick={() => setShowPw(v => !v)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  <PasswordVisibilityIcon visible={showPw} />
                </button>
              </div>

              <PasswordStrength password={newPw} />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="fp-pw2">
                Confirm Password
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>

                <input
                  id="fp-pw2"
                  className="login-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder="Re-enter your password"
                  value={confirmPw}
                  onChange={e => setConfirmPw(e.target.value)}
                  autoComplete="new-password"
                  disabled={loading}
                />
              </div>

              {confirmPw && newPw !== confirmPw && (
                <span className="login-field-err">
                  Passwords do not match.
                </span>
              )}
            </div>

            {error && <div className="login-error">⚠️ {error}</div>}

            <button
              className="login-btn"
              type="submit"
              disabled={loading || newPw !== confirmPw}
            >
              {loading ? (
                <span className="login-spinner" />
              ) : (
                'Set New Password'
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 7. ROLE-SPECIFIC REGISTER MODAL
// ─────────────────────────────────────────────────────────────────────────────

function RoleRegisterModal({ role, onClose }) {
  const isOp = role === 'OPERATOR'

  const title = isOp
    ? 'Operator Registration'
    : 'Maintenance Engineer Registration'

  const success = isOp
    ? 'Operator account created successfully.'
    : 'Maintenance Engineer account created successfully.'

  const button = isOp
    ? 'Create Operator Account'
    : 'Create Engineer Account'

  const accent = isOp ? '#38bdf8' : '#34d399'
  const accentBg = isOp ? '#0369a114' : '#06522214'
  const accentBdr = isOp ? '#0369a155' : '#06522255'

  const [form, setForm] = useState({
    username: '',
    full_name: '',
    password: '',
    confirmPw: '',
  })

  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (
      !form.username.trim() ||
      !form.full_name.trim() ||
      !form.password
    ) {
      setError('Please fill in all required fields.')
      return
    }

    if (form.password.length < 12) {
      setError('Password must be at least 12 characters long.')
      return
    }

    if (form.password !== form.confirmPw) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)

    try {
      const r = await fetch(`${API}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username.trim(),
          full_name: form.full_name.trim(),
          password: form.password,
          role,
        }),
      })

      const d = await r.json().catch(() => ({}))

      if (!r.ok) {
        setError(
          getLoginErrorMessage(d, 'Registration failed.')
        )
        return
      }

      setDone(true)
    } catch (error) {
      console.error(
        '[IntelliWatch] User registration failed:',
        error
      )

      setError('Unable to connect to the server. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title" style={{ color: accent }}>
            {title}
          </span>

          <button
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
            type="button"
          >
            &times;
          </button>
        </div>

        {done ? (
          <div className="modal-success">
            <span className="modal-success-icon">
              {isOp ? '📊' : '🔧'}
            </span>

            <p style={{ color: accent }}>
              {success}
            </p>

            <button
              className="login-btn"
              style={{
                background: `linear-gradient(135deg,${accent},${isOp ? '#0369a1' : '#065f46'})`,
              }}
              onClick={onClose}
              type="button"
            >
              Sign In
            </button>
          </div>
        ) : (
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div
              className="modal-notice"
              style={{
                background: accentBg,
                borderColor: accentBdr,
                color: accent,
              }}
            >
              Account registration requires a reachable IntelliWatch server.
            </div>

            <div className="login-form-row">
              <div className="login-field">
                <label className="login-label" htmlFor="rg-u">
                  Username
                </label>

                <div className="login-input-wrap">
                  <span className="login-input-icon">👤</span>

                  <input
                    id="rg-u"
                    className="login-input"
                    type="text"
                    placeholder="Choose a username"
                    value={form.username}
                    onChange={e =>
                      setForm(f => ({ ...f, username: e.target.value }))
                    }
                    autoComplete="off"
                    disabled={loading}
                    spellCheck={false}
                  />
                </div>
              </div>

              <div className="login-field">
                <label className="login-label" htmlFor="rg-n">
                  Full Name
                </label>

                <div className="login-input-wrap">
                  <span className="login-input-icon">🎭</span>

                  <input
                    id="rg-n"
                    className="login-input"
                    type="text"
                    placeholder="Enter your full name"
                    value={form.full_name}
                    onChange={e =>
                      setForm(f => ({ ...f, full_name: e.target.value }))
                    }
                    autoComplete="off"
                    disabled={loading}
                  />
                </div>
              </div>
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="rg-pw">
                Password{' '}
                <span className="login-label-hint">
                  (Minimum 12 characters)
                </span>
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>

                <input
                  id="rg-pw"
                  className="login-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder="Create a strong password"
                  value={form.password}
                  onChange={e =>
                    setForm(f => ({ ...f, password: e.target.value }))
                  }
                  autoComplete="new-password"
                  disabled={loading}
                />

                <button
                  type="button"
                  className="login-eye-btn"
                  onClick={() => setShowPw(v => !v)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  <PasswordVisibilityIcon visible={showPw} />
                </button>
              </div>

              <PasswordStrength password={form.password} />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="rg-pw2">
                Confirm Password
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>

                <input
                  id="rg-pw2"
                  className="login-input"
                  type={showPw ? 'text' : 'password'}
                  placeholder="Re-enter your password"
                  value={form.confirmPw}
                  onChange={e =>
                    setForm(f => ({ ...f, confirmPw: e.target.value }))
                  }
                  autoComplete="new-password"
                  disabled={loading}
                />
              </div>

              {form.confirmPw && form.password !== form.confirmPw && (
                <span className="login-field-err">
                  Passwords do not match.
                </span>
              )}
            </div>

            {error && <div className="login-error">⚠️ {error}</div>}

            <button
              className="login-btn"
              type="submit"
              style={{
                background: `linear-gradient(135deg,${accent},${isOp ? '#0369a1' : '#065f46'})`,
                boxShadow: `0 4px 20px ${accent}30`,
              }}
              disabled={loading || form.password !== form.confirmPw}
            >
              {loading ? (
                <span className="login-spinner" />
              ) : (
                button
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 8. CREATE ACCOUNT VIEW
// ─────────────────────────────────────────────────────────────────────────────

function CreateAccountView({ onBackToLogin }) {
  const [modal, setModal] = useState(null)

  const roles = [
    {
      role: 'OPERATOR',
      title: 'Operator Account',
      desc: 'For personnel responsible for monitoring equipment and reviewing alerts.',
      btn: 'Create Operator Account',
      icon: '📊',
      accent: '#38bdf8',
      accentBg: '#0369a114',
      accentBdr: '#0369a155',
      accentGlow: '#0369a130',
      features: [
        { icon: '📈', text: 'Real-time sensor monitoring' },
        { icon: '🔍', text: 'Anomaly analysis dashboards' },
        { icon: '🏷️', text: 'Label submission for ML training' },
        { icon: '📋', text: 'Alert log and trend reports' },
      ],
    },
    {
      role: 'MAINTENANCE_ENGINEER',
      title: 'Maintenance Engineer Account',
      desc: 'For personnel responsible for equipment maintenance and calibration.',
      btn: 'Create Engineer Account',
      icon: '🔧',
      accent: '#34d399',
      accentBg: '#06522214',
      accentBdr: '#06522255',
      accentGlow: '#06522230',
      features: [
        { icon: '⚙️', text: 'Equipment control commands' },
        { icon: '🛠️', text: 'Maintenance dispatch and ACK' },
        { icon: '🎛️', text: 'Sensor calibration access' },
        { icon: '📊', text: 'Full anomaly and alert access' },
      ],
    },
  ]

  return (
    <div className="login-root">
      <div className="login-bg">
        <span className="orb orb-1" />
        <span className="orb orb-2" />
        <span className="orb orb-3" />
      </div>

      <div className="create-account-wrap">
        <div className="create-account-header">
          <span className="login-eye" aria-hidden="true">
            <PasswordVisibilityIcon visible={false} size={28} />
          </span>

          <div>
            <h1 className="login-title">
              Create Your Account
            </h1>

            <p className="login-sub">
              Choose the account type that matches your role.
            </p>
          </div>
        </div>

        <div className="role-cards-grid">
          {roles.map(r => (
            <div
              key={r.role}
              className="role-card"
              style={{
                '--role-accent': r.accent,
                '--role-bg': r.accentBg,
                '--role-border': r.accentBdr,
                '--role-glow': r.accentGlow,
              }}
            >
              <div className="role-card-top">
                <span className="role-card-icon">
                  {r.icon}
                </span>

                <h2 className="role-card-title">
                  {r.title}
                </h2>

                <p className="role-card-desc">
                  {r.desc}
                </p>
              </div>

              <ul
                className="role-card-features"
                aria-label="Included features"
              >
                {r.features.map(f => (
                  <li key={f.text} className="role-card-feature">
                    <span className="role-card-feature-icon">
                      {f.icon}
                    </span>

                    <span className="role-card-feature-text">
                      {f.text}
                    </span>
                  </li>
                ))}
              </ul>

              <button
                className="role-card-btn"
                style={{
                  background: `linear-gradient(135deg, ${r.accent}, ${r.role === 'OPERATOR' ? '#0369a1' : '#065f46'})`,
                  boxShadow: `0 4px 22px ${r.accentGlow}`,
                }}
                onClick={() => setModal(r.role)}
                aria-label={r.btn}
                type="button"
              >
                {r.btn}
              </button>
            </div>
          ))}
        </div>

        <div className="create-account-footer">
          <span className="login-hint">
            Already have an account?
          </span>

          <button
            type="button"
            className="login-extra-btn create-account-back"
            onClick={onBackToLogin}
          >
            ← Back to Sign In
          </button>
        </div>
      </div>

      {modal && (
        <RoleRegisterModal
          role={modal}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────────────
// 9. MAIN LOGIN PAGE
// ─────────────────────────────────────────────────────────────────────────────

export default function LoginPage({ onLogin }) {
  useEffect(() => {
    try {
      localStorage.removeItem('iw_saved_accounts')
    } catch (error) {
      console.warn('[IntelliWatch] Legacy saved-account history could not be cleared:', error)
    }
  }, [])

  const [mode, setMode] = useState('operator')
  const [view, setView] = useState('login')
  const [activeRole, setActiveRole] = useState('OPERATOR')

  // 'password' | 'google' | 'phone'
  const [authMethod, setAuthMethod] = useState('password')

  const [timezone, setTimezone] = useState('Asia/Kolkata')

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)

  const [availability, setAvailability] = useState({
    checked: false,
    internetAvailable: false,
    backendAvailable: false,
    onlineMode: false,
    registrationEnabled: false,
  })

  const onlineMode = availability.onlineMode
  const regEnabled =
    onlineMode && availability.registrationEnabled


  // ==================================================
  // AUTOMATIC AVAILABILITY DETECTION
  // ==================================================

  useEffect(() => {
    let cancelled = false

    async function updateAvailability() {
      const result = await detectAvailability()

      if (!cancelled) {
        setAvailability(result)

        if (!result.onlineMode) {
          setModal(null)

          if (result.registrationEnabled === false) {
            setView('login')
          }
        }
      }
    }

    function handleOffline() {
      updateAvailability()
    }

    function handleOnline() {
      updateAvailability()
    }

    updateAvailability()

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      cancelled = true

      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])


  // ==================================================
  // DEMO LOGIN
  //
  // All three roles are available in fallback mode.
  // The selected tab determines the simulated role.
  // ==================================================

  function completeDemoLogin(requestedRole) {
    const demoUser = {
      access_token: DEMO_TOKEN,
      username: 'demo',
      full_name: 'Demo User',
      role: requestedRole,
      account_role: 'DEMO',
      is_restricted_session: true,
      is_demo_session: true,
      user_id: 0,
      session_mode: 'DEMO',
    }

    const sessionUser = {
      username: demoUser.username,
      full_name: demoUser.full_name,
      role: demoUser.role,
      account_role: demoUser.account_role,
      is_restricted_session: true,
      is_demo_session: true,
      user_id: demoUser.user_id,
      session_mode: 'DEMO',
      timezone,
    }

    try {
      saveSession(DEMO_TOKEN, sessionUser)
      onLogin(demoUser)
    } catch (error) {
      clearSavedSession()

      console.error(
        '[IntelliWatch] Demo session initialization failed:',
        error
      )

      setError(
        'The demo session could not be initialized. Please allow session storage and refresh the application.'
      )
    }
  }


  // ==================================================
  // ROLE SWITCHING
  // ==================================================

  function switchMode(nextMode) {
    setMode(nextMode)
    setUsername('')
    setPassword('')
    setError('')
    setAuthMethod('password')
  }

  function switchActiveRole(nextRole) {
    setActiveRole(nextRole)
    setError('')
  }

  function switchAuthMethod(method) {
    setAuthMethod(method)
    setError('')
  }



  // ==================================================
  // LOGIN
  // ==================================================

  async function handleSubmit(e) {
    e.preventDefault()

    if (loading) return

    setError('')

    const enteredUsername = username.trim()

    if (!enteredUsername || !password) {
      setError('Please enter both username and password.')
      return
    }

    const requestedRole =
      mode === 'admin'
        ? 'ADMIN'
        : activeRole

    const exactDemoCredentials =
      DEMO_MODE &&
      enteredUsername.toLowerCase() === 'demo' &&
      password === 'demo'

    setLoading(true)

    try {
      // ------------------------------------------------
      // 1. DEMO LOGIN
      // ------------------------------------------------
      // Demo credentials create a local, restricted session.
      // They never authenticate against the real backend.

      

      // ------------------------------------------------
      // 2. CHECK SERVICE AVAILABILITY
      // ------------------------------------------------

      const currentAvailability = await detectAvailability()

      setAvailability(currentAvailability)

      // ------------------------------------------------
      // 3. REGISTERED ACCOUNT AUTHENTICATION
      // ------------------------------------------------

      if (!currentAvailability.backendAvailable) {
        if (exactDemoCredentials) {
          completeDemoLogin(requestedRole)
          return
        }
        setError(
          DEMO_MODE
            ? 'Online services are unavailable. Use demo / demo for the local demonstration.'
            : 'The IntelliWatch backend is unavailable. Start the backend and try again.'
        )
        return
      }
      // ------------------------------------------------

      let response

      try {
        response = await fetch(`${API}/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            username: enteredUsername,
            password,
            requested_role: requestedRole,
          }),
        })
      } catch (networkError) {
        console.error(
          '[IntelliWatch Login] Authentication request failed:',
          networkError
        )

        const refreshedAvailability = await detectAvailability()

        setAvailability(refreshedAvailability)

        if (exactDemoCredentials && !refreshedAvailability.backendAvailable) {
          completeDemoLogin(requestedRole)
          return
        }

        setError(
          refreshedAvailability.backendAvailable
            ? 'Unable to reach the authentication endpoint. Check the HTTPS certificate, API URL and CORS configuration.'
            : 'The IntelliWatch backend is unavailable. Please start the backend and try again.'
        )

        return
      }

      // ------------------------------------------------
      // 4. PARSE THE SERVER RESPONSE
      // ------------------------------------------------

      if (!response.ok && [502, 503, 504].includes(response.status) && exactDemoCredentials) {
        completeDemoLogin(requestedRole)
        return
      }

      const responseText = await response.text()

      let data = {}

      if (responseText.trim()) {
        try {
          data = JSON.parse(responseText)
        } catch (parseError) {
          console.error(
            '[IntelliWatch Login] Invalid JSON response:',
            parseError
          )

          setError(
            `The authentication server returned an invalid response (HTTP ${response.status}).`
          )

          return
        }
      }

      if (
        !data ||
        typeof data !== 'object' ||
        Array.isArray(data)
      ) {
        console.error(
          '[IntelliWatch Login] Server returned an invalid response object.'
        )

        setError(
          'The authentication server returned an invalid response.'
        )

        return
      }

      // ------------------------------------------------
      // 5. HANDLE BACKEND AUTHENTICATION ERRORS
      // ------------------------------------------------

      if (!response.ok) {
        const serverMessage = getLoginErrorMessage(
          data,
          `Authentication failed (HTTP ${response.status}).`
        )

        console.warn(
          '[IntelliWatch Login] Backend rejected authentication:',
          {
            status: response.status,
            message: serverMessage,
          }
        )

        setError(serverMessage)
        return
      }

      // ------------------------------------------------
      // 6. VALIDATE SUCCESSFUL AUTHENTICATION RESPONSE
      // ------------------------------------------------

      if (
        typeof data.access_token !== 'string' ||
        !data.access_token.trim()
      ) {
        console.error(
          '[IntelliWatch Login] Access token missing from successful response.'
        )

        setError(
          'The authentication server did not return a valid access token.'
        )

        return
      }

      if (
        typeof data.username !== 'string' ||
        typeof data.role !== 'string' ||
        !['ADMIN', 'OPERATOR', 'MAINTENANCE_ENGINEER'].includes(data.role) ||
        data.role !== requestedRole ||
        !Number.isInteger(data.user_id) ||
        typeof data.full_name !== 'string'
      ) {
        console.error(
          '[IntelliWatch Login] Incomplete or invalid account information returned by the backend.'
        )

        setError(
          'The authentication server returned incomplete account information.'
        )

        return
      }

      const onlineUser = {
        ...data,
        account_role: data.account_role || data.role,
        is_restricted_session: !!data.is_restricted_session,
        is_demo_session: false,
        session_mode: 'ONLINE',
      }

      const sessionUser = {
        username: data.username,
        full_name: data.full_name,
        role: data.role,
        account_role: data.account_role || data.role,
        is_restricted_session: !!data.is_restricted_session,
        is_demo_session: false,
        user_id: data.user_id,
        session_mode: 'ONLINE',
        timezone,
      }

      // ------------------------------------------------
      // 7. STORE THE AUTHENTICATED SESSION
      // ------------------------------------------------

      try {
        saveSession(data.access_token, sessionUser)
      } catch (storageError) {
        console.error(
          '[IntelliWatch Login] Session storage failed:',
          storageError
        )

        clearSavedSession()

        setError(
          'Your browser could not store the login session. Please enable session storage and try again.'
        )

        return
      }

      // ------------------------------------------------
      // 9. INITIALIZE THE AUTHENTICATED APPLICATION
      // ------------------------------------------------

      try {
        onLogin(onlineUser)
      } catch (applicationError) {
        console.error(
          '[IntelliWatch Login] Application initialization failed after authentication:',
          applicationError
        )

        clearSavedSession()

        setError(
          'Authentication succeeded, but the application could not initialize. Refresh the page and inspect the application console.'
        )
      }

    } catch (unexpectedError) {
      console.error(
        '[IntelliWatch Login] Unexpected sign-in failure:',
        unexpectedError
      )

      setError(
        'An unexpected sign-in error occurred. Check the browser console for details.'
      )
    } finally {
      setLoading(false)
    }
  }


  // ==================================================
  // CREATE ACCOUNT VIEW
  // ==================================================

  if (view === 'create') {
    if (!regEnabled) {
      return (
        <div className="login-root">
          <div className="login-card">
            <div className="login-error" role="alert">
              Account registration requires both internet and an available
              IntelliWatch backend.
            </div>

            <button
              type="button"
              className="login-btn"
              onClick={() => setView('login')}
            >
              ← Back to Sign In
            </button>
          </div>
        </div>
      )
    }

    return (
      <CreateAccountView
        onBackToLogin={() => setView('login')}
      />
    )
  }


  // ==================================================
  // LOGIN PAGE UI
  // ==================================================

  return (
    <div className="login-root">
      <div className="login-bg">
        <span className="orb orb-1" />
        <span className="orb orb-2" />
        <span className="orb orb-3" />
      </div>

      <div className="login-stack">
        <div className="login-card">
          <div className="login-brand">
            <span className="login-eye" aria-hidden="true">
              &#128065;&#65039;
            </span>

            <div>
              <h1 className="login-title">
                IntelliWatch
              </h1>

              <p className="login-sub">
                Real-Time Monitoring & Decision Support
              </p>
            </div>
          </div>


          {/* ROLE MODE SELECTOR */}

          <div className="mode-selector">
            <button
              type="button"
              className={`mode-tab${mode === 'operator' ? ' mode-tab--active' : ''}`}
              onClick={() => switchMode('operator')}
            >
              <span className="mode-tab-icon">📊</span>

              <span className="mode-tab-text">
                <span className="mode-tab-title">
                  Operator / Engineer
                </span>

                <span className="mode-tab-sub">
                  Equipment monitoring and maintenance
                </span>
              </span>
            </button>

            <button
              type="button"
              className={`mode-tab mode-tab--admin${mode === 'admin' ? ' mode-tab--active-admin' : ''}`}
              onClick={() => switchMode('admin')}
            >
              <span className="mode-tab-icon">🛡️</span>

              <span className="mode-tab-text">
                <span className="mode-tab-title">
                  Administrator
                </span>

                <span className="mode-tab-sub">
                  System administration access
                </span>
              </span>
            </button>
          </div>


          {/* OPERATOR / ENGINEER SUBROLE */}

          {mode === 'operator' && (
            <div className="subrole-bar">
              <button
                type="button"
                className={`subrole-btn${activeRole === 'OPERATOR' ? ' subrole-btn--active subrole-btn--op' : ''}`}
                onClick={() => switchActiveRole('OPERATOR')}
              >
                📊 Operator
              </button>

              <button
                type="button"
                className={`subrole-btn${activeRole === 'MAINTENANCE_ENGINEER' ? ' subrole-btn--active subrole-btn--eng' : ''}`}
                onClick={() => switchActiveRole('MAINTENANCE_ENGINEER')}
              >
                🔧 Engineer
              </button>
            </div>
          )}


          {/* TIMEZONE SELECTOR */}

          <div className="login-field" style={{ marginBottom: 12 }}>
            <label className="login-label" htmlFor="iw-timezone">Time Zone</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">🕐</span>
              <select
                id="iw-timezone"
                className="login-input"
                value={timezone}
                onChange={e => setTimezone(e.target.value)}
                disabled={loading}
                style={{ cursor: 'pointer', appearance: 'auto' }}
              >
                <option value="Asia/Kolkata">India (IST, UTC+5:30)</option>
                <option value="Asia/Dubai">Dubai (GST, UTC+4)</option>
                <option value="Asia/Shanghai">China (CST, UTC+8)</option>
                <option value="Asia/Singapore">Singapore (SGT, UTC+8)</option>
                <option value="Asia/Tokyo">Japan (JST, UTC+9)</option>
                <option value="Asia/Karachi">Pakistan (PKT, UTC+5)</option>
                <option value="Asia/Dhaka">Bangladesh (BST, UTC+6)</option>
                <option value="Asia/Colombo">Sri Lanka (IST, UTC+5:30)</option>
                <option value="Asia/Kathmandu">Nepal (NPT, UTC+5:45)</option>
                <option value="Europe/London">UK (GMT/BST, UTC+0/+1)</option>
                <option value="Europe/Berlin">Central Europe (CET, UTC+1)</option>
                <option value="Europe/Moscow">Moscow (MSK, UTC+3)</option>
                <option value="America/New_York">US Eastern (EST/EDT, UTC-5/-4)</option>
                <option value="America/Chicago">US Central (CST/CDT, UTC-6/-5)</option>
                <option value="America/Los_Angeles">US Pacific (PST/PDT, UTC-8/-7)</option>
                <option value="America/Sao_Paulo">Brazil (BRT, UTC-3)</option>
                <option value="Australia/Sydney">Sydney (AEDT, UTC+11)</option>
                <option value="Pacific/Auckland">New Zealand (NZDT, UTC+13)</option>
                <option value="UTC">UTC</option>
              </select>
            </div>
          </div>


          {/* AUTH METHOD TABS — only shown when backend is online and
              Firebase is configured */}

          {onlineMode && isFirebaseConfigured && (
            <div className="auth-method-tabs" role="tablist" aria-label="Sign-in method">
              <button
                type="button"
                role="tab"
                aria-selected={authMethod === 'password'}
                className={`auth-method-tab${authMethod === 'password' ? ' auth-method-tab--active' : ''}`}
                onClick={() => switchAuthMethod('password')}
              >
                🔒 Password
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={authMethod === 'google'}
                className={`auth-method-tab${authMethod === 'google' ? ' auth-method-tab--active' : ''}`}
                onClick={() => switchAuthMethod('google')}
              >
                <GoogleLogo /> Google
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={authMethod === 'phone'}
                className={`auth-method-tab${authMethod === 'phone' ? ' auth-method-tab--active' : ''}`}
                onClick={() => switchAuthMethod('phone')}
              >
                📱 Phone OTP
              </button>
            </div>
          )}


          {/* GOOGLE SIGN-IN PANEL */}

          {authMethod === 'google' && onlineMode && isFirebaseConfigured && (
            <>
              {error && (
                <div className="login-error" role="alert">⚠️ {error}</div>
              )}
              <GoogleSignInPanel
                onLogin={onLogin}
                onError={setError}
                loading={loading}
                setLoading={setLoading}
                timezone={timezone}
                selectedRole={activeRole}
              />
            </>
          )}


          {/* PHONE + OTP PANEL */}

          {authMethod === 'phone' && onlineMode && isFirebaseConfigured && (
            <>
              {error && (
                <div className="login-error" role="alert">⚠️ {error}</div>
              )}
              <PhoneOtpPanel
                onLogin={onLogin}
                onError={setError}
                loading={loading}
                setLoading={setLoading}
                timezone={timezone}
                selectedRole={activeRole}
              />
            </>
          )}


          {/* LOGIN FORM — shown only for password method */}

          {authMethod === 'password' && (
          <form
            className="login-form"
            onSubmit={handleSubmit}
            autoComplete="off"
            noValidate
          >
            <div className="login-field">
              <label
                className="login-label"
                htmlFor="iw-username"
              >
                Username
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">👤</span>

                <input
                  id="iw-username"
                  className="login-input"
                  type="text"
                  placeholder="Enter your username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  autoComplete="off"
                  disabled={loading}
                  spellCheck={false}
                />
              </div>


            </div>

            <div className="login-field">
              <label
                className="login-label"
                htmlFor="iw-password"
              >
                Password
              </label>

              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>

                <input
                  id="iw-password"
                  className="login-input"
                  type={showPass ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="current-password"
                  disabled={loading}
                />

                <button
                  type="button"
                  className="login-eye-btn"
                  onClick={() => setShowPass(p => !p)}
                  aria-label={showPass ? 'Hide password' : 'Show password'}
                >
                  <PasswordVisibilityIcon visible={showPass} />
                </button>
              </div>
            </div>

            {error && (
              <div className="login-error" role="alert">
                ⚠️ {error}
              </div>
            )}

            <button
              className={`login-btn${mode === 'admin' ? ' login-btn--admin-purple' : ''}`}
              type="submit"
              disabled={loading}
            >
              {loading ? (
                <span className="login-spinner" />
              ) : (
                'Sign In'
              )}
            </button>
          </form>
          )} {/* end authMethod === 'password' */}


          {/* MANUAL OFFLINE DEMO ACCESS */}
          <div style={{ marginTop: '14px' }}>
            <button
              type="button"
              className="login-btn"
              aria-label="Enter Offline Demo"
              onClick={() =>
                completeDemoLogin(
                  mode === 'admin' ? 'ADMIN' : activeRole
                )
              }
              disabled={loading}
            >
              Enter Offline Demo
            </button>
          </div>
          {/* DEMO HINT — SHOWN ONLY IN FALLBACK MODE */}

          {!availability.onlineMode && DEMO_MODE && (
            <p className="login-demo-hint">
              Demo fallback — username: <strong>demo</strong> · password:{' '}
              <strong>demo</strong>
              <span style={{ display: 'block', marginTop: 4 }}>
                Available for Operator, Engineer and Admin demonstration.
              </span>
            </p>
          )}


          {/* ONLINE-ONLY ACCOUNT ACTIONS */}

          {onlineMode && (
            <div className="login-bottom-links">
              <button
                type="button"
                className="login-extra-btn"
                onClick={() => setModal('forgot')}
              >
                Forgot Password?
              </button>

              {mode === 'admin' && (
                <>
                  <span className="login-extra-sep">•</span>

                  <button
                    type="button"
                    className="login-extra-btn login-extra-btn--admin"
                    onClick={() => setModal('admin-register')}
                  >
                    Register as Admin
                  </button>
                </>
              )}
            </div>
          )}
        </div>


        {/* ONLINE-ONLY SELF REGISTRATION */}

        {onlineMode && regEnabled && (
          <div className="new-here-strip">
            <span className="new-here-label">
              New here?
            </span>

            <button
              type="button"
              className="new-here-btn new-here-btn--op"
              onClick={() => setView('create')}
            >
              📊 Operator
            </button>

            <button
              type="button"
              className="new-here-btn new-here-btn--eng"
              onClick={() => setView('create')}
            >
              🔧 Engineer
            </button>
          </div>
        )}
      </div>


      {/* ONLINE-ONLY MODALS */}

      {modal === 'admin-register' && onlineMode && (
        <AdminRegisterModal
          onClose={() => setModal(null)}
          onDone={() => setModal(null)}
        />
      )}

      {modal === 'forgot' && onlineMode && (
        <ForgotModal
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}
