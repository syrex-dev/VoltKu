import React from 'react'

export function BrandLogo({
  theme = 'light',
  displayMode = 'logo_only',
  appName = 'VoltKu',
  variant = 'navbar',
  className = '',
}) {
  const isDark = theme === 'dark'
  const cleanName = (appName || 'VoltKu').trim() || 'VoltKu'
  const logoSrc = isDark
    ? '/brand/voltku-logo-dark.svg?v=4'
    : '/brand/voltku-logo-light.svg?v=4'

  if (variant === 'icon') {
    return (
      <span className={`voltku-brand-badge ${className}`.trim()} aria-hidden="true">
        <img src="/brand/voltku-icon.svg?v=4" alt="" className="voltku-brand-badge-img" />
      </span>
    )
  }

  if (displayMode === 'text_only') {
    return (
      <span className={`voltku-brand-text-only is-${variant}`}>
        {cleanName}
      </span>
    )
  }

  if (displayMode === 'logo_text') {
    return (
      <span className={`voltku-brand-combo is-${variant}`}>
        <span className="voltku-brand-badge" aria-hidden="true">
          <img src="/brand/voltku-icon.svg?v=4" alt="" className="voltku-brand-badge-img" />
        </span>
        <span className={`voltku-brand-text-only is-${variant}`}>{cleanName}</span>
      </span>
    )
  }

  return (
    <span className={`voltku-brand-wordmark is-${variant}`}>
      <img
        src={logoSrc}
        alt={cleanName}
        className={`voltku-brand-wordmark-img is-${variant}`}
      />
    </span>
  )
}

