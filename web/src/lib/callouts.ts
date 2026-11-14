// Where the spot chips go on the island picture, in CSS pixels of the map box.
// Spots sit close together (Harbor, Kanahā and Sprecks are 1-2 km apart), so
// each chip is placed away from its dot and joined to it by a leader line:
//  - north-shore spots: a row of chips over the bay above them, centred on the
//    group and spread so they never overlap;
//  - spots listed in `land` (Harbor, Sprecks): a row below their dots, over the
//    island, so the bay row stays short and readable;
//  - spots listed in `over` (Kanahā -> Harbor): just above another spot's dot,
//    lined up with that spot's chip, so the bay row is left with the far ones;
//  - the others (Kīhei side): a column of chips to the left, over the channel.

export interface Dot {
  id: string
  x: number
  y: number
  w: number // chip width
}

export interface Chip {
  id: string
  cx: number // chip centre
  cy: number
}

export function layoutChips(
  dots: Dot[],
  box: { w: number; h: number },
  opts: {
    northBelowY: number
    land?: string[]
    over?: Record<string, string> // chip id -> spot whose dot it sits just above
    avoid?: { x: number; y: number }[] // small dots (measuring points) a row must not cover
    chipH?: number
    gap?: number
    rise?: number
    drop?: number
    side?: number
    pad?: number
  },
): Chip[] {
  const chipH = opts.chipH ?? 28
  const gap = opts.gap ?? 8
  const rise = opts.rise ?? 58 // how far above the highest north dot the row sits
  const side = opts.side ?? 16 // distance between a dot and its chip on the left
  const pad = opts.pad ?? 4
  const drop = opts.drop ?? 46 // how far below the lowest land dot that row sits
  const lift = chipH + 10 // how far above the other spot's dot an `over` chip sits
  const land = new Set(opts.land ?? [])
  const over = opts.over ?? {}
  const out: Chip[] = []
  const placed: (Chip & { w: number })[] = [] // chips a later row must not overlap
  const widthOf = (ds: Dot[]) => ds.reduce((s, d) => s + d.w, 0) + gap * (ds.length - 1)

  // One row centred on its dots' mean x, spread so the chips never overlap. If it
  // would cover a dot to avoid or a chip already placed, the whole row moves just
  // past it (the smaller move that stays inside the box).
  const clear = 7
  const add = (id: string, cx: number, cy: number, w: number) => {
    out.push({ id, cx, cy })
    placed.push({ id, cx, cy, w })
  }
  const row = (ds: Dot[], cy: number) => {
    const total = widthOf(ds)
    const mean = ds.reduce((s, d) => s + d.x, 0) / ds.length
    const fit = (l: number) => Math.max(pad, Math.min(l, box.w - pad - total))
    let left = fit(mean - total / 2)
    const obstacles = [
      ...(opts.avoid ?? []).map((p) => ({ x: p.x, y: p.y, hw: 0, hh: 0, m: clear })),
      ...placed.map((c) => ({ x: c.cx, y: c.cy, hw: c.w / 2, hh: chipH / 2, m: gap })),
    ]
    for (const o of obstacles) {
      if (Math.abs(o.y - cy) >= chipH / 2 + o.hh + o.m) continue
      if (o.x + o.hw + o.m <= left || o.x - o.hw - o.m >= left + total) continue
      const options = [o.x + o.hw + o.m, o.x - o.hw - o.m - total].filter((l) => fit(l) === l)
      if (options.length) left = options.sort((a, b) => Math.abs(a - left) - Math.abs(b - left))[0]
    }
    for (const d of ds) {
      add(d.id, left + d.w / 2, cy, d.w)
      left += d.w + gap
    }
  }

  const onLand = dots.filter((d) => land.has(d.id) && d.y < opts.northBelowY).sort((a, b) => a.x - b.x)
  if (onLand.length) {
    row(onLand, Math.min(box.h - pad - chipH / 2, Math.max(...onLand.map((d) => d.y)) + drop))
  }

  for (const [id, under] of Object.entries(over)) {
    const d = dots.find((x) => x.id === id)
    const target = dots.find((x) => x.id === under)
    if (!d || !target) continue
    const anchor = placed.find((c) => c.id === under)?.cx ?? target.x
    const cx = Math.max(pad + d.w / 2, Math.min(anchor, box.w - pad - d.w / 2))
    add(id, cx, Math.max(pad + chipH / 2, target.y - lift), d.w)
  }

  const north = dots
    .filter((d) => d.y < opts.northBelowY && !land.has(d.id) && !(d.id in over))
    .sort((a, b) => a.x - b.x)
  if (north.length) {
    const baseY = Math.max(pad + chipH / 2, Math.min(...north.map((d) => d.y)) - rise)
    // One row if it fits, else two staggered rows (every other chip one row up).
    const rows: Dot[][] = widthOf(north) <= box.w - 2 * pad ? [north] : [north.filter((_, i) => i % 2 === 1), north.filter((_, i) => i % 2 === 0)]
    const rowYs = rows.length === 1 ? [baseY] : [Math.max(pad + chipH / 2, baseY - chipH - gap), Math.max(pad + chipH / 2, baseY - chipH - gap) + chipH + gap]
    rows.forEach((ds, r) => row(ds, rowYs[r]))
  }

  const south = dots.filter((d) => d.y >= opts.northBelowY).sort((a, b) => a.y - b.y)
  let lastY = -Infinity
  for (const d of south) {
    const cx = Math.max(pad + d.w / 2, d.x - side - d.w / 2)
    let cy = Math.min(box.h - pad - chipH / 2, Math.max(d.y, lastY + chipH + gap))
    // Pushed against the left edge, a wide chip would sit on its own dot: lift it above.
    if (cx + d.w / 2 > d.x - 5 && Math.abs(cy - d.y) < chipH / 2 + 5) {
      cy = Math.max(lastY + chipH + gap, pad + chipH / 2, d.y - chipH / 2 - 9)
    }
    out.push({ id: d.id, cx, cy })
    lastY = cy
  }
  return out
}

/** Rough chip width: arrow disc + name + value, at the chip's font size. */
export function chipWidth(name: string, value: string, charW = 6.8): number {
  return 26 + 8 + name.length * charW + 6 + value.length * (charW + 0.6) + 22
}
