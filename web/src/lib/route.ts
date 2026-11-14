// Hash routes (GitHub Pages friendly):
//   #/kanaha            spot, default day (today, or tomorrow once today's sun has set)
//   #/kanaha/today      #/kanaha/tomorrow      #/kanaha/days      #/kanaha/2026-11-16
// The pre-redesign #/spot/<id> links still work.

export type View = 'today' | 'tomorrow' | 'days' | { date: string }

export interface Route {
  spot: string | null
  view: View | null
}

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  if (parts[0] === 'spot') parts.shift()
  const spot = parts[0] && /^[\w-]+$/.test(parts[0]) ? parts[0] : null
  const v = parts[1]
  let view: View | null = null
  if (v === 'today' || v === 'tomorrow' || v === 'days') view = v
  else if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) view = { date: v }
  return { spot, view }
}

export function routeHash(spot: string, view?: View | null): string {
  if (!view) return `#/${spot}`
  return `#/${spot}/${typeof view === 'string' ? view : view.date}`
}

export function sameView(a: View | null, b: View | null): boolean {
  if (a === null || b === null) return a === b
  if (typeof a === 'string' || typeof b === 'string') return a === b
  return a.date === b.date
}
