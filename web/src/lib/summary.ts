// One day at a glance for the hero tiles: wind, air, water and waves over daylight
// hours (all hours when the day has none, e.g. a day cut short by the model run).

import type { Hour, WaveType } from './types'

export interface Range {
  min: number
  max: number
}

export interface DaySummary {
  wind: (Range & { gust: number; dir: number }) | null // kn, "from" degrees
  air: Range | null // °C
  water: number | null // °C, mean
  waves: (Range & { per: Range | null; type: WaveType }) | null // m, s
}

const range = (vs: number[]): Range | null => (vs.length ? { min: Math.min(...vs), max: Math.max(...vs) } : null)

/** Circular mean of "from" directions, so 350° and 10° average to 0°, not 180°.
 *  With weights (wind speeds), light and variable hours count for little. */
export function meanDir(degs: number[], weights?: number[]): number {
  let x = 0
  let y = 0
  degs.forEach((d, i) => {
    const w = weights?.[i] ?? 1
    x += w * Math.cos((d * Math.PI) / 180)
    y += w * Math.sin((d * Math.PI) / 180)
  })
  return Math.round(((Math.atan2(y, x) * 180) / Math.PI + 360) % 360)
}

export function daySummary(hours: Hour[]): DaySummary {
  const day = hours.some((h) => h.daylight) ? hours.filter((h) => h.daylight) : hours

  const kn = range(day.map((h) => h.wrf.kn))
  const wind = kn && {
    ...kn,
    gust: Math.max(...day.map((h) => h.wrf.gustEst)),
    dir: meanDir(
      day.map((h) => h.wrf.dir),
      day.map((h) => h.wrf.kn),
    ),
  }

  const air = range(day.map((h) => h.wrf.tairC).filter((v): v is number => v != null))

  const ws = day.map((h) => h.waterC).filter((v): v is number => v != null)
  const water = ws.length ? ws.reduce((a, b) => a + b, 0) / ws.length : null

  const wv = day.map((h) => h.wave).filter((w) => w != null)
  let waves: DaySummary['waves'] = null
  if (wv.length) {
    const count = new Map<WaveType, number>()
    for (const w of wv) count.set(w.type, (count.get(w.type) ?? 0) + 1)
    waves = {
      ...range(wv.map((w) => w.m))!,
      per: range(wv.map((w) => w.per).filter((v): v is number => v != null)),
      type: [...count].sort((a, b) => b[1] - a[1])[0][0],
    }
  }
  return { wind, air, water, waves }
}

/** "15–21", or "21" when both ends show the same. */
export function rangeText(r: Range, fmt: (v: number) => string | number): string {
  const a = String(fmt(r.min))
  const b = String(fmt(r.max))
  return a === b ? b : `${a}–${b}`
}
