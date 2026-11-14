// Prepares the hero picture of Maui and places the spots on it.
//
//   cd web && npm i --no-save sharp && cd ..      # sharp isn't a project dependency
//   node web/scripts/build-aerial.mjs             # web/scripts/maui-aerial.webp -> web/src/assets/
//   AERIAL_DEBUG=/tmp/aerial node web/scripts/build-aerial.mjs   # + a PNG with outline and spots
//   cd web && npm ci                              # afterwards: back to the locked dependencies
//
// The picture (supplied for the project) is not georeferenced and its shore is
// stylised, so spot positions can't come from a plain projection. Instead:
// 1. find the picture's land (water = blue/cyan/white-surf pixels connected to
//    the border; small inlets closed) and trace its shoreline, clockwise;
// 2. pair that shoreline with the real Maui coastline (web/src/assets/
//    maui-coast.json, same projection as the site) through hand-picked
//    landmarks, matching the stretches between them by arc length;
// 3. fit a thin-plate spline map -> picture through those pairs and push each
//    spot's beach (config/spots.json) through it.
// Outputs: maui-aerial-{1536,960}.webp and maui-aerial-spots.json (pixel
// positions in the 1536x1024 frame).
import fs from 'node:fs'
import path from 'node:path'
import sharp from 'sharp'

const ROOT = process.env.MAKANI_ROOT ?? path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..')
const SRC = process.argv[2] ?? path.join(ROOT, 'web/scripts/maui-aerial.webp')
const OUT_DIR = path.join(ROOT, 'web/src/assets')
const DEBUG = process.env.AERIAL_DEBUG

const coast = JSON.parse(fs.readFileSync(path.join(ROOT, 'web/src/assets/maui-coast.json'), 'utf8'))
const spotsCfg = JSON.parse(fs.readFileSync(path.join(ROOT, 'config/spots.json'), 'utf8'))
const { bbox, width: W } = coast
const kx = Math.cos(((bbox.latMin + bbox.latMax) / 2) * (Math.PI / 180))
const sc = W / ((bbox.lonMax - bbox.lonMin) * kx)
const project = (lat, lon) => [(lon - bbox.lonMin) * kx * sc, (bbox.latMax - lat) * sc]

// Landmarks, clockwise from Nakalele Point: picture pixel (1536x1024) -> lat, lon.
const LANDMARKS = [
  ['Nakalele Point', [262, 44], [21.031, -156.594]],
  ['Waiehu', [470, 258], [20.915, -156.492]],
  ['Kahului Harbor', [530, 268], [20.898, -156.474]],
  ['Kanaha', [640, 228], [20.902, -156.435]],
  ['Paia', [722, 182], [20.915, -156.385]],
  ["Ho'okipa / Maliko", [830, 115], [20.94, -156.33]],
  ["Ke'anae", [1105, 205], [20.865, -156.148]],
  ["Wai'anapanapa", [1440, 330], [20.795, -156.02]],
  ['Hana', [1500, 425], [20.757, -155.982]],
  ['Kipahulu', [1385, 655], [20.665, -156.045]],
  ['Kaupo', [1210, 790], [20.635, -156.135]],
  ['Kanaio', [790, 975], [20.578, -156.32]],
  ['La Perouse', [478, 905], [20.598, -156.425]],
  ['North Kihei', [478, 545], [20.783, -156.468]],
  ["Ma'alaea Harbor", [425, 488], [20.792, -156.512]],
  ['McGregor Point', [330, 545], [20.776, -156.528]],
  ['Olowalu', [190, 492], [20.81, -156.623]],
  ['Lahaina', [100, 445], [20.865, -156.675]],
  ["Ka'anapali", [62, 290], [20.925, -156.695]],
  ['Napili', [85, 118], [20.995, -156.672]],
  ['Honolua', [165, 52], [21.015, -156.638]],
]

// ------------------------------------------------------------------ picture shoreline

const { data: img, info } = await sharp(SRC).removeAlpha().raw().toBuffer({ resolveWithObject: true })
const PW = info.width
const PH = info.height
if (PW !== 1536 || PH !== 1024) throw new Error(`landmarks were picked on a 1536x1024 picture, got ${PW}x${PH}`)

function looksLikeWater(i) {
  const r = img[i], g = img[i + 1], b = img[i + 2]
  if (b > r + 25) return true // deep blue and turquoise shallows (land is never much bluer than red)
  if (r > 110 && b > r + 8 && g > r + 8) return true // pale cyan foam (dark rainforest greens can be bluer than red)
  if (r > 185 && g > 185 && b > 185 && Math.max(r, g, b) - Math.min(r, g, b) < 40) return true // white surf
  return false
}

const ocean = new Uint8Array(PW * PH)
{
  const stack = []
  const push = (x, y) => {
    const k = y * PW + x
    if (!ocean[k] && looksLikeWater(k * 3)) {
      ocean[k] = 1
      stack.push(k)
    }
  }
  for (let x = 0; x < PW; x++) push(x, 0), push(x, PH - 1)
  for (let y = 0; y < PH; y++) push(0, y), push(PW - 1, y)
  while (stack.length) {
    const k = stack.pop()
    const x = k % PW
    const y = (k / PW) | 0
    if (x > 0) push(x - 1, y)
    if (x < PW - 1) push(x + 1, y)
    if (y > 0) push(x, y - 1)
    if (y < PH - 1) push(x, y + 1)
  }
}

let land = new Uint8Array(PW * PH)
{
  const label = new Int32Array(PW * PH)
  let best = 0, bestSize = 0, next = 1
  for (let k0 = 0; k0 < PW * PH; k0++) {
    if (ocean[k0] || label[k0]) continue
    const id = next++
    let size = 0
    const stack = [k0]
    label[k0] = id
    while (stack.length) {
      const k = stack.pop()
      size++
      const x = k % PW, y = (k / PW) | 0
      for (const [nx, ny] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
        if (nx < 0 || ny < 0 || nx >= PW || ny >= PH) continue
        const n = ny * PW + nx
        if (!ocean[n] && !label[n]) (label[n] = id), stack.push(n)
      }
    }
    if (size > bestSize) (bestSize = size), (best = id)
  }
  for (let k = 0; k < PW * PH; k++) land[k] = label[k] === best ? 1 : 0
}

function morph(mask, r, grow) {
  const tmp = new Uint8Array(PW * PH)
  const out = new Uint8Array(PW * PH)
  const hit = grow ? 1 : 0
  for (let y = 0; y < PH; y++) for (let x = 0; x < PW; x++) {
    let v = 1 - hit
    for (let k = -r; k <= r && v !== hit; k++) {
      const xx = x + k
      if (xx >= 0 && xx < PW && mask[y * PW + xx] === hit) v = hit
    }
    tmp[y * PW + x] = v
  }
  for (let y = 0; y < PH; y++) for (let x = 0; x < PW; x++) {
    let v = 1 - hit
    for (let k = -r; k <= r && v !== hit; k++) {
      const yy = y + k
      if (yy >= 0 && yy < PH && tmp[yy * PW + x] === hit) v = hit
    }
    out[y * PW + x] = v
  }
  return out
}
land = morph(morph(land, 6, true), 6, false) // close narrow inlets

function traceOutline(mask) {
  let start = -1
  for (let k = 0; k < PW * PH && start < 0; k++) if (mask[k]) start = k
  const dirs = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]]
  const pts = []
  let cx = start % PW, cy = (start / PW) | 0, d = 7
  const sx = cx, sy = cy
  for (let guard = 0; guard < PW * PH; guard++) {
    pts.push([cx, cy])
    let found = false
    for (let t = 0; t < 8; t++) {
      const nd = (d + 6 + t) % 8
      const nx = cx + dirs[nd][0], ny = cy + dirs[nd][1]
      if (nx >= 0 && ny >= 0 && nx < PW && ny < PH && mask[ny * PW + nx]) {
        cx = nx, cy = ny, d = nd, found = true
        break
      }
    }
    if (!found || (cx === sx && cy === sy)) break
  }
  return pts
}

const signedArea = (pts) => pts.reduce((a, [x, y], i) => {
  const [x2, y2] = pts[(i + 1) % pts.length]
  return a + (x * y2 - x2 * y)
}, 0) / 2
const clockwise = (pts) => (signedArea(pts) > 0 ? pts : [...pts].reverse()) // y down: positive = clockwise

function smooth(pts, r) {
  const n = pts.length
  return pts.map((_, i) => {
    let sx = 0, sy = 0
    for (let k = -r; k <= r; k++) {
      const [x, y] = pts[(i + k + n) % n]
      sx += x, sy += y
    }
    return [sx / (2 * r + 1), sy / (2 * r + 1)]
  })
}

function resample(pts, n) {
  const m = pts.length
  const cum = [0]
  for (let i = 1; i <= m; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i % m]
    cum.push(cum[i - 1] + Math.hypot(x1 - x0, y1 - y0))
  }
  const out = []
  let j = 0
  for (let k = 0; k < n; k++) {
    const s = (k / n) * cum[m]
    while (cum[j + 1] < s) j++
    const t = (s - cum[j]) / (cum[j + 1] - cum[j] || 1)
    const [x0, y0] = pts[j], [x1, y1] = pts[(j + 1) % m]
    out.push([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t])
  }
  return out
}

const N = 3000
const photoOutline = resample(clockwise(smooth(traceOutline(land), 6)), N)
const mauiRing = resample(clockwise([...coast.rings].sort((a, b) => b.length - a.length)[0]), N)

const nearestIdx = (pts, [x, y]) => {
  let best = 0, bd = Infinity
  pts.forEach(([px, py], i) => {
    const d = (px - x) ** 2 + (py - y) ** 2
    if (d < bd) (bd = d), (best = i)
  })
  return { i: best, d: Math.sqrt(bd) }
}

const marks = LANDMARKS.map(([name, p, [lat, lon]]) => {
  const a = nearestIdx(photoOutline, p)
  const b = nearestIdx(mauiRing, project(lat, lon))
  if (a.d > 25) console.warn(`landmark ${name}: ${a.d.toFixed(0)} px from the picture's shore`)
  return { name, pi: a.i, mi: b.i }
})
for (const key of ['pi', 'mi']) {
  const rel = marks.map((m) => (m[key] - marks[0][key] + N) % N)
  for (let k = 1; k < rel.length; k++) if (rel[k] <= rel[k - 1]) throw new Error(`landmark order broken at ${marks[k].name}`)
}

const pairs = []
for (let k = 0; k < marks.length; k++) {
  const a = marks[k], b = marks[(k + 1) % marks.length]
  const pLen = (b.pi - a.pi + N) % N
  const mLen = (b.mi - a.mi + N) % N
  const steps = Math.max(2, Math.round(mLen / 12))
  for (let s = 0; s < steps; s++) {
    const t = s / steps
    pairs.push({ map: mauiRing[(a.mi + Math.round(t * mLen)) % N], photo: photoOutline[(a.pi + Math.round(t * pLen)) % N] })
  }
}

// ------------------------------------------------------------------ thin-plate spline

function fitTps(src, dst, lambda) {
  const n = src.length
  const U = (r2) => (r2 === 0 ? 0 : r2 * Math.log(r2))
  const size = n + 3
  const A = Array.from({ length: size }, () => new Float64Array(size))
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const dx = src[i][0] - src[j][0], dy = src[i][1] - src[j][1]
      A[i][j] = U(dx * dx + dy * dy) + (i === j ? lambda : 0)
    }
    A[i][n] = A[n][i] = 1
    A[i][n + 1] = A[n + 1][i] = src[i][0]
    A[i][n + 2] = A[n + 2][i] = src[i][1]
  }
  const solve = (rhs) => {
    const M = A.map((row, i) => [...row, rhs[i]])
    for (let c = 0; c < size; c++) {
      let p = c
      for (let r = c + 1; r < size; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r
      ;[M[c], M[p]] = [M[p], M[c]]
      for (let r = 0; r < size; r++) {
        if (r === c) continue
        const f = M[r][c] / M[c][c]
        if (f) for (let k = c; k <= size; k++) M[r][k] -= f * M[c][k]
      }
    }
    return M.map((row, i) => row[size] / row[i])
  }
  const wu = solve([...dst.map((d) => d[0]), 0, 0, 0])
  const wv = solve([...dst.map((d) => d[1]), 0, 0, 0])
  return (x, y) => {
    let u = wu[n] + wu[n + 1] * x + wu[n + 2] * y
    let v = wv[n] + wv[n + 1] * x + wv[n + 2] * y
    for (let i = 0; i < n; i++) {
      const dx = x - src[i][0], dy = y - src[i][1]
      const k = U(dx * dx + dy * dy)
      u += wu[i] * k
      v += wv[i] * k
    }
    return [u, v]
  }
}

const tps = fitTps(pairs.map((p) => p.map), pairs.map((p) => p.photo), 120)
let worst = 0
for (const p of pairs) {
  const [u, v] = tps(...p.map)
  worst = Math.max(worst, Math.hypot(u - p.photo[0], v - p.photo[1]))
}
console.log(`${marks.length} landmarks, ${pairs.length} shore pairs, worst fit ${worst.toFixed(1)} px`)

// ------------------------------------------------------------------ outputs

const spots = {}
for (const s of spotsCfg.spots) {
  const [u, v] = tps(...project(s.beach.lat, s.beach.lon))
  const near = nearestIdx(photoOutline, [u, v])
  spots[s.id] = [Math.round(u * 10) / 10, Math.round(v * 10) / 10]
  console.log(`${s.id.padEnd(12)} ${spots[s.id].join(', ')}  (${near.d.toFixed(0)} px from the picture's shore)`)
}
// Measurement points shown as small dots: anemometers (observationStations) and buoys.
const stations = {}
for (const [kind, list] of [['anemometer', spotsCfg.observationStations ?? []], ['buoy', spotsCfg.buoys ?? []]]) {
  for (const s of list) {
    const [u, v] = tps(...project(s.lat, s.lon))
    stations[s.id] = { kind, name: s.name, xy: [Math.round(u * 10) / 10, Math.round(v * 10) / 10] }
    console.log(`${kind.padEnd(10)} ${s.id.padEnd(8)} ${stations[s.id].xy.join(', ')}`)
  }
}
fs.writeFileSync(
  path.join(OUT_DIR, 'maui-aerial-spots.json'),
  JSON.stringify({ source: 'web/scripts/build-aerial.mjs', width: PW, height: PH, spots, stations }, null, 2) + '\n',
)

for (const w of [1536, 960]) {
  const out = path.join(OUT_DIR, `maui-aerial-${w}.webp`)
  await sharp(SRC).resize(w).webp({ quality: w > 1000 ? 70 : 72, effort: 6, smartSubsample: true }).toFile(out)
  console.log(`wrote ${path.relative(ROOT, out)} (${(fs.statSync(out).size / 1024).toFixed(0)} KB)`)
}

if (DEBUG) {
  fs.mkdirSync(DEBUG, { recursive: true })
  const outline = photoOutline.filter((_, i) => i % 3 === 0).map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const dots = Object.entries(spots).map(([id, [x, y]]) =>
    `<circle cx="${x}" cy="${y}" r="7" fill="#fff" stroke="#000" stroke-width="2"/><text x="${x + 10}" y="${y - 8}" fill="#fff" font-size="16" font-family="Arial">${id}</text>`).join('')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${PW}" height="${PH}"><polygon points="${outline}" fill="none" stroke="#f33" stroke-width="1.5"/>${dots}</svg>`
  await sharp(SRC).composite([{ input: Buffer.from(svg) }]).png().toFile(path.join(DEBUG, 'aerial-spots.png'))
  console.log(`debug image in ${DEBUG}`)
}
