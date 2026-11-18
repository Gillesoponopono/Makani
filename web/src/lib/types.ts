// Shapes of the JSON published by the pipeline (pipeline/makani/build.py).

export type Sector = 'good' | 'ok' | 'poor' | 'danger'

export interface Hour {
  t: string // ISO with -10:00 offset, e.g. 2026-11-13T14:00:00-10:00
  wrf: {
    kn: number
    dir: number // meteorological "from" degrees
    gustEst: number
    tairC: number | null
    rainMmH: number | null
    knAdj?: number | null // adjusted forecast (pipeline/makani/adjust.py), only where calibrated
  }
  sector: Sector
  sports: string[]
  daylight: boolean
  wave?: Wave | null // missing before schema 3, null when the model has no value
  waterC?: number | null // sea surface °C (PacIOOS ROMS); missing before schema 4
  sky?: Sky | null // from the model's sunshine and rain (schema 5); null at night without rain
  sun?: number | null // share of a clear sky's sunshine reaching the ground, daylight only
  nws?: NwsHour | null // NWS forecast grid (schema 6); null outside its runs
}

/** The National Weather Service forecast for the hour: knots, real gusts, "from" degrees. */
export interface NwsHour {
  kn: number
  gust: number | null
  dir: number | null
}

export type Sky = 'sun' | 'partly' | 'cloud' | 'rain'

export type WaveType = 'flat' | 'chop' | 'swell' | 'mixed'

export interface WavePart {
  m: number // significant height, metres
  per: number // peak period, seconds
  dir: number | null // coming from, degrees
}

/** Sea at the spot (pipeline/makani/waves.py): SWAN near the beach, split from WW3 offshore. */
export interface Wave {
  m: number
  per: number | null
  dir: number | null
  type: WaveType
  swell: WavePart | null
  chop: WavePart | null
}

export interface TideExtreme {
  t: string // ISO, HST
  ft: number // above MLLW
  type: 'H' | 'L'
}

/** NOAA tide predictions (pipeline/makani/tides.py), feet above MLLW. */
export interface Tide {
  station: string
  name: string
  kind: 'harmonic' | 'subordinate'
  datum: string
  units: 'ft'
  curve: { start: string; stepMinutes: number; ft: (number | null)[] }
  extremes: TideExtreme[]
}

export interface SunDay {
  date: string // YYYY-MM-DD (HST)
  rise: string // HH:MM (HST)
  set: string
}

export interface SpotDoc {
  id: string
  name: string
  displayName: string
  beach: { lat: number; lon: number }
  wrfCell: { lat: number; lon: number }
  sectors: Record<string, [number, number][]>
  hours: Hour[]
  sun: SunDay[]
  waves?: { status: 'ok' | 'sheltered' | 'error' | 'none'; swanCell?: { lat: number; lon: number }; ww3Cell?: { lat: number; lon: number } | null }
  tide?: Tide | null
  water?: { status: 'ok' | 'error' | 'none'; cell?: { lat: number; lon: number } }
  nws?: { status: 'ok' | 'error' | 'none'; gridpoint?: string; updated?: string | null }
  /** Where the adjusted forecast comes from; null for spots without a nearby anemometer. */
  adjusted?: {
    reference: string
    fitted: string | null
    maeRaw: number | null // typical miss in kiting hours, before / after, on months the fit didn't see
    maeAdj: number | null
    transferredFrom?: string | null // no anemometer here: a neighbour's correction, not checked
  } | null
}

export interface SportBand {
  id: string
  label: string
  short: string
  minKn: number
  maxKn: number | null
}

export interface Meta {
  schemaVersion: number
  generatedAt: string
  timezone: string
  utcOffsetHours: number
  /** run: when the model run started (UTC), from data built after 2026-11-17 */
  wrf: { dataset: string; coverageEnd: string; run?: string; start: string; end: string; hours: number; status: string }
  ratings: { gustFactor: number; tooLightBelowKn: number; sports: SportBand[] }
  spots: { id: string; name: string; displayName: string; beach?: { lat: number; lon: number } }[]
  map?: { file: string; hours: number; grid: [number, number] }
  waves?: { datasets: string[]; spots: Record<string, string> }
  tides?: { source: string; stations: Record<string, string> }
  water?: { dataset: string; spots: Record<string, string> }
  nws?: { source: string; spots: Record<string, string> }
}
