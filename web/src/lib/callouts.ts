// Where the spot chips go on the island picture, in CSS pixels of the map box.
// Spots sit close together (Harbor, Kanahā and Sprecks are 1-2 km apart), so
// each chip is placed away from its dot and joined to it by a leader line:
//  - north-shore spots: a row of chips over the bay above them, centred on the
//    group and spread so they never overlap;
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
  opts: { northBelowY: number; chipH?: number; gap?: number; rise?: number; side?: number; pad?: number },
): Chip[] {
  const chipH = opts.chipH ?? 28
  const gap = opts.gap ?? 8
  const rise = opts.rise ?? 58 // how far above the highest north dot the row sits
  const side = opts.side ?? 16 // distance between a dot and its chip on the left
  const pad = opts.pad ?? 4
  const out: Chip[] = []

  const north = dots.filter((d) => d.y < opts.northBelowY).sort((a, b) => a.x - b.x)
  if (north.length) {
    const baseY = Math.max(pad + chipH / 2, Math.min(...north.map((d) => d.y)) - rise)
    const widthOf = (ds: Dot[]) => ds.reduce((s, d) => s + d.w, 0) + gap * (ds.length - 1)
    // One row if it fits, else two staggered rows (every other chip one row up).
    const rows: Dot[][] = widthOf(north) <= box.w - 2 * pad ? [north] : [north.filter((_, i) => i % 2 === 1), north.filter((_, i) => i % 2 === 0)]
    const rowYs = rows.length === 1 ? [baseY] : [Math.max(pad + chipH / 2, baseY - chipH - gap), Math.max(pad + chipH / 2, baseY - chipH - gap) + chipH + gap]
    rows.forEach((row, r) => {
      const total = widthOf(row)
      const mean = row.reduce((s, d) => s + d.x, 0) / row.length
      let left = Math.max(pad, Math.min(mean - total / 2, box.w - pad - total))
      for (const d of row) {
        out.push({ id: d.id, cx: left + d.w / 2, cy: rowYs[r] })
        left += d.w + gap
      }
    })
  }

  const south = dots.filter((d) => d.y >= opts.northBelowY).sort((a, b) => a.y - b.y)
  let lastY = -Infinity
  for (const d of south) {
    const cx = Math.max(pad + d.w / 2, d.x - side - d.w / 2)
    const cy = Math.min(box.h - pad - chipH / 2, Math.max(d.y, lastY + chipH + gap))
    out.push({ id: d.id, cx, cy })
    lastY = cy
  }
  return out
}

/** Rough chip width: arrow disc + name + value, at the chip's font size. */
export function chipWidth(name: string, value: string, charW = 6.8): number {
  return 26 + 8 + name.length * charW + 6 + value.length * (charW + 0.6) + 22
}
