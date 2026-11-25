/**
 * IntelliWatch brand logo — exact eye PNG asset, transparent background.
 * Used on Login page and Dashboard navbar.
 * Usage: <IntelliWatchLogo size={32} />
 */
export default function IntelliWatchLogo({ size = 32, className = '' }) {
  const h = size
  const w = Math.round(size * 1.46)
  return (
    <img
      src="/intelliwatch-eye-logo-source.png"
      alt="IntelliWatch"
      width={w}
      height={h}
      className={className}
      style={{
        display: 'inline-block',
        objectFit: 'contain',
        background: 'transparent',
        verticalAlign: 'middle',
      }}
      draggable={false}
    />
  )
}
