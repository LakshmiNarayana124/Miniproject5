/**
 * IntelliWatch brand logo — matches the reference image exactly.
 * Eye + gear (top-right, overlapping upper lid) + 3 data bars.
 * Fully transparent background. Inline SVG, no external file.
 * Usage: <IntelliWatchLogo size={32} />
 */
export default function IntelliWatchLogo({ size = 32, className = '' }) {
  const h = size
  const w = Math.round(size * 1.55)
  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 186 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="IntelliWatch logo"
      role="img"
    >
      <defs>
        {/* Outer eye stroke — deep navy to bright cyan */}
        <linearGradient id="iw_outerEye" x1="0%" y1="20%" x2="100%" y2="80%">
          <stop offset="0%"   stopColor="#0a1a6e"/>
          <stop offset="40%"  stopColor="#1a3fc4"/>
          <stop offset="70%"  stopColor="#2563eb"/>
          <stop offset="100%" stopColor="#38bdf8"/>
        </linearGradient>
        {/* Inner upper lid highlight stroke */}
        <linearGradient id="iw_innerLid" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#38bdf8" stopOpacity="0"/>
          <stop offset="30%"  stopColor="#38bdf8"/>
          <stop offset="70%"  stopColor="#93c5fd"/>
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0"/>
        </linearGradient>
        {/* Lower lid — magenta/purple sweep */}
        <linearGradient id="iw_lowerLid" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#7c3aed"/>
          <stop offset="50%"  stopColor="#a855f7"/>
          <stop offset="100%" stopColor="#be185d"/>
        </linearGradient>
        {/* Iris radial — purple with deep centre */}
        <radialGradient id="iw_iris" cx="38%" cy="35%" r="62%">
          <stop offset="0%"   stopColor="#c4b5fd"/>
          <stop offset="25%"  stopColor="#7c3aed"/>
          <stop offset="60%"  stopColor="#4c1d95"/>
          <stop offset="100%" stopColor="#0f0520"/>
        </radialGradient>
        {/* Gear gradient */}
        <linearGradient id="iw_gear" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stopColor="#1d4ed8"/>
          <stop offset="100%" stopColor="#0a1a6e"/>
        </linearGradient>
        {/* Bar chart gradient */}
        <linearGradient id="iw_bar1" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%"   stopColor="#38bdf8"/>
          <stop offset="100%" stopColor="#1d4ed8"/>
        </linearGradient>
        <linearGradient id="iw_bar2" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%"   stopColor="#60a5fa"/>
          <stop offset="100%" stopColor="#1e40af"/>
        </linearGradient>
        <linearGradient id="iw_bar3" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%"   stopColor="#93c5fd"/>
          <stop offset="100%" stopColor="#2563eb"/>
        </linearGradient>
      </defs>

      {/* ── OUTER EYE BODY — wide almond, thick stroke ── */}
      {/* Main outer path — dark navy fill to give the "lid thickness" look */}
      <path
        d="M4 60 Q20 20 70 14 Q100 10 130 20 Q155 28 182 60
           Q155 92 130 100 Q100 110 70 106 Q20 100 4 60Z"
        fill="#0d1b6e"
        opacity="0.92"
      />
      {/* Inner white of the eye */}
      <path
        d="M14 60 Q28 30 70 24 Q100 18 128 28 Q150 36 172 60
           Q150 84 128 92 Q100 102 70 96 Q28 90 14 60Z"
        fill="white"
      />
      {/* Upper eyelid outer stroke */}
      <path
        d="M4 60 Q20 20 70 14 Q100 10 130 20 Q155 28 182 60"
        fill="none"
        stroke="url(#iw_outerEye)"
        strokeWidth="6"
        strokeLinecap="round"
      />
      {/* Lower eyelid outer stroke */}
      <path
        d="M4 60 Q20 100 70 106 Q100 110 130 100 Q155 92 182 60"
        fill="none"
        stroke="url(#iw_outerEye)"
        strokeWidth="5"
        strokeLinecap="round"
      />
      {/* Inner upper lid highlight (the bright cyan line inside) */}
      <path
        d="M18 54 Q35 28 70 22 Q100 17 128 30 Q148 38 168 56"
        fill="none"
        stroke="url(#iw_innerLid)"
        strokeWidth="2.5"
        strokeLinecap="round"
        opacity="0.85"
      />
      {/* Lower magenta sweep */}
      <path
        d="M16 64 Q34 92 70 100 Q100 106 128 96 Q152 88 170 68"
        fill="none"
        stroke="url(#iw_lowerLid)"
        strokeWidth="4"
        strokeLinecap="round"
        opacity="0.9"
      />
      {/* Left sharp eyelid extension */}
      <path
        d="M4 60 L18 50"
        fill="none"
        stroke="#0a1a6e"
        strokeWidth="4"
        strokeLinecap="round"
      />

      {/* ── IRIS ── */}
      <circle cx="93" cy="60" r="28" fill="url(#iw_iris)"/>
      {/* Iris rim */}
      <circle cx="93" cy="60" r="28" fill="none" stroke="#6d28d9" strokeWidth="1.5" opacity="0.6"/>
      {/* Pupil */}
      <circle cx="93" cy="60" r="13" fill="#050112"/>
      {/* Main highlight — large soft */}
      <circle cx="83" cy="50" r="7" fill="white" fillOpacity="0.65"/>
      {/* Secondary highlight */}
      <circle cx="98" cy="53" r="3" fill="white" fillOpacity="0.3"/>

      {/* ── GEAR — top right, overlapping upper lid ── */}
      {/*
        Gear centre at ~(148, 36), radius ~22.
        12 teeth. Drawn as a path.
      */}
      <g transform="translate(148,36)">
        <path
          d="
            M-4,-22 L-4,-26 L4,-26 L4,-22
            A22,22 0 0,1 10.6,-19.4 L13.4,-22.2 L19.1,-16.5 L16.3,-13.7
            A22,22 0 0,1 19.4,-10.6 L23.4,-10.6 L23.4,-2.6 L19.4,-2.6
            A22,22 0 0,1 19.4,2.6 L23.4,2.6 L23.4,10.6 L19.4,10.6
            A22,22 0 0,1 16.3,13.7 L19.1,16.5 L13.4,22.2 L10.6,19.4
            A22,22 0 0,1 4,22 L4,26 L-4,26 L-4,22
            A22,22 0 0,1 -10.6,19.4 L-13.4,22.2 L-19.1,16.5 L-16.3,13.7
            A22,22 0 0,1 -19.4,10.6 L-23.4,10.6 L-23.4,2.6 L-19.4,2.6
            A22,22 0 0,1 -19.4,-2.6 L-23.4,-2.6 L-23.4,-10.6 L-19.4,-10.6
            A22,22 0 0,1 -16.3,-13.7 L-19.1,-16.5 L-13.4,-22.2 L-10.6,-19.4
            A22,22 0 0,1 -4,-22 Z
          "
          fill="url(#iw_gear)"
          opacity="0.95"
        />
        {/* Gear centre hole */}
        <circle cx="0" cy="0" r="9" fill="white" opacity="0.15"/>
        <circle cx="0" cy="0" r="9" fill="none" stroke="#1d4ed8" strokeWidth="1.5"/>
      </g>

      {/* ── BAR CHART — 3 bars above/right of gear ── */}
      {/* Tallest bar — left */}
      <rect x="128" y="4"  width="9" height="30" rx="2.5" fill="url(#iw_bar1)"/>
      {/* Middle bar */}
      <rect x="140" y="12" width="9" height="22" rx="2.5" fill="url(#iw_bar2)"/>
      {/* Shortest bar — right */}
      <rect x="152" y="18" width="9" height="16" rx="2.5" fill="url(#iw_bar3)"/>
    </svg>
  )
}
