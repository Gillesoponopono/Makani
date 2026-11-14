import { describe, expect, it } from 'vitest'
import {
  nextExtreme,
  tideAt,
  tideDay,
  tideHeight,
  tideRange,
  typeRuns,
  waveBand,
  waveCells,
  waveHeight,
  waveSummary,
} from './sea'
import type { Hour, Tide, Wave } from './types'

const tide: Tide = {
  station: '1615680',
  name: 'Kahului Harbor',
  kind: 'harmonic',
  datum: 'MLLW',
  units: 'ft',
  // Two days of hourly values from 2026-11-13 00:00 HST (a straight ramp is enough here).
  curve: { start: '2026-11-13T00:00:00-10:00', stepMinutes: 60, ft: Array.from({ length: 49 }, (_, i) => i / 10) },
  extremes: [
    { t: '2026-11-12T21:11:00-10:00', ft: -0.08, type: 'L' },
    { t: '2026-11-13T05:10:00-10:00', ft: 2.31, type: 'H' },
    { t: '2026-11-13T21:41:00-10:00', ft: 0.07, type: 'L' },
    { t: '2026-11-14T06:02:00-10:00', ft: 2.17, type: 'H' },
  ],
}

describe('tides', () => {
  it('cuts one day and threads the highs and lows into the curve', () => {
    const d = tideDay(tide, '2026-11-13')
    expect(d.extremes.map((e) => e.type)).toEqual(['H', 'L'])
    expect(d.extremes[0].h).toBeCloseTo(5 + 10 / 60)
    expect(d.pts[0]).toEqual([0, 0])
    expect(d.pts.at(-1)).toEqual([24, 2.4])
    // The 5:10 AM high is in, the 5 AM sample (10 min away) is dropped.
    expect(d.pts.some(([h]) => h === 5)).toBe(false)
    expect(d.pts.find(([h]) => Math.abs(h - 5.1667) < 0.01)?.[1]).toBe(2.31)
    expect(d.pts.every((p, i) => i === 0 || p[0] > d.pts[i - 1][0])).toBe(true)
  })

  it('reads the height at any time and the next turn', () => {
    expect(tideAt(tide, '2026-11-13T03:00:00-10:00')).toBeCloseTo(0.3)
    expect(tideAt(tide, '2026-11-13T03:30:00-10:00')).toBeCloseTo(0.35)
    expect(tideAt(tide, '2026-11-20T03:00:00-10:00')).toBeNull()
    expect(nextExtreme(tide, '2026-11-13T14:00:00-10:00')?.type).toBe('L')
    expect(nextExtreme(tide, '2026-11-15T14:00:00-10:00')).toBeNull()
    expect(tideRange(tide)).toEqual([-0.08, 4.8])
  })

  it('shows feet or metres', () => {
    expect(tideHeight(2.31, 'f')).toBe('2.3 ft')
    expect(tideHeight(2.31, 'c')).toBe('0.7 m')
    expect(tideHeight(-0.02, 'c')).toBe('0.0 m')
  })
})

const wave = (m: number, type: Wave['type']): Wave => ({ m, per: 14, dir: 340, type, swell: null, chop: null })
const hour = (i: number, w: Wave | null, daylight = i >= 7 && i < 18): Hour =>
  ({ t: `2026-11-13T${String(i).padStart(2, '0')}:00:00-10:00`, wave: w, daylight }) as Hour

describe('waves', () => {
  it('formats heights in the chosen system', () => {
    expect(waveHeight(1.24, 'c')).toBe('1.2 m')
    expect(waveHeight(1.24, 'f')).toBe('4 ft')
    expect(waveHeight(0.2, 'f')).toBe('0.7 ft')
  })

  it('bands sizes', () => {
    expect([0.1, 0.4, 1, 1.5, 2.5, 4].map(waveBand)).toEqual([0, 1, 2, 3, 4, 5])
  })

  it('makes 3-hour cells and merges equal types', () => {
    const hours = Array.from({ length: 24 }, (_, i) => hour(i, wave(1, i < 12 ? 'mixed' : 'swell')))
    hours[13] = null as unknown as Hour // a gap falls back to a neighbour hour
    const cells = waveCells(hours)
    expect(cells).toHaveLength(8)
    expect(cells[4]?.wave.type).toBe('swell')
    expect(typeRuns(cells)).toEqual([
      { from: 0, to: 12, type: 'mixed' },
      { from: 12, to: 24, type: 'swell' },
    ])
    expect(waveCells(Array(24).fill(null)).every((c) => c === null)).toBe(true)
  })

  it('sums up a day in daylight', () => {
    const hours = Array.from({ length: 24 }, (_, i) => hour(i, wave(i / 10, i < 10 ? 'chop' : 'swell')))
    expect(waveSummary(hours)).toEqual({ min: 0.7, max: 1.7, type: 'swell' })
    expect(waveSummary([hour(12, null)])).toBeNull()
  })
})
