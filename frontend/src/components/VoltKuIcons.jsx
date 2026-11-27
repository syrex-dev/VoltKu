import React from 'react'

/**
 * Custom utility SVG icons untuk VoltKu — gaya teknis instrumen listrik,
 * menghindari ikon generik Sparkles/Bot.
 */
export function EnergyAssistantIcon({ size = 18, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.85"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <rect x="3" y="4" width="18" height="14" rx="4" />
      <path d="M8 20h8" />
      <path d="M12 18v2" />
      <path d="M6.5 11.5h2.2l1.6-3.2 2.4 6.2 1.7-3H17.5" />
    </svg>
  )
}

export function SignalPulseIcon({ size = 14, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="2.2" fill="currentColor" stroke="none" />
      <path d="M7.8 16.2a6 6 0 0 1 0-8.4" />
      <path d="M16.2 7.8a6 6 0 0 1 0 8.4" />
      <path d="M4.9 19.1a10 10 0 0 1 0-14.2" />
      <path d="M19.1 4.9a10 10 0 0 1 0 14.2" />
    </svg>
  )
}

export function TierShieldIcon({ size = 14, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M12 2.8 4.5 6v5.7c0 4.7 3.2 8.9 7.5 10.1 4.3-1.2 7.5-5.4 7.5-10.1V6L12 2.8Z" />
      <path d="M9.5 12.2 11.3 14l3.5-3.8" />
    </svg>
  )
}

export function MeterPulseIcon({ size = 14, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <rect x="3.5" y="4.5" width="17" height="15" rx="3" />
      <path d="M7.5 13h2l1.6-4 2.2 6 1.5-2h1.7" />
    </svg>
  )
}

