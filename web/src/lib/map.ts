// Arrow glyph shared by the island map chips and the chart's direction strip.

/**
 * Filled arrow pointing "up" (north): a shaft that tapers toward the tail and a
 * swept-back head, tip at (0, -len/2), tail at (0, len/2). Rotate by dir + 180
 * to point downwind.
 */
export function arrowPath(len: number): string {
  const h = len / 2
  const head = Math.max(7, Math.min(12.5, len * 0.38))
  const hw = head * 0.6 // half-width of the head
  const sweep = head * 0.3 // barbs sit this far behind the neck
  const neck = 1.7 // half-width of the shaft under the head
  const tail = 0.5
  const f = (v: number) => Math.round(v * 100) / 100
  const yBarb = -h + head
  const yNeck = yBarb - sweep
  return `M${f(-tail)} ${f(h)}L${f(-neck)} ${f(yNeck)}L${f(-hw)} ${f(yBarb)}L0 ${f(-h)}L${f(hw)} ${f(yBarb)}L${f(neck)} ${f(yNeck)}L${f(tail)} ${f(h)}Z`
}
