import { describe, expect, it } from 'vitest'
import { parseRoute, routeHash, sameView } from './route'
import { tempLabel, windLabel } from './units'

describe('routes', () => {
  it('reads spot and day', () => {
    expect(parseRoute('#/kanaha/tomorrow')).toEqual({ spot: 'kanaha', view: 'tomorrow' })
    expect(parseRoute('#/maui-sunset/2026-11-16')).toEqual({ spot: 'maui-sunset', view: { date: '2026-11-16' } })
    expect(parseRoute('#/harbor')).toEqual({ spot: 'harbor', view: null })
    expect(parseRoute('')).toEqual({ spot: null, view: null })
  })
  it('keeps the old #/spot/<id> links working', () => {
    expect(parseRoute('#/spot/sprecks')).toEqual({ spot: 'sprecks', view: null })
  })
  it('ignores junk days', () => {
    expect(parseRoute('#/kanaha/someday').view).toBeNull()
  })
  it('builds hashes back', () => {
    expect(routeHash('kanaha')).toBe('#/kanaha')
    expect(routeHash('kanaha', 'days')).toBe('#/kanaha/days')
    expect(routeHash('kanaha', { date: '2026-11-16' })).toBe('#/kanaha/2026-11-16')
    expect(sameView({ date: '2026-11-16' }, { date: '2026-11-16' })).toBe(true)
    expect(sameView('today', null)).toBe(false)
  })
})

describe('units', () => {
  it('converts knots for display', () => {
    expect([windLabel(20, 'kn'), windLabel(20, 'mph'), windLabel(20, 'kmh')]).toEqual([20, 23, 37])
  })
  it('formats air temperature', () => {
    expect(tempLabel(26, 'c')).toBe('26°C')
    expect(tempLabel(26, 'f')).toBe('79°F')
  })
})
