import { describe, expect, it } from 'vitest'
import coast from '../assets/maui-coast.json'
import { arrowLength, arrowPath, nearestPoint, nightGradient, pointInRings, projector, type Coast } from './map'

const c = coast as Coast
const project = projector(c.bbox, c.width)

describe('projector', () => {
  it('maps the bbox corners to the SVG corners (same constants as build-coast.mjs)', () => {
    const [x0, y0] = project(c.bbox.latMax, c.bbox.lonMin)
    const [x1, y1] = project(c.bbox.latMin, c.bbox.lonMax)
    expect(x0).toBeCloseTo(0)
    expect(y0).toBeCloseTo(0)
    expect(x1).toBeCloseTo(c.width)
    expect(y1).toBeCloseTo(c.height, 0)
  })
})

describe('pointInRings with the real coastline', () => {
  const at = (lat: number, lon: number) => pointInRings(...project(lat, lon), c.rings)
  it('puts Haleakalā summit and Wailuku on land', () => {
    expect(at(20.71, -156.25)).toBe(true)
    expect(at(20.89, -156.5)).toBe(true)
  })
  it('puts the spot model cells and the channels in the water', () => {
    expect(at(20.92, -156.44)).toBe(false) // Kanahā cell
    expect(at(20.938, -156.4)).toBe(false) // Sprecks cell
    expect(at(20.758, -156.48)).toBe(false) // Maui Sunset cell
    expect(at(20.6, -156.47)).toBe(false) // ʻAlalākeiki channel
  })
  it('includes Kahoʻolawe', () => {
    expect(at(20.55, -156.6)).toBe(true)
  })
})

describe('arrows', () => {
  it('grow with speed but stay under the grid spacing', () => {
    expect(arrowLength(0)).toBe(14)
    expect(arrowLength(20)).toBeGreaterThan(arrowLength(10))
    expect(arrowLength(60)).toBe(44)
  })
  it('path points up: tail at +len/2, tip at -len/2', () => {
    const d = arrowPath(30)
    expect(d.startsWith('M0 15V')).toBe(true)
    expect(d).toContain('L0 -15L')
  })
})

describe('nearestPoint', () => {
  it('finds the closest grid point', () => {
    const pts = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }]
    expect(nearestPoint(8, 1, pts)).toBe(1)
    expect(nearestPoint(-5, 9, pts)).toBe(2)
  })
})

describe('nightGradient', () => {
  it('produces one stop pair per day/night run', () => {
    const g = nightGradient([false, false, true, true, true, false], 'N', 'D')
    expect(g).toBe(
      'linear-gradient(to right, N 0.00%, N 33.33%, D 33.33%, D 83.33%, N 83.33%, N 100.00%)',
    )
  })
})
