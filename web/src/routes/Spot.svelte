<script lang="ts">
  import Arrow from '../components/Arrow.svelte'
  import SportChips from '../components/SportChips.svelte'
  import { loadSpot } from '../lib/data'
  import {
    bestWindow,
    cToF,
    clockLabel,
    compass,
    confidence,
    currentHourKey,
    dateLabel,
    dayIndex,
    dayName,
    groupByDay,
    hourLabel,
    knBand,
    todayKey,
    windowLabel,
  } from '../lib/format'
  import type { Meta, Sector } from '../lib/types'

  let { meta, id }: { meta: Meta; id: string } = $props()

  const docPromise = $derived(loadSpot(id))
  const nowKey = currentHourKey()

  const SECTOR: Record<Sector, { mark: string; label: string }> = {
    good: { mark: '✓', label: 'Good direction for this spot' },
    ok: { mark: '~', label: 'OK direction for this spot' },
    poor: { mark: '·', label: 'Poor direction for this spot' },
    danger: { mark: '⚠', label: 'Offshore / dangerous direction' },
  }
</script>

<a class="back" href="#/">‹ All spots</a>

{#await docPromise}
  <p class="status">Loading…</p>
{:then doc}
  <h1>{doc.displayName}</h1>
  <p class="sub">
    Hourly WRF model wind at {doc.wrfCell.lat.toFixed(3)}°N, {Math.abs(doc.wrfCell.lon).toFixed(2)}°W (just offshore). All times HST.
  </p>

  {#each groupByDay(doc.hours, doc.sun).filter((d) => d.date >= todayKey()) as day (day.date)}
    {@const w = bestWindow(day.hours)}
    {@const conf = confidence(dayIndex(day.date))}
    <section class="day conf-{conf.level}" aria-labelledby="d-{day.date}">
      <header class="day-head">
        <h2 id="d-{day.date}">
          {dayName(day.date)}
          {#if dayName(day.date) !== dateLabel(day.date)}<span class="date">{dateLabel(day.date)}</span>{/if}
        </h2>
        <div class="day-meta">
          {#if day.sun}<span>☀ {clockLabel(day.sun.rise)} – {clockLabel(day.sun.set)}</span>{/if}
          {#if w}
            <span class="best">Best {windowLabel(w)} · {w.minKn}–{w.maxKn} kn</span>
          {:else}
            <span class="muted">No kiteable window</span>
          {/if}
          {#if conf.label}<span class="conf">{conf.label}</span>{/if}
        </div>
      </header>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Wind</th>
              <th scope="col" title="Estimated gust = wind × {meta.ratings.gustFactor}. The model has no gust output.">Gust*</th>
              <th scope="col">Dir</th>
              <th scope="col" class="gear">Gear</th>
              <th scope="col" class="opt">Air</th>
              <th scope="col" class="opt">Rain</th>
            </tr>
          </thead>
          <tbody>
            {#each day.hours as h (h.t)}
              <tr class:night={!h.daylight} class:now={h.t.startsWith(nowKey)} class:danger={h.sector === 'danger'}>
                <th scope="row" class="time">{hourLabel(h.t)}</th>
                <td><span class="kn kn-{knBand(h.wrf.kn)}">{Math.round(h.wrf.kn)}</span></td>
                <td class="num muted">{Math.round(h.wrf.gustEst)}</td>
                <td class="dir" title="From {compass(h.wrf.dir)} ({h.wrf.dir}°). {SECTOR[h.sector].label}">
                  <Arrow dir={h.wrf.dir} size={15} />
                  <span>{compass(h.wrf.dir)}</span>
                  <span class="sector s-{h.sector}" aria-label={SECTOR[h.sector].label}>{SECTOR[h.sector].mark}</span>
                </td>
                <td class="gear"><SportChips hour={h} bands={meta.ratings.sports} /></td>
                <td class="num opt">{h.wrf.tairC == null ? '–' : `${Math.round(cToF(h.wrf.tairC))}°`}</td>
                <td class="num opt rain">{h.wrf.rainMmH != null && h.wrf.rainMmH >= 0.2 ? h.wrf.rainMmH.toFixed(1) : ''}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {/each}

  <p class="foot-note">
    Wind and gust in knots. *Gusts are estimated (wind × {meta.ratings.gustFactor}); the WRF model does not output gusts.
    Air temperature in °F, rain in mm/h (shown from 0.2). ✓ good, ~ OK, · poor, ⚠ offshore direction for this spot.
  </p>
{:catch err}
  <p class="status error">Couldn't load this spot ({err.message}).</p>
{/await}

<style>
  .back {
    display: inline-block;
    margin-bottom: 8px;
    color: var(--accent);
    text-decoration: none;
    font-weight: 600;
  }
  h1 {
    margin: 0;
    font-size: 1.5rem;
  }
  .sub {
    margin: 4px 0 16px;
    color: var(--muted);
    font-size: 0.85rem;
  }
  .day {
    margin-bottom: 22px;
  }
  .day-head {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--bg);
    padding: 8px 0 6px;
  }
  h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  .date {
    color: var(--muted);
    font-weight: 500;
    font-size: 0.9rem;
    margin-left: 6px;
  }
  .day-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 14px;
    font-size: 0.85rem;
    margin-top: 2px;
  }
  .best {
    font-weight: 600;
  }
  .conf {
    color: var(--warn-fg);
    font-weight: 600;
  }
  .conf-lower .table-wrap,
  .conf-low .table-wrap {
    background-image: repeating-linear-gradient(135deg, transparent 0 8px, var(--hatch) 8px 9px);
  }
  .table-wrap {
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  thead th {
    text-align: left;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    font-weight: 600;
    padding: 6px 6px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  td,
  tbody th {
    padding: 4px 6px;
    border-bottom: 1px solid var(--border-soft);
    vertical-align: middle;
  }
  tbody tr:last-child > * {
    border-bottom: 0;
  }
  .time {
    text-align: left;
    font-weight: 600;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .num {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .kn {
    display: inline-block;
    min-width: 2.2em;
    text-align: center;
    font-weight: 700;
    border-radius: 6px;
    padding: 1px 4px;
    font-variant-numeric: tabular-nums;
  }
  .dir {
    white-space: nowrap;
  }
  .dir span {
    margin-left: 2px;
  }
  .sector {
    font-weight: 700;
    margin-left: 4px;
  }
  .s-good { color: var(--good-fg); }
  .s-ok { color: var(--warn-fg); }
  .s-poor { color: var(--muted); }
  .s-danger { color: var(--danger-fg); }
  .gear {
    width: 100%;
  }
  tr.night > * {
    background: var(--night);
    color: var(--muted);
  }
  tr.night .kn {
    opacity: 0.75;
  }
  tr.now > * {
    box-shadow: inset 0 2px 0 var(--accent), inset 0 -2px 0 var(--accent);
  }
  tr.now .time {
    box-shadow: inset 4px 0 0 var(--accent), inset 0 2px 0 var(--accent), inset 0 -2px 0 var(--accent);
  }
  .rain {
    color: var(--rain-fg);
  }
  .muted {
    color: var(--muted);
  }
  .foot-note {
    color: var(--muted);
    font-size: 0.8rem;
  }
  @media (max-width: 420px) {
    .opt {
      display: none;
    }
    table {
      font-size: 0.85rem;
    }
    td,
    tbody th,
    thead th {
      padding-left: 4px;
      padding-right: 4px;
    }
  }
</style>
