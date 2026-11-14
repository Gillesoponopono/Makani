// Sky per hour (pipeline/makani/sky.py): sunny, partly cloudy, cloudy or showers,
// from the model's sunshine at the ground and its rain. Icons share one 24x24 grid
// so the chart (inside its SVG) and HTML (SkyIcon.svelte) draw the same shapes.

import type { Hour, Sky } from './types'

export const SKY_LABEL: Record<Sky, string> = { sun: 'Sunny', partly: 'Partly cloudy', cloud: 'Cloudy', rain: 'Showers' }

export interface IconPart {
  d: string
  kind: 'sun' | 'ray' | 'cloud' | 'drop'
}

const CLOUD = 'M6.5 19h11a4 4 0 0 0 .4-8 5.6 5.6 0 0 0-10.8 1.7A3.2 3.2 0 0 0 6.5 19Z'
const ICONS: Record<Sky, IconPart[]> = {
  sun: [
    { kind: 'sun', d: 'M7.4 12a4.6 4.6 0 1 0 9.2 0a4.6 4.6 0 1 0-9.2 0Z' },
    { kind: 'ray', d: 'M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5.3 5.3 7 7M17 17l1.7 1.7M5.3 18.7 7 17M17 7l1.7-1.7' },
  ],
  partly: [
    { kind: 'sun', d: 'M5.4 9a3.6 3.6 0 1 0 7.2 0a3.6 3.6 0 1 0-7.2 0Z' },
    { kind: 'ray', d: 'M9 2.2V4M2.2 9H4M4.2 4.2l1.3 1.3M13.8 4.2l-1.3 1.3' },
    { kind: 'cloud', d: 'M9.5 20h9a3.5 3.5 0 0 0 .3-7 4.8 4.8 0 0 0-9.2 1.4 2.8 2.8 0 0 0-.1 5.6Z' },
  ],
  cloud: [{ kind: 'cloud', d: CLOUD }],
  rain: [
    { kind: 'cloud', d: 'M6.5 15h11a4 4 0 0 0 .4-8 5.6 5.6 0 0 0-10.8 1.7A3.2 3.2 0 0 0 6.5 15Z' },
    { kind: 'drop', d: 'M8.5 17.5l-1 3M12.5 17.5l-1 3M16.5 17.5l-1 3' },
  ],
}

export const skyIcon = (sky: Sky): IconPart[] => ICONS[sky]

export interface DaySky {
  sky: Sky // icon for the day
  label: string // "Sunny", "Mostly sunny, passing showers", "Showers likely"
}

/** The day's sky over its daylight hours: average sunshine, plus showers if any. */
export function daySky(hours: Hour[]): DaySky | null {
  const day = hours.filter((h) => h.daylight && h.sky)
  if (!day.length) return null
  const rain = day.filter((h) => h.sky === 'rain').length
  const suns = day.map((h) => h.sun).filter((v): v is number => v != null)
  const mean = suns.length ? suns.reduce((a, b) => a + Math.min(b, 1), 0) / suns.length : null
  if (rain >= 3 || (mean == null && rain)) return { sky: 'rain', label: 'Showers likely' }
  const [sky, base]: [Sky, string] =
    mean == null ? ['sun', 'Sunny'] : mean >= 0.85 ? ['sun', 'Sunny'] : mean >= 0.7 ? ['sun', 'Mostly sunny'] : mean >= 0.5 ? ['partly', 'Partly cloudy'] : ['cloud', 'Cloudy']
  return { sky, label: rain ? `${base}, passing showers` : base }
}
