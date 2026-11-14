<script lang="ts">
  import coastData from '../assets/maui-coast.json'
  import { loadFrames } from '../lib/data'
  import { compass, currentHourKey, dateLabel, dayName, hourLabel, knBand, weekdayShort } from '../lib/format'
  import {
    arrowLength,
    arrowPath,
    nearestPoint,
    nightGradient,
    pointInRings,
    projector,
    type Coast,
    type Frames,
  } from '../lib/map'
  import type { SpotDoc } from '../lib/types'

  let { docs }: { docs: SpotDoc[] } = $props()

  const coast = coastData as Coast
  const project = projector(coast.bbox, coast.width)

  // Spot label placement (HTML overlay, so text stays readable at any map size).
  // Maui Sunset sits near the left edge on phones, so its label goes right (over land).
  const LABEL_SIDE: Record<string, 'left' | 'right'> = { kanaha: 'left', sprecks: 'right', 'maui-sunset': 'right' }

  const BANDS = ['< 10', '10–15', '15–20', '20–25', '25–30', '30–35', '35+']

  let frames = $state<Frames | null>(null)
  let error = $state<string | null>(null)
  let idx = $state(0)
  let playing = $state(false)
  let picked = $state<number | null>(null)
  let svgEl: SVGSVGElement | undefined = $state()

  $effect(() => {
    loadFrames()
      .then((f) => {
        frames = f
        const i = f.times.findIndex((t) => t.startsWith(currentHourKey()))
        idx = i >= 0 ? i : 0
      })
      .catch((e: Error) => (error = e.message))
  })

  // Grid points in SVG space, with a land flag (land arrows are drawn faded).
  const points = $derived(
    frames
      ? frames.lats.flatMap((lat) =>
          frames!.lons.map((lon) => {
            const [x, y] = project(lat, lon)
            return { x, y, lat, lon, land: pointInRings(x, y, coast.rings) }
          }),
        )
      : [],
  )
  const cell = $derived.by(() => {
    if (!frames || frames.lats.length < 2 || frames.lons.length < 2) return { w: 0, h: 0 }
    const [x0, y0] = project(frames.lats[0], frames.lons[0])
    const [x1] = project(frames.lats[0], frames.lons[1])
    const [, y1] = project(frames.lats[1], frames.lons[0])
    return { w: Math.abs(x1 - x0), h: Math.abs(y1 - y0) }
  })

  const time = $derived(frames ? frames.times[idx] : '')
  const kn = $derived(frames ? frames.kn10[idx] : [])
  const dir = $derived(frames ? frames.dir[idx] : [])

  const spots = $derived(
    docs.map((d) => {
      const [x, y] = project(d.beach.lat, d.beach.lon)
      const h = d.hours.find((hh) => hh.t === time)
      return { id: d.id, name: d.displayName, x, y, hour: h }
    }),
  )

  const dayTicks = $derived(
    frames
      ? frames.times
          .map((t, i) => ({ t, i }))
          .filter(({ t, i }) => i === 0 || t.slice(11, 13) === '00')
          .map(({ t, i }) => ({ i, label: weekdayShort(t.slice(0, 10)) }))
      : [],
  )

  $effect(() => {
    if (!playing || !frames) return
    const last = frames.times.length - 1
    const id = setInterval(() => {
      if (idx >= last) playing = false
      else idx += 1
    }, 400)
    return () => clearInterval(id)
  })

  function step(d: number) {
    if (!frames) return
    playing = false
    idx = Math.max(0, Math.min(frames.times.length - 1, idx + d))
  }

  function togglePlay() {
    if (!frames) return
    if (!playing && idx >= frames.times.length - 1) idx = 0
    playing = !playing
  }

  function onMapClick(e: MouseEvent) {
    if (!svgEl || !points.length) return
    const ctm = svgEl.getScreenCTM()
    if (!ctm) return
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse())
    picked = nearestPoint(p.x, p.y, points)
  }

  // Keyboard: arrow keys walk the grid (lats ascend, so "up" is +1 row).
  function onMapKey(e: KeyboardEvent) {
    if (!frames) return
    const nLon = frames.lons.length
    const nLat = frames.lats.length
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [1, 0], ArrowDown: [-1, 0],
    }
    const m = moves[e.key]
    if (!m) return
    e.preventDefault()
    const cur = picked ?? Math.floor(nLat / 2) * nLon + Math.floor(nLon / 2)
    const r = Math.max(0, Math.min(nLat - 1, Math.floor(cur / nLon) + m[0]))
    const c = Math.max(0, Math.min(nLon - 1, (cur % nLon) + m[1]))
    picked = r * nLon + c
  }

  const pickedInfo = $derived.by(() => {
    if (picked == null || !frames) return null
    const k = kn[picked]
    const d = dir[picked]
    const p = points[picked]
    if (k == null || d == null || !p) return null
    return { kn: Math.round(k / 10), dir: d, lat: p.lat, lon: p.lon, land: p.land }
  })
</script>

<section class="map-card" aria-labelledby="map-title">
  <div class="map-head">
    <h2 id="map-title">Wind map</h2>
    {#if frames}
      <p class="when" aria-live="polite">
        <strong>{dayName(time.slice(0, 10))} {hourLabel(time)}</strong>
        <span class="muted">{dateLabel(time.slice(0, 10))} · HST</span>
      </p>
    {/if}
  </div>

  {#if error}
    <p class="status error">Map data isn't available right now ({error}).</p>
  {:else}
    <div class="map-wrap" style:aspect-ratio="{coast.width} / {coast.height}">
      <!-- role="application" is a keyboard-operable widget (arrow keys move the reading
           point, see onMapKey); Svelte's checker doesn't count it as interactive. -->
      <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
      <svg
        bind:this={svgEl}
        viewBox="0 0 {coast.width} {coast.height}"
        role="application"
        tabindex="0"
        aria-label={frames
          ? `Wind over Maui, ${dayName(time.slice(0, 10))} ${hourLabel(time)}. Arrow keys move the reading point.`
          : 'Wind map of Maui'}
        onclick={onMapClick}
        onkeydown={onMapKey}
      >
        <rect class="ocean" x="0" y="0" width={coast.width} height={coast.height} />
        {#if frames}
          <g class="heat" aria-hidden="true">
            {#each points as p, i (i)}
              {#if !p.land && kn[i] != null}
                <rect
                  class="b{knBand(kn[i]! / 10)}"
                  x={p.x - cell.w / 2}
                  y={p.y - cell.h / 2}
                  width={cell.w + 0.5}
                  height={cell.h + 0.5}
                />
              {/if}
            {/each}
          </g>
        {/if}
        <path class="land" d={coast.path} />
        {#if frames}
          <g class="arrows" aria-hidden="true">
            {#each points as p, i (i)}
              {#if kn[i] != null && dir[i] != null}
                <path
                  class="arrow b{knBand(kn[i]! / 10)}"
                  class:on-land={p.land}
                  d={arrowPath(arrowLength(kn[i]! / 10))}
                  transform="translate({p.x.toFixed(1)} {p.y.toFixed(1)}) rotate({dir[i]! + 180})"
                />
              {/if}
            {/each}
          </g>
          {#if picked != null && points[picked]}
            <circle class="picked" cx={points[picked].x} cy={points[picked].y} r="24" />
          {/if}
        {/if}
        {#each spots as s (s.id)}
          <circle class="spot" cx={s.x} cy={s.y} r="8" />
        {/each}
      </svg>

      {#each spots as s (s.id)}
        <a
          class="spot-label {LABEL_SIDE[s.id] ?? 'right'}"
          href="#/spot/{s.id}"
          style:left="{(s.x / coast.width) * 100}%"
          style:top="{(s.y / coast.height) * 100}%"
        >
          <span class="name">{s.name.replace(/\s*\(.*\)/, '')}</span>
          {#if s.hour}
            <span class="val kn-{knBand(s.hour.wrf.kn)}">{Math.round(s.hour.wrf.kn)}</span>
            {#if s.hour.sector === 'danger'}<span class="warn" title="Offshore at this spot">⚠</span>{/if}
          {/if}
        </a>
      {/each}

      {#if !frames}
        <p class="loading">Loading wind…</p>
      {/if}
    </div>

    {#if frames}
      <div class="controls">
        <button type="button" class="ctl" onclick={() => step(-1)} aria-label="Previous hour">‹</button>
        <button type="button" class="ctl play" onclick={togglePlay} aria-label={playing ? 'Pause' : 'Play forecast'}>
          {playing ? '❚❚' : '▶'}
        </button>
        <button type="button" class="ctl" onclick={() => step(1)} aria-label="Next hour">›</button>
        <div class="slider">
          <input
            type="range"
            min="0"
            max={frames.times.length - 1}
            bind:value={idx}
            oninput={() => (playing = false)}
            aria-label="Forecast hour"
            aria-valuetext="{dayName(time.slice(0, 10))} {hourLabel(time)}"
            style:background={nightGradient(frames.daylight)}
          />
          <div class="ticks" aria-hidden="true">
            {#each dayTicks as d (d.i)}
              <span style:left="{(d.i / (frames.times.length - 1)) * 100}%">{d.label}</span>
            {/each}
          </div>
        </div>
      </div>

      <div class="foot">
        <ul class="legend" aria-label="Wind speed colours, knots">
          {#each BANDS as label, b (b)}
            <li><span class="sw b{b}"></span>{label}</li>
          {/each}
          <li class="unit">kn</li>
        </ul>
        <p class="info" aria-live="polite">
          {#if pickedInfo}
            <strong>{pickedInfo.kn} kn</strong> from {compass(pickedInfo.dir)} ({pickedInfo.dir}°) at
            {pickedInfo.lat.toFixed(2)}°N {Math.abs(pickedInfo.lon).toFixed(2)}°W{pickedInfo.land ? ' (over land)' : ''}
          {:else}
            Arrows point where the wind blows. Tap the map (or use the arrow keys) to read a value.
          {/if}
        </p>
      </div>
    {/if}
  {/if}
</section>

<style>
  .map-card {
    margin-top: 16px;
    padding: 14px 16px 12px;
    border-radius: 14px;
    background: var(--surface);
    border: 1px solid var(--border);
  }
  .map-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    justify-content: space-between;
    gap: 4px 12px;
    margin-bottom: 8px;
  }
  h2 {
    margin: 0;
    font-size: 1.1rem;
  }
  .when {
    margin: 0;
    font-size: 0.95rem;
  }
  .muted {
    color: var(--muted);
    font-size: 0.82rem;
    margin-left: 4px;
  }
  .map-wrap {
    position: relative;
    width: 100%;
    max-width: 760px;
    margin: 0 auto;
    border-radius: 10px;
    overflow: hidden;
  }
  svg {
    display: block;
    width: 100%;
    height: 100%;
    cursor: crosshair;
    touch-action: manipulation;
  }
  .ocean { fill: var(--ocean); }
  .land {
    fill: var(--land);
    stroke: var(--land-stroke);
    stroke-width: 2;
    stroke-linejoin: round;
  }
  .heat rect { opacity: var(--heat-opacity); }
  .heat .b0 { fill: var(--map-kn0); }
  .heat .b1 { fill: var(--map-kn1); }
  .heat .b2 { fill: var(--map-kn2); }
  .heat .b3 { fill: var(--map-kn3); }
  .heat .b4 { fill: var(--map-kn4); }
  .heat .b5 { fill: var(--map-kn5); }
  .heat .b6 { fill: var(--map-kn6); }
  .arrow {
    fill: none;
    stroke-width: 4.5;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .arrow.b0 { stroke: var(--map-kn0); }
  .arrow.b1 { stroke: var(--map-kn1); }
  .arrow.b2 { stroke: var(--map-kn2); }
  .arrow.b3 { stroke: var(--map-kn3); }
  .arrow.b4 { stroke: var(--map-kn4); }
  .arrow.b5 { stroke: var(--map-kn5); }
  .arrow.b6 { stroke: var(--map-kn6); }
  .arrow.on-land { opacity: 0.35; }
  .spot {
    fill: var(--spot-fill);
    stroke: var(--spot-stroke);
    stroke-width: 4;
  }
  .picked {
    fill: none;
    stroke: var(--text);
    stroke-width: 3;
    stroke-dasharray: 6 5;
  }
  .spot-label {
    position: absolute;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px 2px 7px;
    border-radius: 8px;
    background: var(--label-bg);
    color: var(--text);
    font-size: 0.75rem;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
    transform: translate(10px, -50%);
  }
  .spot-label.left {
    transform: translate(calc(-100% - 10px), -50%);
  }
  .spot-label .val {
    min-width: 1.8em;
    text-align: center;
    border-radius: 5px;
    padding: 0 3px;
    font-variant-numeric: tabular-nums;
  }
  .spot-label .warn {
    color: var(--danger-fg);
  }
  .loading {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    margin: 0;
    color: var(--muted);
  }
  .controls {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    max-width: 760px;
    margin: 10px auto 0;
  }
  .ctl {
    flex: none;
    width: 36px;
    height: 32px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text);
    font-size: 1rem;
    cursor: pointer;
  }
  .ctl.play {
    width: 42px;
    font-size: 0.85rem;
  }
  .slider {
    position: relative;
    flex: 1;
    min-width: 0;
    padding-top: 6px;
  }
  input[type='range'] {
    width: 100%;
    margin: 0;
    height: 20px;
    border-radius: 10px;
    appearance: none;
    -webkit-appearance: none;
    cursor: pointer;
  }
  input[type='range']::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--accent);
    border: 3px solid var(--surface);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
  }
  input[type='range']::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--accent);
    border: 3px solid var(--surface);
  }
  .ticks {
    position: relative;
    height: 16px;
    margin-top: 2px;
  }
  .ticks span {
    position: absolute;
    top: 0;
    font-size: 0.68rem;
    color: var(--muted);
    white-space: nowrap;
    border-left: 1px solid var(--border);
    padding-left: 3px;
  }
  .foot {
    max-width: 760px;
    margin: 6px auto 0;
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 0.72rem;
    color: var(--muted);
  }
  .legend li {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .sw {
    display: inline-block;
    width: 14px;
    height: 8px;
    border-radius: 2px;
  }
  .sw.b0 { background: var(--map-kn0); }
  .sw.b1 { background: var(--map-kn1); }
  .sw.b2 { background: var(--map-kn2); }
  .sw.b3 { background: var(--map-kn3); }
  .sw.b4 { background: var(--map-kn4); }
  .sw.b5 { background: var(--map-kn5); }
  .sw.b6 { background: var(--map-kn6); }
  .info {
    margin: 6px 0 0;
    font-size: 0.82rem;
    color: var(--muted);
    min-height: 1.3em;
  }
  .info strong {
    color: var(--text);
  }
</style>
