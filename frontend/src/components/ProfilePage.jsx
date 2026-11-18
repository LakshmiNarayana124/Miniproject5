import { useState } from 'react'
import './ProfilePage.css'

const API = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '')

const TZ_LABELS = {
  'Asia/Kolkata': 'India (IST)', 'Asia/Dubai': 'Dubai (GST)', 'Asia/Shanghai': 'China (CST)',
  'Asia/Singapore': 'Singapore', 'Asia/Tokyo': 'Japan (JST)', 'Asia/Karachi': 'Pakistan (PKT)',
  'Asia/Dhaka': 'Bangladesh', 'Asia/Colombo': 'Sri Lanka', 'Asia/Kathmandu': 'Nepal',
  'Europe/London': 'UK (GMT)', 'Europe/Berlin': 'Central Europe', 'Europe/Moscow': 'Moscow',
  'America/New_York': 'US Eastern', 'America/Chicago': 'US Central',
  'America/Los_Angeles': 'US Pacific', 'America/Sao_Paulo': 'Brazil',
  'Australia/Sydney': 'Sydney', 'Pacific/Auckland': 'New Zealand', UTC: 'UTC',
}

const ROLE_LABELS = {
  ADMIN: '🛡️ Administrator',
  OPERATOR: '📊 Operator',
  MAINTENANCE_ENGINEER: '🔧 Maintenance Engineer',
}

export default function ProfilePage({ user, token, onLogout }) {
  const [showPw, setShowPw] = useState(false)
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const roleLabel = ROLE_LABELS[user?.role] || user?.role || 'User'
  const initial = user?.full_name?.charAt(0)?.toUpperCase() || 'U'
  const isDemo = user?.is_demo_session

  async function handleChangePassword(e) {
    e.preventDefault()
    setErr(''); setMsg('')
    if (newPw.length < 12) { setErr('New password must be at least 12 characters.'); return }
    if (newPw !== confirmPw) { setErr('Passwords do not match.'); return }
    setLoading(true)
    try {
      const r = await fetch(`${API}/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) { setErr(d.detail || d.message || `Failed (HTTP ${r.status})`) }
      else { setMsg(d.message || 'Password changed.'); setOldPw(''); setNewPw(''); setConfirmPw(''); setShowPw(false) }
    } catch { setErr('Unable to connect to server.') }
    finally { setLoading(false) }
  }

  function Row({ label, children }) {
    return (
      <div className="pp-row">
        <span className="pp-label">{label}</span>
        <span className="pp-val">{children}</span>
      </div>
    )
  }

  return (
    <main className="main">
      <div className="pp-wrap">

        {/* ── Hero header ── */}
        <div className="pp-hero">
          <div className="pp-avatar">{initial}</div>
          <div className="pp-hero-text">
            <h1 className="pp-name">{user?.full_name || 'User'}</h1>
            <span className="pp-role">{roleLabel}</span>
          </div>
          <span className={`pp-mode ${isDemo ? 'pp-mode--demo' : 'pp-mode--live'}`}>
            {isDemo ? '🧪 Demo' : '🟢 Live'}
          </span>
        </div>

        {/* ── Account ── */}
        <h3 className="pp-section">Account</h3>
        <Row label="Username">{user?.username || '—'}</Row>
        <Row label="Role">{roleLabel}</Row>
        <Row label="Account Type">{user?.account_role || user?.role || '—'}</Row>
        <Row label="User ID">#{user?.user_id ?? '—'}</Row>

        {/* ── Session ── */}
        <h3 className="pp-section">Session</h3>
        <Row label="Access">
          {user?.is_restricted_session
            ? <span className="pp-tag pp-tag--warn">🔒 Restricted</span>
            : <span className="pp-tag pp-tag--ok">🔓 Full Access</span>}
        </Row>
        <Row label="Time Zone">{TZ_LABELS[user?.timezone] || user?.timezone || 'India (IST)'}</Row>

        {/* ── Security ── */}
        {!isDemo && token && (
          <>
            <h3 className="pp-section">Security</h3>
            {!showPw ? (
              <button className="pp-link" onClick={() => setShowPw(true)}>🔒 Change Password →</button>
            ) : (
              <form className="pp-pw-form" onSubmit={handleChangePassword}>
                <input className="pp-input" type="password" placeholder="Current password"
                  value={oldPw} onChange={e => setOldPw(e.target.value)} disabled={loading} />
                <input className="pp-input" type="password" placeholder="New password (min 12 chars)"
                  value={newPw} onChange={e => setNewPw(e.target.value)} disabled={loading} />
                <input className="pp-input" type="password" placeholder="Confirm new password"
                  value={confirmPw} onChange={e => setConfirmPw(e.target.value)} disabled={loading} />
                {err && <p className="pp-err">{err}</p>}
                {msg && <p className="pp-ok">{msg}</p>}
                <div className="pp-pw-btns">
                  <button type="submit" className="pp-btn pp-btn--primary" disabled={loading || !oldPw || !newPw || newPw !== confirmPw}>
                    {loading ? '...' : 'Save'}
                  </button>
                  <button type="button" className="pp-btn" onClick={() => { setShowPw(false); setErr(''); setMsg(''); setOldPw(''); setNewPw(''); setConfirmPw('') }}>
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </>
        )}

        {/* ── Logout ── */}
        <div className="pp-logout">
          <button className="pp-btn pp-btn--danger" onClick={onLogout}>🚪 Sign Out</button>
        </div>

      </div>
    </main>
  )
}
