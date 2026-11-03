// ─────────────────────────────────────────────────────────────────────────────
// IntelliWatch — LoginPage.jsx
// All visible strings go through t(key, lang) for full i18n.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect } from 'react'
import './LoginPage.css'
import { t } from '../i18n'
import useLang from '../useLang'

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

function PasswordStrength({ password, lang }) {
  if (!password) return null
  const score = [
    password.length >= 12, /[A-Z]/.test(password), /[a-z]/.test(password),
    /\d/.test(password), /[^A-Za-z0-9]/.test(password),
  ].filter(Boolean).length
  const labelKeys = ['', 'pw_very_weak', 'pw_weak', 'pw_fair', 'pw_strong', 'pw_very_strong']
  const colors    = ['', '#ef4444', '#f59e0b', '#eab308', '#22c55e', '#10b981']
  return (
    <div className="pw-strength">
      <div className="pw-bars">
        {[1,2,3,4,5].map(i => (
          <div key={i} className="pw-bar" style={{ background: i <= score ? colors[score] : '#252837' }} />
        ))}
      </div>
      <span className="pw-label" style={{ color: colors[score] }}>{t(labelKeys[score], lang)}</span>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. ADMIN REGISTER MODAL
// ─────────────────────────────────────────────────────────────────────────────

function AdminRegisterModal({ onClose, onDone, lang }) {
  const [form, setForm]       = useState({ username: '', full_name: '', password: '', confirmPw: '', invite_token: '' })
  const [showPw, setShowPw]   = useState(false)
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault(); setError('')
    if (!form.username.trim() || !form.full_name.trim() || !form.password || !form.invite_token.trim()) {
      setError(t('err_all_required', lang)); return
    }
    if (form.password.length < 12) { setError(t('err_pw_short', lang)); return }
    if (form.password !== form.confirmPw) { setError(t('pw_mismatch', lang)); return }
    setLoading(true)
    try {
      const r = await fetch(`${API}/auth/register-admin`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: form.username.trim(), full_name: form.full_name.trim(), password: form.password, invite_token: form.invite_token.trim() }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || t('err_reg_failed', lang)); setLoading(false); return }
      setSuccess(d.invited_by || '—')
    } catch { setError(t('err_network', lang)) }
    setLoading(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">{t('modal_admin_reg_title', lang)}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        {success ? (
          <div className="modal-success">
            <span className="modal-success-icon">✅</span>
            <p>{t('admin_created', lang)} <strong>{success}</strong>.</p>
            <p className="modal-success-sub">{t('admin_created_sub', lang)}</p>
            <button className="login-btn" onClick={onDone}>{t('btn_done', lang)}</button>
          </div>
        ) : (
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div className="modal-notice">{t('modal_admin_reg_notice', lang)}</div>
            <div className="login-form-row">
              <div className="login-field">
                <label className="login-label" htmlFor="ar-user">{t('lbl_username', lang)}</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">👤</span>
                  <input id="ar-user" className="login-input" type="text" placeholder={t('ph_choose_username', lang)}
                    value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    autoComplete="off" disabled={loading} spellCheck={false} />
                </div>
              </div>
              <div className="login-field">
                <label className="login-label" htmlFor="ar-name">{t('lbl_full_name', lang)}</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">🎭</span>
                  <input id="ar-name" className="login-input" type="text" placeholder={t('ph_your_name', lang)}
                    value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                    autoComplete="off" disabled={loading} />
                </div>
              </div>
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="ar-pw">
                {t('lbl_password', lang)} <span className="login-label-hint">({t('pw_min_hint', lang)})</span>
              </label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="ar-pw" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder={t('ph_strong_password', lang)} value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
                <button type="button" className="login-eye-btn" onClick={() => setShowPw(v => !v)}>{showPw ? '🙈' : '👁'}</button>
              </div>
              <PasswordStrength password={form.password} lang={lang} />
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="ar-pw2">{t('lbl_confirm_pw', lang)}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="ar-pw2" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder={t('ph_repeat_password', lang)} value={form.confirmPw}
                  onChange={e => setForm(f => ({ ...f, confirmPw: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
              </div>
              {form.confirmPw && form.password !== form.confirmPw &&
                <span className="login-field-err">{t('pw_mismatch', lang)}</span>}
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="ar-tok">{t('lbl_invite_token', lang)}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔑</span>
                <input id="ar-tok" className="login-input" type="text" placeholder={t('ph_paste_token', lang)}
                  value={form.invite_token} onChange={e => setForm(f => ({ ...f, invite_token: e.target.value }))}
                  autoComplete="off" disabled={loading} spellCheck={false} />
              </div>
              <span className="login-field-hint">{t('modal_token_hint', lang)}</span>
            </div>
            {error && <div className="login-error" role="alert">⚠️ {error}</div>}
            <button className="login-btn login-btn--admin-purple" type="submit"
              disabled={loading || form.password !== form.confirmPw}>
              {loading ? <span className="login-spinner" /> : t('btn_create_admin', lang)}
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

function ForgotModal({ onClose, lang }) {
  const [step, setStep]           = useState('request')
  const [username, setUsername]   = useState('')
  const [token, setToken]         = useState('')
  const [newPw, setNewPw]         = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showPw, setShowPw]       = useState(false)
  const [error, setError]         = useState('')
  const [info, setInfo]           = useState('')
  const [loading, setLoading]     = useState(false)
  const [done, setDone]           = useState(false)

  async function handleRequest(e) {
    e.preventDefault(); setError(''); setInfo('')
    if (!username.trim()) { setError(t('err_username_required', lang)); return }
    setLoading(true)
    try {
      const r = await fetch(`${API}/auth/forgot-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim() }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || t('err_reset_failed', lang)); setLoading(false); return }
      if (d.reset_token) { setToken(d.reset_token); setInfo(`Token: ${d.reset_token}\n\n(Expires in 15 min)`) }
      else { setInfo('If that account exists, a reset token was generated. Ask your administrator for it.') }
      setStep('reset')
    } catch { setError(t('err_network', lang)) }
    setLoading(false)
  }

  async function handleReset(e) {
    e.preventDefault(); setError('')
    if (!token.trim()) { setError(t('err_token_required', lang)); return }
    if (newPw.length < 12) { setError(t('err_pw_short', lang)); return }
    if (newPw !== confirmPw) { setError(t('pw_mismatch', lang)); return }
    setLoading(true)
    try {
      const r = await fetch(`${API}/auth/reset-password`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim(), new_password: newPw }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || t('err_reset_failed', lang)); setLoading(false); return }
      setDone(true)
    } catch { setError(t('err_network', lang)) }
    setLoading(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">{t('modal_reset_title', lang)}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        {done ? (
          <div className="modal-success">
            <span className="modal-success-icon">✅</span>
            <p>{t('pw_updated', lang)}</p>
            <button className="login-btn" onClick={onClose} style={{ marginTop: 12 }}>{t('btn_done', lang)}</button>
          </div>
        ) : step === 'request' ? (
          <form className="login-form" onSubmit={handleRequest} noValidate>
            <p className="login-fp-desc">{t('fp_desc', lang)}</p>
            <div className="login-field">
              <label className="login-label" htmlFor="fp-u">{t('lbl_username', lang)}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">👤</span>
                <input id="fp-u" className="login-input" type="text" placeholder={t('ph_username', lang)}
                  value={username} onChange={e => setUsername(e.target.value)} disabled={loading} spellCheck={false} />
              </div>
            </div>
            {error && <div className="login-error">⚠️ {error}</div>}
            {info  && <div className="login-info">{info}</div>}
            <button className="login-btn" type="submit" disabled={loading}>
              {loading ? <span className="login-spinner" /> : t('btn_get_token', lang)}
            </button>
          </form>
        ) : (
          <form className="login-form" onSubmit={handleReset} noValidate>
            {info && <div className="login-info login-info--token"><pre>{info}</pre></div>}
            <div className="login-field">
              <label className="login-label" htmlFor="fp-tok">{t('lbl_reset_token', lang)}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🎫</span>
                <input id="fp-tok" className="login-input" type="text" placeholder={t('ph_paste_reset_token', lang)}
                  value={token} onChange={e => setToken(e.target.value)} disabled={loading} spellCheck={false} />
              </div>
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="fp-pw">{t('lbl_new_password', lang)}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="fp-pw" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder={t('ph_new_password', lang)} value={newPw}
                  onChange={e => setNewPw(e.target.value)} autoComplete="new-password" disabled={loading} />
                <button type="button" className="login-eye-btn" onClick={() => setShowPw(v => !v)}>{showPw ? '🙈' : '👁'}</button>
              </div>
              <PasswordStrength password={newPw} lang={lang} />
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="fp-pw2">{t('lbl_confirm_pw', lang)}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="fp-pw2" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder={t('ph_repeat_password', lang)} value={confirmPw}
                  onChange={e => setConfirmPw(e.target.value)} autoComplete="new-password" disabled={loading} />
              </div>
              {confirmPw && newPw !== confirmPw && <span className="login-field-err">{t('pw_mismatch', lang)}</span>}
            </div>
            {error && <div className="login-error">⚠️ {error}</div>}
            <button className="login-btn" type="submit" disabled={loading || newPw !== confirmPw}>
              {loading ? <span className="login-spinner" /> : t('btn_set_password', lang)}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 5. REGISTER MODAL
// ─────────────────────────────────────────────────────────────────────────────

function RegisterModal({ onClose, lang }) {
  const [form, setForm]       = useState({ username: '', full_name: '', password: '', confirmPw: '', role: 'OPERATOR', invite_code: '' })
  const [showPw, setShowPw]   = useState(false)
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone]       = useState(false)

  const regRoles = [
    { role: 'OPERATOR',             icon: '📊', labelKey: 'role_op_label', color: '#38bdf8', bg: '#0369a114', border: '#0369a155' },
    { role: 'MAINTENANCE_ENGINEER', icon: '🔧', labelKey: 'role_eng_label', color: '#34d399', bg: '#06522214', border: '#06522255' },
  ]

  async function handleSubmit(e) {
    e.preventDefault(); setError('')
    if (!form.username.trim() || !form.full_name.trim() || !form.password || !form.invite_code.trim()) {
      setError(t('err_all_required', lang)); return
    }
    if (form.password.length < 12) { setError(t('err_pw_short', lang)); return }
    if (form.password !== form.confirmPw) { setError(t('pw_mismatch', lang)); return }
    setLoading(true)
    try {
      const r = await fetch(`${API}/auth/register`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: form.username.trim(), full_name: form.full_name.trim(), password: form.password, role: form.role, invite_code: form.invite_code.trim() }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || t('err_reg_failed', lang)); setLoading(false); return }
      setDone(true)
    } catch { setError(t('err_network', lang)) }
    setLoading(false)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">{t('modal_register_title', lang)}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        {done ? (
          <div className="modal-success">
            <span className="modal-success-icon">✅</span>
            <p>{t('acct_created', lang)}</p>
            <button className="login-btn" onClick={onClose} style={{ marginTop: 12 }}>{t('btn_sign_in_again', lang)}</button>
          </div>
        ) : (
          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <div className="reg-role-row">
              <span className="login-label">{t('lbl_role', lang)}</span>
              <div className="reg-role-pills">
                {regRoles.map(r => (
                  <button key={r.role} type="button"
                    className={`reg-role-pill${form.role === r.role ? ' reg-role-pill--active' : ''}`}
                    style={form.role === r.role ? { color: r.color, borderColor: r.border, background: r.bg } : {}}
                    onClick={() => setForm(f => ({ ...f, role: r.role }))}>
                    {r.icon} {t(r.labelKey, lang)}
                  </button>
                ))}
              </div>
            </div>
            <div className="login-form-row">
              <div className="login-field">
                <label className="login-label" htmlFor="rg-u">{t('lbl_username', lang)}</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">👤</span>
                  <input id="rg-u" className="login-input" type="text" placeholder={t('ph_choose_username', lang)}
                    value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    autoComplete="off" disabled={loading} spellCheck={false} />
                </div>
              </div>
              <div className="login-field">
                <label className="login-label" htmlFor="rg-n">{t('lbl_full_name', lang)}</label>
                <div className="login-input-wrap">
                  <span className="login-input-icon">🎭</span>
                  <input id="rg-n" className="login-input" type="text" placeholder={t('ph_your_name', lang)}
                    value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                    autoComplete="off" disabled={loading} />
                </div>
              </div>
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="rg-pw">
                {t('lbl_password', lang)} <span className="login-label-hint">({t('pw_min_hint', lang)})</span>
              </label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="rg-pw" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder={t('ph_strong_password', lang)} value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
                <button type="button" className="login-eye-btn" onClick={() => setShowPw(v => !v)}>{showPw ? '🙈' : '👁'}</button>
              </div>
              <PasswordStrength password={form.password} lang={lang} />
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="rg-pw2">{t('lbl_confirm_pw', lang)}</label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🔒</span>
                <input id="rg-pw2" className="login-input" type={showPw ? 'text' : 'password'}
                  placeholder={t('ph_repeat_password', lang)} value={form.confirmPw}
                  onChange={e => setForm(f => ({ ...f, confirmPw: e.target.value }))}
                  autoComplete="new-password" disabled={loading} />
              </div>
              {form.confirmPw && form.password !== form.confirmPw &&
                <span className="login-field-err">{t('pw_mismatch', lang)}</span>}
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="rg-inv">
                {t('lbl_invite_code', lang)} <span className="login-label-hint">({t('lbl_from_admin', lang) || 'from admin'})</span>
              </label>
              <div className="login-input-wrap">
                <span className="login-input-icon">🎫</span>
                <input id="rg-inv" className="login-input" type="text" placeholder={t('ph_invite_code', lang)}
                  value={form.invite_code} onChange={e => setForm(f => ({ ...f, invite_code: e.target.value }))}
                  autoComplete="off" disabled={loading} spellCheck={false} />
              </div>
            </div>
            {error && <div className="login-error">⚠️ {error}</div>}
            <button className="login-btn" type="submit" disabled={loading || form.password !== form.confirmPw}>
              {loading ? <span className="login-spinner" /> : t('btn_create_account', lang)}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 6. MAIN LOGIN PAGE
// ─────────────────────────────────────────────────────────────────────────────

export default function LoginPage({ onLogin }) {
  const lang = useLang()

  const [mode,       setMode]       = useState('operator')
  const [username,   setUsername]   = useState('')
  const [password,   setPassword]   = useState('')
  const [showPass,   setShowPass]   = useState(false)
  const [error,      setError]      = useState('')
  const [loading,    setLoading]    = useState(false)
  const [activeRole, setActiveRole] = useState('OPERATOR')
  const [modal,      setModal]      = useState(null)
  const [regEnabled, setRegEnabled] = useState(false)

  useEffect(() => {
    fetch(`${API}/auth/registration-status`)
      .then(r => r.json()).then(d => setRegEnabled(!!d.registration_enabled)).catch(() => {})
  }, [])

  function switchMode(m) {
    setMode(m); setUsername(''); setPassword(''); setError('')
    setActiveRole(m === 'operator' ? 'OPERATOR' : null)
  }

  function handleRoleClick(role) {
    setActiveRole(role); setError('')
    if (role === 'OPERATOR') setUsername('operator')
    else if (role === 'MAINTENANCE_ENGINEER') setUsername('engineer')
  }

  async function handleSubmit(e) {
    e.preventDefault(); setError('')
    if (!username.trim() || !password) { setError(t('login_error_empty', lang)); return }
    setLoading(true)
    try {
      const res = await fetch(`${API}/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        setError(d.detail || t('login_error_invalid', lang))
        setLoading(false); return
      }
      const data = await res.json()
      sessionStorage.setItem('iw_token', data.access_token)
      sessionStorage.setItem('iw_user', JSON.stringify({ username: data.username, full_name: data.full_name, role: data.role, user_id: data.user_id }))
      saveAccount(data); onLogin(data)
    } catch {
      if (username.trim().toLowerCase() === 'demo' && password === 'demo') {
        const fake = { access_token: 'demo-offline', username: 'demo', full_name: 'Demo User', role: 'OPERATOR', user_id: 0 }
        sessionStorage.setItem('iw_token', fake.access_token)
        sessionStorage.setItem('iw_user', JSON.stringify(fake))
        saveAccount(fake); onLogin(fake)
      } else {
        setError(t('login_error_offline', lang))
      }
    }
    setLoading(false)
  }

  const visibleRoles = [
    { role: 'OPERATOR',             icon: '📊', labelKey: 'role_op_label',  hintKey: 'role_op_hint',  color: '#38bdf8', bg: '#0369a114', border: '#0369a155', glow: '#0369a130' },
    { role: 'MAINTENANCE_ENGINEER', icon: '🔧', labelKey: 'role_eng_label', hintKey: 'role_eng_hint', color: '#34d399', bg: '#06522214', border: '#06522255', glow: '#06522230' },
  ]

  return (
    <div className="login-root">
      <div className="login-bg">
        <span className="orb orb-1" /><span className="orb orb-2" /><span className="orb orb-3" />
      </div>

      <div className="login-card">
        {/* Brand */}
        <div className="login-brand">
          <span className="login-eye">👁️</span>
          <div>
            <h1 className="login-title">{t('login_title', lang)}</h1>
            <p className="login-sub">{t('login_sub', lang)}</p>
          </div>
        </div>

        {/* Mode selector */}
        <div className="mode-selector">
          <button type="button" className={`mode-tab${mode === 'operator' ? ' mode-tab--active' : ''}`} onClick={() => switchMode('operator')}>
            <span className="mode-tab-icon">📊</span>
            <span className="mode-tab-text">
              <span className="mode-tab-title">{t('mode_operator_title', lang)}</span>
              <span className="mode-tab-sub">{t('mode_operator_sub', lang)}</span>
            </span>
          </button>
          <button type="button" className={`mode-tab mode-tab--admin${mode === 'admin' ? ' mode-tab--active-admin' : ''}`} onClick={() => switchMode('admin')}>
            <span className="mode-tab-icon">🛡️</span>
            <span className="mode-tab-text">
              <span className="mode-tab-title">{t('mode_admin_title', lang)}</span>
              <span className="mode-tab-sub">{t('mode_admin_sub', lang)}</span>
            </span>
          </button>
        </div>

        {/* Welcome */}
        <p className="login-welcome">
          {mode === 'admin' ? t('sign_in_admin', lang) : t('sign_in_workspace', lang)}
        </p>

        {/* Form */}
        <form className="login-form" onSubmit={handleSubmit} autoComplete="off" noValidate>
          <div className="login-field">
            <label className="login-label" htmlFor="iw-username">{t('lbl_username', lang)}</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">👤</span>
              <input id="iw-username" className="login-input" type="text"
                placeholder={t('ph_username', lang)} value={username}
                onChange={e => setUsername(e.target.value)} autoComplete="username" disabled={loading} spellCheck={false} />
            </div>
          </div>
          <div className="login-field">
            <label className="login-label" htmlFor="iw-password">{t('lbl_password', lang)}</label>
            <div className="login-input-wrap">
              <span className="login-input-icon">🔒</span>
              <input id="iw-password" className="login-input" type={showPass ? 'text' : 'password'}
                placeholder={t('ph_password', lang)} value={password}
                onChange={e => setPassword(e.target.value)} autoComplete="current-password" disabled={loading} />
              <button type="button" className="login-eye-btn"
                onClick={() => setShowPass(p => !p)}
                aria-label={showPass ? t('hide_password', lang) : t('show_password', lang)}>
                {showPass ? '🙈' : '👁'}
              </button>
            </div>
          </div>
          {error && <div className="login-error" role="alert">⚠️ {error}</div>}
          <button className={`login-btn${mode === 'admin' ? ' login-btn--admin-purple' : ''}`} type="submit" disabled={loading}>
            {loading ? <span className="login-spinner" /> : t('btn_sign_in', lang)}
          </button>
        </form>

        {/* Role buttons — operator mode only */}
        {mode === 'operator' && (
          <div className="login-roles">
            {visibleRoles.map(r => (
              <button key={r.role} type="button"
                className={`login-role-tag${activeRole === r.role ? ' login-role-tag--active' : ''}`}
                style={activeRole === r.role ? { color: r.color, background: r.bg, borderColor: r.border, boxShadow: `0 4px 18px ${r.glow}` } : {}}
                onClick={() => handleRoleClick(r.role)}
                title={`${t(r.labelKey, lang)} — ${t(r.hintKey, lang)}`}>
                <span className="login-role-tag-icon">{r.icon}</span>
                <span className="login-role-tag-label" style={activeRole === r.role ? { color: r.color } : { color: '#a0a8c0' }}>
                  {t(r.labelKey, lang)}
                </span>
                <span className="login-role-tag-hint">{t(r.hintKey, lang)}</span>
              </button>
            ))}
          </div>
        )}

        {/* Extra links */}
        <div className="login-extra-links">
          {mode === 'admin' && (
            <>
              <button type="button" className="login-extra-btn login-extra-btn--admin" onClick={() => setModal('admin-register')}>
                {t('register_as_admin', lang)}
              </button>
              <span className="login-extra-sep">•</span>
            </>
          )}
          <button type="button" className="login-extra-btn" onClick={() => setModal('forgot')}>
            {t('forgot_password', lang)}
          </button>
          {regEnabled && (
            <>
              <span className="login-extra-sep">•</span>
              <button type="button" className="login-extra-btn" onClick={() => setModal('register')}>
                {t('register_link', lang)}
              </button>
            </>
          )}
        </div>

        <p className="login-hint">
          {t('offline_hint_full', lang)} <strong>demo</strong> {t('offline_hint_pw', lang)} <strong>demo</strong>
        </p>
      </div>

      {modal === 'admin-register' && <AdminRegisterModal onClose={() => setModal(null)} onDone={() => setModal(null)} lang={lang} />}
      {modal === 'forgot'         && <ForgotModal        onClose={() => setModal(null)} lang={lang} />}
      {modal === 'register'       && <RegisterModal      onClose={() => setModal(null)} lang={lang} />}
    </div>
  )
}
