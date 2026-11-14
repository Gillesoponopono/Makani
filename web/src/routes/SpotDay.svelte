<script lang="ts">
  import Arrow from '../components/Arrow.svelte'
  import DayStats from '../components/DayStats.svelte'
  import DayTiles from '../components/DayTiles.svelte'
  import IslandMap from '../components/IslandMap.svelte'
  import WindChart from '../components/WindChart.svelte'
  import { axisMax } from '../lib/chart'
  import {
    addDays,
    bestWindow,
    compass,
    confidence,
    currentHourKey,
    dateLong,
    dayIndex,
    groupByDay,
    hourLabel,
    knBand,
    nowHoursHst,
    todayKey,
    weekdayLong,
  } from '../lib/format'
  import { WAVE_TYPE, lengthUnit, tideAt, tideHeight, waveNumber } from '../lib/sea'
  import { tempLabel, windIn, windLabel, windUnitLabel, type TempUnit, type WindUnit } from '../lib/units'
  import type { Hour, Meta, Sector, SpotDoc } from '../lib/types'

  let {
    meta,
    docs,
    doc,
    date,
    wind,
    temp,
    ontemp,
    hrefFor,
  }: {
    meta: Meta
    docs: SpotDoc[]
    doc: SpotDoc
    date: string
    wind: WindUnit
    temp: TempUnit
    ontemp: (u: TempUnit) => void
    hrefFor: (id: string) => string
  } = $props()

  const today = todayKey()
  const days = $derived(groupByDay(doc.hours, doc.sun))
  const di = $derived(days.findIndex((d) => d.date === date))
  const day = $derived(days[di])
  const isToday = $derived(date === today)

  const slots = $derived.by(() => {
    const out: (Hour | null)[] = Array(24).fill(null)
    for (const h of day?.hours ?? []) out[Number(h.t.slice(11, 13))] = h
    return out
  })

  const win = $derived(day ? bestWindow(day.hours) : null)
  const best = $derived(
    win ? { start: Number(win.start.t.slice(11, 13)), end: Number(win.end.t.slice(11, 13)) + 1 } : null,
  )

  // One axis for every day of this spot, in the chosen unit.
  const yMax = $derived(
    axisMax(
      doc.hours.filter((h) => h.t.slice(0, 10) >= today).map((h) => windIn(h.wrf.gustEst, wind)),
      wind === 'kn' ? 25 : wind === 'mph' ? 30 : 50,
    ),
  )

  // Hour picked on the chart; otherwise now (today) or the session's windiest hour.
  let focus = $state<number | null>(null)
  $effect(() => {
    void doc.id
    void date
    focus = null
  })
  const defaultIdx = $derived.by(() => {
    if (isToday) {
      const k = currentHourKey().slice(11, 13)
      if (slots[Number(k)]) return Number(k)
    }
    if (best) {
      let m = best.start
      for (let i = best.start; i < best.end; i++) if (slots[i] && slots[m] && slots[i]!.wrf.kn > slots[m]!.wrf.kn) m = i
      return m
    }
    return slots[14] ? 14 : slots.findIndex(Boolean)
  })
  const shownIdx = $derived(focus ?? defaultIdx)
  const shownHour = $derived(shownIdx >= 0 ? slots[shownIdx] : null)

  const title = $derived(isToday ? 'Today' : date === addDays(today, 1) ? 'Tomorrow' : weekdayLong(date))
  const conf = $derived(confidence(dayIndex(date)))
  const nowKey = currentHourKey()

  const SECTOR: Record<Sector, { mark: string; label: string }> = {
    good: { mark: '✓', label: 'Good direction for this spot' },
    ok: { mark: '~', label: 'OK direction for this spot' },
    poor: { mark: '·', label: 'Poor direction for this spot' },
    danger: { mark: '⚠', label: 'Offshore / dangerous direction' },
  }

  let tableOpen = $state(false)
  const hasWaves = $derived(doc.hours.some((h) => h.wave))
</script>

{#if !day}
  <p class="status">No forecast for {dateLong(date)} at {doc.displayName}. The model currently runs to {dateLong(meta.wrf.end.slice(0, 10))}.</p>
{:else}
  <section class="hero" aria-labelledby="day-title">
    <div class="hero-text">
      <h1 id="day-title" class="display">
        <span>{title}</span>
        <span class="at">at {doc.displayName}</span>
      </h1>
      <p class="date">
        {dateLong(date)}{#if conf.label}<span class="conf">{conf.label}</span>{/if}
      </p>

      <div class="island-phone">
        <IslandMap {docs} selected={doc.id} focusT={shownHour?.t ?? null} {wind} {hrefFor} mode="block" />
      </div>

      <DayTiles hours={day.hours} {wind} {temp} waveStatus={doc.waves?.status ?? null} />
    </div>
    <div class="island-hero">
      <IslandMap {docs} selected={doc.id} focusT={shownHour?.t ?? null} {wind} {hrefFor} mode="hero" />
    </div>
  </section>

  <section class="card forecast" class:hatch={conf.level !== 'normal'} aria-labelledby="wf-title">
    <header class="card-head">
      <h2 id="wf-title" class="display">
        <svg class="wind-icon" viewBox="0 0 32 24" width="30" height="22" aria-hidden="true">
          <path d="M3 8h17a3.5 3.5 0 1 0-3.5-3.5M3 13h23a3.5 3.5 0 1 1-3.5 3.5M3 18h12" />
        </svg>
        Wind Forecast
      </h2>
      <ul class="legend" aria-label="Legend">
        <li><span class="key wind-key"></span>Wind</li>
        <li><span class="key gust-key"></span>Gusts <span class="est">(est.)</span></li>
      </ul>
    </header>
    <WindChart
      hours={slots}
      prev={days[di - 1]?.hours.at(-1) ?? null}
      next={days[di + 1]?.hours[0] ?? null}
      sun={day.sun}
      {yMax}
      {wind}
      {temp}
      nowHours={isToday ? nowHoursHst() : null}
      {best}
      bind:focus
      label="{title}, {doc.displayName}"
      {date}
      tide={doc.tide ?? null}
      waveStatus={doc.waves?.status ?? null}
    />
    <p class="chart-note">
      Arrows under the chart point where the wind blows: <span class="s-good">good</span>,
      <span class="s-ok">OK</span>, <span class="s-poor">poor</span> or <span class="s-danger">offshore</span> for this spot.
      Gusts are estimated (wind × {meta.ratings.gustFactor}).
      {#if doc.waves?.status === 'ok'}
        Waves: model height just off the beach and peak period (PacIOOS SWAN); the type comes from the offshore swell
        and wind-chop split (WaveWatch III).
      {/if}
      {#if doc.tide}
        Tide: NOAA predictions above mean lower low water.
      {/if}
    </p>
  </section>

  <DayStats hour={shownHour} sun={day.sun} {temp} {ontemp} tide={doc.tide ?? null} waveStatus={doc.waves?.status ?? null} />

  <details class="card hourly" bind:open={tableOpen} id="hourly">
    <summary>Hourly table</summary>
    {#if tableOpen}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Wind</th>
              <th scope="col">Gust*</th>
              <th scope="col">Direction</th>
              {#if hasWaves}<th scope="col">Waves</th>{/if}
              {#if doc.tide}<th scope="col">Tide</th>{/if}
              <th scope="col">Air</th>
              <th scope="col" class="opt">Rain</th>
            </tr>
          </thead>
          <tbody>
            {#each day.hours as h (h.t)}
              <tr class:night={!h.daylight} class:now={h.t.startsWith(nowKey)}>
                <th scope="row">{hourLabel(h.t)}</th>
                <td><span class="kn kn-{knBand(h.wrf.kn)}">{windLabel(h.wrf.kn, wind)}</span></td>
                <td class="num muted">{windLabel(h.wrf.gustEst, wind)}</td>
                <td class="dirc" title="From {compass(h.wrf.dir)} ({h.wrf.dir}°). {SECTOR[h.sector].label}">
                  <Arrow dir={h.wrf.dir} size={14} />
                  {compass(h.wrf.dir)}
                  <span class="s-{h.sector}" aria-label={SECTOR[h.sector].label}>{SECTOR[h.sector].mark}</span>
                </td>
                {#if hasWaves}
                  <td class="num">
                    {#if h.wave}
                      {waveNumber(h.wave.m, temp)}
                      {#if h.wave.per != null}<span class="muted">{Math.round(h.wave.per)}s</span>{/if}
                      <span class="wtype">{WAVE_TYPE[h.wave.type].short}</span>
                    {:else}–{/if}
                  </td>
                {/if}
                {#if doc.tide}
                  {@const ft = tideAt(doc.tide, h.t)}
                  <td class="num">{ft == null ? '–' : tideHeight(ft, temp)}</td>
                {/if}
                <td class="num">{h.wrf.tairC == null ? '–' : tempLabel(h.wrf.tairC, temp)}</td>
                <td class="num opt rain">{h.wrf.rainMmH != null && h.wrf.rainMmH >= 0.2 ? `${h.wrf.rainMmH.toFixed(1)} mm` : ''}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <p class="chart-note">
        Wind and gust in {windUnitLabel(wind)}. *Estimated gust. ✓ good, ~ OK, · poor, ⚠ offshore direction.{#if hasWaves}
          Waves in {lengthUnit(temp)}, period in seconds.{/if}
      </p>
    {/if}
  </details>
{/if}

<style>
  .hero {
    position: relative;
    display: grid;
    grid-template-columns: minmax(300px, 0.9fr) 1.1fr;
    min-height: 380px;
    margin: 0 -8px 18px;
    border-radius: 24px;
    overflow: hidden;
    background:
      radial-gradient(900px 420px at 75% 45%, rgba(31, 92, 150, 0.55), transparent 70%),
      linear-gradient(160deg, #0d3157 0%, #092341 55%, #071a30 100%);
    border: 1px solid var(--border);
  }
  .hero-text {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 34px 24px 34px 40px;
  }
  h1 {
    margin: 0;
    font-size: clamp(2.3rem, 4.6vw, 3.5rem);
    line-height: 1.02;
    font-weight: 700;
    letter-spacing: -0.01em;
    display: flex;
    flex-direction: column;
  }
  h1 .at {
    font-size: 0.62em;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.92);
    margin-top: 4px;
  }
  .date {
    margin: 10px 0 22px;
    color: var(--muted);
    font-size: 1.15rem;
  }
  .conf {
    margin-left: 10px;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--warn-bg);
    color: var(--ok);
    font-size: 0.75rem;
    font-weight: 700;
    vertical-align: 2px;
  }
  .island-hero {
    position: relative;
    min-height: 380px;
  }
  .island-hero :global(.island) {
    position: absolute;
    inset: 0;
  }
  .island-phone {
    display: none;
  }

  .forecast {
    padding: 18px 22px 14px;
    margin-bottom: 14px;
  }
  .forecast.hatch {
    background-image:
      repeating-linear-gradient(135deg, transparent 0 10px, rgba(255, 255, 255, 0.025) 10px 11px),
      linear-gradient(180deg, var(--surface-2), var(--surface));
  }
  .card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 6px;
  }
  h2 {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 1.35rem;
    font-weight: 600;
  }
  .wind-icon {
    fill: none;
    stroke: var(--text);
    stroke-width: 1.8;
    stroke-linecap: round;
    opacity: 0.85;
  }
  .legend {
    display: flex;
    gap: 18px;
    margin: 0;
    padding: 0;
    list-style: none;
    color: var(--muted);
    font-size: 0.88rem;
  }
  .legend li {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .est {
    font-size: 0.8em;
  }
  .key {
    display: inline-block;
    width: 22px;
    height: 3px;
    border-radius: 2px;
  }
  .wind-key {
    background: linear-gradient(90deg, var(--wind-kn0), var(--wind-kn2), var(--wind-kn3), var(--wind-kn4));
  }
  .gust-key {
    background: var(--gust);
  }
  .chart-note {
    margin: 8px 0 0;
    color: var(--faint);
    font-size: 0.78rem;
  }

  .hourly {
    margin-top: 14px;
    padding: 0;
  }
  summary {
    cursor: pointer;
    padding: 14px 20px;
    font-weight: 600;
    color: var(--muted);
  }
  summary:hover {
    color: var(--text);
  }
  .hourly .chart-note {
    padding: 0 20px 14px;
  }
  .table-wrap {
    overflow-x: auto;
    padding: 0 12px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
  }
  thead th {
    text-align: left;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--faint);
    font-weight: 600;
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
  }
  td,
  tbody th {
    padding: 5px 8px;
    border-bottom: 1px solid rgba(150, 195, 235, 0.06);
    text-align: left;
    white-space: nowrap;
  }
  tbody th {
    font-weight: 600;
  }
  tr.night > * {
    color: var(--faint);
  }
  tr.now > * {
    background: rgba(60, 198, 216, 0.08);
  }
  .num {
    font-variant-numeric: tabular-nums;
  }
  .muted {
    color: var(--muted);
  }
  .kn {
    display: inline-block;
    min-width: 2.3em;
    text-align: center;
    font-weight: 700;
    border-radius: 6px;
    padding: 1px 5px;
    font-variant-numeric: tabular-nums;
  }
  .rain {
    color: #7ab8ff;
  }
  .wtype {
    margin-left: 4px;
    color: var(--wave);
    font-size: 0.78rem;
    font-weight: 600;
  }

  @media (max-width: 760px) {
    .hero {
      display: block;
      min-height: 0;
      margin: 0 0 14px;
      border-radius: 20px;
    }
    .hero-text {
      padding: 22px 16px 18px;
    }
    .island-hero {
      display: none;
    }
    .island-phone {
      display: block;
      margin-bottom: 14px;
    }
    .date {
      margin: 6px 0 14px;
      font-size: 1rem;
    }
    .forecast {
      padding: 14px 12px 12px;
    }
    h2 {
      font-size: 1.15rem;
    }
    .legend {
      gap: 12px;
      font-size: 0.8rem;
    }
    .opt {
      display: none;
    }
  }
</style>
