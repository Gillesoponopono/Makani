// Display units. The data stays in knots and °C; conversion happens at display time.

export type WindUnit = 'kn' | 'mph' | 'kmh'
export type TempUnit = 'c' | 'f'

export const WIND_UNITS: { id: WindUnit; label: string }[] = [
  { id: 'kn', label: 'kn' },
  { id: 'mph', label: 'mph' },
  { id: 'kmh', label: 'km/h' },
]

const KN_TO: Record<WindUnit, number> = { kn: 1, mph: 1.150779, kmh: 1.852 }

export function windIn(kn: number, unit: WindUnit): number {
  return kn * KN_TO[unit]
}

/** Whole number in the chosen unit, the way every label shows it. */
export function windLabel(kn: number, unit: WindUnit): number {
  return Math.round(windIn(kn, unit))
}

export function windUnitLabel(unit: WindUnit): string {
  return WIND_UNITS.find((u) => u.id === unit)!.label
}

export const cToF = (c: number) => (c * 9) / 5 + 32

export function tempLabel(c: number, unit: TempUnit): string {
  return `${Math.round(unit === 'f' ? cToF(c) : c)}°${unit === 'f' ? 'F' : 'C'}`
}

// ---------------------------------------------------------------- preferences

export interface Prefs {
  wind: WindUnit
  temp: TempUnit
  spot: string | null
}

const KEY = 'makani.prefs'
export const DEFAULT_PREFS: Prefs = { wind: 'kn', temp: 'c', spot: null }

/** Remembered per browser; storage can be missing or blocked, which is fine. */
export function loadPrefs(): Prefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? '{}')
    return {
      wind: WIND_UNITS.some((u) => u.id === raw.wind) ? raw.wind : DEFAULT_PREFS.wind,
      temp: raw.temp === 'f' ? 'f' : 'c',
      spot: typeof raw.spot === 'string' ? raw.spot : null,
    }
  } catch {
    return { ...DEFAULT_PREFS }
  }
}

export function savePrefs(p: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p))
  } catch {
    /* private mode: not remembered */
  }
}
