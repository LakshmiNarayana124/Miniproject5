
import { useState, useEffect } from 'react'
import './LoginPage.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ─────────────────────────────────────────────────────────────────────────────
// 1. HELPERS
// ─────────────────────────────────────────────────────────────────────────────

const SAVED_KEY = 'iw_saved_accounts'

function loadSaved() {
  try { return JSON.parse(localStorage.getItem(SAVED_KEY) || '[]') } catch { return [] }
}

function saveAccount(u) {
  if (!u || u.role === 'ADMIN') return
  const list = loadSaved().filter(a => a.username !== u.username)
  localStorage.setItem(SAVED_KEY, JSON.stringify(
    [{ username: u.username, full_name: u.full_name, role: u.role }, ...list].slice(0, 8)
  ))
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. PASSWORD STRENGTH
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
          <div key={i} className="pw-bar" style={{ background: i <= score ? colors[score] : '#252837' }} />
        ))}
      </div>
      <span className="pw-label" style={{ color: colors[score] }}>{labels[score]}</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. ADMIN REGISTER MODAL
// ─────────────────────────────────────────────────────────────────────────────

function AdminRegisterModal({ onClose, onDone }) {
  const [form, setForm] = useState({ username: '', full_name: '', password: '', confirmPw: '', invite_token: '' })
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!form.username.trim() || !form.full_name.trim() || !form.password || !form.invite_token.trim()) {
      setError('Please fill in all required fields.')
      return
    }
    if (form.password.length < 12) { setError('Password must be at least 12 characters long.'); return }
    if (form.password !== form.confirmPw) { setError('Passwords do not match.'); return }

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
      const d = await r.json()
      if (!r.ok) {
        setError(d.detail || 'Admin registration failed.')
        setLoading(false)
        return
      }
      setSuccess(d.invited_by || '—')
    } catch {
      setError('Unable to connect to the server. Please try again.')
    }
    setLoading(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Admin Registration</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {success ? (
          <div className="modal-success">
            <span className="modal-success-icon">✅</span>
            <p>Administrator account created by <strong>{success}</strong>.</p>
            <p className="modal-success-sub">You can now sign in using your administrator credentials.</p>
            <button className="login-btn" onClick={onDone}>Done</button>
          </div>
        ) : (
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div className="modal-notice">Administrator registration requires a valid invitation token.</div>

            <div className="login-form-row">
              <div className="login-field">
                <label className="login-label" htmlFor="ar-user">Username</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">👤</span>
                  <input id="ar-user" className="login-input" type="text" placeholder="Choose a username"
                    value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    autoComplete="off" disabled={loading} spellCheck={false} />
                </div>
              </div>
              <div className="login-field">
                <label className="login-label" htmlFor="ar-name">Full Name</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">🎭</span>
                  <input id="ar-name" className="login-input" type="text" placeholder="Enter your full name"
                    value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                    autoComplete="off" disabled={loading} />
                </div>
              </div>
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="ar-pw">
                Password <span className="login-label-hint">(Minimum 12 characters)</span>
              </label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="ar-pw" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder="Create a strong password" value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
                <button type="button" className="login-eye-btn" onClick={() => setShowPw(v => !v)}>{showPw ? '🙈' : '👁'}</button>
              </div>
              <PasswordStrength password={form.password} />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="ar-pw2">Confirm Password</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="ar-pw2" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder="Re-enter your password" value={form.confirmPw}
                  onChange={e => setForm(f => ({ ...f, confirmPw: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
              </div>
              {form.confirmPw && form.password !== form.confirmPw &&
                <span className="login-field-err">Passwords do not match.</span>}
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="ar-tok">Invitation Token</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔑</span>
                <input id="ar-tok" className="login-input" type="text" placeholder="Enter invitation token"
                  value={form.invite_token} onChange={e => setForm(f => ({ ...f, invite_token: e.target.value }))}
                  autoComplete="off" disabled={loading} spellCheck={false} />
              </div>
            </div>

            {error && <div className="login-error">⚠️ {error}</div>}
            <button className="login-btn login-btn--admin-purple" type="submit" disabled={loading || form.password !== form.confirmPw}>
              {loading ? <span className="login-spinner" /> : 'Create Administrator Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 4. FORGOT PASSWORD MODAL
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

    if (!username.trim()) { setError('Please enter your username.'); return }

    setLoading(true)
    try {
      const r = await fetch(`${API}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim() }),
      })
      const d = await r.json()
      if (!r.ok) {
        setError(d.detail || 'Unable to process your request.')
        setLoading(false)
        return
      }
      if (d.reset_token) {
        setInfo(`Reset Token: ${d.reset_token}\n\n${'Keep this token secure and use it to reset your password.'}`)
      } else {
        setInfo(d.note || d.message || '')
      }
      setStep('reset')
    } catch {
      setError('Unable to connect to the server. Please try again.')
    }
    setLoading(false)
  }

  async function handleReset(e) {
    e.preventDefault()
    setError('')

    if (!token.trim()) { setError('Please enter the reset token.'); return }
    if (newPw.length < 12) { setError('Password must be at least 12 characters long.'); return }
    if (newPw !== confirmPw) { setError('Passwords do not match.'); return }

    setLoading(true)
    try {
      const r = await fetch(`${API}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim(), new_password: newPw }),
      })
      const d = await r.json()
      if (!r.ok) {
        setError(d.detail || 'Password reset failed.')
        setLoading(false)
        return
      }
      setDone(true)
    } catch {
      setError('Unable to connect to the server. Please try again.')
    }
    setLoading(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Reset Password</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {done ? (
          <div className="modal-success">
            <span className="modal-success-icon">✅</span>
            <p>Your password has been updated successfully.</p>
            <button className="login-btn" onClick={onClose} style={{ marginTop: 12 }}>Done</button>
          </div>
        ) : step === 'request' ? (
          <form className="login-form" onSubmit={handleRequest} noValidate>
            <p className="login-fp-desc">Enter your username to request a password reset.</p>
            <div className="login-field">
              <label className="login-label" htmlFor="fp-u">Username</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">👤</span>
                <input id="fp-u" className="login-input" type="text" placeholder="Enter your username"
                  value={username} onChange={e => setUsername(e.target.value)} disabled={loading} spellCheck={false} />
              </div>
            </div>
            {error && <div className="login-error">⚠️ {error}</div>}
            {info && <div className="login-info">{info}</div>}
            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? <span className="login-spinner" /> : 'Get Reset Token'}
            </button>
          </form>
        ) : (
          <form className="login-form" onSubmit={handleReset} noValidate>
            {info && <div className="login-info login-info--token"><pre>{info}</pre></div>}

            <div className="login-field">
              <label className="login-label" htmlFor="fp-tok">Reset Token</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🎫</span>
                <input id="fp-tok" className="login-input" type="text" placeholder="Paste your reset token"
                  value={token} onChange={e => setToken(e.target.value)} disabled={loading} spellCheck={false} />
              </div>
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="fp-pw">New Password</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="fp-pw" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder="Enter your new password" value={newPw}
                  onChange={e => setNewPw(e.target.value)} autoComplete="new-password" disabled={loading} />
                <button type="button" className="login-eye-btn" onClick={() => setShowPw(v => !v)}>{showPw ? '🙈' : '👁'}</button>
              </div>
              <PasswordStrength password={newPw} />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="fp-pw2">Confirm Password</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="fp-pw2" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder="Re-enter your password" value={confirmPw}
                  onChange={e => setConfirmPw(e.target.value)} autoComplete="new-password" disabled={loading} />
              </div>
              {confirmPw && newPw !== confirmPw &&
                <span className="login-field-err">Passwords do not match.</span>}
            </div>

            {error && <div className="login-error">⚠️ {error}</div>}
            <button className="login-btn" type="submit" disabled={loading || newPw !== confirmPw}>
              {loading ? <span className="login-spinner" /> : 'Set New Password'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. ROLE-SPECIFIC REGISTER MODAL
// ─────────────────────────────────────────────────────────────────────────────

function RoleRegisterModal({ role, onClose }) {
  const isOp = role === 'OPERATOR'
  const title = isOp ? 'Operator Registration' : 'Maintenance Engineer Registration'
  const success = isOp ? 'Operator account created successfully.' : 'Maintenance Engineer account created successfully.'
  const button = isOp ? 'Create Operator Account' : 'Create Engineer Account'
  const accent = isOp ? '#38bdf8' : '#34d399'
  const accentBg = isOp ? '#0369a114' : '#06522214'
  const accentBdr = isOp ? '#0369a155' : '#06522255'

  const [form, setForm] = useState({ username: '', full_name: '', password: '', confirmPw: '', invite_code: '' })
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!form.username.trim() || !form.full_name.trim() || !form.password || !form.invite_code.trim()) {
      setError('Please fill in all required fields.')
      return
    }
    if (form.password.length < 12) { setError('Password must be at least 12 characters long.'); return }
    if (form.password !== form.confirmPw) { setError('Passwords do not match.'); return }

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
          invite_code: form.invite_code.trim(),
        }),
      })
      const d = await r.json()
      if (!r.ok) {
        setError(d.detail || 'Registration failed.')
        setLoading(false)
        return
      }
      setDone(true)
    } catch {
      setError('Unable to connect to the server. Please try again.')
    }
    setLoading(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title" style={{ color: accent }}>{title}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {done ? (
          <div className="modal-success">
            <span className="modal-success-icon">{isOp ? '📊' : '🔧'}</span>
            <p style={{ color: accent }}>{success}</p>
            <button className="login-btn"
              style={{ background: `linear-gradient(135deg,${accent},${isOp ? '#0369a1' : '#065f46'})` }}
              onClick={onClose}>Sign In</button>
          </div>
        ) : (
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div className="modal-notice" style={{ background: accentBg, borderColor: accentBdr, color: accent }}>
              Registration requires a valid invitation code from an administrator.
            </div>

            <div className="login-form-row">
              <div className="login-field">
                <label className="login-label" htmlFor="rg-u">Username</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">👤</span>
                  <input id="rg-u" className="login-input" type="text" placeholder="Choose a username"
                    value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    autoComplete="off" disabled={loading} spellCheck={false} />
                </div>
              </div>
              <div className="login-field">
                <label className="login-label" htmlFor="rg-n">Full Name</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">🎭</span>
                  <input id="rg-n" className="login-input" type="text" placeholder="Enter your full name"
                    value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                    autoComplete="off" disabled={loading} />
                </div>
              </div>
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="rg-pw">
                Password <span className="login-label-hint">(Minimum 12 characters)</span>
              </label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="rg-pw" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder="Create a strong password" value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
                <button type="button" className="login-eye-btn" onClick={() => setShowPw(v => !v)}>{showPw ? '🙈' : '👁'}</button>
              </div>
              <PasswordStrength password={form.password} />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="rg-pw2">Confirm Password</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="rg-pw2" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder="Re-enter your password" value={form.confirmPw}
                  onChange={e => setForm(f => ({ ...f, confirmPw: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
              </div>
              {form.confirmPw && form.password !== form.confirmPw &&
                <span className="login-field-err">Passwords do not match.</span>}
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="rg-inv">
                Invitation Code <span className="login-label-hint">(Provided by administrator)</span>
              </label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🎫</span>
                <input id="rg-inv" className="login-input" type="text" placeholder="Enter invitation code"
                  value={form.invite_code} onChange={e => setForm(f => ({ ...f, invite_code: e.target.value }))}
                  autoComplete="off" disabled={loading} spellCheck={false} />
              </div>
            </div>

            {error && <div className="login-error">⚠️ {error}</div>}

            <button className="login-btn" type="submit"
              style={{ background: `linear-gradient(135deg,${accent},${isOp ? '#0369a1' : '#065f46'})`, boxShadow: `0 4px 20px ${accent}30` }}
              disabled={loading || form.password !== form.confirmPw}>
              {loading ? <span className="login-spinner" /> : button}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. CREATE ACCOUNT VIEW
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
        <span className="orb orb-1" /><span className="orb orb-2" /><span className="orb orb-3" />
      </div>

      <div className="create-account-wrap">
        <div className="create-account-header">
          <span className="login-eye" style={{ fontSize: 28 }}>👁️</span>
          <div>
            <h1 className="login-title">Create Your Account</h1>
            <p className="login-sub">Choose the account type that matches your role.</p>
          </div>
        </div>

        <div className="role-cards-grid">
          {roles.map(r => (
            <div key={r.role} className="role-card"
              style={{ '--role-accent': r.accent, '--role-bg': r.accentBg, '--role-border': r.accentBdr, '--role-glow': r.accentGlow }}>

              <div className="role-card-top">
                <span className="role-card-icon">{r.icon}</span>
                <h2 className="role-card-title">{r.title}</h2>
                <p className="role-card-desc">{r.desc}</p>
              </div>

              <ul className="role-card-features" aria-label="Included features">
                {r.features.map(f => (
                  <li key={f.text} className="role-card-feature">
                    <span className="role-card-feature-icon">{f.icon}</span>
                    <span className="role-card-feature-text">{f.text}</span>
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
              >
                {r.btn}
              </button>
            </div>
          ))}
        </div>

        <div className="create-account-footer">
          <span className="login-hint">Already have an account?</span>
          <button type="button" className="login-extra-btn create-account-back" onClick={onBackToLogin}>
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
// 7. MAIN LOGIN PAGE
// ─────────────────────────────────────────────────────────────────────────────

export default function LoginPage({ onLogin }) {
  const [mode, setMode] = useState('operator')
  const [view, setView] = useState('login')
  const [activeRole, setActiveRole] = useState('OPERATOR')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(null)
  const [regEnabled, setRegEnabled] = useState(false)

  useEffect(() => {
    fetch(`${API}/auth/registration-status`)
      .then(r => r.json())
      .then(d => setRegEnabled(!!d.registration_enabled))
      .catch(() => {})
  }, [])

  function switchMode(m) {
    setMode(m)
    setUsername('')
    setPassword('')
    setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!username.trim() || !password) {
      setError('Please enter both username and password.')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })

      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        setError(d.detail || 'Invalid username or password.')
        setLoading(false)
        return
      }

      const data = await res.json()
      sessionStorage.setItem('iw_token', data.access_token)
      sessionStorage.setItem('iw_user', JSON.stringify({
        username: data.username,
        full_name: data.full_name,
        role: data.role,
        user_id: data.user_id,
      }))
      saveAccount(data)
      onLogin(data)
    } catch {
      if (username.trim().toLowerCase() === 'demo' && password === 'demo') {
        const fake = {
          access_token: 'demo-offline',
          username: 'demo',
          full_name: 'Demo User',
          role: 'OPERATOR',
          user_id: 0,
        }
        sessionStorage.setItem('iw_token', fake.access_token)
        sessionStorage.setItem('iw_user', JSON.stringify(fake))
        saveAccount(fake)
        onLogin(fake)
      } else {
        setError('Unable to connect to the server. Please check your connection.')
      }
    }
    setLoading(false)
  }

  if (view === 'create') {
    return (
      <CreateAccountView
        onBackToLogin={() => setView('login')}
      />
    )
  }

  return (
    <div className="login-root">
      <div className="login-bg">
        <span className="orb orb-1" /><span className="orb orb-2" /><span className="orb orb-3" />
      </div>

      <div className="login-stack">
        <div className="login-card">
          <div className="login-brand">
            <span className="login-eye">👁️</span>
            <div>
              <h1 className="login-title">IntelliWatch</h1>
              <p className="login-sub">Real-Time Monitoring & Decision Support</p>
            </div>
          </div>

          <div className="mode-selector">
            <button type="button"
              className={`mode-tab${mode === 'operator' ? ' mode-tab--active' : ''}`}
              onClick={() => switchMode('operator')}>
              <span className="mode-tab-icon">📊</span>
              <span className="mode-tab-text">
                <span className="mode-tab-title">Operator / Engineer</span>
                <span className="mode-tab-sub">Equipment monitoring and maintenance</span>
              </span>
            </button>

            <button type="button"
              className={`mode-tab mode-tab--admin${mode === 'admin' ? ' mode-tab--active-admin' : ''}`}
              onClick={() => switchMode('admin')}>
              <span className="mode-tab-icon">🛡️</span>
              <span className="mode-tab-text">
                <span className="mode-tab-title">Administrator</span>
                <span className="mode-tab-sub">System administration access</span>
              </span>
            </button>
          </div>

          {mode === 'operator' && (
            <div className="subrole-bar">
              <button type="button"
                className={`subrole-btn${activeRole === 'OPERATOR' ? ' subrole-btn--active subrole-btn--op' : ''}`}
                onClick={() => setActiveRole('OPERATOR')}>
                📊 Operator
              </button>
              <button type="button"
                className={`subrole-btn${activeRole === 'MAINTENANCE_ENGINEER' ? ' subrole-btn--active subrole-btn--eng' : ''}`}
                onClick={() => setActiveRole('MAINTENANCE_ENGINEER')}>
                🔧 Engineer
              </button>
            </div>
          )}

          <form className="login-form" onSubmit={handleSubmit} autoComplete="off" noValidate>
            <div className="login-field">
              <label className="login-label" htmlFor="iw-username">Username</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">👤</span>
                <input id="iw-username" className="login-input" type="text"
                  placeholder="Enter your username" value={username}
                  onChange={e => setUsername(e.target.value)}
                  autoComplete="username" disabled={loading} spellCheck={false} />
              </div>
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="iw-password">Password</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="iw-password" className="login-input" type={showPass ? 'text' : 'password'}
                  placeholder="Enter your password" value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="current-password" disabled={loading} />
                <button type="button" className="login-eye-btn"
                  onClick={() => setShowPass(p => !p)}
                  aria-label={showPass ? 'Hide password' : 'Show password'}>
                  {showPass ? '🙈' : '👁'}
                </button>
              </div>
            </div>

            {error && <div className="login-error" role="alert">⚠️ {error}</div>}

            <button
              className={`login-btn${mode === 'admin' ? ' login-btn--admin-purple' : ''}`}
              type="submit" disabled={loading}>
              {loading ? <span className="login-spinner" /> : 'Sign In'}
            </button>
          </form>

          <p className="login-demo-hint">
            Offline demo — username: <strong>demo</strong> · password: <strong>demo</strong>
          </p>

          <div className="login-bottom-links">
            <button type="button" className="login-extra-btn"
              onClick={() => setModal('forgot')}>
              Forgot Password?
            </button>

            {mode === 'admin' && (
              <>
                <span className="login-extra-sep">•</span>
                <button type="button" className="login-extra-btn login-extra-btn--admin"
                  onClick={() => setModal('admin-register')}>
                  Register as Admin
                </button>
              </>
            )}
          </div>
        </div>

        {regEnabled && (
          <div className="new-here-strip">
            <span className="new-here-label">New here?</span>
            <button type="button" className="new-here-btn new-here-btn--op"
              onClick={() => setView('create')}>
              📊 Operator
            </button>
            <button type="button" className="new-here-btn new-here-btn--eng"
              onClick={() => setView('create')}>
              🔧 Engineer
            </button>
          </div>
        )}
      </div>

      {modal === 'admin-register' && (
        <AdminRegisterModal
          onClose={() => setModal(null)}
          onDone={() => setModal(null)}
        />
      )}

      {modal === 'forgot' && (
        <ForgotModal onClose={() => setModal(null)} />
      )}
    </div>
  )
}
