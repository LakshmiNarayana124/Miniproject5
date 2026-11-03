
import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { SENSORS } from '../sensors'
import { t, setLang, SUPPORTED_LANGUAGES } from '../i18n'
import useLang from '../useLang'

// ==================================================
// NAVBAR — single clean horizontal row
// Logo | Nav links | System status | Lang | Theme | User
// ==================================================

// Map status strings to i18n keys
const STATUS_KEYS = {
  normal:         'status_normal',
  warning:        'status_warning',
  critical:       'status_critical',
  uncertain:      'status_uncertain',
  scanning:       'status_scanning',
  ready:          'status_ready',
  nil:            'status_no_data',
  'awaiting-iot': 'status_awaiting',
  'no-recordings':'status_no_data',
}

export default function Navbar({
  systemStatus,
  tick,
  isLightMode,
  onToggleTheme,
  user,
  onLogout,
}) {
  const isAdmin = user?.role === 'ADMIN'
  const lang = useLang()
  const [showLang, setShowLang] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const currentLang = SUPPORTED_LANGUAGES.find(l => l.code === lang) || SUPPORTED_LANGUAGES[0]

  const statusKey = STATUS_KEYS[systemStatus] || 'status_awaiting'

  return (
    <header className="navbar">

      {/* ── Brand ── */}
      <NavLink to="/" className="logo" style={{ textDecoration: 'none', flexShrink: 0 }}>
        <span className="logo-eye">👁️</span>
        <span className="logo-text">IntelliWatch</span>
      </NavLink>

      {/* ── Hamburger toggle (mobile only) ── */}
      <button
        className="hamburger"
        onClick={() => { setMenuOpen(o => !o); setShowLang(false) }}
        aria-label="Toggle navigation menu"
        aria-expanded={menuOpen}
      >
        {menuOpen ? '✕' : '☰'}
      </button>

      {/* ── Nav links (center) ── */}
      <nav className={`nav-links${menuOpen ? ' nav-links-open' : ''}`} aria-label="Main navigation">

        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' nav-active' : ''}`} onClick={() => setMenuOpen(false)}>
          🏠 {t('nav_home', lang)}
        </NavLink>

        <NavLink to="/vibration" className={({ isActive }) => `nav-link${isActive ? ' nav-active' : ''}`} onClick={() => setMenuOpen(false)}>
          {SENSORS.vibration.icon} {t('nav_vibration', lang)}
        </NavLink>

        <NavLink to="/temperature" className={({ isActive }) => `nav-link${isActive ? ' nav-active' : ''}`} onClick={() => setMenuOpen(false)}>
          {SENSORS.temperature.icon} {t('nav_temperature', lang)}
        </NavLink>

        <NavLink to="/current" className={({ isActive }) => `nav-link${isActive ? ' nav-active' : ''}`} onClick={() => setMenuOpen(false)}>
          {SENSORS.current.icon} {t('nav_current', lang)}
        </NavLink>

        <NavLink to="/explorer" className={({ isActive }) => `nav-link${isActive ? ' nav-active' : ''}`} onClick={() => setMenuOpen(false)}>
          🧩 {t('nav_explorer', lang)}
        </NavLink>

        <NavLink to="/about" className={({ isActive }) => `nav-link${isActive ? ' nav-active' : ''}`} onClick={() => setMenuOpen(false)}>
          💡 {t('nav_about', lang)}
        </NavLink>

        {isAdmin && (
          <NavLink to="/admin/users" className={({ isActive }) => `nav-link nav-link--admin${isActive ? ' nav-active' : ''}`} onClick={() => setMenuOpen(false)}>
            👥 {t('nav_users', lang)}
          </NavLink>
        )}

      </nav>

      {/* ── Right controls ── */}
      <div className="navbar-right">

        {/* System status pill */}
        <div
          className={`sys-status sys-${systemStatus}`}
          title={`System: ${t(statusKey, lang)}`}
          aria-label={`System status: ${t(statusKey, lang)}`}
        >
          <span className="pulse-dot" />
          <span className="sys-label">{t(statusKey, lang)}</span>
        </div>

        {/* Tick — only show when IoT is active */}
        {tick > 0 && (
          <span className="tick-counter" aria-label={`Tick ${tick}`}>#{tick}</span>
        )}

        {/* Language switcher */}
        <div className="navbar-lang-wrap">
          <button
            className="navbar-lang-btn"
            onClick={() => { setShowLang(s => !s); setMenuOpen(false) }}
            title="Change language"
            aria-label="Select language"
          >
            {currentLang.flag} <span>{currentLang.label}</span>
            <span className="lang-caret">{showLang ? '▲' : '▼'}</span>
          </button>

          {showLang && (
            <div className="navbar-lang-dropdown">
              {SUPPORTED_LANGUAGES.map(l => (
                <button
                  key={l.code}
                  className={`navbar-lang-opt${l.code === lang ? ' lang-opt-active' : ''}`}
                  onClick={() => { setLang(l.code); setShowLang(false) }}
                >
                  <span>{l.flag}</span>
                  <span className="nlopt-code">{l.label}</span>
                  <span className="nlopt-name">{l.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Theme toggle */}
        <button
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={isLightMode ? t('theme_switch_dark', lang) : t('theme_switch_light', lang)}
          title={isLightMode ? t('theme_dark', lang) : t('theme_light', lang)}
        >
          {isLightMode ? '🌑' : '☀️'}
        </button>

        {/* User info + logout */}
        {user && (
          <div className="navbar-user">
            <span className="user-name" title={user.role}>
              {user.full_name || user.username}
            </span>
            <button
              className="logout-btn"
              onClick={onLogout}
              title={t('sign_out', lang)}
              aria-label={t('sign_out', lang)}
            >
              {t('logout_btn', lang)}
            </button>
          </div>
        )}

      </div>
    </header>
  )
}
