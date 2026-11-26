import React, { useId } from 'react'

function VoltKuMarkSvg({ uid, isDark, className }) {
  const g1 = `${uid}-l1`
  const g2 = `${uid}-l2`
  const gs = `${uid}-ls`
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" className={className}>
      <defs>
        <linearGradient id={g1} x1="8" y1="8" x2="34" y2="56" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={isDark ? '#FFFFFF' : '#0B1B3A'} />
          <stop offset="100%" stopColor={isDark ? '#D7E6FF' : '#1E40AF'} />
        </linearGradient>
        <linearGradient id={g2} x1="56" y1="8" x2="28" y2="56" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={isDark ? '#38BDF8' : '#0EA5E9'} />
          <stop offset="50%" stopColor={isDark ? '#2563EB' : '#1677FF'} />
          <stop offset="100%" stopColor="#1D4ED8" />
        </linearGradient>
        <linearGradient id={gs} x1="29" y1="38" x2="38" y2="56" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={isDark ? '#09204A' : '#081530'} stopOpacity="0.32" />
          <stop offset="100%" stopColor={isDark ? '#09204A' : '#081530'} stopOpacity="0" />
        </linearGradient>
      </defs>
      <g transform="translate(-4.5 -4.5) scale(1.14)">
        <path
          fill={`url(#${g1})`}
          d="M10.4 14.4C9.8 12.9 10.9 11.4 12.5 11.4H20.8C21.8 11.4 22.7 12 23.1 12.9L36.2 44.3L33.4 50.6C32.4 52.8 29.2 52.8 28.2 50.6L10.4 14.4Z"
        />
        <path
          fill={`url(#${g2})`}
          d="M43.2 11.4H51.5C53.1 11.4 54.2 12.9 53.6 14.4L36.2 50.5C35.4 52.1 33.8 52.6 32 52.6C30.4 52.6 29 51.8 28.3 50.5L32.8 40.3L40.9 13C41.3 12 42.2 11.4 43.2 11.4Z"
        />
        <path fill={`url(#${gs})`} d="M32.8 40.3L36.2 44.3L33.4 50.6L28.3 50.5L32.8 40.3Z" />
        <circle cx="32" cy="17.5" r="3.6" fill={isDark ? '#FBBF24' : '#F59E0B'} />
      </g>
    </svg>
  )
}

function VoltKuWordmarkSvg({ uid, isDark, appName, className }) {
  const g1 = `${uid}-wl1`
  const g2 = `${uid}-wl2`
  const gs = `${uid}-wls`
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="4 4 188 56"
      role="img"
      aria-label={appName}
      className={className}
    >
      <defs>
        <linearGradient id={g1} x1="12" y1="12" x2="34" y2="52" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={isDark ? '#FFFFFF' : '#0F295C'} />
          <stop offset="100%" stopColor={isDark ? '#D7E6FF' : '#1E40AF'} />
        </linearGradient>
        <linearGradient id={g2} x1="52" y1="12" x2="30" y2="52" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={isDark ? '#38BDF8' : '#0EA5E9'} />
          <stop offset="52%" stopColor={isDark ? '#2563EB' : '#1677FF'} />
          <stop offset="100%" stopColor={isDark ? '#1D4ED8' : '#1677FF'} />
        </linearGradient>
        <linearGradient id={gs} x1="30" y1="36" x2="38" y2="52" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor={isDark ? '#09204A' : '#0B1B3A'} stopOpacity="0.3" />
          <stop offset="100%" stopColor={isDark ? '#09204A' : '#0B1B3A'} stopOpacity="0" />
        </linearGradient>
      </defs>
      <g transform="translate(2 4) scale(0.875)">
        <path
          fill={`url(#${g1})`}
          d="M10.4 14.4C9.8 12.9 10.9 11.4 12.5 11.4H20.8C21.8 11.4 22.7 12 23.1 12.9L36.2 44.3L33.4 50.6C32.4 52.8 29.2 52.8 28.2 50.6L10.4 14.4Z"
        />
        <path
          fill={`url(#${g2})`}
          d="M43.2 11.4H51.5C53.1 11.4 54.2 12.9 53.6 14.4L36.2 50.5C35.4 52.1 33.8 52.6 32 52.6C30.4 52.6 29 51.8 28.3 50.5L32.8 40.3L40.9 13C41.3 12 42.2 11.4 43.2 11.4Z"
        />
        <path fill={`url(#${gs})`} d="M32.8 40.3L36.2 44.3L33.4 50.6L28.3 50.5L32.8 40.3Z" />
        <circle cx="32" cy="17.5" r="3.4" fill={isDark ? '#FBBF24' : '#F59E0B'} />
      </g>
      <g transform="translate(-14 0)">
        <path
          fill={isDark ? '#EAF1FF' : '#0B1B3A'}
          d="M100.57 17.9 93.16 37.45 85.72 17.9H80.23L91.29 45.5H95L106 17.9ZM116.97 45.89C123 45.89 126.97 41.22 126.97 35.7C126.97 30.19 123 25.58 116.97 25.58C110.93 25.58 106.97 30.19 106.97 35.7C106.97 41.22 110.93 45.89 116.97 45.89ZM116.97 41.79C113.37 41.79 111.93 38.9 111.93 35.7C111.93 32.49 113.37 29.7 116.97 29.7C120.58 29.7 122 32.49 122 35.7C122 38.9 120.58 41.79 116.97 41.79ZM134.5 45.89C135.63 45.89 137.06 45.7 138.05 45.5V41.5C137.54 41.57 137.02 41.61 136.74 41.61C135.79 41.61 135.18 41.22 135.18 40.3V17.9H130.42V41.61C130.42 45.05 132.25 45.89 134.5 45.89ZM148.32 45.89C149.74 45.89 151.15 45.58 151.87 45.3V40.99C151.23 41.3 150.15 41.69 149.16 41.69C147.91 41.69 146.99 41.14 146.99 39.27V29.97H151.87V25.99H146.99V17.75L142.3 21.14V25.99H139.08V29.97H142.22V40.11C142.22 43.66 144.51 45.89 148.32 45.89Z"
        />
        <path
          fill={isDark ? '#5B9DFF' : '#1677FF'}
          d="M156.57 45.5H161.53V38.33L167.14 32.53L175.66 45.5H181.83L170.58 29.21L181.61 17.9H174.97L161.53 32.3V17.9H156.57ZM191.2 45.89C193.13 45.89 195.39 45.15 196.96 43.21V45.5H201.68V25.99H196.96V36.65C196.96 40.05 195.24 41.5 192.56 41.5C190.12 41.5 188.83 39.66 188.83 37.1V25.99H184.12V37.71C184.12 41.79 186.08 45.89 191.2 45.89Z"
        />
      </g>
    </svg>
  )
}

export function BrandLogo({
  theme = 'light',
  displayMode = 'logo_only',
  appName = 'VoltKu',
  variant = 'navbar',
  className = '',
}) {
  const uid = useId().replace(/:/g, '')
  const isDark = theme === 'dark'
  const cleanName = (appName || 'VoltKu').trim() || 'VoltKu'

  if (variant === 'icon') {
    return (
      <span className={`voltku-brand-badge ${className}`.trim()} aria-hidden="true">
        <VoltKuMarkSvg uid={uid} isDark={isDark} className="voltku-brand-badge-img" />
      </span>
    )
  }

  if (displayMode === 'text_only') {
    return <span className={`voltku-brand-text-only is-${variant}`}>{cleanName}</span>
  }

  if (displayMode === 'logo_text') {
    return (
      <span className={`voltku-brand-combo is-${variant}`}>
        <span className="voltku-brand-badge" aria-hidden="true">
          <VoltKuMarkSvg uid={uid} isDark={isDark} className="voltku-brand-badge-img" />
        </span>
        <span className={`voltku-brand-text-only is-${variant}`}>{cleanName}</span>
      </span>
    )
  }

  return (
    <span className={`voltku-brand-wordmark is-${variant}`}>
      <VoltKuWordmarkSvg
        uid={uid}
        isDark={isDark}
        appName={cleanName}
        className={`voltku-brand-wordmark-img is-${variant}`}
      />
    </span>
  )
}
