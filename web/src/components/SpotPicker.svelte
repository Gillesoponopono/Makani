<script lang="ts">
  // Location menu in the header: the forecast spots.
  let {
    spots,
    current,
    hrefFor,
  }: {
    spots: { id: string; displayName: string }[]
    current: string
    hrefFor: (id: string) => string
  } = $props()

  let open = $state(false)
  let root: HTMLDivElement | undefined = $state()
  const currentName = $derived(spots.find((s) => s.id === current)?.displayName ?? '')

  $effect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (root && !root.contains(e.target as Node)) open = false
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') open = false
    }
    document.addEventListener('click', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  })
</script>

<div class="picker" bind:this={root}>
  <button type="button" class="trigger" aria-haspopup="true" aria-expanded={open} onclick={() => (open = !open)}>
    <svg class="pin" viewBox="0 0 24 24" width="17" height="17" aria-hidden="true">
      <path d="M12 2.5a7 7 0 0 0-7 7c0 5.2 7 12 7 12s7-6.8 7-12a7 7 0 0 0-7-7Zm0 9.6a2.6 2.6 0 1 1 0-5.2 2.6 2.6 0 0 1 0 5.2Z" />
    </svg>
    <span class="name">{currentName}</span>
    <svg class="chev" class:up={open} viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  </button>
  {#if open}
    <ul class="menu">
      {#each spots as s (s.id)}
        <li>
          <a
            href={hrefFor(s.id)}
            class:active={s.id === current}
            aria-current={s.id === current ? 'true' : undefined}
            onclick={() => (open = false)}
          >
            {s.displayName}
            {#if s.id === current}<span class="tick" aria-hidden="true">✓</span>{/if}
          </a>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .picker {
    position: relative;
  }
  .trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border: 1px solid transparent;
    border-radius: 10px;
    background: transparent;
    cursor: pointer;
    font-weight: 600;
    font-size: 0.98rem;
    white-space: nowrap;
    max-width: 52vw;
  }
  .trigger:hover {
    background: var(--surface-2);
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pin {
    flex: none;
    fill: var(--text);
  }
  .chev {
    flex: none;
    fill: none;
    stroke: var(--text);
    stroke-width: 2.2;
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: transform 0.15s;
  }
  .chev.up {
    transform: rotate(180deg);
  }
  .menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    z-index: 20;
    min-width: 230px;
    margin: 0;
    padding: 6px;
    list-style: none;
    background: var(--surface-2);
    border: 1px solid var(--border-strong);
    border-radius: 14px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
  }
  .menu a {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 12px;
    border-radius: 9px;
    color: var(--text);
    text-decoration: none;
    font-weight: 500;
  }
  .menu a:hover {
    background: var(--surface-3);
  }
  .menu a.active {
    color: var(--accent-2);
    font-weight: 700;
  }
</style>
