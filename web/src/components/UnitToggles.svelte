<script lang="ts">
  import { WIND_UNITS, type TempUnit, type WindUnit } from '../lib/units'

  let {
    wind,
    temp,
    onwind,
    ontemp,
  }: {
    wind: WindUnit
    temp: TempUnit
    onwind: (u: WindUnit) => void
    ontemp: (u: TempUnit) => void
  } = $props()
</script>

<div class="toggles">
  <div class="seg" role="group" aria-label="Wind speed unit">
    {#each WIND_UNITS as u (u.id)}
      <button type="button" aria-pressed={wind === u.id} onclick={() => onwind(u.id)}>{u.label}</button>
    {/each}
  </div>
  <div class="seg" role="group" aria-label="Temperature and height units">
    <button type="button" aria-pressed={temp === 'c'} onclick={() => ontemp('c')} title="°C, waves and tide in metres">°C · m</button>
    <button type="button" aria-pressed={temp === 'f'} onclick={() => ontemp('f')} title="°F, waves and tide in feet">°F · ft</button>
  </div>
</div>

<style>
  .toggles {
    display: flex;
    gap: 8px;
    flex-wrap: nowrap;
  }
  .seg {
    display: inline-flex;
    padding: 2px;
    border-radius: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
  }
  button {
    padding: 4px 10px;
    border: 1px solid transparent;
    border-radius: 8px;
    background: transparent;
    color: var(--muted);
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }
  button:hover {
    color: var(--text);
  }
  button[aria-pressed='true'] {
    color: var(--accent-2);
    border-color: rgba(246, 166, 35, 0.7);
    background: var(--accent-soft);
  }
</style>
