import type { Hour, SunDay } from './types'

export const HST_OFFSET_MS = -10 * 3600_000 // Hawaii: UTC-10, no DST

/** "YYYY-MM-DDTHH" for the current hour in HST, comparable with hour.t.slice(0, 13). */
export function currentHourKey(now = Date.now()): string {
  return new Date(now + HST_OFFSET_MS).toISOString().slice(0, 13)
}

export function todayKey(now = Date.now()): string {
  return currentHourKey(now).slice(0, 10)
}

export function addDays(dateKey: string, n: number): string {
  const d = new Date(`${dateKey}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

const WEEKDAY = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTH = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function dateLabel(dateKey: string): string {
  const d = new Date(`${dateKey}T00:00:00Z`)
  return `${WEEKDAY[d.getUTCDay()]} ${MONTH[d.getUTCMonth()]} ${d.getUTCDate()}`
}

/** "Fri" — short enough for slider ticks on a phone. */
export function weekdayShort(dateKey: string): string {
  return WEEKDAY[new Date(`${dateKey}T00:00:00Z`).getUTCDay()]
}

export function dayName(dateKey: string, today = todayKey()): string {
  if (dateKey === today) return 'Today'
  if (dateKey === addDays(today, 1)) return 'Tomorrow'
  return dateLabel(dateKey)
}

/** 0 for today, 1 for tomorrow, ... */
export function dayIndex(dateKey: string, today = todayKey()): number {
  return Math.round((Date.parse(`${dateKey}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / 86400_000)
}

export function confidence(idx: number): { label: string; level: 'normal' | 'lower' | 'low' } {
  if (idx <= 1) return { label: '', level: 'normal' }
  if (idx <= 3) return { label: 'Lower confidence', level: 'lower' }
  return { label: 'Low confidence', level: 'low' }
}

/** "2 PM" from an ISO string already in HST. */
export function hourLabel(t: string): string {
  const h = Number(t.slice(11, 13))
  return `${h % 12 || 12} ${h < 12 ? 'AM' : 'PM'}`
}

/** "6:34 AM" from "06:34". */
export function clockLabel(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number)
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`
}

const POINTS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
const WORDS = [
  'North', 'North-northeast', 'Northeast', 'East-northeast', 'East', 'East-southeast', 'Southeast', 'South-southeast',
  'South', 'South-southwest', 'Southwest', 'West-southwest', 'West', 'West-northwest', 'Northwest', 'North-northwest',
]
const point = (deg: number) => Math.floor(((deg % 360) + 360) % 360 / 22.5 + 0.5) % 16
export function compass(deg: number): string {
  return POINTS[point(deg)]
}
/** "East-northeast" for 68°. */
export function compassWords(deg: number): string {
  return WORDS[point(deg)]
}

/** "Sat, Nov 14" */
export function dateLong(dateKey: string): string {
  const d = new Date(`${dateKey}T00:00:00Z`)
  return `${WEEKDAY[d.getUTCDay()]}, ${MONTH[d.getUTCMonth()]} ${d.getUTCDate()}`
}

/** "Saturday" */
export function weekdayLong(dateKey: string): string {
  return ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][new Date(`${dateKey}T00:00:00Z`).getUTCDay()]
}

/** Fractional HST hour now, e.g. 14.5 at 2:30 PM. */
export function nowHoursHst(now = Date.now()): number {
  const d = new Date(now + HST_OFFSET_MS)
  return d.getUTCHours() + d.getUTCMinutes() / 60
}

/** Wind colour band index used by .kn-0 … .kn-6 (same thresholds as the map legend, §8.4). */
export function knBand(kn: number): number {
  const edges = [10, 15, 20, 25, 30, 35]
  const i = edges.findIndex((e) => kn < e)
  return i === -1 ? edges.length : i
}

export function timeAgo(iso: string, now = Date.now()): string {
  const mins = Math.max(0, Math.round((now - Date.parse(iso)) / 60_000))
  if (mins < 60) return `${mins} min ago`
  const h = Math.round(mins / 60)
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} days ago`
}

export function ageHours(iso: string, now = Date.now()): number {
  return (now - Date.parse(iso)) / 3600_000
}

export interface Day {
  date: string
  hours: Hour[]
  sun?: SunDay
}

export function groupByDay(hours: Hour[], sun: SunDay[]): Day[] {
  const days: Day[] = []
  for (const h of hours) {
    const date = h.t.slice(0, 10)
    let day = days[days.length - 1]
    if (!day || day.date !== date) {
      day = { date, hours: [], sun: sun.find((s) => s.date === date) }
      days.push(day)
    }
    day.hours.push(h)
  }
  return days
}

export interface Window {
  start: Hour
  end: Hour
  hours: number
  minKn: number
  maxKn: number
}

/** Longest run of consecutive daylight hours that suit at least one sport. */
export function bestWindow(hours: Hour[]): Window | null {
  let best: Hour[] = []
  let run: Hour[] = []
  for (const h of hours) {
    if (h.daylight && h.sports.length > 0) {
      run.push(h)
      if (run.length > best.length) best = [...run]
    } else {
      run = []
    }
  }
  if (best.length === 0) return null
  const kns = best.map((h) => h.wrf.kn)
  return {
    start: best[0],
    end: best[best.length - 1],
    hours: best.length,
    minKn: Math.round(Math.min(...kns)),
    maxKn: Math.round(Math.max(...kns)),
  }
}

/** "8 AM–5 PM": the window ends at the end of its last hour. */
export function windowLabel(w: Window): string {
  const endHour = (Number(w.end.t.slice(11, 13)) + 1) % 24
  const end = `${endHour % 12 || 12} ${endHour < 12 ? 'AM' : 'PM'}`
  return `${hourLabel(w.start.t)}–${end}`
}
