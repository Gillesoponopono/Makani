// Whether to warn that the forecast is old, and why (SPEC §8.10).
//
// Two clocks: the wind model run (University of Hawaiʻi WRF, one run a day that
// PacIOOS publishes about a day after it starts, and sometimes skips), and
// Makani's own refresh (every ~6 h: waves, sea temperature, tides). When the
// refresh is recent but the run is old, the model is late, not Makani.
import { HST_OFFSET_MS, ageHours, dateLong, hourLabel } from './format'
import type { Meta } from './types'

const RUN_HOURS = 168
/** A run normally appears ~1 day after it starts and is replaced a day later; the
 *  check fires every 4-8 h. Past this age the next run is late. */
export const RUN_LATE_HOURS = 56
/** Two runs missed. */
export const RUN_VERY_LATE_HOURS = 80
/** Refreshes run every ~6 h: past this, they are failing. */
export const REFRESH_LATE_HOURS = 24

export interface Freshness {
  level: 'warn' | 'bad'
  text: string
}

/** When the wind model run started (UTC ISO). Older data has no `run`: coverage end - 168 h. */
export function runStart(meta: Meta): string {
  return meta.wrf.run ?? new Date(Date.parse(meta.wrf.coverageEnd) - RUN_HOURS * 3600_000).toISOString()
}

/** "Sat, Nov 14, 2 PM" in Hawaii time. */
export function runLabel(meta: Meta): string {
  const hst = new Date(Date.parse(runStart(meta)) + HST_OFFSET_MS).toISOString()
  return `${dateLong(hst.slice(0, 10))}, ${hourLabel(hst)}`
}

export function freshness(meta: Meta, now = Date.now()): Freshness | null {
  const runAge = ageHours(runStart(meta), now)
  const refreshAge = ageHours(meta.generatedAt, now)
  const run = runLabel(meta)
  if (refreshAge > REFRESH_LATE_HOURS) {
    return {
      level: runAge > RUN_VERY_LATE_HOURS ? 'bad' : 'warn',
      text: `Forecast data last refreshed ${Math.round(refreshAge)} hours ago (wind model run of ${run}). The model server may be unreachable; treat it with caution.`,
    }
  }
  if (runAge > RUN_VERY_LATE_HOURS) {
    return {
      level: 'bad',
      text: `The wind forecast comes from the model run of ${run}, ${Math.floor(runAge / 24)} days ago: the University of Hawaiʻi model hasn't published a newer one. Treat it with caution.`,
    }
  }
  if (runAge > RUN_LATE_HOURS) {
    return {
      level: 'warn',
      text: `The wind forecast comes from the model run of ${run}: the University of Hawaiʻi model hasn't published a newer one yet. It still covers until ${dateLong(meta.wrf.end.slice(0, 10))}, less reliable for the later days.`,
    }
  }
  return null
}
