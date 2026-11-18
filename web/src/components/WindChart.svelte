<script lang="ts">
  // One day of wind for a spot: wind and estimated-gust curves on one axis (plus the
  // adjusted forecast, dashed, where the spot has one, and the NWS forecast, dotted), the best session
  // highlighted, and a strip of direction arrows under the time axis.
  // Below, on the same time axis: a sky strip (sun, cloud, showers by hour), a wave
  // strip (3-hour cells with height and period, the wave type underneath) and a
  // slim tide panel with its highs and lows.
  // Hover/tap/keyboard selects an hour (`focus`), shared with the map and stats.
  import { areaPath, axisTicks, monotonePath, segments, type Pt } from '../lib/chart'
  import { compass, hourLabel, knBand } from '../lib/format'
  import { arrowPath } from '../lib/map'
  import { SKY_LABEL, skyIcon } from '../lib/sky'
  import SkyIcon from './SkyIcon.svelte'
  import {
    WAVE_TYPE,
    lengthUnit,
    nextExtreme,
    tideAt,
    tideDay,
    tideHeight,
    tideRange,
    typeRuns,
    waveBand,
    waveCells,
    waveHeight,
    waveNumber,
  } from '../lib/sea'
  import { tempLabel, windIn, windLabel, windUnitLabel, type TempUnit, type WindUnit } from '../lib/units'
  import type { Hour, Sector, SpotDoc, SunDay, Tide } from '../lib/types'

  let {
    hours,
    next = null,
    prev = null,
    sun,
    yMax,
    wind,
    temp,
    nowHours = null,
    best = null,
    focus = $bindable(null),
    compact = false,
    label,
    date = '',
    tide = null,
    waveStatus = null,
  }: {
    hours: (Hour | null)[] // 24 slots, index = HST hour
    next?: Hour | null // next day's midnight: the curve reaches the right edge
    prev?: Hour | null
    sun?: SunDay
    yMax: number // in the display unit
    wind: WindUnit
    temp: TempUnit
    nowHours?: number | null
    best?: { start: number; end: number } | null // hours [start, end)
    focus?: number | null
    compact?: boolean
    label: string
    date?: string // YYYY-MM-DD, to cut the tide curve
    tide?: Tide | null
    waveStatus?: NonNullable<SpotDoc['waves']>['status'] | null
  } = $props()

  const uid = $props.id()
  let width = $state(0)

  const SECTOR: Record<Sector, string> = {
    good: 'good direction',
    ok: 'OK direction',
    poor: 'poor direction',
    danger: 'offshore, dangerous',
  }

  // Layout (px), drawn at the real pixel width so text stays crisp.
  const G = $derived(compact ? 6 : 36)
  const R = $derived(compact ? 6 : 10)
  const T = $derived(compact ? 18 : 30)
  const plotH = $derived(compact ? 64 : width < 560 ? 168 : 232)
  const plotW = $derived(Math.max(0, width - G - R))
  const axisY = $derived(T + plotH)
  const dirY = $derived(axisY + 38)
  const dirStep = $derived(plotW / 24 >= 16 ? 1 : 2) // arrows and sky icons every hour, or every 2 h when narrow

  // Sea rows (full chart only).
  const cells = $derived(compact ? [] : waveCells(hours))
  const runs = $derived(typeRuns(cells))
  const sheltered = $derived(!compact && waveStatus === 'sheltered')
  const showWaves = $derived(sheltered || cells.some(Boolean))
  const tday = $derived(!compact && tide && date ? tideDay(tide, date) : null)
  const showTide = $derived(!!tday && tday.pts.length > 1)
  const tRange = $derived(tide ? tideRange(tide) : [0, 1])

  const showSky = $derived(!compact && hours.some((h) => h?.sky))
  const skyTitleY = $derived(dirY + 34)
  const skyY = $derived(skyTitleY + 20) // icon centres
  const skyEnd = $derived(showSky ? skyY + 12 : dirY + 10)
  const skySize = $derived(Math.min(19, (plotW / 24) * dirStep * 0.95))

  const wavesTitleY = $derived(showSky ? skyEnd + 26 : dirY + 34)
  const cellY = $derived(wavesTitleY + 8)
  const cellH = 34
  const runY = $derived(cellY + cellH + 15)
  const wavesEnd = $derived(showWaves ? (sheltered ? cellY + cellH : runY) : skyEnd)
  const tideTitleY = $derived(wavesEnd + 30)
  const tideTop = $derived(tideTitleY + 24) // highs are labelled above this line
  const tideH = $derived(width < 560 ? 40 : 50)
  const tideBottom = $derived(tideTop + tideH) // lows below this one
  const sectionsEnd = $derived(showTide ? tideBottom + 20 : wavesEnd + 8)
  const height = $derived(compact ? axisY + 4 : Math.max(dirY + 16, sectionsEnd))

  const ty = (ft: number) => {
    const [lo, hi] = tRange
    return tideBottom - ((ft - lo) / Math.max(hi - lo, 0.5)) * tideH
  }
  const tidePts = $derived(tday ? tday.pts.map(([h, v]) => [x(h), ty(v)] as Pt) : [])
  const tideLabels = $derived.by(() => {
    if (!tday) return []
    return tday.extremes.map((e) => {
      const text = `${e.type} ${tideHeight(e.ft, temp)} · ${clock(e.t)}`
      const w = text.length * 6.1
      const cx = x(e.h)
      const anchor = cx - w / 2 < G ? 'start' : cx + w / 2 > G + plotW ? 'end' : 'middle'
      const lx = anchor === 'start' ? Math.max(G, cx - 6) : anchor === 'end' ? Math.min(G + plotW, cx + 6) : cx
      return { ...e, text, cx, cy: ty(e.ft), lx, anchor }
    })
  })
  const clock = (iso: string) => {
    const h = Number(iso.slice(11, 13))
    return `${h % 12 || 12}:${iso.slice(14, 16)} ${h < 12 ? 'AM' : 'PM'}`
  }
  // Wave cells get one hue, stronger with size; text stays in the text colour.
  const WAVE_ALPHA = [0.07, 0.16, 0.26, 0.38, 0.5, 0.62]
  const runLabel = (r: { from: number; to: number; type: keyof typeof WAVE_TYPE }) => {
    const w = x(r.to) - x(r.from) - 6
    const long = WAVE_TYPE[r.type].long
    if (long.length * 6.4 <= w) return long
    const short = WAVE_TYPE[r.type].short
    return short.length * 6.4 <= w ? short : ''
  }

  const x = (t: number) => G + (t / 24) * plotW // t = HST hour, 0..24
  const val = (kn: number) => windIn(kn, wind)
  const y = (v: number) => T + plotH * (1 - Math.min(v, yMax) / yMax)

  const series = $derived([prev, ...hours, next])
  const tAt = (i: number) => i - 1
  const windRuns = $derived(segments(series, (h, i) => [x(tAt(i)), y(val(h.wrf.kn))] as Pt))
  const gustRuns = $derived(segments(series, (h, i) => [x(tAt(i)), y(val(h.wrf.gustEst))] as Pt))
  const adjRuns = $derived(
    segments(
      series.map((h) => (h && h.wrf.knAdj != null ? h : null)),
      (h, i) => [x(tAt(i)), y(val(h.wrf.knAdj!))] as Pt,
    ),
  )
  const nwsRuns = $derived(
    segments(
      series.map((h) => (h?.nws ? h : null)),
      (h, i) => [x(tAt(i)), y(val(h.nws!.kn))] as Pt,
    ),
  )
  const ticks = $derived(axisTicks(yMax))

  const bandVar = (kn: number) => `var(--wind-kn${knBand(kn)})`
  const gradStops = $derived(
    series.flatMap((h, i) => (h ? [{ o: i / (series.length - 1), c: bandVar(h.wrf.kn) }] : [])),
  )

  // The labelled peak: inside the best session, else the windiest daylight hour.
  const peak = $derived.by(() => {
    let bestH: { i: number; h: Hour } | null = null
    hours.forEach((h, i) => {
      if (!h) return
      const inside = best ? i >= best.start && i < best.end : h.daylight
      if (inside && (!bestH || h.wrf.kn > bestH.h.wrf.kn)) bestH = { i, h }
    })
    return bestH as { i: number; h: Hour } | null
  })

  const night = $derived.by(() => {
    if (!sun || compact) return []
    const toH = (s: string) => {
      const [a, b] = s.split(':').map(Number)
      return a + b / 60
    }
    return [
      { x0: x(0), x1: x(toH(sun.rise)) },
      { x0: x(toH(sun.set)), x1: x(24) },
    ]
  })

  // Time labels: 12 AM, 6 AM, 12 PM, 6 PM, 12 AM, plus the session bounds; base
  // labels too close to a session label give way.
  const timeTicks = $derived.by(() => {
    if (compact) return []
    const session = best ? [best.start, best.end] : []
    const minGap = plotW < 420 ? 3 : 2
    const base = [0, 6, 12, 18, 24].filter((h) => session.every((s) => Math.abs(s - h) >= minGap || s === h))
    const all = [...new Set([...base, ...session])].sort((a, b) => a - b)
    return all.map((h) => ({ h, accent: session.includes(h) }))
  })
  const tickText = (h: number) => `${h % 12 || 12} ${h % 24 < 12 ? 'AM' : 'PM'}`


  function pick(e: PointerEvent) {
    if (compact) return
    const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
    const i = Math.round(((e.clientX - r.left - G) / plotW) * 24)
    if (i >= 0 && i < 24 && hours[i]) focus = i
  }
  function onKey(e: KeyboardEvent) {
    const filled = hours.map((h, i) => (h ? i : -1)).filter((i) => i >= 0)
    if (!filled.length) return
    const cur = focus ?? (nowHours != null ? Math.floor(nowHours) : peak?.i ?? filled[0])
    let n: number | null = cur
    if (e.key === 'ArrowRight') n = filled.find((i) => i > cur) ?? cur
    else if (e.key === 'ArrowLeft') n = [...filled].reverse().find((i) => i < cur) ?? cur
    else if (e.key === 'Home') n = filled[0]
    else if (e.key === 'End') n = filled[filled.length - 1]
    else if (e.key === 'Escape') n = null
    else return
    e.preventDefault()
    focus = n
  }

  const focusHour = $derived(focus != null ? hours[focus] : null)
  const focusTide = $derived(focusHour && tide ? tideAt(tide, focusHour.t) : null)
  const focusTurn = $derived(focusHour && tide ? nextExtreme(tide, focusHour.t) : null)
  let tipW = $state(0)
  const tipX = $derived.by(() => {
    if (focus == null) return 0
    const cx = x(focus)
    if (cx + 14 + tipW <= width) return cx + 14
    return Math.max(0, cx - 14 - tipW)
  })
</script>

<div class="chart" class:compact bind:clientWidth={width}>
  {#if width > 0}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
    <svg
      {width}
      {height}
      viewBox="0 0 {width} {height}"
      role={compact ? 'img' : 'application'}
      aria-label={compact
        ? `${label}: wind and gust`
        : `${label}: wind and estimated gust in ${windUnitLabel(wind)} by hour${showSky ? ', sky' : ''}${showWaves ? ', waves' : ''}${showTide ? ', tide' : ''}. Left and right arrow keys read each hour.`}
      tabindex={compact ? undefined : 0}
      onpointermove={pick}
      onpointerdown={pick}
      onpointerleave={(e) => {
        if (e.pointerType === 'mouse') focus = null
      }}
      onkeydown={compact ? undefined : onKey}
    >
      <defs>
        <clipPath id="plot-{uid}">
          <rect x={G} y={0} width={plotW} height={axisY} />
        </clipPath>
        <linearGradient id="band-{uid}" gradientUnits="userSpaceOnUse" x1={x(-1)} y1="0" x2={x(25)} y2="0">
          {#each gradStops as s, k (k)}
            <stop offset={s.o} style:stop-color={s.c} />
          {/each}
        </linearGradient>
        <linearGradient id="fade-{uid}" gradientUnits="userSpaceOnUse" x1="0" y1={T} x2="0" y2={axisY}>
          <stop offset="0" stop-color="#fff" stop-opacity="0.75" />
          <stop offset="1" stop-color="#fff" stop-opacity="0.04" />
        </linearGradient>
        <mask id="mask-{uid}" maskUnits="userSpaceOnUse">
          <rect x={G} y={0} width={plotW} height={axisY} fill="url(#fade-{uid})" />
        </mask>
        <linearGradient id="amber-{uid}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="var(--accent)" stop-opacity="0.55" />
          <stop offset="1" stop-color="var(--accent)" stop-opacity="0.12" />
        </linearGradient>
        <clipPath id="under-{uid}">
          {#each windRuns as run, k (k)}
            <path d={areaPath(run, y(0))} />
          {/each}
        </clipPath>
      </defs>

      {#each night as n, k (k)}
        <rect class="night" x={n.x0} y={T - 4} width={Math.max(0, n.x1 - n.x0)} height={height - T + 2} />
      {/each}

      {#if !compact}
        <text class="unit" x={G - 8} y={T - 14} text-anchor="end">{windUnitLabel(wind)}</text>
      {/if}
      {#each ticks as v (v)}
        <line class={v === 0 ? 'base' : 'grid'} x1={G} x2={G + plotW} y1={y(v)} y2={y(v)} />
        {#if !compact}
          <text class="tick" x={G - 8} y={y(v) + 4} text-anchor="end">{v}</text>
        {/if}
      {/each}

      <g clip-path="url(#plot-{uid})">
        {#each windRuns as run, k (k)}
          <path class="area" d={areaPath(run, y(0))} fill="url(#band-{uid})" mask="url(#mask-{uid})" />
        {/each}
        {#if best}
          <rect class="session-band" x={x(best.start)} y={T - 4} width={x(best.end) - x(best.start)} height={plotH + 4} />
          <rect
            x={x(best.start)}
            y={T}
            width={x(best.end) - x(best.start)}
            height={plotH}
            fill="url(#amber-{uid})"
            clip-path="url(#under-{uid})"
          />
        {/if}
        {#each gustRuns as run, k (k)}
          <path class="gust" d={monotonePath(run)} />
        {/each}
        {#each windRuns as run, k (k)}
          <path class="wind" d={monotonePath(run)} stroke="url(#band-{uid})" />
        {/each}
        {#each nwsRuns as run, k (k)}
          <path class="nws" d={monotonePath(run)} />
        {/each}
        {#each adjRuns as run, k (k)}
          <path class="adj" d={monotonePath(run)} />
        {/each}
      </g>

      {#if nowHours != null && !compact}
        <line class="now" x1={x(nowHours)} x2={x(nowHours)} y1={T - 4} y2={axisY} />
        <text class="now-label" x={x(nowHours)} y={T - 14} text-anchor="middle">NOW</text>
      {/if}

      {#if peak && focus == null}
        <circle class="peak-dot" cx={x(peak.i)} cy={y(val(peak.h.wrf.kn))} r={compact ? 3.5 : 5} />
        <text class="peak" class:small={compact} x={x(peak.i)} y={y(val(peak.h.wrf.kn)) - (compact ? 7 : 12)} text-anchor="middle">
          {windLabel(peak.h.wrf.kn, wind)} {compact ? '' : windUnitLabel(wind)}
        </text>
      {/if}

      {#if focusHour && focus != null}
        <line class="cross" x1={x(focus)} x2={x(focus)} y1={T - 4} y2={height - 2} />
        <circle class="dot" cx={x(focus)} cy={y(val(focusHour.wrf.gustEst))} r="4" style:fill="var(--gust)" />
        <circle class="dot" cx={x(focus)} cy={y(val(focusHour.wrf.kn))} r="5" style:fill={bandVar(focusHour.wrf.kn)} />
        {#if focusHour.nws}
          <circle class="dot nws-dot" cx={x(focus)} cy={y(val(focusHour.nws.kn))} r="4" />
        {/if}
        {#if focusHour.wrf.knAdj != null}
          <circle class="dot adj-dot" cx={x(focus)} cy={y(val(focusHour.wrf.knAdj))} r="4" />
        {/if}
      {/if}

      {#each timeTicks as tk (tk.h)}
        <line class="tick-mark" class:accent={tk.accent} x1={x(tk.h)} x2={x(tk.h)} y1={axisY} y2={axisY + 5} />
        <text
          class="time"
          class:accent={tk.accent}
          x={x(tk.h)}
          y={axisY + 19}
          text-anchor={tk.h === 0 ? 'start' : tk.h === 24 ? 'end' : 'middle'}>{tickText(tk.h)}</text
        >
      {/each}

      {#if !compact}
        {#each hours as h, i (i)}
          {#if h && i % dirStep === 0}
            <g transform="translate({x(i)} {dirY}) rotate({h.wrf.dir + 180}) scale({Math.min(15, (plotW / 24) * dirStep * 0.8) / 20})">
              <path class="dir s-{h.sector}" d={arrowPath(20)} />
            </g>
          {/if}
        {/each}
      {/if}

      {#if showSky}
        <text class="section" x={G} y={skyTitleY}>Sky</text>
        {#each hours as h, i (i)}
          {#if h?.sky && (i % dirStep === 0 || h.sky === 'rain')}
            <g transform="translate({x(i) - skySize / 2} {skyY - skySize / 2}) scale({skySize / 24})">
              {#each skyIcon(h.sky) as p, k (k)}
                <path class="sky-{p.kind}" d={p.d} />
              {/each}
            </g>
          {/if}
        {/each}
      {/if}

      {#if showWaves}
        <text class="section" x={G} y={wavesTitleY}>Waves <tspan class="section-unit">{lengthUnit(temp)} · period</tspan></text>
        {#if sheltered}
          <rect class="wcell" x={G} y={cellY} width={plotW} height={cellH} rx="7" style:fill-opacity={WAVE_ALPHA[0]} />
          <text class="wnote" x={G + plotW / 2} y={cellY + cellH / 2 + 4} text-anchor="middle">Sheltered harbor: flat water, wind chop only</text>
        {:else}
          {#each cells as c, k (k)}
            {#if c}
              {@const cx = (x(c.from) + x(c.from + 3)) / 2}
              <rect
                class="wcell"
                x={x(c.from) + 1}
                y={cellY}
                width={Math.max(0, x(c.from + 3) - x(c.from) - 2)}
                height={cellH}
                rx="6"
                style:fill-opacity={WAVE_ALPHA[waveBand(c.wave.m)]}
              />
              <text class="wnum" x={cx} y={cellY + 15} text-anchor="middle">{waveNumber(c.wave.m, temp)}</text>
              {#if c.wave.per != null}
                <text class="wper" x={cx} y={cellY + 28} text-anchor="middle">{Math.round(c.wave.per)}s</text>
              {/if}
            {/if}
          {/each}
          {#each runs as r, k (k)}
            {@const lbl = runLabel(r)}
            <line class="run" x1={x(r.from) + 3} x2={x(r.to) - 3} y1={runY - 13} y2={runY - 13} />
            {#if lbl}
              <text class="wtype" x={(x(r.from) + x(r.to)) / 2} y={runY} text-anchor="middle">{lbl}</text>
            {/if}
          {/each}
        {/if}
      {/if}

      {#if showTide && tide}
        <text class="section" x={G} y={tideTitleY}>Tide <tspan class="section-unit">{lengthUnit(temp)}</tspan></text>
        <text class="section-src" x={G + plotW} y={tideTitleY} text-anchor="end">
          {tide.name}{tide.kind === 'subordinate' ? ' (curve estimated)' : ''}
        </text>
        <defs>
          <linearGradient id="tide-{uid}" gradientUnits="userSpaceOnUse" x1="0" y1={tideTop} x2="0" y2={tideBottom}>
            <stop offset="0" stop-color="var(--tide)" stop-opacity="0.32" />
            <stop offset="1" stop-color="var(--tide)" stop-opacity="0.04" />
          </linearGradient>
        </defs>
        <line class="grid" x1={G} x2={G + plotW} y1={tideBottom} y2={tideBottom} />
        <path d={areaPath(tidePts, tideBottom)} fill="url(#tide-{uid})" />
        <path class="tide" d={monotonePath(tidePts)} />
        {#each tideLabels as e (e.t)}
          <circle class="tide-dot" cx={e.cx} cy={e.cy} r="3.5" />
          <text
            class="tide-label"
            class:high={e.type === 'H'}
            x={e.lx}
            y={e.type === 'H' ? tideTop - 8 : tideBottom + 15}
            text-anchor={e.anchor}>{e.text}</text
          >
        {/each}
        {#if focus != null && focusTide != null}
          <circle class="dot" cx={x(focus)} cy={ty(focusTide)} r="4" style:fill="var(--tide)" />
        {/if}
      {/if}
    </svg>

    {#if !compact}
      <div class="tip" class:hidden={!focusHour} style:left="{tipX}px" bind:offsetWidth={tipW} aria-live="polite">
        {#if focusHour}
          <div class="tip-time">{hourLabel(focusHour.t)}</div>
          <div class="row"><span class="key" style:background={bandVar(focusHour.wrf.kn)}></span><strong>{windLabel(focusHour.wrf.kn, wind)} {windUnitLabel(wind)}</strong><span>wind</span></div>
          <div class="row"><span class="key gust"></span><strong>{windLabel(focusHour.wrf.gustEst, wind)} {windUnitLabel(wind)}</strong><span>gust est.</span></div>
          {#if focusHour.wrf.knAdj != null}
            <div class="row"><span class="key adj-key"></span><strong>{windLabel(focusHour.wrf.knAdj, wind)} {windUnitLabel(wind)}</strong><span>adjusted</span></div>
          {/if}
          {#if focusHour.nws}
            <div class="row">
              <span class="key nws-key"></span><strong>{windLabel(focusHour.nws.kn, wind)} {windUnitLabel(wind)}</strong>
              <span>NWS{focusHour.nws.gust != null ? ` · gusts ${windLabel(focusHour.nws.gust, wind)}` : ''}</span>
            </div>
          {/if}
          <div class="row">
            <svg class="s-{focusHour.sector}" viewBox="-12 -12 24 24" width="13" height="13" aria-hidden="true">
              <path d={arrowPath(20)} transform="rotate({focusHour.wrf.dir + 180})" fill="currentColor" />
            </svg>
            <strong>{compass(focusHour.wrf.dir)}</strong><span>{focusHour.wrf.dir}° · {SECTOR[focusHour.sector]}</span>
          </div>
          {#if focusHour.wave}
            <div class="row">
              <svg viewBox="-12 -12 24 24" width="13" height="13" aria-hidden="true">
                {#if focusHour.wave.dir != null}
                  <path d={arrowPath(20)} transform="rotate({focusHour.wave.dir + 180})" fill="var(--wave)" />
                {/if}
              </svg>
              <strong>{waveHeight(focusHour.wave.m, temp)}</strong>
              <span>{focusHour.wave.per != null ? `${Math.round(focusHour.wave.per)} s · ` : ''}{WAVE_TYPE[focusHour.wave.type].long.toLowerCase()}</span>
            </div>
          {/if}
          {#if focusTide != null}
            <div class="row">
              <span class="key tide-key"></span><strong>{tideHeight(focusTide, temp)}</strong>
              <span>tide{focusTurn ? `, ${focusTurn.type === 'H' ? 'rising' : 'falling'}` : ''}</span>
            </div>
          {/if}
          {#if focusHour.wrf.tairC != null || focusHour.sky}
            {@const rain = focusHour.wrf.rainMmH ?? 0}
            <div class="row" class:plain={!focusHour.sky}>
              {#if focusHour.sky}<SkyIcon sky={focusHour.sky} size={13} />{/if}
              {#if focusHour.wrf.tairC != null}<strong>{tempLabel(focusHour.wrf.tairC, temp)}</strong>{/if}
              <span
                >{focusHour.wrf.tairC != null ? 'air' : ''}{focusHour.sky
                  ? `${focusHour.wrf.tairC != null ? ' · ' : ''}${SKY_LABEL[focusHour.sky].toLowerCase()}${rain >= 0.2 ? ` ${rain.toFixed(1)} mm/h` : ''}`
                  : ''}</span
              >
            </div>
          {/if}
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .chart {
    position: relative;
    width: 100%;
    min-height: 60px;
  }
  svg {
    display: block;
    overflow: visible;
    touch-action: pan-y;
    -webkit-tap-highlight-color: transparent;
    user-select: none;
  }
  svg:focus {
    outline: none;
  }
  svg:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 4px;
    border-radius: 10px;
  }
  text {
    font-family: inherit;
  }
  .night {
    fill: rgba(0, 0, 0, 0.16);
  }
  .grid {
    stroke: var(--chart-grid);
    shape-rendering: crispEdges;
  }
  .base {
    stroke: var(--chart-axis);
    shape-rendering: crispEdges;
  }
  .tick,
  .unit,
  .time {
    fill: var(--muted);
    font-size: 12px;
    font-variant-numeric: tabular-nums;
  }
  .unit {
    font-size: 11px;
  }
  .time.accent {
    fill: var(--accent-2);
    font-weight: 700;
  }
  .tick-mark {
    stroke: var(--chart-axis);
  }
  .tick-mark.accent {
    stroke: var(--accent);
  }
  .area {
    opacity: 0.55;
  }
  .session-band {
    fill: var(--accent);
    opacity: 0.06;
  }
  .wind {
    fill: none;
    stroke-width: 3;
    stroke-linejoin: round;
    stroke-linecap: round;
    filter: drop-shadow(0 0 6px rgba(120, 200, 255, 0.25));
  }
  .compact .wind {
    stroke-width: 2.2;
  }
  .gust {
    fill: none;
    stroke: var(--gust);
    stroke-width: 1.6;
    stroke-linejoin: round;
    stroke-linecap: round;
    opacity: 0.85;
  }
  .adj {
    fill: none;
    stroke: var(--adj);
    stroke-width: 2;
    stroke-dasharray: 6 4;
    stroke-linecap: round;
    opacity: 0.95;
  }
  .adj-dot {
    fill: var(--adj);
  }
  .nws {
    fill: none;
    stroke: var(--nws);
    stroke-width: 3.4;
    stroke-dasharray: 0.1 6.5;
    stroke-linecap: round;
    opacity: 0.95;
  }
  .nws-dot {
    fill: var(--nws);
  }
  .key.nws-key {
    height: 0;
    border-top: 3px dotted var(--nws);
    border-radius: 0;
  }
  .key.adj-key {
    height: 0;
    border-top: 2px dashed var(--adj);
    border-radius: 0;
  }
  .now {
    stroke: var(--teal);
    stroke-width: 1.5;
    stroke-dasharray: 3 3;
  }
  .now-label {
    fill: var(--teal);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
  }
  .peak-dot {
    fill: var(--accent);
    stroke: #fff;
    stroke-width: 2;
  }
  .peak {
    fill: #fff;
    font-family: var(--font-display);
    font-size: 15px;
    font-weight: 700;
    paint-order: stroke;
    stroke: rgba(6, 18, 31, 0.85);
    stroke-width: 4px;
    stroke-linejoin: round;
  }
  .peak.small {
    font-size: 11px;
    stroke-width: 3px;
  }
  .cross {
    stroke: rgba(255, 255, 255, 0.35);
    shape-rendering: crispEdges;
  }
  .dot {
    stroke: var(--surface);
    stroke-width: 2;
  }
  .dir {
    fill: currentColor;
  }
  .tip {
    position: absolute;
    top: 0;
    min-width: 150px;
    padding: 9px 11px;
    border-radius: 12px;
    background: rgba(9, 24, 40, 0.96);
    border: 1px solid var(--border-strong);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.45);
    font-size: 0.8rem;
    line-height: 1.4;
    pointer-events: none;
    z-index: 2;
  }
  .tip.hidden {
    visibility: hidden;
  }
  .tip-time {
    font-weight: 700;
    margin-bottom: 3px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }
  .row span:last-child {
    color: var(--muted);
  }
  .row.plain {
    padding-left: 19px;
  }
  .key {
    width: 13px;
    height: 3px;
    border-radius: 2px;
    flex: none;
  }
  .key.gust {
    background: var(--gust);
    height: 2px;
  }
  .key.tide-key {
    background: var(--tide);
    height: 2px;
  }
  .section {
    fill: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .section-unit {
    fill: var(--faint);
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: none;
  }
  .section-src {
    fill: var(--faint);
    font-size: 11px;
  }
  .wcell {
    fill: var(--wave);
  }
  .wnum {
    fill: var(--text);
    font-size: 13px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }
  .wper {
    fill: var(--muted);
    font-size: 10.5px;
    font-variant-numeric: tabular-nums;
  }
  .wnote {
    fill: var(--muted);
    font-size: 12px;
  }
  .run {
    stroke: var(--wave);
    stroke-opacity: 0.45;
    stroke-width: 2;
    stroke-linecap: round;
  }
  .wtype {
    fill: var(--muted);
    font-size: 11.5px;
    font-weight: 600;
  }
  .tide {
    fill: none;
    stroke: var(--tide);
    stroke-width: 2;
    stroke-linejoin: round;
  }
  .tide-dot {
    fill: var(--tide);
    stroke: var(--surface);
    stroke-width: 2;
  }
  .tide-label {
    fill: var(--muted);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .tide-label.high {
    fill: var(--text);
  }
</style>
