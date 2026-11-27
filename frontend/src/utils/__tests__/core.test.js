import { describe, it, expect } from 'vitest'
import { formatRp, formatNum } from '../formatters'
import {
  INDONESIAN_TIMEZONES,
  getTimeZoneShortLabel,
  TIMEZONE_SHORT_MAP,
} from '../userPrefs'

describe('VoltKu formatters & timezone utilities', () => {
  it('formats Rupiah integers cleanly without decimals', () => {
    expect(formatRp(30000)).toMatch(/Rp\s?30\.000/)
    expect(formatRp(null)).toBe('Rp -')
    expect(formatRp(undefined)).toBe('Rp -')
  })

  it('formats numbers with Indonesian locale decimals', () => {
    expect(formatNum(1234.56, 2)).toBe('1.234,56')
    expect(formatNum(null)).toBe('-')
  })

  it('provides complete WIB, WITA, and WIT Indonesian timezone options', () => {
    const ids = INDONESIAN_TIMEZONES.map((z) => z.id)
    expect(ids).toEqual(['Asia/Jakarta', 'Asia/Makassar', 'Asia/Jayapura'])
    expect(getTimeZoneShortLabel('Asia/Jakarta')).toBe('WIB')
    expect(getTimeZoneShortLabel('Asia/Makassar')).toBe('WITA')
    expect(getTimeZoneShortLabel('Asia/Jayapura')).toBe('WIT')
    expect(TIMEZONE_SHORT_MAP['Asia/Singapore']).toBe('SGT')
  })
})
