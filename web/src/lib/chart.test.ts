import { describe, expect, it } from 'vitest'
import { areaPath, axisMax, axisTicks, monotonePath, segments, type Pt } from './chart'

/** Samples a path made of one M and cubic C segments. */
function sample(d: string, steps = 20): Pt[] {
  const nums = d.match(/-?\d+(\.\d+)?/g)!.map(Number)
  let [x0, y0] = nums
  const out: Pt[] = [[x0, y0]]
  for (let k = 2; k + 5 < nums.length + 1; k += 6) {
    const [c1x, c1y, c2x, c2y, x1, y1] = nums.slice(k, k + 6)
    for (let s = 1; s <= steps; s++) {
      const t = s / steps
      const u = 1 - t
      out.push([
        u * u * u * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t * t * t * x1,
        u * u * u * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t * t * t * y1,
      ])
    }
    x0 = x1
    y0 = y1
  }
  return out
}

describe('monotonePath', () => {
  const pts: Pt[] = [
    [0, 100],
    [10, 40],
    [20, 42],
    [30, 90],
    [40, 90],
    [50, 10],
  ]

  it('passes through every point', () => {
    const d = monotonePath(pts)
    for (const [x, y] of pts) expect(d).toContain(`${x},${y}`)
  })

  it('never overshoots a segment (no invented wind)', () => {
    const d = monotonePath(pts)
    const curve = sample(d)
    for (let i = 0; i < pts.length - 1; i++) {
      const [xa, ya] = pts[i]
      const [xb, yb] = pts[i + 1]
      const lo = Math.min(ya, yb) - 0.15
      const hi = Math.max(ya, yb) + 0.15
      for (const [x, y] of curve.filter(([x]) => x >= xa && x <= xb)) {
        expect(y, `x=${x.toFixed(1)}`).toBeGreaterThanOrEqual(lo)
        expect(y, `x=${x.toFixed(1)}`).toBeLessThanOrEqual(hi)
      }
    }
  })

  it('handles one and two points', () => {
    expect(monotonePath([])).toBe('')
    expect(monotonePath([[1, 2]])).toBe('M1,2')
    expect(monotonePath([[0, 0], [9, 9]])).toBe('M0,0C3,3,6,6,9,9')
  })
})

describe('segments and areas', () => {
  it('breaks the line at missing hours', () => {
    const runs = segments([1, 2, null, 4], (v, i) => [i, v] as Pt)
    expect(runs).toEqual([[[0, 1], [1, 2]], [[3, 4]]])
  })
  it('closes the area on the baseline', () => {
    expect(areaPath([[0, 5], [10, 5]], 50).endsWith('L10,50L0,50Z')).toBe(true)
    expect(areaPath([[0, 5]], 50)).toBe('')
  })
})

describe('axis', () => {
  it('shares one rounded top across days, never below 25 kn', () => {
    expect(axisMax([12, 18.2])).toBe(25)
    expect(axisMax([31.4])).toBe(35)
    expect(axisMax([])).toBe(25)
  })
  it('ticks every 10 kn, every 20 for big km/h numbers', () => {
    expect(axisTicks(35)).toEqual([0, 10, 20, 30])
    expect(axisTicks(40)).toEqual([0, 10, 20, 30, 40])
    expect(axisTicks(80)).toEqual([0, 20, 40, 60, 80])
  })
  it('rounds km/h tops to 10', () => {
    expect(axisMax([61], 50)).toBe(70)
  })
})
