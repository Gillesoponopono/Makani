import { describe, expect, it } from 'vitest'
import { chipWidth, layoutChips } from './callouts'

const overlap = (a: { cx: number; cy: number; w: number }, b: { cx: number; cy: number; w: number }, h = 28) =>
  Math.abs(a.cx - b.cx) < (a.w + b.w) / 2 && Math.abs(a.cy - b.cy) < h

describe('layoutChips', () => {
  // Phone-sized map: the three north-shore spots are ~20 px apart.
  const dots = [
    { id: 'harbor', x: 206, y: 117, w: 96 },
    { id: 'kanaha', x: 224, y: 101, w: 96 },
    { id: 'sprecks', x: 257, y: 95, w: 96 },
    { id: 'maui-sunset', x: 148, y: 279, w: 110 },
    { id: 'keawakapu', x: 154, y: 325, w: 110 },
  ]
  const box = { w: 343, h: 352 }
  const chips = layoutChips(dots, box, { northBelowY: 200 })
  const withW = chips.map((c) => ({ ...c, w: dots.find((d) => d.id === c.id)!.w }))

  it('places every chip inside the box', () => {
    for (const c of withW) {
      expect(c.cx - c.w / 2).toBeGreaterThanOrEqual(0)
      expect(c.cx + c.w / 2).toBeLessThanOrEqual(box.w)
      expect(c.cy).toBeGreaterThan(0)
      expect(c.cy).toBeLessThan(box.h)
    }
  })

  it('never overlaps two chips', () => {
    for (let i = 0; i < withW.length; i++) for (let j = i + 1; j < withW.length; j++) {
      expect(overlap(withW[i], withW[j]), `${withW[i].id} / ${withW[j].id}`).toBe(false)
    }
  })

  it('keeps north chips above their dots, in west-east order, and Kihei chips to the left', () => {
    const by = Object.fromEntries(chips.map((c) => [c.id, c]))
    expect(by.harbor.cx).toBeLessThan(by.kanaha.cx)
    expect(by.kanaha.cx).toBeLessThan(by.sprecks.cx)
    expect(by.kanaha.cy).toBeLessThan(95)
    expect(by['maui-sunset'].cx).toBeLessThan(148)
    expect(by.keawakapu.cy).toBeGreaterThan(by['maui-sunset'].cy)
  })
})

describe('narrow maps', () => {
  it('splits the north row in two when the chips do not fit side by side', () => {
    const dots = [
      { id: 'harbor', x: 206, y: 117, w: 120 },
      { id: 'kanaha', x: 224, y: 101, w: 120 },
      { id: 'sprecks', x: 257, y: 95, w: 125 },
    ]
    const chips = layoutChips(dots, { w: 343, h: 352 }, { northBelowY: 200 })
    for (const c of chips) {
      const w = dots.find((d) => d.id === c.id)!.w
      expect(c.cx - w / 2).toBeGreaterThanOrEqual(0)
      expect(c.cx + w / 2).toBeLessThanOrEqual(343)
    }
    expect(new Set(chips.map((c) => c.cy)).size).toBe(2)
    for (let i = 0; i < chips.length; i++) for (let j = i + 1; j < chips.length; j++) {
      const a = { ...chips[i], w: dots.find((d) => d.id === chips[i].id)!.w }
      const b = { ...chips[j], w: dots.find((d) => d.id === chips[j].id)!.w }
      expect(overlap(a, b)).toBe(false)
    }
  })
})

describe('land row', () => {
  it('puts the listed spots in a row below their dots, the rest stay over the bay', () => {
    const dots = [
      { id: 'harbor', x: 206, y: 117, w: 96 },
      { id: 'kanaha', x: 224, y: 101, w: 96 },
      { id: 'sprecks', x: 257, y: 95, w: 96 },
      { id: 'hookipa', x: 300, y: 70, w: 100 },
    ]
    const chips = layoutChips(dots, { w: 343, h: 352 }, { northBelowY: 200, land: ['harbor', 'sprecks'] })
    const by = Object.fromEntries(chips.map((c) => [c.id, c]))
    expect(by.harbor.cy).toBeGreaterThan(117)
    expect(by.sprecks.cy).toBe(by.harbor.cy)
    expect(by.harbor.cx).toBeLessThan(by.sprecks.cx)
    expect(by.kanaha.cy).toBeLessThan(70)
    expect(by.hookipa.cy).toBe(by.kanaha.cy) // two chips fit in one bay row
    const withW = chips.map((c) => ({ ...c, w: dots.find((d) => d.id === c.id)!.w }))
    for (let i = 0; i < withW.length; i++) for (let j = i + 1; j < withW.length; j++) {
      expect(overlap(withW[i], withW[j]), `${withW[i].id} / ${withW[j].id}`).toBe(false)
    }
  })
})

describe('chip above another spot', () => {
  it('puts Kanahā just above the Harbor dot, lined up with the Harbor chip, and Hoʻokipa near its dot', () => {
    // hero-sized map
    const dots = [
      { id: 'kanaha', x: 239, y: 99, w: 114 },
      { id: 'sprecks', x: 266, y: 93, w: 118 },
      { id: 'harbor', x: 225, y: 113, w: 111 },
      { id: 'hookipa', x: 301, y: 62, w: 123 },
    ]
    const buoy = { x: 239, y: 37 }
    const chips = layoutChips(dots, { w: 591, h: 436 }, {
      northBelowY: 300, rise: 54, land: ['harbor', 'sprecks'], over: { kanaha: 'harbor' }, avoid: [buoy],
    })
    const by = Object.fromEntries(chips.map((c) => [c.id, c]))
    expect(by.kanaha.cx).toBe(by.harbor.cx)
    expect(by.kanaha.cy).toBeLessThan(113)
    expect(by.kanaha.cy).toBeGreaterThan(62)
    expect(Math.abs(by.hookipa.cx - 301)).toBeLessThan(15)
    const withW = chips.map((c) => ({ ...c, w: dots.find((d) => d.id === c.id)!.w }))
    for (let i = 0; i < withW.length; i++) for (let j = i + 1; j < withW.length; j++) {
      expect(overlap(withW[i], withW[j]), `${withW[i].id} / ${withW[j].id}`).toBe(false)
    }
    for (const c of withW) expect(buoy.x < c.cx - c.w / 2 || buoy.x > c.cx + c.w / 2 || Math.abs(buoy.y - c.cy) > 14).toBe(true)
  })
})

describe('Kihei column', () => {
  it('lifts a wide chip above its dot instead of covering it', () => {
    const dots = [
      { id: 'maui-sunset', x: 136, y: 282, w: 141 },
      { id: 'keawakapu', x: 141, y: 325, w: 121 },
    ]
    const by = Object.fromEntries(layoutChips(dots, { w: 317, h: 343 }, { northBelowY: 200 }).map((c) => [c.id, c]))
    expect(by['maui-sunset'].cy + 14).toBeLessThan(282 - 4) // chip bottom above the dot
    expect(by.keawakapu.cy).toBe(325)
  })
})

describe('measuring points', () => {
  it('moves a row so it does not cover a dot to avoid', () => {
    const dots = [
      { id: 'kanaha', x: 264, y: 99, w: 114 },
      { id: 'hookipa', x: 333, y: 61, w: 123 },
    ]
    const buoy = { x: 239, y: 37 }
    const [a, b] = layoutChips(dots, { w: 591, h: 436 }, { northBelowY: 300, rise: 54, avoid: [buoy] })
    for (const c of [a, b]) {
      const w = dots.find((d) => d.id === c.id)!.w
      expect(buoy.x < c.cx - w / 2 || buoy.x > c.cx + w / 2).toBe(true)
    }
  })
})

describe('chipWidth', () => {
  it('grows with the text', () => {
    expect(chipWidth('Keawakapu', '18')).toBeGreaterThan(chipWidth('Harbor', '18'))
  })
})
