// Map geometry shared by the SVG map: projection, land test, arrow shapes.
// The projection must match web/scripts/build-coast.mjs (which produced the coastline).

export interface BBox {
  latMin: number
  latMax: number
  lonMin: number
  lonMax: number
}

export interface Coast {
  source: string
  bbox: BBox
  width: number
  height: number
  rings: [number, number][][]
  path: string
}

export interface Frames {
  bbox: BBox
  stride: number
  lats: number[]
  lons: number[]
  times: string[]
  daylight: boolean[]
  kn10: (number | null)[][]
  dir: (number | null)[][]
}

export type Projector = (lat: number, lon: number) => [number, number]

/** Equirectangular, x scaled by cos(mid-latitude); same constants as build-coast.mjs. */
export function projector(bbox: BBox, width: number): Projector {
  const kx = Math.cos(((bbox.latMin + bbox.latMax) / 2) * (Math.PI / 180))
  const scale = width / ((bbox.lonMax - bbox.lonMin) * kx)
  return (lat, lon) => [(lon - bbox.lonMin) * kx * scale, (bbox.latMax - lat) * scale]
}

/** Even-odd ray casting over all rings (islands; no holes in this data). */
export function pointInRings(x: number, y: number, rings: [number, number][][]): boolean {
  let inside = false
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i]
      const [xj, yj] = ring[j]
      if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
    }
  }
  return inside
}

/** Arrow length in viewBox units: grows with speed, capped below the ~50-unit grid spacing. */
export function arrowLength(kn: number): number {
  return Math.max(14, Math.min(44, 12 + kn * 1.1))
}

/**
 * Arrow pointing "up" (north) with its tail at (0, len/2) and tip at (0, -len/2);
 * rotate by dir + 180 to point downwind.
 */
export function arrowPath(len: number): string {
  const h = len / 2
  const head = Math.min(11, len * 0.42)
  const w = head * 0.62
  return `M0 ${h}V${-h + head * 0.6}M${-w} ${-h + head}L0 ${-h}L${w} ${-h + head}`
}

/** Index of the grid point nearest to an SVG point (for tap-to-inspect). */
export function nearestPoint(x: number, y: number, pts: { x: number; y: number }[]): number {
  let best = -1
  let bestD = Infinity
  pts.forEach((p, i) => {
    const d = (p.x - x) ** 2 + (p.y - y) ** 2
    if (d < bestD) {
      bestD = d
      best = i
    }
  })
  return best
}

/** CSS gradient for the slider track: darker stripes where it's night. */
export function nightGradient(daylight: boolean[], night = 'var(--slider-night)', day = 'var(--slider-day)'): string {
  if (daylight.length === 0) return day
  const n = daylight.length
  const stops: string[] = []
  let start = 0
  for (let i = 1; i <= n; i++) {
    if (i === n || daylight[i] !== daylight[start]) {
      const c = daylight[start] ? day : night
      stops.push(`${c} ${((start / n) * 100).toFixed(2)}%`, `${c} ${((i / n) * 100).toFixed(2)}%`)
      start = i
    }
  }
  return `linear-gradient(to right, ${stops.join(', ')})`
}
