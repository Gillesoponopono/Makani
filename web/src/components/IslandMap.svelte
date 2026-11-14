<script lang="ts">
  // The aerial picture of Maui with one marker per spot: a dot at the beach and a
  // chip with the wind arrow (pointing downwind, coloured by speed) and the
  // speed for the chosen hour, plus small dots for the measuring points: anemometers
  // (red) and wave buoys (yellow). Positions come from web/scripts/build-aerial.mjs.
  import aerial960 from '../assets/maui-aerial-960.webp'
  import aerial1536 from '../assets/maui-aerial-1536.webp'
  import placement from '../assets/maui-aerial-spots.json'
  import { chipWidth, layoutChips } from '../lib/callouts'
  import { compass, hourLabel, knBand } from '../lib/format'
  import { arrowPath } from '../lib/map'
  import { windLabel, windUnitLabel, type WindUnit } from '../lib/units'
  import type { Hour, SpotDoc } from '../lib/types'

  let {
    docs,
    selected,
    focusT,
    wind,
    hrefFor,
    mode = 'block',
  }: {
    docs: SpotDoc[]
    selected: string
    focusT: string | null // hour shown, as Hour.t
    wind: WindUnit
    hrefFor: (id: string) => string
    mode?: 'hero' | 'block' // hero: fills its parent, whole island; block: full width, cropped on the spots
  } = $props()

  const PW = placement.width
  const PH = placement.height
  const POS = placement.spots as Record<string, number[]>
  const STATIONS = Object.entries(
    (placement as { stations?: Record<string, { kind: 'anemometer' | 'buoy'; name: string; xy: number[] }> }).stations ?? {},
  ).map(([id, s]) => ({ id, ...s }))
  const STATION_LABEL = { anemometer: 'Anemometer', buoy: 'Wave buoy' }
  // Chips for these spots go below their dots, over the island; Kanahā's sits just above
  // the Harbor dot, lined up with the Harbor chip. That leaves Hoʻokipa alone in the bay row.
  const ON_LAND = ['harbor', 'sprecks']
  // Short chip names; the hero title carries the full one.
  const SHORT: Record<string, string> = { sprecks: 'Sprecks', harbor: 'Harbor', 'maui-sunset': 'Maui Sunset' }
  const shortName = (d: SpotDoc) => SHORT[d.id] ?? d.displayName.replace(/\s*\(.*\)/, '')

  // Crop of the 1536x1024 picture: whole island, or the central valley where all spots are.
  // The block crop starts above the picture (y < 0) so the north-shore chips have sea to
  // sit on: Hoʻokipa is close to the picture's top edge.
  const crop = $derived(mode === 'hero' ? { x: 0, y: 0, w: PW, h: PH } : { x: 150, y: -40, w: 720, h: 780 })

  let boxW = $state(0)
  let boxH = $state(0)
  // Real chip widths once rendered (the estimate only serves the first layout).
  let measured = $state<Record<string, number>>({})

  function hourAt(doc: SpotDoc, t: string | null): Hour | undefined {
    if (!t) return undefined
    return doc.hours.find((h) => h.t === t)
  }

  const markers = $derived.by(() => {
    if (!boxW || !boxH) return []
    const sx = boxW / crop.w
    const sy = boxH / crop.h
    const list = docs
      .filter((d) => POS[d.id])
      .map((d) => {
        const [px, py] = POS[d.id]
        const h = hourAt(d, focusT)
        const value = h ? String(windLabel(h.wrf.kn, wind)) : '–'
        return {
          id: d.id,
          name: shortName(d),
          x: (px - crop.x) * sx,
          y: (py - crop.y) * sy,
          hour: h,
          value,
          w: measured[d.id] || chipWidth(shortName(d), value),
        }
      })
    const chips = layoutChips(
      list.map(({ id, x, y, w }) => ({ id, x, y, w })),
      { w: boxW, h: boxH },
      {
        northBelowY: (420 - crop.y) * sy,
        rise: mode === 'hero' ? 54 : 50,
        land: ON_LAND,
        over: { kanaha: 'harbor' },
        avoid: STATIONS.map((s) => ({ x: (s.xy[0] - crop.x) * sx, y: (s.xy[1] - crop.y) * sy })),
      },
    )
    return list.map((m) => ({ ...m, chip: chips.find((c) => c.id === m.id)! }))
  })

  const shownHour = $derived(markers.find((m) => m.hour)?.hour)

  const stationDots = $derived.by(() => {
    if (!boxW || !boxH) return []
    const sx = boxW / crop.w
    const sy = boxH / crop.h
    return STATIONS.map((s) => ({ ...s, x: (s.xy[0] - crop.x) * sx, y: (s.xy[1] - crop.y) * sy })).filter(
      (s) => s.x >= 0 && s.x <= boxW && s.y >= 0 && s.y <= boxH,
    )
  })
</script>

<div class="island {mode}" style:aspect-ratio={mode === 'block' ? `${crop.w} / ${crop.h}` : undefined} bind:clientWidth={boxW} bind:clientHeight={boxH}>
  <img
    src={aerial960}
    srcset="{aerial960} 960w, {aerial1536} 1536w"
    sizes={mode === 'hero' ? '(min-width: 760px) 640px, 100vw' : '(min-width: 760px) 640px, 200vw'}
    alt="Aerial view of Maui with the forecast spots"
    decoding="async"
    style:left="{(-crop.x / crop.w) * 100}%"
    style:top="{(-crop.y / crop.h) * 100}%"
    style:width="{(PW / crop.w) * 100}%"
    style:height="{(PH / crop.h) * 100}%"
  />

  <svg class="leaders" viewBox="0 0 {boxW || 1} {boxH || 1}" aria-hidden="true">
    {#each markers as m (m.id)}
      <line x1={m.x} y1={m.y} x2={m.chip.cx} y2={m.chip.cy} class:sel={m.id === selected} />
    {/each}
  </svg>

  {#each markers as m (m.id)}
    <span class="dot" class:sel={m.id === selected} style:left="{m.x}px" style:top="{m.y}px" aria-hidden="true"></span>
  {/each}

  {#each stationDots as s (s.id)}
    <span
      class="st {s.kind}"
      style:left="{s.x}px"
      style:top="{s.y}px"
      title="{STATION_LABEL[s.kind]}: {s.name}"
      role="img"
      aria-label="{STATION_LABEL[s.kind]}: {s.name}"
    ></span>
  {/each}

  {#each markers as m (m.id)}
    <a
      class="chip"
      class:sel={m.id === selected}
      href={hrefFor(m.id)}
      style:left="{m.chip.cx}px"
      style:top="{m.chip.cy}px"
      aria-current={m.id === selected ? 'true' : undefined}
      bind:offsetWidth={measured[m.id]}
      aria-label={m.hour
        ? `${m.name}: ${m.value} ${windUnitLabel(wind)} from ${compass(m.hour.wrf.dir)}${m.hour.sector === 'danger' ? ', offshore' : ''}`
        : m.name}
    >
      <span class="disc">
        {#if m.hour}
          <svg viewBox="-12 -12 24 24" width="20" height="20" aria-hidden="true">
            <path
              d={arrowPath(19)}
              transform="rotate({m.hour.wrf.dir + 180})"
              style:fill="var(--wind-kn{knBand(m.hour.wrf.kn)})"
            />
          </svg>
        {/if}
      </span>
      <span class="name">{m.name}</span>
      <span class="val">{m.value}{#if m.hour && m.hour.sector === 'danger'}<span class="warn" title="Offshore">⚠</span>{/if}</span>
    </a>
  {/each}

  <div class="corner">
    {#if stationDots.length}
      <ul class="key" aria-label="Measuring points">
        {#if stationDots.some((s) => s.kind === 'anemometer')}<li><span class="st anemometer"></span>Anemometer</li>{/if}
        {#if stationDots.some((s) => s.kind === 'buoy')}<li><span class="st buoy"></span>Wave buoy</li>{/if}
      </ul>
    {/if}
    {#if shownHour}
      <p class="when">Wind at {hourLabel(shownHour.t)}</p>
    {/if}
  </div>
</div>

<style>
  .island {
    position: relative;
    overflow: hidden;
  }
  .island.hero {
    width: 100%;
    height: 100%;
  }
  .island.block {
    width: 100%;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    background: var(--bg-hero);
  }
  img {
    position: absolute;
    max-width: none;
    object-fit: fill;
    user-select: none;
    pointer-events: none;
  }
  .block img {
    /* the picture's top edge fades into the sea band above it */
    -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 7%);
    mask-image: linear-gradient(to bottom, transparent 0, #000 7%);
  }
  .hero img {
    /* melt the picture's edges into the hero's sea */
    -webkit-mask-image: radial-gradient(ellipse 72% 70% at 55% 50%, #000 62%, transparent 100%);
    mask-image: radial-gradient(ellipse 72% 70% at 55% 50%, #000 62%, transparent 100%);
  }
  .leaders {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }
  .leaders line {
    stroke: rgba(255, 255, 255, 0.55);
    stroke-width: 1;
  }
  .leaders line.sel {
    stroke: var(--accent-2);
    stroke-width: 1.5;
  }
  .dot {
    position: absolute;
    width: 9px;
    height: 9px;
    margin: -4.5px 0 0 -4.5px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 0 0 2px rgba(6, 18, 31, 0.85), 0 1px 4px rgba(0, 0, 0, 0.5);
  }
  .dot.sel {
    width: 12px;
    height: 12px;
    margin: -6px 0 0 -6px;
    background: var(--accent);
    box-shadow: 0 0 0 2.5px #fff, 0 0 12px rgba(246, 166, 35, 0.8);
  }
  .chip {
    position: absolute;
    transform: translate(-50%, -50%);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 30px;
    padding: 0 10px 0 4px;
    border-radius: 999px;
    background: rgba(6, 20, 36, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.18);
    -webkit-backdrop-filter: blur(6px);
    backdrop-filter: blur(6px);
    color: #fff;
    text-decoration: none;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
    transition: border-color 0.15s, background 0.15s;
  }
  .chip:hover {
    border-color: rgba(255, 255, 255, 0.45);
  }
  .chip.sel {
    border-color: var(--accent);
    background: rgba(40, 26, 6, 0.82);
    box-shadow: 0 0 0 1px rgba(246, 166, 35, 0.35), 0 6px 18px rgba(0, 0, 0, 0.4);
  }
  .disc {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
  }
  .disc svg {
    filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.6));
  }
  .name {
    color: rgba(255, 255, 255, 0.9);
  }
  .val {
    margin-left: auto;
    font-variant-numeric: tabular-nums;
    font-weight: 800;
  }
  .warn {
    margin-left: 3px;
    color: var(--danger);
  }
  .when {
    position: absolute;
    left: 10px;
    bottom: 8px;
    margin: 0;
    padding: 3px 9px;
    border-radius: 999px;
    background: rgba(6, 20, 36, 0.7);
    color: rgba(255, 255, 255, 0.85);
    font-size: 0.72rem;
    font-weight: 600;
  }
  .corner {
    position: absolute;
    right: 10px;
    bottom: 8px;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 5px;
  }
  .hero .corner {
    right: 12px;
    bottom: 14px;
  }
  .corner .when {
    position: static;
  }
  .key {
    display: flex;
    gap: 10px;
    margin: 0;
    padding: 3px 9px;
    list-style: none;
    border-radius: 999px;
    background: rgba(6, 20, 36, 0.7);
    color: rgba(255, 255, 255, 0.85);
    font-size: 0.68rem;
    font-weight: 600;
  }
  .key li {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .block .key {
    /* narrow on phones: one item per line, clear of the Kīhei chips on the left */
    flex-direction: column;
    gap: 2px;
    border-radius: 10px;
  }
  .key .st {
    position: static;
    margin: 0;
  }
  .st {
    position: absolute;
    width: 7px;
    height: 7px;
    margin: -3.5px 0 0 -3.5px;
    border-radius: 50%;
    box-shadow: 0 0 0 1.5px rgba(6, 18, 31, 0.9);
  }
  .st.anemometer {
    background: #ff5a4f;
  }
  .st.buoy {
    background: #ffd84a;
  }
  .block .chip {
    height: 28px;
    gap: 5px;
    padding: 0 9px 0 3px;
    font-size: 0.74rem;
  }
  .block .disc {
    width: 22px;
    height: 22px;
  }
</style>
