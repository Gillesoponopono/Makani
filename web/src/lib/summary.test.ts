import { describe, expect, it } from 'vitest'
import { daySummary, meanDir, rangeText } from './summary'
import type { Hour, Wave } from './types'

const hour = (i: number, kn: number, extra: Partial<Hour> = {}): Hour =>
  ({
    t: `2026-11-14T${String(i).padStart(2, '0')}:00:00-10:00`,
    wrf: { kn, dir: 70, gustEst: kn * 1.3, tairC: 22 + i / 4, rainMmH: 0 },
    sector: 'good',
    sports: [],
    daylight: i >= 7 && i < 18,
    ...extra,
  }) as Hour

const wave = (m: number, per: number, type: Wave['type']): Wave => ({ m, per, dir: 340, type, swell: null, chop: null })

describe('day summary', () => {
  it('uses daylight hours only', () => {
    const hours = Array.from({ length: 24 }, (_, i) =>
      hour(i, i < 7 ? 30 : 15 + (i % 7), { waterC: i < 7 ? 20 : 25.6, wave: wave(1 + i / 100, 14 + (i % 3), i < 12 ? 'mixed' : 'swell') }),
    )
    const s = daySummary(hours)
    expect(s.wind).toMatchObject({ min: 15, max: 21, dir: 70 })
    expect(s.wind!.gust).toBeCloseTo(21 * 1.3)
    expect(s.air).toEqual({ min: 23.75, max: 26.25 })
    expect(s.water).toBeCloseTo(25.6)
    expect(s.waves).toMatchObject({ min: 1.07, max: 1.17, per: { min: 14, max: 16 }, type: 'swell' })
  })

  it('falls back to all hours and copes with missing data', () => {
    const s = daySummary([hour(20, 12), hour(21, 14, { wrf: { kn: 14, dir: 80, gustEst: 18, tairC: null, rainMmH: null } })])
    expect(s.wind).toMatchObject({ min: 12, max: 14 })
    expect(s.air).toEqual({ min: 27, max: 27 })
    expect(s.water).toBeNull()
    expect(s.waves).toBeNull()
  })

  it('averages directions around north', () => {
    expect(meanDir([350, 10])).toBe(0)
    expect(meanDir([60, 80])).toBe(70)
    // A calm sea-breeze morning barely moves a strong northerly afternoon.
    expect(meanDir([240, 250, 0, 5], [2, 3, 25, 27])).toBeGreaterThanOrEqual(350)
  })

  it('writes one number when both ends match', () => {
    expect(rangeText({ min: 15.2, max: 21.4 }, Math.round)).toBe('15–21')
    expect(rangeText({ min: 20.6, max: 21.4 }, Math.round)).toBe('21')
  })
})
