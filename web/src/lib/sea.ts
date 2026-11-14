// Waves and tides for display: the `wave` on each hour and the `tide` block that
// pipeline/makani/waves.py and tides.py add to each spot file.
// Heights follow the temperature choice: metres with °C, feet with °F.

import type { Hour, Tide, TideExtreme, Wave, WaveType } from './types'
import type { TempUnit } from './units'

const FT_PER_M = 3.28084
const HOUR_MS = 3_600_000
/** Under this the pipeline calls the sea flat (pipeline/makani/waves.py FLAT_M). */
export const FLAT_M = 0.3

export const lengthUnit = (temp: TempUnit) => (temp === 'f' ? 'ft' : 'm')

const tidy = (s: string) => (s === '-0.0' ? '0.0' : s)

/** Wave height number alone: "1.2" (m), "4" or "0.7" (ft). */
export function waveNumber(m: number, temp: TempUnit): string {
  if (temp === 'f') {
    const ft = m * FT_PER_M
    return ft >= 3 ? String(Math.round(ft)) : ft.toFixed(1)
  }
  return m.toFixed(1)
}

export function waveHeight(m: number, temp: TempUnit): string {
  return `${waveNumber(m, temp)} ${lengthUnit(temp)}`
}

/** Tide height above MLLW; the data is in feet. "2.3 ft", "0.7 m". */
export function tideHeight(ft: number, temp: TempUnit): string {
  return `${tidy((temp === 'f' ? ft : ft / FT_PER_M).toFixed(1))} ${lengthUnit(temp)}`
}

export const WAVE_TYPE: Record<WaveType, { short: string; long: string }> = {
  flat: { short: 'Flat', long: 'Flat' },
  chop: { short: 'Chop', long: 'Wind chop' },
  swell: { short: 'Swell', long: 'Swell' },
  mixed: { short: 'Mixed', long: 'Swell + chop' },
}

/** Size band 0..5 (flat, < 2 ft, < 4 ft, < 6.5 ft, < 10 ft, bigger) for shading. */
export function waveBand(m: number): number {
  const edges = [0.3, 0.6, 1.2, 2, 3]
  const i = edges.findIndex((e) => m < e)
  return i === -1 ? edges.length : i
}

// ---------------------------------------------------------------- waves by day

export interface WaveCell {
  from: number // hour, start of the 3-hour cell
  wave: Wave
}

/** One cell per 3 hours (8 a day), valued at the cell's middle hour when it has data. */
export function waveCells(hours: (Hour | null)[]): (WaveCell | null)[] {
  const out: (WaveCell | null)[] = []
  for (let from = 0; from < 24; from += 3) {
    const pick = [from + 1, from, from + 2].map((i) => hours[i]?.wave).find((w) => w != null)
    out.push(pick ? { from, wave: pick } : null)
  }
  return out
}

/** Runs of cells with the same wave type, in hours [from, to). */
export function typeRuns(cells: (WaveCell | null)[]): { from: number; to: number; type: WaveType }[] {
  const runs: { from: number; to: number; type: WaveType }[] = []
  for (const c of cells) {
    const last = runs[runs.length - 1]
    if (!c) continue
    if (last && last.type === c.wave.type && last.to === c.from) last.to = c.from + 3
    else runs.push({ from: c.from, to: c.from + 3, type: c.wave.type })
  }
  return runs
}

/** Daylight wave range and most common type, for the day list. */
export function waveSummary(hours: Hour[]): { min: number; max: number; type: WaveType } | null {
  const ws = hours.filter((h) => h.daylight && h.wave).map((h) => h.wave!)
  if (!ws.length) return null
  const count = new Map<WaveType, number>()
  for (const w of ws) count.set(w.type, (count.get(w.type) ?? 0) + 1)
  const type = [...count].sort((a, b) => b[1] - a[1])[0][0]
  return { min: Math.min(...ws.map((w) => w.m)), max: Math.max(...ws.map((w) => w.m)), type }
}

// ---------------------------------------------------------------- tides

/** Hours from dateKey's HST midnight to an ISO time with offset. */
export function hoursInto(dateKey: string, iso: string): number {
  return (Date.parse(iso) - Date.parse(`${dateKey}T00:00:00-10:00`)) / HOUR_MS
}

export interface TideDay {
  pts: [number, number][] // [hour 0..24, ft], through the day's highs and lows
  extremes: (TideExtreme & { h: number })[]
}

/** The day's tide curve, with its highs and lows inserted so the line passes through them. */
export function tideDay(tide: Tide, dateKey: string): TideDay {
  const off = hoursInto(dateKey, tide.curve.start)
  const step = tide.curve.stepMinutes / 60
  const extremes = tide.extremes
    .map((e) => ({ ...e, h: hoursInto(dateKey, e.t) }))
    .filter((e) => e.h >= 0 && e.h <= 24)
  const pts: [number, number][] = []
  tide.curve.ft.forEach((v, i) => {
    const h = off + i * step
    if (v == null || h < 0 || h > 24) return
    if (extremes.some((e) => Math.abs(e.h - h) < 0.25)) return // keep the line smooth at the turn
    pts.push([h, v])
  })
  for (const e of extremes) pts.push([e.h, e.ft])
  pts.sort((a, b) => a[0] - b[0])
  return { pts, extremes }
}

/** Lowest and highest curve values over the whole block, so every day shares one scale. */
export function tideRange(tide: Tide): [number, number] {
  const vs = [...tide.curve.ft.filter((v): v is number => v != null), ...tide.extremes.map((e) => e.ft)]
  return [Math.min(...vs), Math.max(...vs)]
}

/** Tide height at a time, linear between curve samples. */
export function tideAt(tide: Tide, iso: string): number | null {
  const step = tide.curve.stepMinutes * 60_000
  const k = (Date.parse(iso) - Date.parse(tide.curve.start)) / step
  const i = Math.floor(k)
  const a = tide.curve.ft[i]
  if (a == null) return null
  if (k === i) return a
  const b = tide.curve.ft[i + 1]
  return b == null ? null : a + (b - a) * (k - i)
}

/** The next high or low after a time (rising when it's a high). */
export function nextExtreme(tide: Tide, iso: string): TideExtreme | null {
  const t = Date.parse(iso)
  return tide.extremes.find((e) => Date.parse(e.t) > t) ?? null
}
