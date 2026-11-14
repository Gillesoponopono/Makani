<script lang="ts">
  import SpotPicker from './components/SpotPicker.svelte'
  import UnitToggles from './components/UnitToggles.svelte'
  import SpotDay from './routes/SpotDay.svelte'
  import SpotDays from './routes/SpotDays.svelte'
  import { loadMeta, loadSpot } from './lib/data'
  import { addDays, ageHours, dateLong, groupByDay, nowHoursHst, timeAgo, todayKey } from './lib/format'
  import { parseRoute, routeHash, type View } from './lib/route'
  import { loadPrefs, savePrefs, type Prefs, type TempUnit, type WindUnit } from './lib/units'
  import type { Meta, SpotDoc } from './lib/types'

  let route = $state(parseRoute(location.hash))
  $effect(() => {
    const onHash = () => {
      route = parseRoute(location.hash)
      window.scrollTo(0, 0)
      menuOpen = false
    }
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  })

  let prefs = $state<Prefs>(loadPrefs())
  $effect(() => savePrefs($state.snapshot(prefs)))
  const setWind = (u: WindUnit) => (prefs.wind = u)
  const setTemp = (u: TempUnit) => (prefs.temp = u)

  let menuOpen = $state(false)

  const metaPromise = loadMeta()
  const docsPromise: Promise<{ meta: Meta; docs: SpotDoc[] }> = metaPromise.then(async (meta) => ({
    meta,
    docs: await Promise.all(meta.spots.map((s) => loadSpot(s.id))),
  }))

  const today = todayKey()
  const tomorrow = addDays(today, 1)

  function spotIdFor(meta: Meta): string {
    const ids = meta.spots.map((s) => s.id)
    for (const c of [route.spot, prefs.spot, 'kanaha']) if (c && ids.includes(c)) return c
    return ids[0]
  }

  // No day in the URL: today, or tomorrow once today's sun has set at the spot.
  function resolveView(doc: SpotDoc): View {
    if (route.view) return route.view
    const sun = doc.sun.find((s) => s.date === today)
    if (sun) {
      const [h, m] = sun.set.split(':').map(Number)
      if (nowHoursHst() > h + m / 60) return 'tomorrow'
    }
    return 'today'
  }

  $effect(() => {
    if (route.spot && route.spot !== prefs.spot) prefs.spot = route.spot
  })

  function dateOf(view: View): string | null {
    if (view === 'today') return today
    if (view === 'tomorrow') return tomorrow
    if (view === 'days') return null
    return view.date
  }
  // A dated view of today/tomorrow highlights that tab; later dates highlight "days".
  function tabOf(view: View): 'today' | 'tomorrow' | 'days' {
    const d = dateOf(view)
    if (d === today) return 'today'
    if (d === tomorrow) return 'tomorrow'
    return 'days'
  }

  function scrollToId(id: string) {
    menuOpen = false
    const el = document.getElementById(id)
    if (el instanceof HTMLDetailsElement) el.open = true
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
</script>

{#await docsPromise}
  <header class="top"><div class="bar"><span class="brand display"><span class="logo"></span>Makani</span></div></header>
  <main><p class="status">Loading forecast…</p></main>
{:then { meta, docs }}
  {@const spotId = spotIdFor(meta)}
  {@const doc = docs.find((d) => d.id === spotId)!}
  {@const view = resolveView(doc)}
  {@const tab = tabOf(view)}
  {@const dayCount = groupByDay(doc.hours, doc.sun).filter((d) => d.date >= today).length}
  {@const tabs = [
    { id: 'today', label: 'Today', href: routeHash(spotId, 'today') },
    { id: 'tomorrow', label: 'Tomorrow', href: routeHash(spotId, 'tomorrow') },
    { id: 'days', label: `${dayCount} Days`, href: routeHash(spotId, 'days') },
  ]}
  {@const age = ageHours(meta.generatedAt)}

  <header class="top">
    <div class="bar">
      <a class="brand display" href={routeHash(spotId)} aria-label="Makani home">
        <svg class="logo" viewBox="0 0 40 24" width="40" height="24" aria-hidden="true">
          <defs>
            <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stop-color="#5ee7df" />
              <stop offset="1" stop-color="#2bb3d6" />
            </linearGradient>
          </defs>
          <path d="M2 15c5-7 11-7 16-2s10 5 16-3c-2 8-8 12-15 8S7 12 2 15Z" fill="url(#logo-g)" />
          <path d="M6 9c4-4 9-4 13-1s8 3 13-1" fill="none" stroke="url(#logo-g)" stroke-width="2.2" stroke-linecap="round" />
        </svg>
        Makani
      </a>
      <span class="sep" aria-hidden="true"></span>
      <SpotPicker
        spots={meta.spots}
        current={spotId}
        hrefFor={(id) => routeHash(id, route.view)}
      />

      <nav class="tabs" aria-label="Forecast day">
        {#each tabs as t (t.id)}
          <a href={t.href} class:active={tab === t.id} aria-current={tab === t.id ? 'page' : undefined}>{t.label}</a>
        {/each}
      </nav>

      <div class="units"><UnitToggles wind={prefs.wind} temp={prefs.temp} onwind={setWind} ontemp={setTemp} /></div>

      <div class="menu-wrap">
        <button type="button" class="menu-btn" aria-label="Menu" aria-expanded={menuOpen} onclick={() => (menuOpen = !menuOpen)}>
          <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
        </button>
        {#if menuOpen}
          <div class="menu card">
            <div class="menu-units">
              <div class="menu-label">Units</div>
              <UnitToggles wind={prefs.wind} temp={prefs.temp} onwind={setWind} ontemp={setTemp} />
            </div>
            {#if view !== 'days'}
              <button type="button" onclick={() => scrollToId('hourly')}>Hourly table</button>
            {/if}
            <button type="button" onclick={() => scrollToId('credits')}>Data &amp; credits</button>
          </div>
        {/if}
      </div>
    </div>
  </header>

  <main>
    {#if age > 36}
      <p class="banner bad" role="alert">Forecast data is {Math.round(age)} hours old. The model server may be down; treat it with caution.</p>
    {:else if age > 18}
      <p class="banner warn" role="status">Forecast data is {Math.round(age)} hours old.</p>
    {/if}

    {#if view === 'days'}
      <SpotDays {meta} {doc} wind={prefs.wind} temp={prefs.temp} dayHref={(d) => routeHash(spotId, { date: d })} />
    {:else}
      <SpotDay
        {meta}
        {docs}
        {doc}
        date={dateOf(view)!}
        wind={prefs.wind}
        temp={prefs.temp}
        ontemp={setTemp}
        hrefFor={(id) => routeHash(id, route.view)}
      />
    {/if}

    <p class="run">PacIOOS WRF model run through {dateLong(meta.wrf.end.slice(0, 10))} · updated {timeAgo(meta.generatedAt)}</p>
  </main>

  <nav class="tabbar" aria-label="Forecast day">
    {#each tabs as t (t.id)}
      <a href={t.href} class:active={tab === t.id} aria-current={tab === t.id ? 'page' : undefined}>
        {#if t.id === 'today'}
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M4 11 12 4l8 7v8a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1Z" /></svg>
        {:else if t.id === 'tomorrow'}
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M4 10h16M9 3v4M15 3v4" /></svg>
        {:else}
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M5 20v-6M10 20V9M15 20v-8M20 20V5" /></svg>
        {/if}
        <span>{t.label}</span>
      </a>
    {/each}
  </nav>
{:catch err}
  <main><p class="status error">Forecast data isn't available right now ({err.message}).</p></main>
{/await}

<footer class="foot" id="credits">
  <p>
    Wind model: <a href="https://www.pacioos.hawaii.edu/weather/model-wind-maui/">PacIOOS WRF Maui-Oʻahu</a> (University of
    Hawaiʻi, Yi-Leng Chen), funded by NOAA/IOOS. Waves: <a href="https://www.pacioos.hawaii.edu/waves/model-maui/">PacIOOS
    SWAN Maui</a> and <a href="https://www.pacioos.hawaii.edu/waves/model-hawaii/">WaveWatch III Hawaiʻi</a>. Tides:
    <a href="https://tidesandcurrents.noaa.gov/">NOAA CO-OPS</a> predictions for Kahului (1615680) and Makena (1615202).
    Spots placed on the picture using the US Census coastline (Hawaiʻi Statewide GIS Program). The island picture is
    illustrative.
  </p>
  <p>
    Forecasts can be wrong. This site doesn't replace checking conditions on the beach, local knowledge or official NWS
    warnings. Kite at your own risk.
  </p>
</footer>

<style>
  .top {
    position: sticky;
    top: 0;
    z-index: 10;
    background: rgba(7, 22, 38, 0.82);
    -webkit-backdrop-filter: blur(14px);
    backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--border);
  }
  .bar {
    display: flex;
    align-items: center;
    gap: 14px;
    max-width: 1100px;
    margin: 0 auto;
    padding: 10px 20px;
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--text);
    text-decoration: none;
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  .logo {
    flex: none;
  }
  .sep {
    width: 1px;
    height: 26px;
    background: var(--border-strong);
  }
  .tabs {
    display: flex;
    gap: 26px;
    margin-left: auto;
  }
  .tabs a {
    position: relative;
    padding: 8px 2px;
    color: var(--muted);
    text-decoration: none;
    font-weight: 500;
    white-space: nowrap;
  }
  .tabs a:hover {
    color: var(--text);
  }
  .tabs a.active {
    color: var(--text);
    font-weight: 700;
  }
  .tabs a.active::after {
    content: '';
    position: absolute;
    left: -8px;
    right: -8px;
    bottom: -11px;
    height: 3px;
    border-radius: 3px;
    background: var(--accent);
  }
  .units {
    margin-left: 18px;
  }
  .menu-wrap {
    position: relative;
  }
  .menu-btn {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    cursor: pointer;
  }
  .menu-btn:hover {
    background: var(--surface-2);
  }
  .menu-btn path {
    fill: none;
    stroke: var(--text);
    stroke-width: 2;
    stroke-linecap: round;
  }
  .menu {
    position: absolute;
    right: 0;
    top: calc(100% + 8px);
    z-index: 20;
    display: grid;
    gap: 4px;
    min-width: 230px;
    padding: 8px;
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.5);
  }
  .menu > button {
    padding: 10px 12px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    text-align: left;
    cursor: pointer;
    font-weight: 500;
  }
  .menu > button:hover {
    background: var(--surface-3);
  }
  .menu-units {
    display: none;
    padding: 6px 8px 10px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
  }
  .menu-label {
    color: var(--muted);
    font-size: 0.78rem;
    margin-bottom: 6px;
  }
  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 22px 20px 30px;
  }
  .banner {
    padding: 10px 14px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 0.92rem;
  }
  .warn {
    background: var(--warn-bg);
    color: var(--ok);
  }
  .bad {
    background: var(--danger-bg);
    color: var(--danger);
  }
  .run {
    margin: 18px 0 0;
    color: var(--faint);
    font-size: 0.8rem;
  }
  .foot {
    max-width: 1100px;
    margin: 0 auto;
    padding: 18px 20px 28px;
    border-top: 1px solid var(--border);
    color: var(--faint);
    font-size: 0.8rem;
  }
  .foot a {
    color: var(--muted);
  }
  .tabbar {
    display: none;
  }

  @media (max-width: 1080px) {
    .units {
      display: none;
    }
    .menu-units {
      display: block;
    }
  }
  @media (max-width: 760px) {
    .bar {
      padding: 8px 12px;
      gap: 6px;
    }
    .brand {
      font-size: 1.3rem;
      gap: 8px;
    }
    .sep,
    .tabs {
      display: none;
    }
    .menu-wrap {
      margin-left: auto;
    }
    main {
      padding: 14px 12px 24px;
    }
    .foot {
      padding-bottom: 96px; /* room for the tab bar */
    }
    .tabbar {
      position: fixed;
      left: 10px;
      right: 10px;
      bottom: calc(10px + env(safe-area-inset-bottom));
      z-index: 15;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      padding: 6px;
      border-radius: 20px;
      background: rgba(13, 34, 54, 0.92);
      -webkit-backdrop-filter: blur(14px);
      backdrop-filter: blur(14px);
      border: 1px solid var(--border-strong);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
    }
    .tabbar a {
      position: relative;
      display: grid;
      justify-items: center;
      gap: 2px;
      padding: 6px 0 8px;
      color: var(--muted);
      text-decoration: none;
      font-size: 0.78rem;
      font-weight: 600;
    }
    .tabbar svg {
      fill: none;
      stroke: currentColor;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .tabbar a.active {
      color: var(--accent-2);
    }
    .tabbar a.active::after {
      content: '';
      position: absolute;
      left: 22%;
      right: 22%;
      bottom: 0;
      height: 3px;
      border-radius: 3px;
      background: var(--accent);
    }
  }
</style>
