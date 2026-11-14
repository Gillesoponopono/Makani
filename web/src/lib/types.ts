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
  }
  sector: Sector
  sports: string[]
  daylight: boolean
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
  wrf: { dataset: string; coverageEnd: string; start: string; end: string; hours: number; status: string }
  ratings: { gustFactor: number; tooLightBelowKn: number; sports: SportBand[] }
  spots: { id: string; name: string; displayName: string }[]
}
