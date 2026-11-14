<script lang="ts">
  // Every forecast day for one spot: best session, peak and a small chart; each
  // row opens that day.
  import WindChart from '../components/WindChart.svelte'
  import { axisMax } from '../lib/chart'
  import { addDays, bestWindow, compass, confidence, dateLong, dayIndex, groupByDay, todayKey, weekdayLong, windowLabel } from '../lib/format'
  import { arrowPath } from '../lib/map'
  import { WAVE_TYPE, waveNumber, waveSummary, lengthUnit } from '../lib/sea'
  import { windIn, windLabel, windUnitLabel, type TempUnit, type WindUnit } from '../lib/units'
  import type { Hour, Meta, SpotDoc } from '../lib/types'

  let {
    meta,
    doc,
    wind,
    temp,
    dayHref,
  }: {
    meta: Meta
    doc: SpotDoc
    wind: WindUnit
    temp: TempUnit
    dayHref: (date: string) => string
  } = $props()

  const today = todayKey()
  const days = $derived(groupByDay(doc.hours, doc.sun).filter((d) => d.date >= today))
  const yMax = $derived(
    axisMax(
      days.flatMap((d) => d.hours.map((h) => windIn(h.wrf.gustEst, wind))),
      wind === 'kn' ? 25 : wind === 'mph' ? 30 : 50,
    ),
  )
  const slots = (hours: Hour[]) => {
    const out: (Hour | null)[] = Array(24).fill(null)
    for (const h of hours) out[Number(h.t.slice(11, 13))] = h
    return out
  }
  const label = (date: string) => (date === today ? 'Today' : date === addDays(today, 1) ? 'Tomorrow' : weekdayLong(date))
</script>

<header class="head">
  <h1 class="display">Next {days.length} days <span>at {doc.displayName}</span></h1>
  <p>Model runs to {dateLong(meta.wrf.end.slice(0, 10))}. Later days are less certain.</p>
</header>

<ol class="days">
  {#each days as d, i (d.date)}
    {@const w = bestWindow(d.hours)}
    {@const peak = d.hours.filter((h) => h.daylight).reduce<Hour | null>((m, h) => (!m || h.wrf.kn > m.wrf.kn ? h : m), null)}
    {@const conf = confidence(dayIndex(d.date))}
    {@const sea = waveSummary(d.hours)}
    <li>
      <a class="day card" href={dayHref(d.date)}>
        <div class="when">
          <div class="name display">{label(d.date)}</div>
          <div class="date">{dateLong(d.date)}</div>
          {#if conf.label}<div class="conf">{conf.label}</div>{/if}
        </div>
        <div class="sess">
          {#if w}
            <div class="lbl">Best session</div>
            <div class="time display">{windowLabel(w)}</div>
            <div class="range">{windLabel(w.minKn, wind)}–{windLabel(w.maxKn, wind)} {windUnitLabel(wind)}</div>
          {:else}
            <div class="lbl">Best session</div>
            <div class="none">No kiteable window</div>
          {/if}
          {#if sea}
            {@const lo = waveNumber(sea.min, temp)}
            {@const hi = waveNumber(sea.max, temp)}
            <div class="sea">
              {sea.type === 'flat' ? 'Flat' : `Waves ${lo === hi ? lo : `${lo}–${hi}`} ${lengthUnit(temp)} · ${WAVE_TYPE[sea.type].long.toLowerCase()}`}
            </div>
          {:else if doc.waves?.status === 'sheltered'}
            <div class="sea">Sheltered, flat water</div>
          {/if}
        </div>
        <div class="mini">
          <WindChart
            hours={slots(d.hours)}
            prev={days[i - 1]?.hours.at(-1) ?? null}
            next={days[i + 1]?.hours[0] ?? null}
            {yMax}
            {wind}
            {temp}
            best={w ? { start: Number(w.start.t.slice(11, 13)), end: Number(w.end.t.slice(11, 13)) + 1 } : null}
            compact
            label={label(d.date)}
          />
        </div>
        <div class="peak">
          {#if peak}
            <svg class="s-{peak.sector}" viewBox="-12 -12 24 24" width="22" height="22" aria-hidden="true">
              <path d={arrowPath(20)} transform="rotate({peak.wrf.dir + 180})" fill="currentColor" />
            </svg>
            <div>
              <div class="pk display">{windLabel(peak.wrf.kn, wind)} <span>{windUnitLabel(wind)}</span></div>
              <div class="pd">peak · {compass(peak.wrf.dir)}</div>
            </div>
          {/if}
        </div>
        <span class="go" aria-hidden="true">›</span>
      </a>
    </li>
  {/each}
</ol>

<style>
  .head {
    margin: 8px 0 18px;
  }
  h1 {
    margin: 0;
    font-size: clamp(1.7rem, 3.4vw, 2.4rem);
    font-weight: 700;
  }
  h1 span {
    color: var(--muted);
    font-weight: 500;
    font-size: 0.65em;
  }
  .head p {
    margin: 4px 0 0;
    color: var(--muted);
  }
  .days {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 12px;
  }
  .day {
    display: grid;
    grid-template-columns: 150px 170px 1fr 110px 14px;
    align-items: center;
    gap: 16px;
    padding: 12px 18px;
    color: inherit;
    text-decoration: none;
    transition: border-color 0.15s;
  }
  .day:hover {
    border-color: rgba(246, 166, 35, 0.5);
  }
  .name {
    font-size: 1.25rem;
    font-weight: 600;
  }
  .date,
  .lbl,
  .pd {
    color: var(--muted);
    font-size: 0.82rem;
  }
  .conf {
    margin-top: 3px;
    color: var(--ok);
    font-size: 0.72rem;
    font-weight: 700;
  }
  .time {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--accent-2);
    white-space: nowrap;
  }
  .range {
    font-size: 0.9rem;
    font-weight: 600;
  }
  .sea {
    margin-top: 4px;
    color: var(--wave);
    font-size: 0.8rem;
    font-weight: 600;
  }
  .none {
    color: var(--muted);
    font-weight: 600;
  }
  .mini {
    min-width: 0;
  }
  .peak {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .pk {
    font-size: 1.3rem;
    font-weight: 600;
    white-space: nowrap;
  }
  .pk span {
    font-size: 0.6em;
    color: var(--muted);
  }
  .go {
    color: var(--muted);
    font-size: 1.5rem;
  }
  @media (max-width: 760px) {
    .day {
      grid-template-columns: 1fr auto;
      grid-template-areas: 'when peak' 'sess sess' 'mini mini';
      gap: 8px 12px;
      padding: 12px 14px;
    }
    .when {
      grid-area: when;
    }
    .sess {
      grid-area: sess;
      display: flex;
      align-items: baseline;
      gap: 10px;
      flex-wrap: wrap;
    }
    .mini {
      grid-area: mini;
    }
    .peak {
      grid-area: peak;
    }
    .go {
      display: none;
    }
  }
</style>
