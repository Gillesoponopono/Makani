<script lang="ts">
  import type { Hour, SportBand } from '../lib/types'

  let { hour, bands }: { hour: Hour; bands: SportBand[] } = $props()
  const byId = $derived(new Map(bands.map((b) => [b.id, b])))
</script>

{#if hour.sector === 'danger'}
  <span class="chip danger" title="Offshore wind at this spot: you can be blown out to sea">⚠ Offshore</span>
{:else if hour.sports.length}
  <span class="chips">
    {#each hour.sports as id (id)}
      {@const b = byId.get(id)}
      <span class="chip sport-{id}" title={b ? `${b.label}: ${b.minKn}${b.maxKn ? `–${b.maxKn}` : '+'} kn` : id}>
        {b?.short ?? id}
      </span>
    {/each}
  </span>
{:else if hour.sector === 'poor'}
  <span class="none" title="Wind direction doesn't work well at this spot">poor dir.</span>
{:else}
  <span class="none">{Math.round(hour.wrf.kn) < bands[0].minKn ? 'too light' : '—'}</span>
{/if}

<style>
  .chips {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 3px;
  }
  .chip {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    line-height: 1.5;
    white-space: nowrap;
    background: var(--chip-bg);
    color: var(--chip-fg);
  }
  .sport-foil_wing { background: var(--sport-foil); color: var(--sport-fg); }
  .sport-directional { background: var(--sport-dir); color: var(--sport-fg); }
  .sport-twintip { background: var(--sport-tt); color: var(--sport-fg); }
  .sport-expert { background: var(--sport-exp); color: #fff; }
  .danger {
    background: var(--danger-bg);
    color: var(--danger-fg);
  }
  .none {
    color: var(--muted);
    font-size: 0.78rem;
  }
</style>
