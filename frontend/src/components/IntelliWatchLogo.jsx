/**
 * IntelliWatch brand logo — uses the official PNG asset.
 * Transparent background. Served from /intelliwatch-eye-logo-source.png
 * Usage: <IntelliWatchLogo size={32} />
 */
export default function IntelliWatchLogo({ size = 32, className = '' }) {
  const h = size
  const w = Math.round(size * 1.46)
  return (
    <img
      src="/intelliwatch-eye-logo-source.png"
      alt="IntelliWatch logo"
      width={w}
      height={h}
      className={className}
      style={{ display: 'inline-block', objectFit: 'contain', background: 'transparent', verticalAlign: 'middle' }}
      draggable={false}
    />
  )
}
