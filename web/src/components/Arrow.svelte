<script lang="ts">
  // Points DOWNWIND (where the air goes); `dir` is the meteorological "from" direction.
  let { dir, size = 18 }: { dir: number; size?: number } = $props()
</script>

<svg
  class="arrow"
  width={size}
  height={size}
  viewBox="-10 -10 20 20"
  aria-hidden="true"
  style:transform={`rotate(${dir + 180}deg)`}
>
  <path d="M0 -8 L5.5 5 L0 2.2 L-5.5 5 Z" fill="currentColor" />
</svg>

<style>
  .arrow {
    flex: none;
    vertical-align: middle;
  }
</style>
