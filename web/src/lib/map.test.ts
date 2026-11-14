import { describe, expect, it } from 'vitest'
import { arrowPath } from './map'

describe('arrows', () => {
  it('is a closed shape pointing up: tail at +len/2, tip at -len/2', () => {
    const d = arrowPath(30)
    expect(d.startsWith('M-0.5 15L')).toBe(true)
    expect(d).toContain('L0 -15L')
    expect(d.endsWith('L0.5 15Z')).toBe(true)
  })
  it('keeps a swept-back head: barbs behind the neck', () => {
    const ys = arrowPath(30).match(/-?\d+(\.\d+)?/g)!.map(Number).filter((_, i) => i % 2 === 1)
    const [, neckY, barbY] = ys
    expect(barbY).toBeGreaterThan(neckY)
  })
})
