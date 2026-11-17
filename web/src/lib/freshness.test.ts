import { describe, expect, it } from 'vitest'
import { freshness, runLabel, runStart } from './freshness'
import type { Meta } from './types'

const meta = (over: Partial<Meta['wrf']> = {}, generatedAt = '2026-11-16T00:56:00Z'): Meta =>
  ({
    generatedAt,
    wrf: {
      dataset: 'wrf_mo',
      coverageEnd: '2026-11-22T00:00:00Z',
      start: '2026-11-15T00:00:00-10:00',
      end: '2026-11-21T14:00:00-10:00',
      hours: 159,
      status: 'ok',
      ...over,
    },
  }) as Meta

const at = (iso: string) => Date.parse(iso)

describe('runStart', () => {
  it('uses the recorded run, else coverage end - 168 h', () => {
    expect(runStart(meta({ run: '2026-11-15T00:00:00Z' }))).toBe('2026-11-15T00:00:00Z')
    expect(runStart(meta())).toBe('2026-11-15T00:00:00.000Z')
  })
  it('labels it in Hawaii time', () => {
    expect(runLabel(meta())).toBe('Sat, Nov 14, 2 PM')
  })
})

describe('freshness', () => {
  it('says nothing for a normal day', () => {
    // run published ~1 day after it starts, refreshed 3 h ago
    expect(freshness(meta({}, '2026-11-16T03:00:00Z'), at('2026-11-16T06:00:00Z'))).toBeNull()
  })
  it('blames the model when Makani refreshed recently but the run is late', () => {
    const f = freshness(meta({}, '2026-11-17T08:00:00Z'), at('2026-11-17T10:00:00Z'))! // run 58 h old
    expect(f.level).toBe('warn')
    expect(f.text).toContain('model run of Sat, Nov 14, 2 PM')
    expect(f.text).toContain('University of Hawaiʻi')
    expect(f.text).toContain('until Sat, Nov 21')
  })
  it('turns red when two runs are missing', () => {
    const f = freshness(meta({}, '2026-11-18T09:00:00Z'), at('2026-11-18T10:00:00Z'))! // 82 h
    expect(f.level).toBe('bad')
    expect(f.text).toContain('3 days ago')
  })
  it('flags failing refreshes without blaming the model', () => {
    const f = freshness(meta({}, '2026-11-16T00:56:00Z'), at('2026-11-17T05:00:00Z'))! // 28 h
    expect(f.level).toBe('warn')
    expect(f.text).toContain('last refreshed 28 hours ago')
    expect(f.text).not.toContain('University')
  })
})
