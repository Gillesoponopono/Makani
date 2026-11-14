# Makani — Maui Kitesurf Wind Forecast

> *Makani* (Hawaiian) — wind.

A free, mobile-first wind forecast website for kitesurfers, wing foilers and kite foilers on Maui. It turns the PacIOOS high-resolution WRF model into a plain answer to "is it on, and for what gear?" for each spot, adds National Weather Service (NWS) data as a second opinion, and sends optional alerts by email or browser push.

- **Hosting:** static site on GitHub Pages — `https://gillesoponopono.github.io/Makani/` (public repo `Gillesoponopono/Makani`)
- **Data refresh:** GitHub Actions, every 6 hours, publishes JSON only when there is a new model run
- **Alerts backend:** one small Cloudflare Worker (free tier), the only server-side piece
- **Cost target:** $0/month

---

## 1. Goals and non-goals

### Goals
1. Answer within seconds, on a phone at the beach: *which spot, which hours, which board/kite*.
2. Show the wind field on an SVG coastline map of Maui with arrows in knots, plus an hour slider.
3. Hourly forecast per kite spot for the whole model run (~5–7 days), all 24 hours, with night rows dimmed.
4. Make safety obvious: offshore or dangerous directions are flagged at every spot.
5. Optional alerts by email and Chrome (Web Push) when a spot's wind is inside the user's own knots range.
6. Fully free to run and easy to maintain alone.

### Non-goals (v1)
- User accounts or passwords (magic links only).
- Swell or wave forecasting, apart from NWS marine text and advisories.
- Islands other than Maui.
- Native mobile apps (the site works as an installable PWA).
- Languages other than English (strings kept in one file so translation stays possible).
- Analytics or tracking.

---

## 2. Audience

Local and visiting kiters of mixed skill. Visitors need clear verdicts and safety context, and locals want the detail (model vs NWS, observations, tides). Design for both: a verdict first, with the detail one tap away.

---

## 3. Data sources

| Source | What | Where it's fetched | Refresh |
|---|---|---|---|
| **PacIOOS WRF `wrf_mo`** (ERDDAP griddap) | 10 m wind U/V, air temp, rain, ~2 km grid, hourly | GitHub Action | every 6 h, skipped if no new run |
| **NWS gridpoint raw forecast** (`api.weather.gov/gridpoints/HFO/x,y`) | Hourly wind speed, **gusts** and direction per spot (second opinion) | GitHub Action | every 6 h |
| **NWS observations** (`/stations/{id}/observations`) | Measured wind and gusts now (Kahului Airport `PHOG` and nearby stations) | **Browser, live** (API sends `Access-Control-Allow-Origin: *`), plus the Action for verification history | on page load / every 10 min while open |
| **NWS active alerts** (`/alerts/active?zone=…`) | Wind Advisory, Small Craft Advisory, High Surf, etc. | Browser live + Action (for alert emails) | on page load / every 6 h |
| **NWS Coastal Waters Forecast** (`/products/types/CWF/locations/HFO`) | Marine text for zones `PHZ117` Maui County Windward Waters and `PHZ119` Maalaea Bay | GitHub Action | every 6 h |
| **NOAA CO-OPS tide predictions** | High/low tides and an hourly curve | GitHub Action | daily (predictions are deterministic) |
| **Sunrise/sunset** | Computed locally (NOAA solar algorithm), no API | Action (for alert windows) and browser | — |
| **Coastline** | Maui coastline polygon (OSM coastline or Hawaii Statewide GIS), simplified at build time | committed asset | static |

### 3.1 WRF `wrf_mo` facts (checked 2026-11-13)
- ERDDAP: `https://pae-paha.pacioos.hawaii.edu/erddap/griddap/wrf_mo`
- Grid: lat 20.2–21.892 (step 0.018°, 95 rows), lon −159.12 to −155.64 (step 0.02°, 175 cols) ≈ 2 km.
- Variables used: `Uwind`, `Vwind` (m/s, 10 m), `Tair` (°C, 2 m), `rain` (kg m⁻² s⁻¹ = mm/s).
- Time: hourly. It is an FMRC "best" time series: the past stretches back to 2010 and the future to the end of the latest run (currently ~5 days ahead; the metadata says up to 7). **There is no run ID**, so a new run is detected from `time_coverage_end` (see §7.2).
- **No gust variable** (see §5.3).
- License: free use and redistribution, no warranty. Attribution to PacIOOS / UH (Yi-Leng Chen) is required.
- **The server is slow**: queries over the 142k-step time axis can take minutes. Always bound the time range explicitly, use long timeouts (300 s) and retries with backoff, and never block the site on it.

### 3.2 NWS facts (checked 2026-11-13)
- Forecast office: **HFO** (Honolulu).
- Gridpoints: Kanaha `HFO/213,126`, Sprecks `HFO/215,127`, Maui Sunset `HFO/213,120`.
- Land zones: `HIZ045` (Kanaha, Sprecks), `HIZ049` (Kihei). Marine zones: `PHZ117`, `PHZ119`.
- Use the raw `/gridpoints/HFO/x,y` endpoint (not `/forecast/hourly`) to get `windGust`. Values are km/h with ISO-8601 `validTime` intervals and must be expanded to hourly.
- Server-side requests must send a `User-Agent` such as `Makani-forecast (https://github.com/Gillesoponopono/Makani)`.

---

## 4. Spots

The single source of truth is `config/spots.json`, shared by the pipeline, the web app and the Worker.

| id | Name | Beach coord (lat, lon) | WRF sample cell | NWS gridpoint | Obs station | Tide station | Marine zone |
|---|---|---|---|---|---|---|---|
| `kanaha` | Kanaha (Kite Beach) | 20.899, −156.447 | nearest **offshore water** cell, set by hand | HFO 213,126 | PHOG | Kahului 1615680 | PHZ117 |
| `sprecks` | Spreckelsville | 20.907, −156.410 | nearest offshore water cell | HFO 215,127 | PHOG | Kahului 1615680 | PHZ117 |
| `maui-sunset` | Maui Sunset (Kihei) | 20.751, −156.459 | nearest offshore water cell | HFO 213,120 | nearest from `/gridpoints/HFO/213,120/stations` that reports wind | nearest CO-OPS prediction station to Kihei (confirm during build; fallback Kahului) | PHZ119 |

Coordinates are approximate and **must be checked on a map** before launch.

**Grid sampling:** each spot takes its value from one hand-picked WRF cell just offshore (`wrfCell: {lat, lon}` in the config). A 2 km cell over land carries land roughness and thermal effects that don't match conditions on the water. The pipeline snaps to the exact grid indices and logs them.

### 4.1 Direction sectors (initial values, to be reviewed with local riders)
Directions are **meteorological "from"** degrees.

| Spot | Good (✓) | OK (~) | Dangerous / offshore (⚠) |
|---|---|---|---|
| Kanaha | 30–100 (NE–E trades, side-on) | 0–30, 100–130 | 150–270 (S–W, offshore) |
| Sprecks | 45–90 | 20–45, 90–110 | 140–260 |
| Maui Sunset | 340–30 (N–NNE funnel, side-shore) | 300–340, 30–50 | 50–160 (E–SE, offshore & gusty) |

Any direction outside these lists is "poor" (shown without a sport recommendation, no warning).

---

## 5. Ratings

### 5.1 Sport bands (overlapping)
Each hour gets one or more sport icons from the **WRF sustained wind** at the spot:

| Icon | Sport | Wind (kn) |
|---|---|---|
| 🪁〰 | Kite foil & wing foil | 10–20 |
| 🏄 | Directional / surf kite | 15–25 |
| 🛹 | Twin tip | 18–30 |
| ⚡ | Experts only / small kites | > 30 |
| — | Too light | < 10 |

- Bands overlap on purpose: 16 kn shows foil/wing **and** directional.
- Emoji are placeholders. Ship custom monochrome SVG icons (wing, kite-foil, surfboard, twin tip, bolt) that also work in dark mode.
- Every icon has a text label or tooltip. Color is never the only signal.
- Band limits live in `config/ratings.json` so they can be tuned without code changes.

### 5.2 Direction overlay
- **⚠ dangerous/offshore:** every sport icon is replaced by a red "Offshore — dangerous" badge. The hour never counts toward an alert.
- **~ OK:** sport icons are shown with an "OK direction" marker.
- **poor:** wind and arrow are shown, no sport icons.

### 5.3 Gusts
WRF has no gust field. Show an **estimated gust = sustained × 1.3** (factor in `config/ratings.json`), always labeled "est." with an explanation in About. The NWS gust forecast appears beside it as a real second opinion (§8.3). Ratings and alerts use sustained WRF wind only.

### 5.4 Reliability
Day 1–2 normal. Day 3–4 marked "lower confidence" with a subtle hatch. Day 5+ marked "low confidence".

### 5.5 Units and math
- Knots by default, with a toggle for kn / mph / km/h / m/s (stored in `localStorage`). Pipeline JSON stays in knots.
- `kn = m/s × 1.943844`
- Direction from U/V (from-direction): `dir = (270 − atan2(V, U)·180/π) mod 360`
- Map arrows point **downwind** (the direction the air moves). Tooltips and tables give the "from" compass point (e.g. "ENE 65°").
- Rain: `mm/h = rain × 3600`. Shown as an icon at ≥ 0.2 mm/h, plus a value.
- All times shown in **HST (UTC−10, no daylight saving)** and labeled so.

---

## 6. Architecture

```
                 ┌──────────────── GitHub ────────────────┐
  PacIOOS ERDDAP │  Action: forecast.yml (cron every 6 h)  │
  NWS API ──────▶│   Python pipeline → JSON                │
  NOAA CO-OPS    │   ├─ force-push → `data` branch          │
                 │   ├─ build Svelte app + data → Pages     │
                 │   └─ alerts.py → match → send            │──▶ Resend (email)
                 │                                          │──▶ Web Push services
                 └──────────────────────────────────────────┘
                          ▲ GET /internal/alerts (bearer)
                          │ POST /internal/sent
  Browser ────────▶ GitHub Pages (static Svelte SPA + JSON)
     │  live: NWS observations + active alerts (CORS)
     └──────────▶ Cloudflare Worker + D1 (signups, push subscriptions, manage links)
                          └──▶ Resend (confirmation emails)
```

---

## 7. Data pipeline (Python)

### 7.1 Schedule
`.github/workflows/forecast.yml`
- `cron: "0 4,10,16,22 * * *"` → **18:00, 00:00, 06:00, 12:00 HST**. GitHub cron can run 5–60 min late, so nothing depends on exact timing.
- `workflow_dispatch` for manual runs.
- `concurrency: forecast` (no overlapping runs).
- Scheduled workflows on public repos are disabled after 60 days without repo activity. Add a keepalive step (an empty monthly commit to `main`, or a keepalive action) and document it.

### 7.2 Steps
1. **Detect new run:** read `time_coverage_end` from `erddap/info/wrf_mo/index.csv`. If it equals `meta.json.wrf.coverageEnd` on the `data` branch, skip the WRF fetch. NWS, tides and alerts still run.
2. **Fetch WRF** with one bounded request in **NetCDF (`.nc`)** format (much smaller than CSV/JSON):
   - `Uwind,Vwind` over the Maui box lat **20.50–21.10**, lon **−156.72 to −155.95**, time `now−1h` → `last`, stride 1.
   - `Tair,rain` only at the three spot cells (three small requests, or one small box).
   - Read with `xarray` + `netCDF4`. Timeout 300 s, 3 retries with exponential backoff.
3. **Build spot series** (§7.4) and **map frames** (§7.5).
4. **NWS:** gridpoint raw forecasts per spot (expand intervals to hourly, km/h → kn); active alerts for `PHZ117,PHZ119,HIZ045,HIZ049`; latest CWF product → split out the PHZ117/PHZ119 sections; observations for the last 6 h from PHOG and the Kihei station, appended to a rolling 7-day verification file.
5. **Tides:** CO-OPS `datagetter` `product=predictions`, `datum=MLLW`, `units=english`, `time_zone=lst_ldt`, `interval=hilo` plus `interval=h` for the curve, covering the forecast span.
6. **Verification:** pair WRF (at Kanaha's cell) with PHOG observations over the past 7 days → mean bias, MAE (kn), direction error. Shown on an "Accuracy" panel.
7. **Validate** the output against JSON Schemas (`pipeline/schemas/`). If anything fails, keep the previous files and fail the job loudly; never publish partial data.
8. **Publish:** commit `data/` to the orphan **`data` branch** with a single amended commit and force-push, so history doesn't grow by ~0.5 MB × 4/day. Then build the web app with that data copied into `public/data/` and deploy with `actions/deploy-pages`.
9. **Alerts:** on the 04:00 and 16:00 UTC runs only, run `alerts.py` (§9).

Each source fails on its own. If NWS is down, WRF still publishes (and the reverse); `meta.json` records each source's status and timestamp.

### 7.3 Output files (`data/`)
```
meta.json            run info, per-source status, generatedAt, schemaVersion
spots/kanaha.json    hourly series per spot
spots/sprecks.json
spots/maui-sunset.json
map/frames.json      quantized wind grid for all hours
nws/alerts.json      active advisories (also fetched live client-side)
nws/marine.json      CWF text for PHZ117, PHZ119
verification.json    7-day WRF-vs-PHOG pairs + stats
```

### 7.4 `spots/{id}.json`
```jsonc
{
  "id": "kanaha",
  "wrfCell": { "lat": 20.902, "lon": -156.44, "i": 39, "j": 134 },
  "hours": [
    {
      "t": "2026-11-13T14:00:00-10:00",
      "wrf": { "kn": 18.4, "dir": 68, "gustEst": 23.9, "tairC": 26.1, "rainMmH": 0.0 },
      "nws": { "kn": 17, "gust": 24, "dir": 70 },       // null if unavailable
      "tideFt": 1.2,
      "sector": "good",                                   // good | ok | poor | danger
      "sports": ["foil_wing", "directional", "twintip"],
      "daylight": true
    }
  ],
  "tides": [{ "t": "...", "type": "H", "ft": 2.1 }],
  "sun": [{ "date": "2026-11-13", "rise": "06:41", "set": "17:47" }]
}
```
Sectors and sports are computed in the pipeline (one implementation, also used by alerts). The front end only displays them.

### 7.5 `map/frames.json`
- Grid stride 2 (≈ 4 km) over the Maui box → about 15 × 20 ≈ 300 arrows per hour.
- Quantized: speed as integer tenths of a knot, direction as integer degrees; flat arrays per hour.
- `{ "lats": [...], "lons": [...], "times": [...], "kn10": [[...]], "dir": [[...]] }`
- Budget: ≤ 400 KB raw for the whole run (Pages serves it gzipped). If it grows past that, split into per-day files.

---

## 8. Front end (Svelte + Vite)

### 8.1 General
- Svelte 5 + Vite, TypeScript, no UI framework. Hand-written SVG for the map and icons.
- **Hash routing** (works on GitHub Pages without 404 tricks): `#/`, `#/spot/:id`, `#/alerts`, `#/about`.
- **Mobile-first**, light/dark following `prefers-color-scheme`, plus a manual toggle.
- PWA: manifest + service worker (also required for Web Push). Caches the app shell and last data for offline viewing at the beach.
- Budget: first load ≤ 250 KB gzipped, excluding `frames.json`, which loads after first paint.
- Accessibility: WCAG AA contrast, keyboard-operable slider, text labels on all icons, `prefers-reduced-motion` stops slider autoplay.
- Header shows "Model run: Nov 13, 06:00 HST · updated 2 h ago". A yellow banner appears if WRF data is > 18 h old, red if > 36 h.

### 8.2 Home `#/`
1. **NWS advisory banner** (live), when any advisory is active for the Maui zones.
2. **Spot cards** (3): a "now/next" verdict, today's best window ("Kanaha · 11am–5pm · 18–24 kn ENE · 🪁〰 🏄 🛹"), live observed wind from NWS, and a link to the hourly page.
3. **Map** (§8.4).
4. Footer: attribution and disclaimer.

### 8.3 Spot page `#/spot/:id`
- Day tabs (Today, Tomorrow, then weekday names) with a per-day summary strip (best window, peak knots).
- **Hourly table, all 24 hours**, night rows dimmed using sunrise/sunset; a marker row at sunrise and sunset.
- Columns: Time · **Wind kn** (colored cell) · est. gust · direction (arrow + compass + sector icon) · sport icons · **NWS kn / gust** · air °F/°C · rain · tide (ft, H/L markers, mini curve).
- On narrow screens each hour is a compact two-line row; NWS, temp and tide sit in a second line.
- A "Now" section at the top with live NWS observations (wind, gust, direction, observation age).
- Reliability hatching for later days (§5.4).
- Collapsible **NWS marine forecast** text for the spot's zone.
- **Accuracy** panel: WRF vs observed over the last 7 days (bias, MAE) and a small chart.

### 8.4 SVG map
- Extent: Maui island (lat 20.55–21.05, lon −156.72 to −155.95), equirectangular projection with cos(lat) x-scaling (fine for this small area).
- Layers: ocean background → optional speed-colored heat cells → coastline (simplified path, ~20–40 KB) → wind arrows (stride 2), sized and colored by knots → spot markers with a live knots label → legend.
- Color scale in knots (same as the tables): < 10 grey-blue, 10–15 green, 15–20 bright green, 20–25 yellow, 25–30 orange, 30–35 red, > 35 purple. Must stay legible in light and dark themes.
- **Time slider:** scrub through all hours, play/pause (1 h per 400 ms), day ticks, and night shading on the slider track. Defaults to the next full hour.
- Tap or hover on an arrow shows "18 kn from ENE (68°)". Tapping a spot marker opens the spot page.
- Coastline build: download source → `mapshaper` simplify → GeoJSON → project to an SVG path at build time (`scripts/build-coast`). The output is committed under `web/src/assets/`.

### 8.5 Alerts page `#/alerts`
Create or manage alerts (§9). Shows the user's push alerts for this browser. Email alerts are managed through the link in each email.

### 8.6 About `#/about`
Data sources and attribution (PacIOOS/UH WRF, NWS, NOAA CO-OPS), the gust estimate explained, model limits (2 km grid, sea breeze/thermal effects at Kihei), how ratings work, privacy note, and disclaimer.

---

## 9. Alerts

### 9.1 Alert definition
| Field | Default |
|---|---|
| Spot | (required) |
| Knots min / max | (required), e.g. 18–28 |
| Hour window (HST) | **daylight** (sunrise → sunset); user can set e.g. 10:00–17:00 |
| Min matching hours (consecutive) | 2 |
| Days ahead | today + tomorrow (option: up to 3 days) |
| Direction | always excludes ⚠ dangerous; option "good sector only" |
| Channels | email and/or this browser (push) |

An hour **matches** when WRF sustained knots fall in [min, max], the hour is inside the window, and the direction is allowed. A day matches when it has ≥ N consecutive matching hours.

### 9.2 Timing and dedup
- **Evening alert** at the 04:00 UTC run (18:00 HST): "Tomorrow at Kanaha: 11am–4pm, 19–24 kn ENE".
- **Morning update** at the 16:00 UTC run (06:00 HST): sent for *today* only if it still matches; it also says if the window has moved.
- At most 2 messages per alert per day. Dedup key: `(alertId, targetDate, slot)` stored in the Worker.
- One message per channel per run, even with several matching alerts (all matches grouped into one email or push).

### 9.3 Backend: Cloudflare Worker + D1
- TypeScript Worker on the free tier (100k requests/day) with a **D1** SQLite database.
- **Tables:** `subscribers(id, email, confirmed, manage_token_hash, created_at)`, `push_subscriptions(id, endpoint, p256dh, auth, manage_token_hash, created_at)`, `alerts(id, owner_type, owner_id, spot, kn_min, kn_max, window_start, window_end, use_daylight, min_hours, days_ahead, good_only, created_at)`, `sent_log(alert_id, target_date, slot, sent_at)`.
- **Public endpoints** (CORS limited to the Pages origin):
  - `POST /subscribe` — email + alert. Stores it unconfirmed and sends a confirmation email (double opt-in). Protected by **Cloudflare Turnstile** and per-IP rate limiting.
  - `GET /confirm?token=` — confirms and redirects to the site.
  - `GET|POST|DELETE /manage?token=` — list, edit and delete alerts for that email; unsubscribe all.
  - `POST /push/subscribe` — PushSubscription + alert(s); returns a browser manage token kept in `localStorage`.
  - `PUT|DELETE /push/manage` — with that token.
- **Internal endpoints** (bearer `ALERTS_API_TOKEN`, used only by the Action):
  - `GET /internal/alerts` — confirmed alerts with channel details.
  - `POST /internal/sent` — record sends; `POST /internal/prune` — remove dead push endpoints.
- Tokens are random 32-byte values; only SHA-256 hashes are stored.

### 9.4 Sending (in the GitHub Action, `pipeline/makani/alerts.py`)
1. Pull alerts from the Worker.
2. Match against the freshly built `spots/*.json` using the same sector and band code as the site.
3. **Email:** Resend API (free tier: 3,000/month, 100/day). Plain HTML template with the spot, window, knots, direction, sport icons, link to the spot page, and a **manage/unsubscribe link**. Add `List-Unsubscribe` headers.
4. **Web Push:** `pywebpush` with VAPID keys. Payload `{title, body, url}`; the service worker shows the notification and opens the spot page on click. HTTP 404/410 responses → prune the subscription.
5. Report sends back to the Worker for dedup.
6. If the volume would exceed Resend's daily cap, send push first, then email in priority order, log the shortfall, and show "alerts temporarily limited" on the Alerts page.

### 9.5 Browser push notes
Works in Chrome/Edge/Firefox on desktop and Android, and on iOS Safari 16.4+ **only when the site is installed to the Home Screen**. The Alerts page explains this. Permission is requested only after the user clicks "Enable browser alerts".

---

## 10. Repository layout

```
Makani/
├─ SPEC.md
├─ README.md
├─ LICENSE                      # MIT (code); data keeps its own terms
├─ config/
│  ├─ spots.json                # spots, cells, sectors, stations, zones
│  └─ ratings.json              # sport bands, gust factor, color scale
├─ pipeline/                    # Python 3.12
│  ├─ makani/{wrf,nws,tides,sun,ratings,build,alerts,publish}.py
│  ├─ schemas/*.schema.json
│  ├─ tests/                    # pytest, with recorded fixtures
│  └─ requirements.txt          # requests, numpy, xarray, netCDF4, pywebpush, jsonschema
├─ web/                         # Svelte + Vite + TS
│  ├─ src/{routes,lib,components,assets}/
│  ├─ public/ (manifest, icons, sw.js)
│  └─ scripts/build-coast.mjs
├─ worker/                      # Cloudflare Worker + D1 (TS, wrangler)
│  ├─ src/  migrations/  test/
│  └─ wrangler.toml
└─ .github/workflows/
   ├─ ci.yml                    # lint + tests (pipeline, web, worker) on PRs
   ├─ forecast.yml              # cron pipeline + deploy + alerts
   └─ deploy.yml                # on push to main: build with data branch → Pages
```

### 10.1 Secrets and config
| Name | Where | Purpose |
|---|---|---|
| `ALERTS_API_URL`, `ALERTS_API_TOKEN` | GitHub Actions secrets | Worker internal API |
| `RESEND_API_KEY` | GitHub + Worker secrets | email |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | public key in web config; private key in GitHub secrets | Web Push |
| `TURNSTILE_SECRET` | Worker secret | signup bot protection |
| `MAIL_FROM` | Worker + Actions vars | sender address (needs a verified domain with Resend; see §13) |

---

## 11. Testing

- **Pipeline (pytest):** unit conversions, U/V→direction (all quadrants), sector classification incl. wrap-around (340–30), band overlaps, NWS interval expansion, run-change detection, schema validation. Recorded ERDDAP/NWS/CO-OPS fixtures; no live network in CI.
- **Alert matching:** table-driven tests (window, consecutive hours, daylight, dangerous-direction exclusion, dedup).
- **Web (vitest):** unit toggles, color scale, time formatting in HST; **Playwright** smoke test on the built site at mobile and desktop widths, light and dark.
- **Worker (vitest + Workers pool):** subscribe/confirm/manage flows, token hashing, auth on internal routes, rate limits.
- **Manual pre-launch check:** compare a few days of WRF vs PHOG observations and adjust the Kanaha cell choice if bias is large.

---

## 12. Legal, attribution, privacy

- Footer and About: "Model data: PacIOOS WRF Maui-Oahu (University of Hawaiʻi, Yi-Leng Chen), funded by NOAA/IOOS. Forecasts, observations and advisories: NOAA National Weather Service. Tides: NOAA CO-OPS."
- Disclaimer: forecasts can be wrong; not a substitute for checking conditions on site, local knowledge, or official NWS warnings. Kite at your own risk.
- Privacy: only an email address (if given) and push endpoints are stored, used only for alerts, deletable at any time through the manage link. No analytics, no cookies, no third-party trackers.
- Hawaiian names spelled with ʻokina and kahakō where correct (e.g. Kanahā, Hoʻokipa) in display text; ASCII ids in code.

---

## 13. Milestones

| # | Deliverable |
|---|---|
| M1 | Repo, CI, `config/spots.json`, WRF pipeline → `spots/*.json`, data branch, Pages deploy of a bare hourly table |
| M2 | Coastline asset, SVG map with arrows, time slider |
| M3 | Ratings: sport icons, direction sectors and warnings, estimated gusts, unit toggle, light/dark, mobile layout |
| M4 | NWS gridpoint, live observations, advisories, marine text, tides, sunrise/sunset, accuracy panel |
| M5 | Worker + D1, email signup with double opt-in, alert matching, Resend emails |
| M6 | PWA service worker, Web Push subscribe/send/prune |
| M7 | Polish: custom icons, performance budget, accessibility pass, About page, launch |

**Email sending domain:** Resend requires a verified domain to send to arbitrary recipients. With github.io only, either use a cheap domain just for mail, or ship M5 behind a flag until one exists. Decide before M5.

---

## 14. Decisions taken by default (not explicitly confirmed)

These were left unanswered in the interview and were set to sensible defaults. Change them here if needed.

1. **Alert timing:** evening-before (18:00 HST) + morning update (06:00 HST), max 2/day per alert.
2. **Alert hours:** per-alert window, defaulting to sunrise–sunset.
3. **Analytics:** none.
4. **Grid sampling:** one hand-picked offshore water cell per spot (no interpolation or averaging).
5. **Spot coordinates and direction sectors:** initial estimates, to be checked with local knowledge.
6. **Data storage:** latest data force-pushed to an orphan `data` branch (no history), not committed to `main`.
