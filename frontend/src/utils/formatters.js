import { getPreferredTimeZone } from './userPrefs'

// Formatters (Default strict Intl Asia/Jakarta, mendukung preferensi zona tampilan user)
export const formatRp = (val) => {
  if (val === null || val === undefined || isNaN(val)) return 'Rp -'
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(val)
}

export const formatNum = (val, decimals = 1) => {
  if (val === null || val === undefined || isNaN(val)) return '-'
  return new Intl.NumberFormat('id-ID', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val)
}

export const formatTimeWIB = (epochSec) => {
  if (!epochSec) return '-'
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: getPreferredTimeZone(),
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(epochSec * 1000))
}

export const formatDateTimeWIB = (epochSec) => {
  if (!epochSec) return '-'
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: getPreferredTimeZone(),
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(epochSec * 1000))
}

export const formatDateWIB = (epochSec) => {
  if (!epochSec) return '-'
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: getPreferredTimeZone(),
    day: 'numeric',
    month: 'short',
  }).format(new Date(epochSec * 1000))
}
