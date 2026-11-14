import type { Frames } from './map'
import type { Meta, SpotDoc } from './types'

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { cache: 'no-cache' })
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`)
  return res.json() as Promise<T>
}

let metaPromise: Promise<Meta> | null = null
const spotCache = new Map<string, Promise<SpotDoc>>()

export function loadMeta(): Promise<Meta> {
  metaPromise ??= getJson<Meta>('data/meta.json')
  return metaPromise
}

export function loadSpot(id: string): Promise<SpotDoc> {
  let p = spotCache.get(id)
  if (!p) {
    p = getJson<SpotDoc>(`data/spots/${encodeURIComponent(id)}.json`)
    spotCache.set(id, p)
  }
  return p
}

let framesPromise: Promise<Frames> | null = null

/** Wind grid for the map (~90 KB gzipped); loaded after the page has rendered. */
export function loadFrames(): Promise<Frames> {
  framesPromise ??= getJson<Frames>('data/map/frames.json')
  return framesPromise
}
