<script lang="ts">
  import { skyIcon } from '../lib/sky'
  import type { Sky } from '../lib/types'

  let { sky, size = 18 }: { sky: Sky; size?: number } = $props()
</script>

<svg class="sky-icon" viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
  {#each skyIcon(sky) as p, k (k)}
    <path class="sky-{p.kind}" d={p.d} />
  {/each}
</svg>

<style>
  .sky-icon {
    flex: none;
    overflow: visible;
  }
</style>
