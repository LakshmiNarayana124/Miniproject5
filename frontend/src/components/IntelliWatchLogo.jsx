/**
 * IntelliWatch brand logo — uses the official PNG asset.
 * Transparent background. Served from /public/intelliwatch-eye-logo-source.png
 * Usage: <IntelliWatchLogo size={32} />
 */
export default function IntelliWatchLogo({ size = 32, className = '' }) {
  // The PNG is 1244×851 — aspect ratio ~1.46:1
  const h = size
  const w = Math.round(size * 1.46)

  return (
    <img
      src="/intelliwatch-eye-logo-source.png"
      alt="IntelliWatch logo"
      width={w}
      height={h}
      className={className}
      style={{
        display: 'inline-block',
        objectFit: 'contain',
        background: 'transparent',
      }}
      draggable={false}
    />
  )
}
