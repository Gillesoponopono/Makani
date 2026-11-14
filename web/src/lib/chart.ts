// Geometry helpers for the spot wind chart (WindChart.svelte). Pure functions, unit-tested.

export type Pt = [number, number]

/**
 * Smooth path through the points that never overshoots them (monotone cubic,
 * Steffen 1990, the same family as d3.curveMonotoneX). A curve that bulged above
 * the real values would invent wind the model never forecast.
 */
export function monotonePath(pts: Pt[]): string {
  const n = pts.length
  if (n === 0) return ''
  const f = (v: number) => Math.round(v * 10) / 10
  if (n === 1) return `M${f(pts[0][0])},${f(pts[0][1])}`
  const h: number[] = []
  const s: number[] = []
  for (let i = 0; i < n - 1; i++) {
    h[i] = pts[i + 1][0] - pts[i][0]
    s[i] = h[i] === 0 ? 0 : (pts[i + 1][1] - pts[i][1]) / h[i]
  }
  const t: number[] = new Array(n)
  for (let i = 1; i < n - 1; i++) {
    const p = (s[i - 1] * h[i] + s[i] * h[i - 1]) / (h[i - 1] + h[i])
    t[i] = (Math.sign(s[i - 1]) + Math.sign(s[i])) * Math.min(Math.abs(s[i - 1]), Math.abs(s[i]), 0.5 * Math.abs(p))
  }
  t[0] = endSlope(h[0], s[0], n > 2 ? t[1] : s[0])
  t[n - 1] = endSlope(h[n - 2], s[n - 2], n > 2 ? t[n - 2] : s[n - 2])
  let d = `M${f(pts[0][0])},${f(pts[0][1])}`
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = pts[i]
    const [x1, y1] = pts[i + 1]
    const k = h[i] / 3
    d += `C${f(x0 + k)},${f(y0 + t[i] * k)},${f(x1 - k)},${f(y1 - t[i + 1] * k)},${f(x1)},${f(y1)}`
  }
  return d
}

function endSlope(h: number, s: number, tNext: number): number {
  // One-sided three-point estimate, clamped so the end segment stays monotone.
  const t = (3 * s - tNext) / 2
  if (Math.sign(t) !== Math.sign(s)) return 0
  return Math.abs(t) > 3 * Math.abs(s) ? 3 * s : t
}

/** Splits a series with gaps (null) into runs of consecutive points. */
export function segments<T>(items: (T | null)[], toPt: (item: T, i: number) => Pt): Pt[][] {
  const out: Pt[][] = []
  let run: Pt[] = []
  items.forEach((it, i) => {
    if (it == null) {
      if (run.length) out.push(run)
      run = []
    } else {
      run.push(toPt(it, i))
    }
  })
  if (run.length) out.push(run)
  return out
}

/** Closed area under one run of points, down to the baseline y. */
export function areaPath(run: Pt[], baseY: number): string {
  if (run.length < 2) return ''
  const f = (v: number) => Math.round(v * 10) / 10
  return `${monotonePath(run)}L${f(run[run.length - 1][0])},${f(baseY)}L${f(run[0][0])},${f(baseY)}Z`
}

/**
 * Top of the knots axis, shared by every day so a 12 kn day never looks as big
 * as a 30 kn one: the highest gust rounded up to 5, at least 25.
 */
export function axisMax(values: number[], floor = 25): number {
  const top = values.length ? Math.max(...values) : 0
  const step = floor > 40 ? 10 : 5
  return Math.max(floor, Math.ceil(top / step) * step)
}

export function axisTicks(max: number): number[] {
  const step = max <= 20 ? 5 : max <= 60 ? 10 : 20
  const out: number[] = []
  for (let v = 0; v <= max + 1e-9; v += step) out.push(v)
  return out
}
