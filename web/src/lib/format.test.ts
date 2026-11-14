import { describe, expect, it } from 'vitest'
import {
  bestWindow,
  compass,
  currentHourKey,
  dayName,
  groupByDay,
  hourLabel,
  knBand,
  weekdayShort,
  windowLabel,
} from './format'
import type { Hour } from './types'

const hour = (t: string, kn: number, opts: Partial<Hour> = {}): Hour => ({
  t,
  wrf: { kn, dir: 70, gustEst: kn * 1.3, tairC: 25, rainMmH: 0 },
  sector: 'good',
  sports: kn >= 10 ? ['foil_wing'] : [],
  daylight: true,
  ...opts,
})

describe('time in HST', () => {
  it('current hour key is UTC-10 regardless of the browser zone', () => {
    expect(currentHourKey(Date.parse('2026-11-14T00:30:00Z'))).toBe('2026-11-13T14')
  })
  it('labels hours and days', () => {
    expect(hourLabel('2026-11-13T00:00:00-10:00')).toBe('12 AM')
    expect(hourLabel('2026-11-13T14:00:00-10:00')).toBe('2 PM')
    expect(dayName('2026-11-13', '2026-11-13')).toBe('Today')
    expect(dayName('2026-11-14', '2026-11-13')).toBe('Tomorrow')
    expect(dayName('2026-11-15', '2026-11-13')).toBe('Sun Nov 15')
    expect(weekdayShort('2026-11-13')).toBe('Fri')
  })
})

describe('wind helpers', () => {
  it('compass points', () => {
    expect(compass(0)).toBe('N')
    expect(compass(68)).toBe('ENE')
    expect(compass(359)).toBe('N')
  })
  it('colour bands match the legend edges', () => {
    expect([9.9, 10, 14.9, 15, 20, 25, 30, 35, 50].map(knBand)).toEqual([0, 1, 1, 2, 3, 4, 5, 6, 6])
  })
})

describe('best window', () => {
  it('is the longest daylight run with a sport, ending at the end of its last hour', () => {
    const hs = [
      hour('2026-11-13T07:00:00-10:00', 12),
      hour('2026-11-13T08:00:00-10:00', 8),
      hour('2026-11-13T09:00:00-10:00', 14),
      hour('2026-11-13T10:00:00-10:00', 18),
      hour('2026-11-13T11:00:00-10:00', 22),
      hour('2026-11-13T18:00:00-10:00', 20, { daylight: false }),
    ]
    const w = bestWindow(hs)!
    expect(windowLabel(w)).toBe('9 AM–12 PM')
    expect([w.minKn, w.maxKn, w.hours]).toEqual([14, 22, 3])
  })
  it('is null when nothing is kiteable', () => {
    expect(bestWindow([hour('2026-11-13T07:00:00-10:00', 5)])).toBeNull()
  })
  it('groups by HST date', () => {
    const days = groupByDay(
      [hour('2026-11-13T23:00:00-10:00', 10), hour('2026-11-14T00:00:00-10:00', 10)],
      [],
    )
    expect(days.map((d) => d.date)).toEqual(['2026-11-13', '2026-11-14'])
  })
})
