/**
 * IntelliWatch brand logo — eye + gear + data bars.
 * Transparent background, inline SVG, no external file dep.
 * Usage: <IntelliWatchLogo size={32} />
 */
export default function IntelliWatchLogo({ size = 32, className = '' }) {
  const h = size
  const w = Math.round(size * 1.6)
  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 160 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="IntelliWatch logo"
      role="img"
    >
      <defs>
        <linearGradient id="iwEyeOuter" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#1d4ed8"/>
          <stop offset="55%" stopColor="#6d28d9"/>
          <stop offset="100%" stopColor="#be185d"/>
        </linearGradient>
        <linearGradient id="iwLidLow" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#7c3aed"/>
          <stop offset="100%" stopColor="#be185d"/>
        </linearGradient>
        <radialGradient id="iwIris" cx="38%" cy="35%" r="62%">
          <stop offset="0%" stopColor="#a78bfa"/>
          <stop offset="55%" stopColor="#6d28d9"/>
          <stop offset="100%" stopColor="#1e1b4b"/>
        </radialGradient>
      </defs>
      {/* upper eyelid / eye shape */}
      <path
        d="M6 50 Q38 14 80 14 Q122 14 154 50 Q122 86 80 86 Q38 86 6 50Z"
        fill="none"
        stroke="url(#iwEyeOuter)"
        strokeWidth="5"
        strokeLinejoin="round"
      />
      {/* lower lid accent */}
      <path
        d="M12 56 Q45 80 80 84 Q115 80 148 56"
        fill="none"
        stroke="url(#iwLidLow)"
        strokeWidth="3.5"
        strokeLinecap="round"
        opacity="0.75"
      />
      {/* upper inner lash line */}
      <path
        d="M18 44 Q52 20 80 18 Q108 20 142 44"
        fill="none"
        stroke="#93c5fd"
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.5"
      />
      {/* iris */}
      <circle cx="80" cy="50" r="22" fill="url(#iwIris)"/>
      {/* pupil */}
      <circle cx="80" cy="50" r="11" fill="#0a0520"/>
      {/* highlight */}
      <circle cx="72" cy="42" r="5" fill="white" fillOpacity="0.55"/>
      <circle cx="86" cy="44" r="2.5" fill="white" fillOpacity="0.3"/>
      {/* gear — top right */}
      <g transform="translate(118,8) scale(0.72)" fill="#2563eb" opacity="0.92">
        <path d="M20 0l-2.5 6a16 16 0 00-4 1.8L7.5 5 1 11.5l2.5 7A16 16 0 003 23H0l2.5 7H6a16 16 0 002 4l-3 7 7 7 7-3a16 16 0 004 2l2.5 6h9.5l2.5-6a16 16 0 004-2l7 3 7-7-3-7a16 16 0 002-4h3.5l2.5-7h-3.5a16 16 0 00-1.8-4l2.5-7-7-7-7 3a16 16 0 00-4-1.8zm4 15a12 12 0 110 24 12 12 0 010-24z"/>
      </g>
      {/* data bars — top right */}
      <rect x="126" y="6"  width="6" height="20" rx="2" fill="#38bdf8" opacity="0.95"/>
      <rect x="134" y="12" width="6" height="14" rx="2" fill="#60a5fa" opacity="0.95"/>
      <rect x="142" y="17" width="6" height="9"  rx="2" fill="#93c5fd" opacity="0.9"/>
    </svg>
  )
}
