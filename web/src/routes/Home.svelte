<script lang="ts">
  import Arrow from '../components/Arrow.svelte'
  import SportChips from '../components/SportChips.svelte'
  import WindMap from '../components/WindMap.svelte'
  import { loadSpot } from '../lib/data'
  import { bestWindow, compass, currentHourKey, dayName, groupByDay, knBand, todayKey, windowLabel } from '../lib/format'
  import type { Meta, SpotDoc } from '../lib/types'

  let { meta }: { meta: Meta } = $props()

  const spotsPromise = $derived(Promise.all(meta.spots.map((s) => loadSpot(s.id))))

  function nowHour(doc: SpotDoc) {
    const key = currentHourKey()
    return doc.hours.find((h) => h.t.startsWith(key)) ?? doc.hours[0]
  }
</script>

{#await spotsPromise}
  <p class="status">Loading spots…</p>
{:then docs}
  <div class="cards">
    {#each docs as doc (doc.id)}
      {@const now = nowHour(doc)}
      {@const days = groupByDay(doc.hours, doc.sun).filter((d) => d.date >= todayKey()).slice(0, 3)}
      <a class="card" href="#/spot/{doc.id}">
        <div class="card-head">
          <h2>{doc.displayName}</h2>
          <span class="go" aria-hidden="true">›</span>
        </div>
        <div class="now">
          <span class="kn-pill kn-{knBand(now.wrf.kn)}">{Math.round(now.wrf.kn)}<small> kn</small></span>
          <span class="dir"><Arrow dir={now.wrf.dir} /> {compass(now.wrf.dir)}</span>
          <span class="gust">gust ~{Math.round(now.wrf.gustEst)}</span>
          <span class="label">now</span>
        </div>
        <div class="now-gear"><SportChips hour={now} bands={meta.ratings.sports} /></div>
        <ul class="windows">
          {#each days as day (day.date)}
            {@const w = bestWindow(day.hours)}
            <li>
              <span class="day">{dayName(day.date)}</span>
              {#if w}
                <span class="win">{windowLabel(w)}</span>
                <span class="range">{w.minKn}–{w.maxKn} kn</span>
              {:else}
                <span class="win muted">no kiteable window</span>
              {/if}
            </li>
          {/each}
        </ul>
      </a>
    {/each}
  </div>
  <p class="hint">Best window = longest daylight stretch suited to at least one sport, with a safe wind direction. Tap a spot for the hourly forecast.</p>
  <WindMap {docs} />
{:catch err}
  <p class="status error">Couldn't load forecast data ({err.message}).</p>
{/await}

<style>
  .cards {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  }
  .card {
    display: block;
    padding: 14px 16px;
    border-radius: 14px;
    background: var(--surface);
    border: 1px solid var(--border);
    color: inherit;
    text-decoration: none;
    transition: border-color 0.15s;
  }
  .card:hover,
  .card:focus-visible {
    border-color: var(--accent);
  }
  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  h2 {
    margin: 0 0 10px;
    font-size: 1.1rem;
  }
  .go {
    color: var(--muted);
    font-size: 1.4rem;
    line-height: 1;
  }
  .now {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .kn-pill {
    font-size: 1.6rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 10px;
    font-variant-numeric: tabular-nums;
  }
  .kn-pill small {
    font-size: 0.8rem;
    font-weight: 600;
  }
  .dir {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-weight: 600;
  }
  .gust,
  .label {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .label {
    margin-left: auto;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.7rem;
  }
  .now-gear {
    margin: 8px 0 10px;
    min-height: 1.3em;
  }
  .windows {
    list-style: none;
    margin: 0;
    padding: 8px 0 0;
    border-top: 1px solid var(--border);
    display: grid;
    gap: 4px;
    font-size: 0.88rem;
  }
  .windows li {
    display: grid;
    grid-template-columns: 6.5em 1fr auto;
    gap: 8px;
  }
  .day {
    color: var(--muted);
  }
  .win {
    font-weight: 600;
  }
  .range {
    font-variant-numeric: tabular-nums;
  }
  .muted {
    color: var(--muted);
    font-weight: 400;
  }
  .hint {
    color: var(--muted);
    font-size: 0.82rem;
    margin-top: 16px;
  }
</style>
