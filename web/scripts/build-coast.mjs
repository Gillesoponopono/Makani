// Builds web/src/assets/maui-coast.json from the Maui County polygon (US Census 2020,
// served by the Hawaii Statewide GIS Program), clipped to the map box in
// config/map.json and projected to SVG coordinates. Run once; the output is committed.
//
//   node web/scripts/build-coast.mjs
//
// Projection: equirectangular with x scaled by cos(mid-latitude), good enough
// for an ~80 km box. The site projects wind arrows with the same bbox/size.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const cfg = JSON.parse(readFileSync(resolve(here, '../../config/map.json'), 'utf8'))
const { latMin, latMax, lonMin, lonMax } = cfg.bbox
const out = resolve(here, '../src/assets/maui-coast.json')

const kx = Math.cos(((latMin + latMax) / 2) * (Math.PI / 180))
const width = cfg.svgWidth
const scale = width / ((lonMax - lonMin) * kx)
const height = Math.round((latMax - latMin) * scale)
const project = ([lon, lat]) => [
  Math.round((lon - lonMin) * kx * scale * 10) / 10,
  Math.round((latMax - lat) * scale * 10) / 10,
]

// Sutherland–Hodgman clip of one ring against the bbox (lon/lat space).
function clipRing(ring) {
  const edges = [
    (p) => p[0] >= lonMin, (p) => p[0] <= lonMax,
    (p) => p[1] >= latMin, (p) => p[1] <= latMax,
  ]
  const cross = [
    (a, b) => lerp(a, b, (lonMin - a[0]) / (b[0] - a[0])),
    (a, b) => lerp(a, b, (lonMax - a[0]) / (b[0] - a[0])),
    (a, b) => lerp(a, b, (latMin - a[1]) / (b[1] - a[1])),
    (a, b) => lerp(a, b, (latMax - a[1]) / (b[1] - a[1])),
  ]
  let pts = ring
  for (let e = 0; e < 4 && pts.length; e++) {
    const input = pts
    pts = []
    for (let i = 0; i < input.length; i++) {
      const cur = input[i]
      const prev = input[(i + input.length - 1) % input.length]
      const inCur = edges[e](cur)
      const inPrev = edges[e](prev)
      if (inCur) {
        if (!inPrev) pts.push(cross[e](prev, cur))
        pts.push(cur)
      } else if (inPrev) {
        pts.push(cross[e](prev, cur))
      }
    }
  }
  return pts
}
const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]

function ringArea(r) {
  let s = 0
  for (let i = 0; i < r.length; i++) {
    const [x1, y1] = r[i]
    const [x2, y2] = r[(i + 1) % r.length]
    s += x1 * y2 - x2 * y1
  }
  return Math.abs(s / 2)
}

const params = new URLSearchParams({
  where: "geoid20='15009'", // Maui County
  geometry: `${lonMin - 0.05},${latMin - 0.05},${lonMax + 0.05},${latMax + 0.05}`,
  geometryType: 'esriGeometryEnvelope',
  inSR: '4326',
  spatialRel: 'esriSpatialRelIntersects',
  outSR: '4326',
  outFields: 'name20',
  maxAllowableOffset: String(cfg.coastline.generalizeDeg),
  f: 'geojson',
})
const res = await fetch(`${cfg.coastline.url}?${params}`, {
  headers: { 'User-Agent': 'Makani-forecast (+https://github.com/Gillesoponopono/Makani)' },
})
if (!res.ok) throw new Error(`coastline download failed: HTTP ${res.status}`)
const geo = await res.json()
if (!geo.features?.length) throw new Error(`no features: ${JSON.stringify(geo).slice(0, 300)}`)

const rings = []
for (const f of geo.features) {
  const g = f.geometry
  const polys = g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates]
  for (const poly of polys) {
    for (const ring of poly) {
      const clipped = clipRing(ring.slice(0, -1)).map(project)
      // Drop slivers and specks under ~4 px² (e.g. offshore rocks).
      if (clipped.length >= 3 && ringArea(clipped) > 4) rings.push(clipped)
    }
  }
}

const toPath = (r) => 'M' + r.map(([x, y]) => `${x} ${y}`).join('L') + 'Z'
const asset = {
  source: cfg.coastline.source,
  bbox: cfg.bbox,
  width,
  height,
  rings,
  path: rings.map(toPath).join(''),
}
mkdirSync(dirname(out), { recursive: true })
writeFileSync(out, JSON.stringify(asset))
const nPts = rings.reduce((n, r) => n + r.length, 0)
console.log(`Wrote ${out}: ${rings.length} rings, ${nPts} points, ${width}x${height}, ${(JSON.stringify(asset).length / 1024).toFixed(1)} KB`)
