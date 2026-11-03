
import { useState, useEffect, useCallback } from 'react'
import { t } from '../i18n'
import useLang from '../useLang'
import './UserManagement.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const ROLE_COLORS = {
  ADMIN:               { bg: '#7c3aed22', border: '#7c3aed60', text: '#a78bfa' },
  OPERATOR:            { bg: '#0369a122', border: '#0369a160', text: '#38bdf8' },
  MAINTENANCE_ENGINEER:{ bg: '#06522222', border: '#06522260', text: '#34d399' },
}

const ROLE_LABELS = {
  ADMIN:               'Admin',
  OPERATOR:            'Operator',
  MAINTENANCE_ENGINEER:'Maintenance Engineer',
}

function RoleBadge({ role }) {
  const c = ROLE_COLORS[role] || { bg: '#33333322', border: '#55555560', text: '#aaa' }
  return (
    <span className="um-role-badge" style={{ background: c.bg, borderColor: c.border, color: c.text }}>
      {ROLE_LABELS[role] || role}
    </span>
  )
}

function StatusDot({ active }) {
  return (
    <span
      className={`um-status-dot${active ? ' um-status-dot--active' : ' um-status-dot--inactive'}`}
      title={active ? t('um_status_active', lang) : t('um_status_inactive', lang)}
    />
  )
}

// ==================================================
// ADMIN INVITE PANEL
// Shown at the top of the admin group section.
// Lets primary admin generate a one-time invite token
// for a co-admin and see / revoke pending invites.
// ==================================================

function AdminInvitePanel({ token }) {
  const lang = useLang()
  const [inviteToken,   setInviteToken]   = useState('')
  const [pendingList,   setPendingList]   = useState([])
  const [generating,    setGenerating]    = useState(false)
  const [revoking,      setRevoking]      = useState(false)
  const [copied,        setCopied]        = useState(false)
  const [error,         setError]         = useState('')
  const [open,          setOpen]          = useState(false)

  const loadPending = useCallback(async () => {
    try {
      const r = await fetch(`${API}/auth/admin-invite`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (r.ok) {
        const d = await r.json()
        setPendingList(d.pending_invites || [])
      }
    } catch {}
  }, [token])

  useEffect(() => { if (open) loadPending() }, [open, loadPending])

  async function generateInvite() {
    setError('')
    setInviteToken('')
    setGenerating(true)
    try {
      const r = await fetch(`${API}/auth/admin-invite`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || t('um_err_invite', lang)); setGenerating(false); return }
      setInviteToken(d.admin_invite_token)
      loadPending()
    } catch { setError(t('um_err_network', lang)) }
    setGenerating(false)
  }

  async function revokeAll() {
    setRevoking(true)
    try {
      const r = await fetch(`${API}/auth/admin-invite`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (r.ok) { setPendingList([]); setInviteToken('') }
    } catch {}
    setRevoking(false)
  }

  function copy() {
    if (!inviteToken) return
    navigator.clipboard?.writeText(inviteToken).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="um-invite-panel">
      <button
        className="um-invite-toggle"
        onClick={() => setOpen(o => !o)}
        type="button"
      >
        <span className="um-invite-toggle-icon">&#x1F511;</span>
        <span className="um-invite-toggle-text">
          Co-Admin Invite System
          {pendingList.length > 0 && !open && (
            <span className="um-invite-badge">{pendingList.length} pending</span>
          )}
        </span>
        <span className="um-invite-toggle-caret">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="um-invite-body">
          <p className="um-invite-desc">
            Generate a single-use, 24-hour token to invite a new co-admin.
            Share it <strong>securely</strong> (in person or via a private channel).
            The person uses it on the login page under <em>Admin Mode → Register with Invite</em>.
          </p>

          {/* Generate button */}
          <div className="um-invite-actions">
            <button
              className="um-btn um-btn--primary um-btn--sm"
              onClick={generateInvite}
              disabled={generating}
            >
              {generating ? <span className="um-spinner" /> : '&#x2795; Generate Admin Invite Token'}
            </button>

            {pendingList.length > 0 && (
              <button
                className="um-btn um-btn--danger-ghost um-btn--sm"
                onClick={revokeAll}
                disabled={revoking}
              >
                {revoking ? <span className="um-spinner" /> : '&#x1F6AB; Revoke All Pending'}
              </button>
            )}
          </div>

          {error && <div className="um-alert-error um-alert-error--sm">&#x26A0; {error}</div>}

          {/* Generated token display */}
          {inviteToken && (
            <div className="um-token-box">
              <div className="um-token-header">
                <span className="um-token-label">&#x1F511; One-Time Admin Invite Token</span>
                <span className="um-token-expiry">Expires in 24 hours &bull; single use</span>
              </div>
              <div className="um-token-value-row">
                <code className="um-token-value">{inviteToken}</code>
                <button className="um-btn um-btn--sm um-btn--ghost" onClick={copy}>
                  {copied ? '&#x2705; Copied' : '&#x1F4CB; Copy'}
                </button>
              </div>
              <p className="um-token-instruction">
                &#x26A0;&#xFE0F; This token is shown <strong>only once</strong>. Copy and share it immediately.
                The recipient opens the login page, chooses <strong>Admin Mode</strong>, then clicks
                <strong> Register as Admin (Invite Required)</strong>.
              </p>
            </div>
          )}

          {/* Pending invites list */}
          {pendingList.length > 0 && (
            <div className="um-pending-list">
              <p className="um-pending-title">Pending Invites ({pendingList.length})</p>
              {pendingList.map((inv, i) => (
                <div key={i} className="um-pending-item">
                  <span className="um-pending-by">Created by: <strong>{inv.created_by}</strong></span>
                  <span className="um-pending-exp">Expires in {inv.expires_in_minutes} min</span>
                  <span className="um-pending-tok">Token: <code>{inv.token_preview}</code></span>
                </div>
              ))}
            </div>
          )}

          {pendingList.length === 0 && !inviteToken && (
            <p className="um-invite-empty">No pending invites.</p>
          )}
        </div>
      )}
    </div>
  )
}

// ==================================================
// PROMOTE / DEMOTE MODAL
// Lets admin promote an Operator/Engineer to Admin
// (requires them to generate an admin invite token
//  internally and consume it automatically), or
// demote an Admin to Operator.
// ==================================================

function RoleChangeModal({ user, token, currentUser, onChanged, onClose }) {
  const lang = useLang()
  const isAdmin    = user.role === 'ADMIN'
  const targetRole = isAdmin ? 'OPERATOR' : 'ADMIN'
  const [confirm,  setConfirm]  = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')

  async function handleChange() {
    setError('')
    setLoading(true)
    try {
      // Use the existing create-user pattern: update role via admin endpoint
      // We PATCH the role — reuse /auth/users/{id}/role (added below in backend)
      const r = await fetch(`${API}/auth/users/${user.id}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ role: targetRole }),
      })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || 'Role change failed.'); setLoading(false); return }
      onChanged()
      onClose()
    } catch { setError(t('um_err_network', lang)) }
    setLoading(false)
  }

  return (
    <div className="um-modal-overlay" onClick={onClose}>
      <div className="um-modal" onClick={e => e.stopPropagation()} role="dialog">
        <div className="um-modal-header">
          <h3>
            {isAdmin ? '&#x2B07; Demote to Operator' : '&#x2B06; Promote to Admin'}
          </h3>
          <button className="um-modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="um-form" style={{ padding: '20px' }}>
          {!isAdmin ? (
            <div className="um-role-change-warn">
              <span className="um-role-change-icon">&#x1F6E1;&#xFE0F;</span>
              <div>
                <strong>You are about to grant Admin access to:</strong>
                <p className="um-role-change-user">{user.full_name} (@{user.username})</p>
                <p>
                  This person will have <strong>full system access</strong> — they can manage all users,
                  generate admin invite tokens, and access all endpoints.
                  Only proceed if you explicitly authorise this person as a co-admin.
                </p>
              </div>
            </div>
          ) : (
            <div className="um-role-change-warn um-role-change-warn--neutral">
              <span className="um-role-change-icon">&#x2B07;&#xFE0F;</span>
              <div>
                <strong>Demote to Operator:</strong>
                <p className="um-role-change-user">{user.full_name} (@{user.username})</p>
                <p>
                  This will remove admin privileges. They will retain their account
                  as a standard Operator. This action can be reversed.
                </p>
              </div>
            </div>
          )}

          <label className="um-confirm-check">
            <input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />
            &nbsp;I confirm I want to {isAdmin ? 'demote' : 'promote'} <strong>{user.username}</strong>
          </label>

          {error && <div className="um-error">&#x26A0; {error}</div>}

          <div className="um-form-actions" style={{ marginTop: 16 }}>
            <button className="um-btn um-btn--ghost" onClick={onClose} disabled={loading}>Cancel</button>
            <button
              className={`um-btn ${isAdmin ? 'um-btn--warn' : 'um-btn--primary'}`}
              onClick={handleChange}
              disabled={!confirm || loading}
            >
              {loading ? <span className="um-spinner" /> : (isAdmin ? 'Demote' : 'Promote to Admin')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ==================================================
// CREATE USER MODAL
// ==================================================

function CreateUserModal({ token, onCreated, onClose }) {
  const lang = useLang()
  const [form,    setForm]    = useState({ username: '', full_name: '', password: '', role: 'OPERATOR' })
  const [error,   setError]   = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.username.trim() || !form.full_name.trim() || !form.password) {
      setError('All fields are required.')
      return
    }
    if (form.password.length < 12) {
      setError('Password must be at least 12 characters.')
      return
    }
    setLoading(true)
    try {
      const res = await fetch(`${API}/auth/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || t('um_err_create', lang)); setLoading(false); return }
      setSuccess(true)
      setTimeout(() => { onCreated(); onClose() }, 1200)
    } catch { setError(t('um_err_network', lang)) }
    setLoading(false)
  }

  return (
    <div className="um-modal-overlay" onClick={onClose}>
      <div className="um-modal" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="um-modal-header">
          <h3>&#x2795; Create New User</h3>
          <button className="um-modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>

        {success ? (
          <div className="um-modal-success">&#x2705; User created successfully!</div>
        ) : (
          <form className="um-form" onSubmit={handleSubmit} noValidate>
            <label className="um-label">
              Username
              <input className="um-input" type="text" value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                placeholder="e.g. john_doe" autoComplete="off" disabled={loading} />
            </label>
            <label className="um-label">
              Full Name
              <input className="um-input" type="text" value={form.full_name}
                onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                placeholder="e.g. John Doe" autoComplete="off" disabled={loading} />
            </label>
            <label className="um-label">
              Password <span className="um-hint">(min 12 characters)</span>
              <input className="um-input" type="password" value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                placeholder="Strong password" autoComplete="new-password" disabled={loading} />
            </label>
            <label className="um-label">
              Role
              <select className="um-select" value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                disabled={loading}>
                <option value="OPERATOR">Operator</option>
                <option value="MAINTENANCE_ENGINEER">Maintenance Engineer</option>
                <option value="ADMIN">Admin</option>
              </select>
            </label>
            {error && <div className="um-error">&#x26A0; {error}</div>}
            <div className="um-form-actions">
              <button type="button" className="um-btn um-btn--ghost" onClick={onClose} disabled={loading}>Cancel</button>
              <button type="submit" className="um-btn um-btn--primary" disabled={loading}>
                {loading ? <span className="um-spinner" /> : 'Create User'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ==================================================
// MAIN USER MANAGEMENT PAGE
// ==================================================

export default function UserManagement({ token, currentUser }) {
  const lang = useLang()
  const [users,        setUsers]        = useState([])
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState('')
  const [showCreate,   setShowCreate]   = useState(false)
  const [roleModal,    setRoleModal]    = useState(null)   // user object to promote/demote
  const [actionLoading,setActionLoading]= useState({})
  const [confirmDelete,setConfirmDelete]= useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API}/auth/users`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        setError(d.detail || `Server error ${res.status}`)
        setLoading(false); return
      }
      const data = await res.json()
      setUsers(data.users || [])
    } catch {
      setError(t('um_err_network', lang) + ' — cannot reach the server.')
    }
    setLoading(false)
  }, [token])

  useEffect(() => { load() }, [load])

  async function toggleActive(userId, currentActive) {
    setActionLoading(prev => ({ ...prev, [userId]: true }))
    try {
      const res = await fetch(`${API}/auth/users/${userId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ is_active: !currentActive }),
      })
      if (res.ok) {
        setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: !currentActive } : u))
      } else {
        const d = await res.json().catch(() => ({}))
        alert(d.detail || t('um_err_status', lang))
      }
    } catch { alert(t('um_err_network', lang)) }
    setActionLoading(prev => ({ ...prev, [userId]: false }))
  }

  async function deleteUser(userId) {
    setActionLoading(prev => ({ ...prev, [userId]: true }))
    setConfirmDelete(null)
    try {
      const res = await fetch(`${API}/auth/users/${userId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        setUsers(prev => prev.filter(u => u.id !== userId))
      } else {
        const d = await res.json().catch(() => ({}))
        alert(d.detail || t('um_err_delete', lang))
      }
    } catch { alert(t('um_err_network', lang)) }
    setActionLoading(prev => ({ ...prev, [userId]: false }))
  }

  const roleGroups = {
    ADMIN:                users.filter(u => u.role === 'ADMIN'),
    OPERATOR:             users.filter(u => u.role === 'OPERATOR'),
    MAINTENANCE_ENGINEER: users.filter(u => u.role === 'MAINTENANCE_ENGINEER'),
  }

  return (
    <main className="um-page">
      {/* Header */}
      <div className="um-page-header">
        <div>
          <div className="um-breadcrumb">INTELLIWATCH / ADMIN</div>
          <h1 className="um-page-title">&#x1F465; User Management</h1>
          <p className="um-page-sub">
            Manage all accounts. Promote users to admin, generate co-admin invite tokens,
            create, activate/deactivate, and delete accounts.
          </p>
        </div>
        <button className="um-btn um-btn--primary" onClick={() => setShowCreate(true)}>
          &#x2795; New User
        </button>
      </div>

      {/* Stats row */}
      <div className="um-stats-row">
        {Object.entries(roleGroups).map(([role, list]) => (
          <div key={role} className="um-stat-card" style={{ borderColor: ROLE_COLORS[role]?.border }}>
            <span className="um-stat-num" style={{ color: ROLE_COLORS[role]?.text }}>{list.length}</span>
            <span className="um-stat-label">{ROLE_LABELS[role]}</span>
            <span className="um-stat-active">{list.filter(u => u.is_active).length} active</span>
          </div>
        ))}
        <div className="um-stat-card">
          <span className="um-stat-num" style={{ color: '#38bdf8' }}>{users.length}</span>
          <span className="um-stat-label">{t('um_total', lang)}</span>
          <span className="um-stat-active">{users.filter(u => u.is_active).length} {t('um_active', lang)}</span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="um-alert-error">
          &#x26A0; {error}
          <button className="um-btn um-btn--ghost um-btn--sm" onClick={load} style={{ marginLeft: 12 }}>Retry</button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="um-loading">
          <span className="um-spinner um-spinner--lg" />
          <span>{t('um_loading', lang)}</span>
        </div>
      )}

      {/* Tables grouped by role */}
      {!loading && !error && (
        <>
          {Object.entries(roleGroups).map(([role, list]) => (
            <section key={role} className="um-group">
              <div className="um-group-header">
                <RoleBadge role={role} />
                <span className="um-group-count">{list.length} account{list.length !== 1 ? 's' : ''}</span>
              </div>

              {/* Admin invite panel — only shown in the ADMIN group */}
              {role === 'ADMIN' && <AdminInvitePanel token={token} />}

              {list.length === 0 ? (
                <p className="um-empty">No {ROLE_LABELS[role]} accounts yet.</p>
              ) : (
                <div className="um-table-wrap">
                  <table className="um-table">
                    <thead>
                      <tr>
                        <th>{t('um_th_status', lang)}</th>
                        <th>{t('um_th_username', lang)}</th>
                        <th>{t('um_th_name', lang)}</th>
                        <th>{t('um_th_role', lang)}</th>
                        <th>{t('um_th_created', lang)}</th>
                        <th>{t('um_th_login', lang)}</th>
                        <th>{t('um_th_actions', lang)}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.map(u => {
                        const isSelf    = u.id === currentUser?.id
                        const isLoading = actionLoading[u.id]
                        return (
                          <tr key={u.id} className={!u.is_active ? 'um-row--inactive' : ''}>
                            <td><StatusDot active={u.is_active} /></td>
                            <td className="um-username">
                              {u.username}
                              {isSelf && <span className="um-you-tag">you</span>}
                            </td>
                            <td>{u.full_name}</td>
                            <td><RoleBadge role={u.role} /></td>
                            <td className="um-date">{u.created_at?.slice(0, 10) || '\u2014'}</td>
                            <td className="um-date">{u.last_login ? u.last_login.slice(0, 19).replace('T', ' ') : 'Never'}</td>
                            <td className="um-actions">
                              {/* Activate / Deactivate */}
                              <button
                                className={`um-btn um-btn--sm${u.is_active ? ' um-btn--warn' : ' um-btn--success'}`}
                                onClick={() => toggleActive(u.id, u.is_active)}
                                disabled={isLoading || isSelf}
                                title={isSelf ? t('um_cant_self', lang) : u.is_active ? t('um_deactivate', lang) : t('um_activate', lang)}
                              >
                                {isLoading ? <span className="um-spinner" /> : u.is_active ? t('um_deactivate', lang) : t('um_activate', lang)}
                              </button>

                              {/* Promote to Admin / Demote — not self, not already the only admin */}
                              {!isSelf && (
                                <button
                                  className={`um-btn um-btn--sm ${u.role === 'ADMIN' ? 'um-btn--warn' : 'um-btn--promote'}`}
                                  onClick={() => setRoleModal(u)}
                                  disabled={isLoading}
                                  title={u.role === 'ADMIN' ? 'Demote from Admin' : 'Promote to Admin'}
                                >
                                  {u.role === 'ADMIN' ? '\u2B07 Demote' : '\uD83D\uDEE1 Promote'}
                                </button>
                              )}

                              {/* Delete — only non-admin, non-self */}
                              {u.role !== 'ADMIN' && (
                                confirmDelete === u.id ? (
                                  <span className="um-confirm-row">
                                    <span className="um-confirm-text">Sure?</span>
                                    <button className="um-btn um-btn--sm um-btn--danger" onClick={() => deleteUser(u.id)} disabled={isLoading}>
                                      {isLoading ? <span className="um-spinner" /> : 'Delete'}
                                    </button>
                                    <button className="um-btn um-btn--sm um-btn--ghost" onClick={() => setConfirmDelete(null)}>Cancel</button>
                                  </span>
                                ) : (
                                  <button
                                    className="um-btn um-btn--sm um-btn--danger-ghost"
                                    onClick={() => setConfirmDelete(u.id)}
                                    disabled={isLoading}
                                    title={t('um_delete', lang)}
                                  >
                                    &#x1F5D1; Delete
                                  </button>
                                )
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </>
      )}

      {/* Modals */}
      {showCreate && (
        <CreateUserModal token={token} onCreated={load} onClose={() => setShowCreate(false)} />
      )}

      {roleModal && (
        <RoleChangeModal
          user={roleModal}
          token={token}
          currentUser={currentUser}
          onChanged={load}
          onClose={() => setRoleModal(null)}
        />
      )}
    </main>
  )
}
