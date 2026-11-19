
import { useState } from 'react'
import { NavLink } from 'react-router-dom'

import { SENSORS } from '../sensors'
import { t, setLang, SUPPORTED_LANGUAGES } from '../i18n'
import useLang from '../useLang'

// ==================================================
// NAVBAR
// Logo | Navigation | Operating Mode | Controls
// ==================================================

// Map status strings to i18n keys.
const STATUS_KEYS = {
  normal: 'status_normal',
  warning: 'status_warning',
  critical: 'status_critical',
  uncertain: 'status_uncertain',
  scanning: 'status_scanning',
  ready: 'status_ready',
  nil: 'status_no_data',
  'awaiting-iot': 'status_awaiting',
  'no-recordings': 'status_no_data',
}

// ==================================================
// NAVBAR COMPONENT
// ==================================================

export default function Navbar({
  systemStatus,
  tick,
  isLightMode,
  onToggleTheme,
  user,
  onLogout,

  // Operating mode.
  operatingMode = 'iot',
  onOperatingModeChange,
  isDemoSession = false,
}) {
  const isAdmin = user?.role === 'ADMIN'

  const lang = useLang()

  const [showLang, setShowLang] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const currentLang =
    SUPPORTED_LANGUAGES.find(
      language => language.code === lang
    ) || SUPPORTED_LANGUAGES[0]

  const statusKey =
    STATUS_KEYS[systemStatus] || 'status_awaiting'

  const navLinkClass = ({ isActive }) =>
    `nav-link${isActive ? ' nav-active' : ''}`

  // ==================================================
  // MENU CONTROLS
  // ==================================================

  function closeMobileMenu() {
    setMenuOpen(false)
  }

  function toggleMobileMenu() {
    setMenuOpen(open => !open)
    setShowLang(false)
  }

  function toggleLanguageMenu() {
    setShowLang(show => !show)
    setMenuOpen(false)
  }

  // ==================================================
  // OPERATING MODE SELECTION
  //
  // IoT is the default.
  // Simulation requires explicit selection.
  // Offline Demo remains a separate session.
  // ==================================================

  function selectOperatingMode(mode) {
    if (isDemoSession) return

    if (
      mode !== 'iot' &&
      mode !== 'simulation'
    ) {
      return
    }

    if (mode === operatingMode) return

    onOperatingModeChange?.(mode)

    setShowLang(false)
    closeMobileMenu()
  }

  // ==================================================
  // RENDER
  // ==================================================

  return (
    <header className="navbar">

      {/* Brand */}

      <NavLink
        to="/"
        className="logo"
        style={{
          textDecoration: 'none',
          flexShrink: 0,
        }}
        onClick={closeMobileMenu}
      >
        <span className="logo-eye">
          👁️
        </span>

        <span className="logo-text">
          IntelliWatch
        </span>
      </NavLink>

      {/* Hamburger toggle — mobile only */}

      <button
        type="button"
        className="hamburger"
        onClick={toggleMobileMenu}
        aria-label="Toggle navigation menu"
        aria-expanded={menuOpen}
        aria-controls="intelliwatch-main-navigation"
      >
        {menuOpen ? '✕' : '☰'}
      </button>

      {/* Navigation links */}

      <nav
        id="intelliwatch-main-navigation"
        className={`nav-links${menuOpen ? ' nav-links-open' : ''}`}
        aria-label="Main navigation"
      >

        <NavLink
          to="/"
          end
          className={navLinkClass}
          onClick={closeMobileMenu}
        >
          🏠 {t('nav_home', lang)}
        </NavLink>

        <NavLink
          to="/vibration"
          className={navLinkClass}
          onClick={closeMobileMenu}
        >
          {SENSORS.vibration.icon} {t('nav_vibration', lang)}
        </NavLink>

        <NavLink
          to="/temperature"
          className={navLinkClass}
          onClick={closeMobileMenu}
        >
          {SENSORS.temperature.icon} {t('nav_temperature', lang)}
        </NavLink>

        <NavLink
          to="/current"
          className={navLinkClass}
          onClick={closeMobileMenu}
        >
          {SENSORS.current.icon} {t('nav_current', lang)}
        </NavLink>

        <NavLink
          to="/explorer"
          className={navLinkClass}
          onClick={closeMobileMenu}
        >
          🧩 {t('nav_explorer', lang)}
        </NavLink>

        {/* Equipment Vision */}

        <NavLink
          to="/vision"
          className={navLinkClass}
          onClick={closeMobileMenu}
        >
          📷 {t('nav_vision', lang)}
        </NavLink>

        <NavLink
          to="/about"
          className={navLinkClass}
          onClick={closeMobileMenu}
        >
          💡 {t('nav_about', lang)}
        </NavLink>

        {/* Admin navigation */}

        {isAdmin && (
          <NavLink
            to="/admin/users"
            className={({ isActive }) =>
              `nav-link nav-link--admin${
                isActive ? ' nav-active' : ''
              }`
            }
            onClick={closeMobileMenu}
          >
            👥 {t('nav_users', lang)}
          </NavLink>
        )}

      </nav>

      {/* ==================================================
          RIGHT CONTROLS
      ================================================== */}

      <div className="navbar-right">

        {/* Operating mode selector */}

        <div
          className="navbar-mode-wrap"
          role="group"
          aria-label="Operating mode"
        >

          {isDemoSession ? (

            <span
              className="navbar-mode-demo"
              title="Offline demonstration session"
            >
              🧪 Offline Demo
            </span>

          ) : (

            <>
              <button
                type="button"
                className={`navbar-mode-btn navbar-mode-iot${
                  operatingMode === 'iot'
                    ? ' navbar-mode-active'
                    : ''
                }`}
                onClick={() => selectOperatingMode('iot')}
                aria-pressed={operatingMode === 'iot'}
                title="Use IoT / Hardware data"
              >
                🔌 IoT
              </button>

              <button
                type="button"
                className={`navbar-mode-btn navbar-mode-simulation${
                  operatingMode === 'simulation'
                    ? ' navbar-mode-active'
                    : ''
                }`}
                onClick={() => selectOperatingMode('simulation')}
                aria-pressed={operatingMode === 'simulation'}
                title="Use optional local simulation data"
              >
                🧪 Simulation
              </button>
            </>

          )}

        </div>

        {/* System status pill */}

        <div
          className={`sys-status sys-${systemStatus}`}
          title={`System: ${t(statusKey, lang)}`}
          aria-label={`System status: ${t(statusKey, lang)}`}
        >
          <span className="pulse-dot" />

          <span className="sys-label">
            {t(statusKey, lang)}
          </span>
        </div>

        {/* Tick counter */}

        {tick > 0 && (
          <span
            className="tick-counter"
            aria-label={`Tick ${tick}`}
          >
            #{tick}
          </span>
        )}

        {/* Language switcher */}

        <div className="navbar-lang-wrap">

          <button
            type="button"
            className="navbar-lang-btn"
            onClick={toggleLanguageMenu}
            title="Change language"
            aria-label="Select language"
            aria-expanded={showLang}
          >
            {currentLang.flag}
            {' '}
            <span>
              {currentLang.label}
            </span>

            <span className="lang-caret">
              {showLang ? '▲' : '▼'}
            </span>
          </button>

          {showLang && (
            <div className="navbar-lang-dropdown">

              {SUPPORTED_LANGUAGES.map(language => (
                <button
                  type="button"
                  key={language.code}
                  className={
                    `navbar-lang-opt${
                      language.code === lang
                        ? ' lang-opt-active'
                        : ''
                    }`
                  }
                  onClick={() => {
                    setLang(language.code)
                    setShowLang(false)
                  }}
                >
                  <span>
                    {language.flag}
                  </span>

                  <span className="nlopt-code">
                    {language.label}
                  </span>

                  <span className="nlopt-name">
                    {language.name}
                  </span>
                </button>
              ))}

            </div>
          )}

        </div>

        {/* Theme toggle */}

        <button
          type="button"
          className="theme-toggle"
          onClick={onToggleTheme}
          aria-label={
            isLightMode
              ? t('theme_switch_dark', lang)
              : t('theme_switch_light', lang)
          }
          title={
            isLightMode
              ? t('theme_dark', lang)
              : t('theme_light', lang)
          }
        >
          {isLightMode ? '🌑' : '☀️'}
        </button>

        {/* User information and logout */}

        {user && (
          <div className="navbar-user">

            <span
              className="user-name"
              title={user.role}
            >
              {user.full_name || user.username}
            </span>

            <button
              type="button"
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
