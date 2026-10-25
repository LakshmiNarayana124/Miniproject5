import { NavLink } from 'react-router-dom'
import { SENSORS, statusLabel } from '../sensors'
export default function Navbar({
  systemStatus,
  tick,
  isLightMode,
  onToggleTheme
}) {
  return (
    <header className="navbar">
      <div className="navbar-left">
        <NavLink to="/" className="logo" style={{ textDecoration: 'none' }}>
          <span className="logo-eye">👁️</span>
          <span className="logo-text">IntelliWatch</span>
        </NavLink>
        <span className="logo-sub">Anomaly Detection &amp; Decision Support</span>
      </div>
      {/* Page navigation */}
      <nav className="nav-links">
        <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`}>
          🏠 Home
        </NavLink>
        <NavLink to="/vibration"   className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`}>
          {SENSORS.vibration.icon} Vibration
        </NavLink>
        <NavLink to="/temperature" className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`}>
          {SENSORS.temperature.icon} Temperature
        </NavLink>
        <NavLink to="/current"     className={({ isActive }) => `nav-link ${isActive ? 'nav-active' : ''}`}>
          {SENSORS.current.icon} Current
        </NavLink>
      </nav>

      <div className="navbar-right">
        <div className={`sys-status sys-${systemStatus}`}>
          <span className="pulse-dot" />
          <span>System: {statusLabel(systemStatus)}</span>
        </div>
        <span className="tick-counter">Tick #{tick}</span>
        <button className="theme-toggle" onClick={onToggleTheme}>
          {isLightMode ? "🌕 Dark Mode" : "☀️ Light Mode"}
        </button>
      </div>
    </header>
  )
}
