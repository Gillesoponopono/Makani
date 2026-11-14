<script lang="ts">
  // The day at a glance in the hero: wind, air, water and waves over daylight hours.
  // The stats under the chart give the same things for the selected hour.
  import { compass } from '../lib/format'
  import { WAVE_TYPE, FLAT_M, lengthUnit, waveNumber } from '../lib/sea'
  import { daySummary, rangeText } from '../lib/summary'
  import { cToF, windLabel, windUnitLabel, type TempUnit, type WindUnit } from '../lib/units'
  import type { Hour, SpotDoc } from '../lib/types'

  let {
    hours,
    wind,
    temp,
    waveStatus = null,
  }: {
    hours: Hour[]
    wind: WindUnit
    temp: TempUnit
    waveStatus?: NonNullable<SpotDoc['waves']>['status'] | null
  } = $props()

  const s = $derived(daySummary(hours))
  const deg = (c: number) => Math.round(temp === 'f' ? cToF(c) : c)
  const tempUnit = $derived(temp === 'f' ? '°F' : '°C')
</script>

<ul class="tiles" aria-label="Daytime conditions">
  <li class="tile">
    <div class="head">
      <svg class="icon wind" viewBox="0 0 32 24" aria-hidden="true">
        <path d="M3 8h17a3.5 3.5 0 1 0-3.5-3.5M3 13h23a3.5 3.5 0 1 1-3.5 3.5M3 18h12" />
      </svg>
      Wind
    </div>
    {#if s.wind}
      <div class="value display">
        {rangeText(s.wind, (kn) => windLabel(kn, wind))}<span class="unit">{windUnitLabel(wind)}</span>
      </div>
      <div class="sub">{compass(s.wind.dir)} · gusts to {windLabel(s.wind.gust, wind)}</div>
    {:else}
      <div class="value display">–</div>
    {/if}
  </li>

  <li class="tile">
    <div class="head">
      <svg class="icon air" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M10 4a2 2 0 1 1 4 0v9.3a4.5 4.5 0 1 1-4 0Z" />
        <path d="M12 9v7" class="mercury" />
      </svg>
      Air
    </div>
    <div class="value display">
      {#if s.air}{rangeText(s.air, deg)}<span class="unit">{tempUnit}</span>{:else}–{/if}
    </div>
    <div class="sub">Daytime</div>
  </li>

  <li class="tile">
    <div class="head">
      <svg class="icon water" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3.5c3 4.2 5.5 7.3 5.5 10.3a5.5 5.5 0 0 1-11 0c0-3 2.5-6.1 5.5-10.3Z" />
        <path d="M9.3 14.5a2.8 2.8 0 0 0 2.7 2.4" />
      </svg>
      Water
    </div>
    <div class="value display">
      {#if s.water != null}{deg(s.water)}<span class="unit">{tempUnit}</span>{:else}–{/if}
    </div>
    <div class="sub">{s.water != null ? 'Sea surface' : 'No data'}</div>
  </li>

  <li class="tile">
    <div class="head">
      <svg class="icon waves" viewBox="0 0 32 24" aria-hidden="true">
        <path d="M2 10c3 0 3-3 6-3s3 3 6 3 3-3 6-3 3 3 6 3 3-3 4-3M2 17c3 0 3-3 6-3s3 3 6 3 3-3 6-3 3 3 6 3 3-3 4-3" />
      </svg>
      Waves
    </div>
    {#if s.waves && s.waves.max >= FLAT_M}
      <div class="value display">
        {rangeText(s.waves, (m) => waveNumber(m, temp))}<span class="unit">{lengthUnit(temp)}</span>
      </div>
      <div class="sub">
        {#if s.waves.per}<span class="per">{rangeText(s.waves.per, Math.round)} s</span> ·{/if}
        <span class="type">{WAVE_TYPE[s.waves.type].long}</span>
      </div>
    {:else if s.waves || waveStatus === 'sheltered'}
      <div class="value display">Flat</div>
      <div class="sub">{waveStatus === 'sheltered' ? 'Sheltered harbor' : temp === 'f' ? 'Under 1 ft' : `Under ${FLAT_M} m`}</div>
    {:else}
      <div class="value display">–</div>
      <div class="sub">No wave data</div>
    {/if}
  </li>
</ul>

<style>
  .tiles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    max-width: 440px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .tile {
    min-width: 0;
    padding: 12px 16px 13px;
    border-radius: 16px;
    border: 1px solid rgba(150, 195, 235, 0.2);
    background: linear-gradient(160deg, rgba(14, 44, 76, 0.72), rgba(7, 24, 42, 0.72));
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .icon {
    width: 20px;
    height: 18px;
    flex: none;
    fill: none;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .icon.wind {
    stroke: var(--wind-kn2);
  }
  .icon.air {
    stroke: var(--text);
  }
  .mercury {
    stroke: var(--accent);
    stroke-width: 2.4;
  }
  .icon.water {
    stroke: var(--teal);
  }
  .icon.waves {
    stroke: var(--wave);
  }
  .value {
    margin-top: 4px;
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .unit {
    margin-left: 4px;
    font-size: 0.58em;
    font-weight: 600;
    color: var(--muted);
  }
  .sub {
    margin-top: 2px;
    color: var(--muted);
    font-size: 0.84rem;
  }
  .per {
    color: var(--text);
    font-weight: 600;
  }
  .type {
    color: var(--wave);
    font-weight: 600;
  }

  @media (max-width: 760px) {
    .tiles {
      max-width: none;
      gap: 8px;
    }
    .tile {
      padding: 10px 12px 11px;
      border-radius: 14px;
    }
    .value {
      font-size: 1.45rem;
    }
    .sub {
      font-size: 0.8rem;
    }
  }
</style>
