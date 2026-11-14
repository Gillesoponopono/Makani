// App icons and the link-preview image, from the header logo and the island picture.
//
//   cd web && npm i --no-save sharp && cd ..      # sharp isn't a project dependency
//   node web/scripts/build-icons.mjs
//   cd web && npm ci                              # afterwards: back to the locked dependencies
//
// Writes (committed): web/public/favicon.svg, web/public/icons/{icon-192,icon-512,
// icon-maskable-512,apple-touch-icon}.png and web/public/og-image.jpg (1200x630,
// shown by WhatsApp, iMessage, Slack... when the link is shared).
import fs from 'node:fs'
import path from 'node:path'
import sharp from 'sharp'

const ROOT = process.env.MAKANI_ROOT ?? path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..')
const PUB = path.join(ROOT, 'web/public')
const ICONS = path.join(PUB, 'icons')
fs.mkdirSync(ICONS, { recursive: true })

// The header logo (App.svelte), 40x24 grid: a wave and a gust line.
const LOGO = `
  <path d="M2 15c5-7 11-7 16-2s10 5 16-3c-2 8-8 12-15 8S7 12 2 15Z" fill="url(#g)"/>
  <path d="M6 9c4-4 9-4 13-1s8 3 13-1" fill="none" stroke="url(#g)" stroke-width="2.2" stroke-linecap="round"/>`
const DEFS = `
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0f3a66"/><stop offset="1" stop-color="#071626"/>
  </linearGradient>
  <linearGradient id="g" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#5ee7df"/><stop offset="1" stop-color="#2bb3d6"/>
  </linearGradient>`

// Logo content spans x 2..34, y 5..21 of its grid: centre it in a square of `size`,
// `share` of the width wide.
function logoAt(size, share) {
  const k = (size * share) / 32
  const tx = (size - 32 * k) / 2 - 2 * k
  const ty = (size - 16 * k) / 2 - 5 * k
  return `<g transform="translate(${tx.toFixed(2)} ${ty.toFixed(2)}) scale(${k.toFixed(4)})">${LOGO}</g>`
}

// Full-bleed square: the phone rounds the corners itself. Maskable icons keep the
// logo inside the central safe circle (80 % of the width).
const square = (size, share, rx = 0) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><defs>${DEFS}</defs>` +
  `<rect width="${size}" height="${size}" rx="${rx}" fill="url(#bg)"/>${logoAt(size, share)}</svg>`

const png = (svg, out) => sharp(Buffer.from(svg)).png().toFile(out).then(() => console.log(`wrote ${path.relative(ROOT, out)}`))

fs.writeFileSync(path.join(PUB, 'favicon.svg'), square(32, 0.84, 7) + '\n')
console.log('wrote web/public/favicon.svg')
await png(square(192, 0.62), path.join(ICONS, 'icon-192.png'))
await png(square(512, 0.62), path.join(ICONS, 'icon-512.png'))
await png(square(512, 0.5), path.join(ICONS, 'icon-maskable-512.png'))
await png(square(180, 0.62), path.join(ICONS, 'apple-touch-icon.png'))

// Link preview: the island on the right, title on a dark band on the left.
const W = 1200
const H = 630
const island = await sharp(path.join(ROOT, 'web/scripts/maui-aerial.webp'))
  .resize({ width: 860, height: H, fit: 'cover', position: 'centre' })
  .toBuffer()
const FONT = "'Avenir Next', 'Helvetica Neue', Helvetica, Arial, sans-serif"
const text = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"><defs>${DEFS}
  <linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0.28" stop-color="#071626" stop-opacity="1"/><stop offset="0.62" stop-color="#071626" stop-opacity="0"/>
  </linearGradient></defs>
  <rect width="${W}" height="${H}" fill="url(#fade)"/>
  <g transform="translate(70 150) scale(3.2)">${LOGO}</g>
  <text x="70" y="300" font-family="${FONT}" font-size="104" font-weight="700" fill="#eef4f8">Makani</text>
  <text x="74" y="368" font-family="${FONT}" font-size="40" font-weight="600" fill="#eef4f8">Maui wind forecast</text>
  <text x="74" y="420" font-family="${FONT}" font-size="30" fill="#9cb2c5">Wind, waves, tides and sky, hour by hour</text>
  <text x="74" y="520" font-family="${FONT}" font-size="26" font-weight="600" fill="#5ee7df">Kanahā · Sprecks · Harbor · Hoʻokipa · Kīhei</text>
</svg>`
await sharp({ create: { width: W, height: H, channels: 3, background: '#071626' } })
  .composite([
    { input: island, left: W - 860, top: 0 },
    { input: Buffer.from(text), left: 0, top: 0 },
  ])
  .jpeg({ quality: 82, mozjpeg: true }) // small enough for WhatsApp's preview limit (~300 KB)
  .toFile(path.join(PUB, 'og-image.jpg'))
console.log(`wrote web/public/og-image.jpg (${(fs.statSync(path.join(PUB, 'og-image.jpg')).size / 1024).toFixed(0)} KB)`)
