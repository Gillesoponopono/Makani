<script lang="ts">
  // Direction, waves, tide, air temperature, sunrise and sunset under the chart.
  // All but the sun times follow the hour selected on the chart.
  import { clockLabel, compass, compassWords, hourLabel, weekdayShort } from '../lib/format'
  import { arrowPath } from '../lib/map'
  import { WAVE_TYPE, nextExtreme, tideAt, tideHeight, waveHeight } from '../lib/sea'
  import { SKY_LABEL } from '../lib/sky'
  import { tempLabel, type TempUnit } from '../lib/units'
  import SkyIcon from './SkyIcon.svelte'
  import type { Hour, SpotDoc, SunDay, Tide } from '../lib/types'

  let {
    hour,
    sun,
    temp,
    ontemp,
    tide = null,
    waveStatus = null,
  }: {
    hour: Hour | null | undefined
    sun?: SunDay
    temp: TempUnit
    ontemp: (u: TempUnit) => void
    tide?: Tide | null
    waveStatus?: NonNullable<SpotDoc['waves']>['status'] | null
  } = $props()

  const wave = $derived(hour?.wave ?? null)
  const tideNow = $derived(hour && tide ? tideAt(tide, hour.t) : null)
  const turn = $derived(hour && tide ? nextExtreme(tide, hour.t) : null)
  const turnText = $derived.by(() => {
    if (!turn || !hour) return ''
    const day = turn.t.slice(0, 10) === hour.t.slice(0, 10) ? '' : `${weekdayShort(turn.t.slice(0, 10))} `
    return `${turn.type === 'H' ? 'High' : 'Low'} ${tideHeight(turn.ft, temp)} · ${day}${clockLabel(turn.t.slice(11, 16))}`
  })

  const SECTOR_NOTE = { good: 'Good for this spot', ok: 'OK for this spot', poor: 'Poor for this spot', danger: 'Offshore · dangerous' }
</script>

<section class="stats card" aria-label={hour ? `Conditions at ${hourLabel(hour.t)}` : 'Conditions'}>
  <div class="tile dir">
    {#if hour}
      <svg class="arrow s-{hour.sector}" viewBox="-12 -12 24 24" width="34" height="34" aria-hidden="true">
        <path d={arrowPath(22)} transform="rotate({hour.wrf.dir + 180})" />
      </svg>
      <div>
        <div class="big display">{compass(hour.wrf.dir)}</div>
        <div class="small">{compassWords(hour.wrf.dir)} wind</div>
        <div class="note s-{hour.sector}">{SECTOR_NOTE[hour.sector]}</div>
      </div>
    {:else}
      <div class="small">No data</div>
    {/if}
  </div>

  <div class="tile">
    {#if wave}
      <svg class="arrow wave-arrow" viewBox="-12 -12 24 24" width="34" height="34" aria-hidden="true">
        {#if wave.dir != null}<path d={arrowPath(22)} transform="rotate({wave.dir + 180})" />{/if}
      </svg>
      <div>
        <div class="big display">{waveHeight(wave.m, temp)}</div>
        <div class="small">
          {wave.per != null ? `${Math.round(wave.per)} s` : 'Waves'}{wave.dir != null ? ` · from ${compass(wave.dir)}` : ''}
        </div>
        <div class="note sea">{WAVE_TYPE[wave.type].long}</div>
      </div>
    {:else}
      <svg class="icon sea-icon" viewBox="0 0 32 24" width="34" height="26" aria-hidden="true">
        <path d="M2 10c3 0 3-3 6-3s3 3 6 3 3-3 6-3 3 3 6 3 3-3 4-3M2 17c3 0 3-3 6-3s3 3 6 3 3-3 6-3 3 3 6 3 3-3 4-3" />
      </svg>
      <div>
        <div class="big display">{waveStatus === 'sheltered' ? 'Flat' : '–'}</div>
        <div class="small">{waveStatus === 'sheltered' ? 'Sheltered harbor' : 'No wave data'}</div>
        {#if waveStatus === 'sheltered'}<div class="note sea">Wind chop only</div>{/if}
      </div>
    {/if}
  </div>

  <div class="tile">
    <svg class="icon tide-icon" viewBox="0 0 24 24" width="30" height="30" aria-hidden="true">
      <path d="M3 17c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 3 2M3 21h18" />
      {#if turn?.type === 'L'}<path d="M12 3v8m-3.5-3.5L12 11l3.5-3.5" />{:else}<path d="M12 11V3M8.5 6.5 12 3l3.5 3.5" />{/if}
    </svg>
    <div>
      <div class="big display">{tideNow != null ? tideHeight(tideNow, temp) : '–'}</div>
      <div class="small">
        {tideNow != null && hour ? `Tide at ${hourLabel(hour.t)}${turn ? (turn.type === 'H' ? ', rising' : ', falling') : ''}` : 'No tide data'}
      </div>
      {#if turnText}<div class="note tide-note">{turnText}</div>{/if}
    </div>
  </div>

  <button
    type="button"
    class="tile temp"
    onclick={() => ontemp(temp === 'c' ? 'f' : 'c')}
    title="Switch to °{temp === 'c' ? 'F' : 'C'}"
    aria-label={hour?.wrf.tairC != null
      ? `Air ${tempLabel(hour.wrf.tairC, temp)}${hour.sky ? `, ${SKY_LABEL[hour.sky].toLowerCase()}` : ''}, switch unit`
      : 'Air temperature'}
  >
    {#if hour?.sky}
      <SkyIcon sky={hour.sky} size={30} />
    {:else}
      <svg class="icon" viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
        <path d="M10 4a2 2 0 1 1 4 0v9.3a4.5 4.5 0 1 1-4 0Z" />
        <path d="M12 9v7" class="mercury" />
      </svg>
    {/if}
    <div>
      <div class="big display">{hour?.wrf.tairC != null ? tempLabel(hour.wrf.tairC, temp) : '–'}</div>
      <div class="small">Air{hour ? ` at ${hourLabel(hour.t)}` : ''}</div>
      {#if hour?.sky}
        <div class="note sky-note">
          {SKY_LABEL[hour.sky]}{hour.sky === 'rain' && (hour.wrf.rainMmH ?? 0) >= 0.2 ? ` · ${hour.wrf.rainMmH!.toFixed(1)} mm/h` : ''}
        </div>
      {/if}
    </div>
  </button>

  <div class="tile">
    <svg class="icon sun" viewBox="0 0 32 24" width="34" height="26" aria-hidden="true">
      <path d="M4 20h24M9 20a7 7 0 0 1 14 0M16 6V3M8.5 9.5 6.5 7.5M23.5 9.5l2-2M3 15h3M26 15h3" />
      <path d="M13 3.5 16 1l3 2.5" />
    </svg>
    <div>
      <div class="big display">{sun ? clockLabel(sun.rise) : '–'}</div>
      <div class="small">Sunrise</div>
    </div>
  </div>

  <div class="tile">
    <svg class="icon sun" viewBox="0 0 32 24" width="34" height="26" aria-hidden="true">
      <path d="M4 20h24M9 20a7 7 0 0 1 14 0M16 6V3M8.5 9.5 6.5 7.5M23.5 9.5l2-2M3 15h3M26 15h3" />
      <path d="M13 1 16 3.5 19 1" />
    </svg>
    <div>
      <div class="big display">{sun ? clockLabel(sun.set) : '–'}</div>
      <div class="small">Sunset</div>
    </div>
  </div>
</section>

<style>
  .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    padding: 6px;
  }
  .tile {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    min-width: 0;
    text-align: left;
    border: 0;
    background: transparent;
  }
  .tile:not(:nth-child(3n + 1)) {
    border-left: 1px solid var(--border);
  }
  .tile:nth-child(n + 4) {
    border-top: 1px solid var(--border);
  }
  button.tile {
    cursor: pointer;
    border-radius: 12px;
  }
  button.tile:hover {
    background: rgba(255, 255, 255, 0.03);
  }
  .big {
    font-size: 1.45rem;
    font-weight: 600;
    line-height: 1.1;
    white-space: nowrap;
  }
  .small {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .note {
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 1px;
  }
  .arrow {
    flex: none;
    fill: currentColor;
    filter: drop-shadow(0 0 8px currentColor);
  }
  .icon {
    flex: none;
    fill: none;
    stroke: var(--text);
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .icon.sun {
    stroke: var(--accent);
  }
  .mercury {
    stroke: var(--accent);
    stroke-width: 2.2;
  }
  .wave-arrow {
    color: var(--wave);
  }
  .sea-icon {
    stroke: var(--wave);
  }
  .tide-icon {
    stroke: var(--tide);
  }
  .note.sea {
    color: var(--wave);
  }
  .note.tide-note {
    color: var(--tide);
  }
  .note.sky-note {
    color: var(--sun);
  }
  @media (max-width: 760px) {
    .stats {
      grid-template-columns: 1fr 1fr;
      gap: 0;
    }
    .tile {
      padding: 12px;
    }
    .tile:not(:nth-child(3n + 1)) {
      border-left: 0;
    }
    .tile:nth-child(n + 4) {
      border-top: 0;
    }
    .tile:nth-child(even) {
      border-left: 1px solid var(--border);
    }
    .tile:nth-child(n + 3) {
      border-top: 1px solid var(--border);
    }
    .big {
      font-size: 1.2rem;
    }
  }
</style>
