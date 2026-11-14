<script lang="ts">
  import Home from './routes/Home.svelte'
  import Spot from './routes/Spot.svelte'
  import { loadMeta } from './lib/data'
  import { ageHours, dateLabel, timeAgo } from './lib/format'

  type Route = { name: 'home' } | { name: 'spot'; id: string }

  function parse(hash: string): Route {
    const m = hash.match(/^#\/spot\/([\w-]+)/)
    return m ? { name: 'spot', id: m[1] } : { name: 'home' }
  }

  let route = $state<Route>(parse(location.hash))
  $effect(() => {
    const onHash = () => {
      route = parse(location.hash)
      window.scrollTo(0, 0)
    }
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  })

  const metaPromise = loadMeta()
</script>

<header class="site-head">
  <a class="brand" href="#/">
    <img src="./favicon.svg" alt="" width="28" height="28" />
    <span>Makani</span>
  </a>
  <span class="tagline">Maui kite wind forecast</span>
</header>

<main>
  {#await metaPromise}
    <p class="status">Loading forecast…</p>
  {:then meta}
    {@const age = ageHours(meta.generatedAt)}
    <p class="run">
      Model through {dateLabel(meta.wrf.end.slice(0, 10))} · updated {timeAgo(meta.generatedAt)}
    </p>
    {#if age > 36}
      <p class="banner bad" role="alert">Forecast data is {Math.round(age)} hours old. The model server may be down; treat it with caution.</p>
    {:else if age > 18}
      <p class="banner warn" role="status">Forecast data is {Math.round(age)} hours old.</p>
    {/if}

    {@const spotId = route.name === 'spot' ? route.id : null}
    {#if spotId && meta.spots.some((s) => s.id === spotId)}
      <Spot {meta} id={spotId} />
    {:else}
      <Home {meta} />
    {/if}
  {:catch err}
    <p class="status error">Forecast data isn't available right now ({err.message}).</p>
  {/await}
</main>

<footer class="site-foot">
  <p>
    Model data: <a href="https://www.pacioos.hawaii.edu/weather/model-wind-maui/">PacIOOS WRF Maui-Oahu</a>
    (University of Hawaiʻi, Yi-Leng Chen), funded by NOAA/IOOS. Coastline: US Census Bureau, via the
    <a href="https://geoportal.hawaii.gov/">Hawaiʻi Statewide GIS Program</a>.
  </p>
  <p>
    Forecasts can be wrong. This site doesn't replace checking conditions on the beach, local knowledge or
    official NWS warnings. Kite at your own risk.
  </p>
</footer>

<style>
  .site-head {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 800;
    font-size: 1.25rem;
    letter-spacing: -0.01em;
    color: inherit;
    text-decoration: none;
  }
  .tagline {
    color: var(--muted);
    font-size: 0.9rem;
  }
  main {
    max-width: 980px;
    margin: 0 auto;
    padding: 12px 16px 24px;
  }
  .run {
    margin: 0 0 12px;
    color: var(--muted);
    font-size: 0.82rem;
  }
  .banner {
    padding: 8px 12px;
    border-radius: 10px;
    font-size: 0.9rem;
    font-weight: 600;
  }
  .warn {
    background: var(--warn-bg);
    color: var(--warn-fg);
  }
  .bad {
    background: var(--danger-bg);
    color: var(--danger-fg);
  }
  .site-foot {
    max-width: 980px;
    margin: 0 auto;
    padding: 16px;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 0.8rem;
  }
  .site-foot a {
    color: inherit;
  }
</style>
