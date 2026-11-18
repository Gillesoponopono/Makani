# Makani — Maui Kitesurf Wind Forecast

> *Makani* (Hawaiian) — wind.

A free, mobile-first wind forecast website for kitesurfers, wing foilers and kite foilers on Maui. It turns the PacIOOS high-resolution WRF model into a clear hourly wind chart and a plain answer to "is it on?" for each spot, adds National Weather Service (NWS) data as a second opinion, and sends optional alerts by email or browser push.

- **Hosting:** static site on GitHub Pages — `https://gillesoponopono.github.io/Makani/` (public repo `Gillesoponopono/Makani`)
- **Data refresh:** GitHub Actions, an hourly light check (~13 KB); full download and republish only when a new model run is complete, observations every ~6 h
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
7. Go back in time and compare what was forecast with the wind that actually blew (§3.2, §7.6, §8.6).

### Non-goals (v1)
- User accounts or passwords (magic links only).
- A full surf forecast (break-by-break surf heights, surf ratings). The site shows model waves and tides as context for kiting (§8.8), nothing more.
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
| **PacIOOS WRF `wrf_mo`** (ERDDAP griddap) | 10 m wind U/V, air temp, rain, ~2 km grid, hourly — the site's current forecast | GitHub Action | hourly check, full fetch for a new complete run and every ~6 h with the same run |
| **PacIOOS WRF individual runs** (THREDDS `wrf_mo/runs`, NCSS point CSV) | Every run since 2010-05-14, exactly as issued | GitHub Action → forecast archive | when a new run is complete; one-off backfill |
| **NWS gridpoint raw forecast** (`api.weather.gov/gridpoints/HFO/x,y`) | Hourly wind speed, **gusts** and direction per spot (second opinion, built: `makani/nws.py`) | GitHub Action | with each build: new WRF run or every 6 h |
| **NOAA CO-OPS Kahului Harbor wind** (station `1615680`, `product=wind`) | Measured wind, direction, gusts on the waterfront, 6-min data, **years of history** | GitHub Action → observation archive | every ~6 h (last 7 days re-merged); one-off backfill |
| **NWS observations** (`/stations/PHOG/observations`) | Measured wind and gusts at Kahului Airport (ASOS) | **Browser, live** for "now" (API sends `Access-Control-Allow-Origin: *`), plus the Action → observation archive | on page load / every 10 min while open; Action every 6 h |
| **NWS active alerts** (`/alerts/active?zone=…`) | Wind Advisory, Small Craft Advisory, High Surf, etc. | Browser live + Action (for alert emails) | on page load / every 6 h |
| **NWS Coastal Waters Forecast** (`/products/types/CWF/locations/HFO`) | Marine text for zones `PHZ117` Maui County Windward Waters and `PHZ119` Maalaea Bay | GitHub Action | every 6 h |
| **NOAA CO-OPS tide predictions** (Kahului `1615680`, Makena `1615202`) | High/low tides and an hourly curve, feet above MLLW | GitHub Action | with each new WRF run (predictions are deterministic; the last good block is kept if NOAA fails) |
| **PacIOOS SWAN Maui** `swan_maui` (ERDDAP griddap, ~500 m) | Waves just off each beach: height, peak period, peak direction, hourly, ~7 days | GitHub Action | with each new WRF run |
| **PacIOOS WaveWatch III Hawaii** `ww3_hawaii` (ERDDAP griddap, ~5 km) | Offshore sea split into wind waves and swell (gives the wave type) | GitHub Action | with each new WRF run |
| **PacIOOS ROMS Hawaii** `roms_hiig` (ERDDAP griddap, ~4 km, 3-hourly) | Sea surface temperature just offshore of each spot (top level, 0.25 m), ~5 days | GitHub Action | with each new WRF run |
| **Sunrise/sunset** | Computed locally (NOAA solar algorithm), no API | Action (for alert windows) and browser | — |
| **Coastline** | Maui coastline polygon (OSM coastline or Hawaii Statewide GIS), simplified at build time | committed asset | static |

### 3.1 WRF `wrf_mo` facts (checked 2026-11-13)
- ERDDAP: `https://pae-paha.pacioos.hawaii.edu/erddap/griddap/wrf_mo`
- Grid: lat 20.2–21.892 (step 0.018°, 95 rows), lon −159.12 to −155.64 (step 0.02°, 175 cols) ≈ 2 km.
- Variables used: `Uwind`, `Vwind` (m/s, 10 m), `Tair` (°C, 2 m), `rain` (kg m⁻² s⁻¹ = mm/s).
- Time: hourly. It is an FMRC "best" time series: the past stretches back to 2010 and the future to the end of the latest run (currently ~5 days ahead; the metadata says up to 7). **There is no run ID**, so a new run is detected from `time_coverage_end` (see §7.2).
- **Runs** (checked 2026-11-13 on THREDDS `catalog/wrf_mo/runs/catalog.xml`, 5,578 runs): one per day, initialised **00Z** (14:00 HST the day before), valid from +6 h to **+168 h**; some days are missing (e.g. 2026-11-06, -09). Runs land slowly: on 2026-11-14 01Z the 11-12 run had 67 of 163 hours online and the 11-11 run was the newest complete one. ERDDAP's `time_coverage_end` = latest complete run + 168 h, so it changes once per completed run.
- **Individual runs are kept forever** on THREDDS: one NCSS point request per run and spot (`/thredds/ncss/grid/wrf_mo/runs/WRF_Maui-Oahu_Regional_Atmospheric_Model_RUN_<init>?var=Uwind&var=Vwind&latitude=…&longitude=…&temporal=all&accept=csv`) returns the 163 hourly values in ~1 s / ~12 KB, including runs from years ago.
- **No gust variable** (see §5.3).
- License: free use and redistribution, no warranty. Attribution to PacIOOS / UH (Yi-Leng Chen) is required.
- **The server is slow**: queries over the 142k-step time axis can take minutes. Always bound the time range explicitly, use long timeouts (300 s) and retries with backoff, and never block the site on it.

### 3.2 Observed wind ("what actually happened", checked 2026-11-13)
| Station | Where | Data | History | Notes |
|---|---|---|---|---|
| **Kahului Harbor** CO-OPS `1615680` | waterfront, ~2 km W of Kanahā (20.8949, −156.469) | speed, direction, gust every 6 min; `units=english` = knots (verified: 12.44 kn = 6.4 m/s) | back to at least 2020; **31-day limit per request** | best match for Kanahā/Sprecks conditions on the water |
| **Kahului Airport** NWS `PHOG` | ~1 km inland (20.8925, −156.437) | ASOS, ~hourly at :54 (+ specials); km/h → kn; gust only when reported | **API keeps ~7 days only** | recent values often arrive empty (QC `Z`) and get filled later; usually reads lower than on the water |
| **Kīhei** | — | no free official station found | — | Maui Sunset has no observed reference yet; Synoptic/MesoWest (free key) to investigate |

The NWS API forgets after a week, and the ERDDAP "best" series overwrites past hours with newer model analysis, so we keep our own archive (§7.6). Both halves can be backfilled: **PacIOOS THREDDS keeps every individual WRF run since 2010** (§3.1), and Kahului Harbor keeps years of observations. Only PHOG is limited to 7 days.

### 3.3 NWS facts (checked 2026-11-13)
- Forecast office: **HFO** (Honolulu).
- Gridpoints: Kanaha `HFO/213,126`, Sprecks `HFO/215,127`, Kahului Harbor `HFO/212,126`, Maui Sunset `HFO/213,120`, Keawakapu `HFO/213,117`.
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
| `harbor` | Kahului Harbor (Hoaloha Park launch, wing foil) | 20.8938, −156.468 | 20.902, −156.46 (harbor mouth) | HFO 212,126 | Kahului Harbor 1615680, at the harbor itself | Kahului 1615680 | PHZ117 |
| `hookipa` | Hoʻokipa (mainly windsurf and surf; State restricted zones, HAR 13-256-127, to check before kiting) | 20.9336, −156.3566 | 20.956, −156.36 (~2.5 km out) | HFO 217,128 | PHOG (~9 km west) | Kahului 1615680 | PHZ117 |
| `maui-sunset` | Maui Sunset (Kihei) | 20.751, −156.459 | nearest offshore water cell | HFO 213,120 | nearest from `/gridpoints/HFO/213,120/stations` that reports wind | Makena 1615202 (subordinate) | PHZ119 |
| `keawakapu` | Keawakapu (Kihei) | 20.701, −156.446 | 20.704, −156.48 (~3.5 km out; the 1.4 km cell read up to 7 kn lower, likely land in the model cell) | HFO 213,117 | none yet (as Maui Sunset) | Makena 1615202 (subordinate) | PHZ119 |

**Wave cells** (`waves` in the config, checked 2026-11-13 for valid model values): SWAN 20.905, −156.445 (Kanahā, ~0.7 km out), 20.915, −156.41 (Sprecks), 20.94, −156.355 (Hoʻokipa), 20.75, −156.465 (Maui Sunset), 20.70, −156.45 (Keawakapu); WW3 20.95, −156.45 / 20.95, −156.40 / 20.95, −156.35 off the north shore and 20.70, −156.50 off Kīhei. The Harbor is `sheltered`: SWAN's 500 m grid doesn't resolve the basin (its nearest cells read open-ocean swell), so the site says "flat water, wind chop only" there.

Coordinates are approximate and **must be checked on a map** before launch.

**Grid sampling:** each spot takes its value from one hand-picked WRF cell just offshore (`wrfCell: {lat, lon}` in the config). A 2 km cell over land carries land roughness and thermal effects that don't match conditions on the water. The pipeline snaps to the exact grid indices and logs them.

### 4.1 Direction sectors (initial values, to be reviewed with local riders)
Directions are **meteorological "from"** degrees.

| Spot | Good (✓) | OK (~) | Dangerous / offshore (⚠) |
|---|---|---|---|
| Kanaha | 30–100 (NE–E trades, side-on) | 0–30, 100–130 | 150–270 (S–W, offshore) |
| Sprecks | 45–90 | 20–45, 90–110 | 140–260 |
| Kahului Harbor | 30–100 (NE–E trades across the harbor; same as Kanaha, to confirm locally) | 0–30, 100–130 | 150–270 (S–W, offshore) |
| Hoʻokipa | 30–80 (NE–ENE trades, side-shore from the right; shore faces ~334°) | 0–30, 80–100 (E is side-off) | 125–250 (SE–WSW, offshore) |
| Maui Sunset | 340–30 (N–NNE funnel, side-shore) | 300–340, 30–50 | 50–160 (E–SE, offshore & gusty) |
| Keawakapu | 340–30 (same west-facing coast as Maui Sunset; to confirm locally) | 300–340, 30–50 | 50–160 (E–SE, offshore & gusty) |

Any direction outside these lists is "poor" (grey arrow, never counts as kiteable, no warning).

---

## 5. Ratings

### 5.1 Sport bands (overlapping, not displayed)
The pipeline still tags each hour with the sports its **WRF sustained wind** suits:

| Sport | Wind (kn) |
|---|---|
| Kite foil & wing foil | 10–20 |
| Directional / surf kite | 15–25 |
| Twin tip | 18–30 |
| Experts only / small kites | > 30 |
| Too light | < 10 |

- **Not shown on the site** (decided after M2: the gear badges took a lot of room for little value). The tags only decide what counts as kiteable: an hour is kiteable when it suits at least one sport, i.e. ≥ 10 kn from a good or OK direction. That drives the "best window" and the alerts.
- Bands are applied to the **whole knots the site displays** (the 1-decimal value rounded half-up), so an hour reading "10" is never "too light". Alerts use the same value.
- Band limits live in `config/ratings.json` so they can be tuned without code changes.

### 5.2 Direction overlay
- Direction arrows are coloured by sector: green good, amber OK, grey poor, red **offshore/dangerous**. The colour is backed by text in the chart readout ("Offshore, dangerous"), the table's ✓ ~ · ⚠ marks, and a "⚠ Offshore direction right now" line on the home card.
- Offshore and poor hours never count as kiteable or toward an alert.

### 5.3 Gusts
WRF has no gust field. Show an **estimated gust = sustained × 1.3** (factor in `config/ratings.json`), always labeled "est." with an explanation in About. The NWS gust forecast appears beside it as a real second opinion (readout and hourly table). Ratings and alerts use sustained WRF wind only.

### 5.4 Reliability
Day 1–2 normal. Day 3–4 marked "lower confidence" with a subtle hatch. Day 5+ marked "low confidence".

### 5.5 Units and math
- Knots by default, with a toggle for kn / mph / km/h (stored in `localStorage`). Pipeline JSON stays in knots; conversion at display (`mph = kn × 1.150779`, `km/h = kn × 1.852`). Ratings always use knots.
- Heights follow the temperature toggle, labelled "°C · m" / "°F · ft": waves (data in metres) and tides (data in feet, `ft = m × 3.28084`). Waves show one decimal in metres, whole feet from 3 ft; tides one decimal.
- `kn = m/s × 1.943844`
- Direction from U/V (from-direction): `dir = (270 − atan2(V, U)·180/π) mod 360`
- Arrows (map chips, chart strip, stats) point **downwind** (the direction the air moves). Readouts and tables give the "from" compass point (e.g. "ENE 65°").
- Rain: `mm/h = rain × 3600`. Shown as an icon at ≥ 0.2 mm/h, plus a value.
- All times shown in **HST (UTC−10, no daylight saving)** and labeled so.

---

## 6. Architecture

```
                 ┌──────────────── GitHub ────────────────┐
  PacIOOS ERDDAP │  Action: forecast.yml (hourly check)     │
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
- `cron: "7 * * * *"`: an **hourly light check** (one ~13 KB ERDDAP request). The full download runs when a new run is complete (about once a day) and, with the same run, every 6 h (`--refresh-every-hours 6`) so waves, sea temperature and tides stay fresh when PacIOOS skips a day of WRF (7 of 37 days in Oct–Nov 2026); observations are refreshed at most every 6 h (`--obs-every-hours 6`), so the site redeploys ~5 times a day rather than 24. GitHub cron in practice fires every 4–8 h, not hourly. GitHub cron can run 5–60 min late, so nothing depends on exact timing.
- `workflow_dispatch` for manual runs.
- `concurrency: forecast` (no overlapping runs).
- Scheduled workflows on public repos are disabled after 60 days without repo activity; once a day the job re-enables itself through the API, which resets that timer.

### 7.2 Steps
1. **Detect new run:** read `time_coverage_end` from `erddap/info/wrf_mo/index.csv` (~13 KB, 0.2 s). If it equals `meta.json.wrf.coverageEnd` on the `data` branch and the last build (`generatedAt`) is less than 6 h old, skip the WRF fetch. `meta.wrf.run` records when the run started (coverage end − 168 h: ERDDAP's coverage end only moves once a new run is almost complete). When it changes, also scan THREDDS and archive every complete run of the last 10 days that isn't archived yet (`makani/thredds.py`). NWS, tides and alerts run on their own cadence.
2. **Fetch WRF** with small, bounded ERDDAP **`.json`** requests, parsed with the Python standard library (no numpy/xarray needed; measured 2026-11-13: one spot ≈ 2 s / 7 KB, the stride-2 map box ≈ 4 s / 2.4 MB):
   - Spots: `Uwind,Vwind,Tair,rain` at each spot's cell, from **local midnight HST** → `last` (so "today" shows all 24 hours; past hours come from the model analysis).
   - Map (M2): `Uwind,Vwind` over the Maui box lat **20.50–21.10**, lon **−156.72 to −155.95**, stride 2.
   - Timeout 300 s, 3 retries with exponential backoff; HTML proxy-error pages are treated as failures.
3. **Build spot series** (§7.4) and **map frames** (§7.5).
4. **NWS:** gridpoint raw forecasts per spot (built, `makani/nws.py`, an extra like waves: a failure is a warning): `api.weather.gov/gridpoints/HFO/x,y`, `windSpeed`, `windGust`, `windDirection`, each a list of `start/duration` runs (often 6–24 h) expanded to hourly, km/h → kn, one request per distinct gridpoint, kept to the WRF hours. Forecasters update the grid several times a day, so it keeps coming when PacIOOS skips a WRF run. Not built yet: active alerts for `PHZ117,PHZ119,HIZ045,HIZ049`; latest CWF product → split out the PHZ117/PHZ119 sections.
   **Observations** (implemented in M1, `makani/obs.py`): every run re-reads the last 7 days from Kahului Harbor (CO-OPS) and PHOG (NWS), bins them to hourly values and merges them into `archive/obs/` (§7.6). Re-reading 7 days catches PHOG values that QC fills in late. A failing station is a warning only.
5. **Waves, sea temperature and tides** (implemented, `makani/waves.py`, `makani/water.py`, `makani/tides.py`), with each new WRF run, after the wind is built and validated. They are extras: a failure is a warning, never a reason not to publish the wind.
   - Waves: one SWAN request per spot (`shgt,pper,pdir`, local midnight → `last`) and one WW3 request per distinct offshore cell (`whgt,wper,wdir,shgt,sper,sdir`). Both datasets have a depth axis (`[(0)]`) and 0–360 longitudes. Rule for the wave type in §8.8.
   - Sea temperature: one ROMS request per distinct cell (`temp`, depth `[(0.25)]`, from 3 h before local midnight → `last`, normal −180–180 longitudes). Cells are picked by hand just offshore (config `water`), because the shallows at the beach are masked; hours are interpolated between the 3-hour steps.
   - Tides: CO-OPS `datagetter` `product=predictions`, `datum=MLLW`, `units=english`, `time_zone=lst`: `interval=hilo` from the day before to the day after the forecast, plus `interval=h` for the curve at harmonic stations. Makena (subordinate) has no hourly product (NOAA answers "No Predictions data"), so its curve is a cosine fit between its highs and lows. If NOAA fails, the previously published tide block is kept.
6. **Verification:** pair archived forecasts with archived observations (Kahului Harbor for Kanahā/Sprecks, PHOG as a second reference) → mean bias, MAE (kn), direction error, **by lead time** (same day, D-1, D-2, …). Shown on the Accuracy panel and the History page (§8.6).
7. **Validate** the output (`pipeline/makani/validate.py`: hour count, hourly steps, value ranges, known sectors/sports). If anything fails, keep the previous files and fail the job loudly; never publish partial data.
8. **Publish:** commit `data/` to the orphan **`data` branch** as a single commit and force-push, so git history doesn't grow by ~0.5 MB × 4/day. The archive files **accumulate** in that commit (each run restores the previous `data` branch first). Safety: the restore step fails the job if the branch exists but can't be fetched, and publishing is refused if the archive would contain fewer files than before. Then build the web app with that data copied into `public/data/` and deploy with `actions/deploy-pages`. Publishing happens whenever the forecast **or** the observations changed (so in practice every run).
9. **Alerts:** on the 04:00 and 16:00 UTC runs only, run `alerts.py` (§9).

Each source fails on its own. If NWS is down, WRF still publishes (and the reverse); `meta.json` records each source's status and timestamp.

**PacIOOS outages** (seen 2026-11-14: connection timeouts from some GitHub runners while others got through): the hourly check uses a short timeout (45 s, 2 tries); if ERDDAP is unreachable the published site stays as is, observations are still merged, and the job only **fails once the site's data is more than 24 h old**, so a passing blip doesn't send failure emails every hour. A "Connectivity probe" step logs the runner IP and a `curl` check before each build.

### 7.3 Output files (`data/`)
```
meta.json            run info, per-source status, generatedAt, schemaVersion
spots/kanaha.json    hourly series per spot
spots/sprecks.json
spots/harbor.json
spots/hookipa.json
spots/maui-sunset.json
spots/keawakapu.json
map/frames.json      quantized wind grid for all hours
nws/alerts.json      active advisories (also fetched live client-side)
nws/marine.json      CWF text for PHZ117, PHZ119
archive/index.json                 forecast runs + observation months available, per-station status
archive/forecast/<run>.json        every WRF run as first published (e.g. 2026-11-18T00Z.json)
archive/obs/<station>/<YYYY-MM>.json   hourly observed wind per station and HST month
```

### 7.4 `spots/{id}.json`
```jsonc
{
  "id": "kanaha",
  "wrfCell": { "lat": 20.902, "lon": -156.44, "i": 39, "j": 134 },
  "hours": [
    {
      "t": "2026-11-13T14:00:00-10:00",
      "wrf": { "kn": 18.4, "dir": 68, "gustEst": 23.9, "tairC": 26.1, "rainMmH": 0.0,
               "knAdj": 13.5 },                           // adjusted forecast, only where calibrated (adjust.py)
      "sky": "sun", "sun": 0.97,                          // sun | partly | cloud | rain | null (night); sunshine vs a clear sky
      "nws": { "kn": 17, "gust": 24, "dir": 70 },       // later (M4); null if unavailable
      "sector": "good",                                   // good | ok | poor | danger
      "sports": ["foil_wing", "directional", "twintip"],
      "daylight": true,
      "wave": {                                           // null without a model value (always at the Harbor)
        "m": 1.24, "per": 13.8, "dir": 345,               // SWAN near the beach: height m, peak period s, from°
        "type": "mixed",                                  // flat | chop | swell | mixed
        "swell": { "m": 1.96, "per": 12.9, "dir": 350 },  // WW3 offshore split; chop is null when it blows out to sea
        "chop":  { "m": 1.61, "per": 7.4, "dir": 69 }
      },
      "waterC": 25.6,                                     // ROMS sea surface °C, null without a value
      "nws": { "kn": 18.0, "gust": 24.0, "dir": 70 }      // NWS forecast grid (schema 6), null outside its runs
    }
  ],
  "waves": { "status": "ok", "swanCell": { "lat": 20.905, "lon": -156.445 }, "ww3Cell": { "lat": 20.95, "lon": -156.45 } },
  "water": { "status": "ok", "cell": { "lat": 20.931, "lon": -156.444 } },
  "nws": { "status": "ok", "gridpoint": "HFO/213,126", "updated": "2026-11-17T17:37:08Z" },
  "tide": {                                               // null if the spot has no station
    "station": "1615680", "name": "Kahului Harbor", "kind": "harmonic", "datum": "MLLW", "units": "ft",
    "curve": { "start": "2026-11-13T00:00:00-10:00", "stepMinutes": 60, "ft": [0.59, 1.05, "..."] },
    "extremes": [{ "t": "2026-11-13T05:10:00-10:00", "ft": 2.31, "type": "H" }]
  },
  "sun": [{ "date": "2026-11-13", "rise": "06:41", "set": "17:47" }]
}
```
The spot document also carries `"adjusted": { "reference", "fitted", "maeRaw", "maeAdj" }` (null without a calibration).
`meta.json` gains `waves.spots` (status per spot: ok / sheltered / error), `water.spots` (ok / error) and `tides.stations` (ok / kept / error). Schema version 5 (3 added waves and tides, 4 sea temperature, 5 sky and the adjusted wind).

**Sky** (`makani/sky.py`): WRF's ground-level solar radiation (`swrad`, in the same ERDDAP request as the wind) over the Haurwitz clear-sky radiation for the sun's height gives the sunshine share: ≥ 80 % "sun", 50–80 % "partly", < 50 % "cloud"; rain ≥ 0.25 mm/h "rain", day or night. With the sun under ~12° the ratio is unreliable, so those daylight hours borrow the nearest judged hour. Shown simply (icons and words, the rain rate when it rains): a single model run gives no probability, and a sunshine percentage would read like one.

**Adjusted forecast** (`makani/adjust.py`, `config/calibration.json` from `pipeline/tools/calibrate.py`): measured = a + b × forecast, fitted per spot and situation (trade direction 30–100° or not × day 7–18 h or night) on 14 months of archived forecasts vs measured wind. Reference: the mean of the Kahului Harbor and Airport anemometers for Kanahā and Sprecks, the harbor anemometer for Kahului Harbor, and the Kealia Pond weather station (USFWS refuge, HADS KPDH1 from the Iowa Environmental Mesonet archive, hourly, 5 km north of Maui Sunset, by a pond inland of the beach, so probably reading lower than the water) for Maui Sunset. Hoʻokipa and Keawakapu have no station: they use the Sprecks and Maui Sunset fits (`transferredFrom`), shown as estimates, not checked. Checked on months the fit didn't see (Jul–Nov 2026), kiting hours: Kanahā 4.4 → 2.8 kn typical miss, Sprecks 4.9 → 2.9, Harbor 4.2 → 2.7, Maui Sunset 6.6 → 3.0. E.g. trade-wind day at Kanahā: 25 kn forecast → ~17 kn. The ratings and best session still use the raw model. Rerun the tool from time to time as the archive grows.
Sectors and sports are computed in the pipeline (one implementation, also used by alerts). The front end only displays them.

### 7.5 `map/frames.json`
Implemented in M2 (`makani/mapframes.py`), box and stride in `config/map.json`. **Not displayed since the Pacific redesign** (the island map shows the spots only); still built, cheaply, for a possible wind-field layer later.
- Grid stride 2 (≈ 4 km) over the Maui box lat 20.5–21.1, lon −156.72 to −155.95 → **17 × 20 = 340 points** per hour, same hours as the spot files (local midnight → end of run).
- Quantized: speed as integer tenths of a knot, direction as integer degrees ("from"); `null` where missing.
- `{ "bbox", "stride", "lats": [...], "lons": [...], "times": [HST...], "daylight": [bool...], "kn10": [[...]], "dir": [[...]] }`; each frame is row-major (lat index × len(lons) + lon index), lats/lons ascending. `daylight` is at Kahului, for the slider's night shading.
- Measured 2026-11-13: 111 hours = **269 KB raw, 89 KB gzipped** (budget ≤ 400 KB raw; split per day if it grows past that).
- Validated before publishing (shape, hourly steps, ≥ 90 % filled, plausible speeds). `meta.json` gets `"map": {"file", "hours", "grid"}`; schema version 2.

### 7.6 Archive formats (implemented in M1)
**Forecast run** — `archive/forecast/<run>.json`, ~4 KB, one per WRF run, fetched from THREDDS exactly as issued (run id = init time):
```jsonc
{
  "run": "2026-11-11T00Z", "init": "2026-11-11T00:00:00Z", "source": "thredds",
  "start": "2026-11-10T20:00:00-10:00", "end": "2026-11-17T14:00:00-10:00", "hours": 163,
  "spots": { "kanaha": { "kn": [18.7, …], "dir": [74, …] }, "sprecks": {…}, "maui-sunset": {…}, "keawakapu": {…} }
}
```
- Hourly arrays from `start` on a shared axis, `null` where a value is missing.
- **Lead time = valid time − `init`**, exact, so the History page can compare D-0/D-1/D-2… forecasts honestly.
- A run is archived only once complete (+168 h online), or once it's 3 days old (it'll never complete). Archived runs are immutable and never re-fetched. Several THREDDS errors in a row stop the pass; the next one resumes.
- The M1 records (named by ERDDAP coverage end, without `init`) are removed by `archive.migrate_legacy`.

**Observations** — `archive/obs/<station>/<YYYY-MM>.json`, ~35 KB per station-month:
```jsonc
{ "station": "1615680", "source": "coops", "month": "2026-11",
  "hours": { "2026-11-13T14": { "kn": 14.2, "gust": 20.0, "dir": 71, "n": 10 } } }
```
- Hour keys are HST. Each hour is the **centred** bin [H−30 min, H+30 min), matching WRF's instantaneous hourly values (PHOG's 13:54 report → 14:00).
- `kn` = mean, `gust` = max (null if none reported), `dir` = speed-weighted vector mean (wraps correctly around north), `n` = samples.
- Merge rule: an hour is replaced only by a bin with at least as many samples, so a partial bin at the edge of a fetch window never overwrites a complete one, while late QC fills and corrections still get in.
- Sizes: ~1.5 MB/year for forecasts + ~1 MB/year for observations.

**Backfill:** run the Forecast workflow manually with `forecast_days` and `obs_days` = e.g. 400:
- Forecasts: ~3 requests per run (one per spot), ~0.2 s pause between requests: ~1,100 requests and ~15–20 min for a year.
- Kahului Harbor: requests split into 30-day chunks, ~13 requests for a year.
- PHOG can't be backfilled beyond 7 days.

---

## 8. Front end (Svelte + Vite)

### 8.1 General
- Svelte 5 + Vite, TypeScript, no UI framework. Hand-written SVG for the chart, arrows and icons.
- **"Pacific" design** (concept supplied 2026-11-13, web + phone): one dark, ocean-led theme, deep navy surfaces, amber accent for the best session on the chart and the active tab, headings in Outfit (self-hosted via `@fontsource-variable/outfit`, no third-party request). Dark only by design.
- **Hash routing** (GitHub Pages friendly): `#/<spot>` (today, or tomorrow once today's sun has set at the spot), `#/<spot>/today`, `#/<spot>/tomorrow`, `#/<spot>/days`, `#/<spot>/<YYYY-MM-DD>`. Old `#/spot/<id>` links still work. Later: `#/history`, `#/alerts`, `#/about`.
- **Header:** logo, **location menu** listing the spots (Kanahā, Spreckelsville, Kahului Harbor, Maui Sunset, Keawakapu), tabs **Today / Tomorrow / N Days** (N = days the model covers), **wind unit kn / mph / km/h** and **°C / °F**, and a menu (units on small screens, hourly table, data & credits). On phones the tabs move to a bottom tab bar.
- Spot and units are remembered in `localStorage` (wrapped in try/catch; the site works without it).
- Budget: first load ≤ 250 KB gzipped (JS + CSS ≈ 50 KB today), excluding the island picture (≈ 76 KB on phones, 185 KB on large screens).
- Accessibility: WCAG AA contrast on the dark theme, chart operable with the keyboard (← → Home End Esc) with an `aria-live` readout, a full hourly table behind a disclosure, text with every colour signal.
- Banner when the forecast is old (§8.10). The model run and refresh time are on the Guide page.
- PWA (manifest + service worker, needed for Web Push) comes with M6.

### 8.2 Spot day `#/<spot>/<day>`
1. **Hero:** "Tomorrow / at Kanahā (Kite Beach)", the date, a lower-confidence tag from day 3, and **four day tiles** (`DayTiles.svelte`, `lib/summary.ts`) over the day's daylight hours: **Wind** "15–21 kn" with the speed-weighted mean direction and top gust ("ENE · gusts to 27"); **Sky & air** "24–26 °C" with the day's sky icon and words ("Sunny", "Mostly sunny, passing showers", "Showers likely"); **Water** "26 °C" (sea surface, ROMS); **Waves** "1.1–1.3 m" with the period range and the most common type ("15–17 s · Swell + chop"), "Flat" under 0.3 m or at the sheltered harbor. Units follow the toggles. The stats under the chart give the same things for the selected hour. On wide screens the island picture fills the right of the hero (§8.4); on phones it sits under the title.
2. **Wind Forecast** card (`WindChart.svelte`, geometry in `lib/chart.ts`): wind (3 px, coloured hour by hour by the knots scale, blue → green → yellow → orange) and estimated gusts (grey) on one axis shared by all days of the spot, in the chosen unit; the **adjusted forecast** dashed near-white where the spot has one (legend "Adjusted"); the **NWS forecast** dotted pink (legend "NWS"; readout "18 kn NWS · gusts 24"; coarse steps, as the grid has one value per 6–24 h); area under the wind fading out; **best session** shaded amber with its bounds labelled on the time axis; the session's peak labelled ("21 kn"); night shaded; "NOW" line on today; a strip of **direction arrows** under the time axis coloured by sector (good / OK / poor / offshore). Hover, tap or keys select an hour: crosshair + readout, and the hero map and the stats follow that hour.
   Under the arrows, on the same time axis: the **wave strip** and the **tide panel** (§8.8).
3. **Stats** card, 3 × 2 (2 × 3 on phones): direction (arrow, compass point, words, sector note), waves, tide, air temperature with the hour's sky icon and word (tap to switch °C/°F), sunrise, sunset. All but the sun follow the selected hour, else the current hour (today) or the session peak.
4. **Hourly table** (collapsed): time, wind badge, gust, adjusted, NWS (wind/gust), direction + sector mark, waves (height, period, type), tide, air, sky.
- Later (M4): live observations, marine text.

### 8.3 Next days `#/<spot>/days`
One row per forecast day: name and date, confidence tag, best session and range, the daylight wave range and most common type ("Waves 1.1–1.3 m · swell + chop"), a small chart (same axis for all rows), daylight peak with direction. A row opens that day.

### 8.4 Island map (spot markers on the aerial picture)
Replaces the M2 grid-of-arrows map (judged not very useful): just the spots, on a picture of the island.
- `IslandMap.svelte` shows the aerial picture (`web/scripts/maui-aerial.webp`, supplied for the project) and one marker per spot: a **dot at the beach** (amber for the selected spot) and a **chip** joined to it by a leader line, with the **wind arrow** (pointing downwind, coloured by the knots scale), a short name and the speed in the chosen unit, ⚠ when offshore. Chips link to that spot. The hour shown is the one selected on the chart ("Wind at 3 PM").
- Spots 1–2 km apart (Harbor, Kanahā, Sprecks) can't carry chips at their dots, so `lib/callouts.ts` lays chips out from the real chip widths: Kanahā and Hoʻokipa chips in a row over the bay above their dots (two staggered rows when one doesn't fit), Harbor and Sprecks in a row below theirs, over the island, and the Kīhei chips in a column over the channel to their left (lifted above the dot when a wide chip would cover it). Rows step aside so they never cover a measuring-point dot. Unit-tested for no overlap and staying inside the picture.
- **Measuring points:** small red dots for the anemometers (Kahului Harbor, NOAA 1615680; Kahului Airport PHOG) and yellow for the wave buoy (Pauwela 51205; the other nearby buoy, 51213 Kaumalapau off Lānaʻi, is outside the picture), named on hover; no key, it added nothing to the reading. Positions come from the same script (`stations` in `maui-aerial-spots.json`, from `observationStations` and `buoys` in the config).
- Wide screens: whole island, edges melting into the hero. Phones: cropped on the central valley so the markers spread out, starting a little above the picture (a sea band) so the north-shore chips have room above Hoʻokipa.
- **Placing spots on a picture that isn't georeferenced:** `node web/scripts/build-aerial.mjs` (needs `sharp`: `npm i --no-save sharp` in `web/`, then `npm ci`) finds the picture's shoreline, pairs it with the real coastline (`web/src/assets/maui-coast.json`) through 21 hand-picked landmarks, fits a thin-plate spline map → picture and pushes each spot's beach through it (all land within 2 px of the picture's shore). It also writes the two web sizes of the picture. Outputs are committed: `maui-aerial-{1536,960}.webp`, `maui-aerial-spots.json`. Rerun it after adding a spot.
- **Coastline:** `node web/scripts/build-coast.mjs` downloads the Maui County polygon (US Census 2020 county boundaries, public domain, from the Hawaiʻi Statewide GIS Program ArcGIS service, server-side generalised to 0.0004° ≈ 40 m), clips it to the `config/map.json` box, projects it and writes `web/src/assets/maui-coast.json`. Only the aerial script uses it now.

### 8.5 Alerts page `#/alerts`
Create or manage alerts (§9). Shows the user's push alerts for this browser. Email alerts are managed through the link in each email.

### 8.6 History `#/history` — forecast vs observed
- Pick a past date (and spot: Kanahā or Sprecks; Maui Sunset and Keawakapu show "no observation station yet").
- Chart for that day: **observed** wind and gusts (Kahului Harbor, with PHOG as a dashed second line) against the forecasts that were issued **D-0, D-1, D-2…** before, from `archive/forecast/`.
- Hourly table under the chart: observed kn/gust/dir vs each forecast, with the error.
- Summary stats over the last 7 / 30 days: bias and MAE by lead time, so riders learn e.g. "the model runs 2 kn light at Kanahā in strong trades".
- Data loads lazily: `archive/index.json`, then only the months and runs needed for the chosen date.
- First analysis (2026-11-14, `pipeline/tools/error_factors.py`, 14 months, forecasts 1–2 days ahead, 9 AM–5 PM): the forecast strength is the main driver of the error, then the direction; month, hour, air temperature and clouds matter little overall. Model vs its own cell: Kahului Harbor +3.1 kn bias, 4.2 kn MAE, growing with the forecast strength (+7.7 kn when ≥ 25 kn); Kahului Airport −1.6 kn, 3.5 kn MAE, only 2.5 kn in trades ≥ 14 kn after 11 AM, but 8 kn under on hot days with a light non-trade forecast (sea breeze the model misses).
- Honest caveats on the page: the stations aren't exactly at the spot (Harbor on the waterfront west of Kanahā, airport inland), and WRF is a 2 km cell value.

### 8.7 Guide & sources `#/guide` (built)
From the menu (☰ → Guide & sources), so the forecast screen carries no long text and no footer: how to read the chart (wind, best session, estimated gusts, the adjusted line with each spot's before/after typical miss, direction colours and table marks, sky, waves, tide, water, units, map dots), the data sources with links (PacIOOS WRF, SWAN, WaveWatch III, ROMS, NOAA CO-OPS, the anemometers, the coastline), and the warning. The model run and update time moved there too: the forecast screen carries no text below the hourly table.

---

### 8.8 Tides and waves (built)
Sources are in §3 and the fetch in §7.2 step 5; helpers in `web/src/lib/sea.ts`.

**Wave type** per hour (`makani/waves.py`):
- `flat` when SWAN's height at the beach cell is under 0.3 m (1 ft);
- otherwise from WW3's offshore energy split (height²): swell share ≥ 65 % → `swell`, ≤ 35 % → `chop`, else `mixed` ("Swell + chop");
- wind waves coming from the spot's offshore (danger) sector travel out to sea, so they are dropped and don't count. Example: ENE trade chop off Kīhei;
- without WW3, SWAN's peak period decides: ≥ 10 s swell, else chop.
Checked on 2026-11-13 data: Kanahā 1.1–1.4 m, mostly mixed (≈ 1.6 m of 7 s trade chop + ≈ 2 m of 13 s NNW swell offshore); Sprecks 1.5–2.5 m; Kīhei 0.1–0.2 m, flat.

### 8.9 Home screen and link previews
- **Home screen:** `manifest.webmanifest` (name, standalone display, navy theme, 192/512 and maskable icons) for Android and an `apple-touch-icon` for iPhone, so "Add to Home Screen" gives a Makani icon and opens like an app.
- **Link previews:** Open Graph and Twitter card tags in `index.html` with an absolute `og-image.jpg` (1200 × 630, ~90 KB to stay under WhatsApp's limit): the title, a one-line description and the island picture. Spot links (`#/kanaha`, `#/hookipa/tomorrow`...) share the same preview, the hash never reaches the server.
- Generated by `node web/scripts/build-icons.mjs` (needs `sharp`, as the aerial script) from the header logo and the island picture; the outputs and the favicon, now the same logo, are committed.

### 8.10 Old-forecast banner (built)
Two clocks (`web/src/lib/freshness.ts`): the WRF run (`meta.wrf.run`, or coverage end − 168 h for older data) and Makani's refresh (`meta.generatedAt`, every ~6 h). A run is normally published about a day after it starts and replaced a day later.
- Refresh older than 24 h: yellow "Forecast data last refreshed N hours ago (wind model run of …). The model server may be unreachable", red once the run is also > 80 h old.
- Otherwise run older than 56 h (the next run is late): yellow "The wind forecast comes from the model run of Sat, Nov 14, 2 PM: the University of Hawaiʻi model hasn't published a newer one yet. It still covers until …", plus "The NWS line (dotted) is up to date." when the NWS forecast is there.
- Run older than 80 h (two runs missed): red, "treat it with caution".

**On the chart** (no second y-axis on the wind plot):
- **Wave strip** under the direction arrows, titled "Waves m · period": one cell every 3 h (value of the middle hour) with the height and the period ("1.3 / 17s"), shaded in one hue that gets stronger with size (bands at 0.3 / 0.6 / 1.2 / 2 / 3 m). Text stays in the text colour. Under the cells, runs of the same type are underlined and named ("Swell + chop", "Wind chop", "Flat"); the name shortens or hides when the run is too narrow. At the Harbor: "Sheltered harbor: flat water, wind chop only".
- **Tide panel** under that, titled "Tide m" with the station on the right ("Makena (curve estimated)" for the cosine fit): area curve on a scale shared by all days of the spot, passing through the day's highs and lows. Highs are labelled above ("H 0.7 m · 6:02 AM"), lows below, so neighbouring turns never collide.
- A **Sky** strip sits above the waves: one icon per hour (every 2 h on narrow screens) for sun, partly cloudy, cloudy or showers.
- Night shading, the NOW line and the crosshair run through all of them. The readout adds the adjusted wind, the waves (height, period, type, direction arrow), the tide (height, rising/falling) and the air with the sky ("25°C air · sunny", "showers 1.2 mm/h").
- The compact charts of the day list leave both out.

**Stats tiles:** Waves (height, period, from-direction, type, arrow pointing where the waves go) and Tide (height at the hour, rising/falling, next high or low with its time).

Later: buoy observations (CDIP/NDBC 51205 Pauwela off the north shore) for the History page.

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
3. **Email:** Resend API (free tier: 3,000/month, 100/day). Plain HTML template with the spot, window, knots, direction, link to the spot page, and a **manage/unsubscribe link**. Add `List-Unsubscribe` headers.
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
│  ├─ ratings.json              # sport bands, gust factor
│  └─ map.json                  # map box, grid stride, coastline source
├─ pipeline/                    # Python 3.12
│  ├─ makani/{erddap,thredds,obs,waves,water,tides,sky,adjust,sun,ratings,build,archive,validate}.py (later nws, alerts)
│  ├─ tests/                    # pytest, with recorded fixtures
│  └─ pyproject.toml            # stdlib only in M1; pywebpush added in M6
├─ web/                         # Svelte + Vite + TS
│  ├─ src/{routes,lib,components,assets}/
│  ├─ public/ (manifest, icons, sw.js)
│  ├─ src/assets/maui-coast.json   # generated coastline (committed)
│  └─ scripts/build-coast.mjs
├─ worker/                      # Cloudflare Worker + D1 (TS, wrangler)
│  ├─ src/  migrations/  test/
│  └─ wrangler.toml
└─ .github/workflows/
   ├─ ci.yml                    # lint + tests (pipeline, web, worker) on PRs
   ├─ forecast.yml              # hourly check: pipeline + archive + deploy + alerts
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

- Footer and About: "Model data: PacIOOS WRF Maui-Oahu (University of Hawaiʻi, Yi-Leng Chen), funded by NOAA/IOOS. Waves: PacIOOS SWAN Maui and WaveWatch III Hawaiʻi. Sea temperature: PacIOOS ROMS Hawaiʻi. Forecasts, observations and advisories: NOAA National Weather Service. Tides: NOAA CO-OPS."
- Disclaimer: forecasts can be wrong; not a substitute for checking conditions on site, local knowledge, or official NWS warnings. Kite at your own risk.
- Privacy: only an email address (if given) and push endpoints are stored, used only for alerts, deletable at any time through the manage link. No analytics, no cookies, no third-party trackers.
- Hawaiian names spelled with ʻokina and kahakō where correct (e.g. Kanahā, Hoʻokipa) in display text; ASCII ids in code.

---

## 13. Milestones

| # | Deliverable |
|---|---|
| M1 | Repo, CI, `config/spots.json`, WRF pipeline → `spots/*.json`, data branch, Pages deploy of a bare hourly table, **forecast archive (every THREDDS run, backfilled a year) + observed-wind archive (Kahului Harbor backfilled, PHOG)**, hourly light check |
| M2 | Coastline asset, SVG map with arrows, time slider (**done**; replaced in M3 by the island map with spot markers) |
| M3 | **Pacific redesign** (built locally, not yet deployed): location menu, Today / Tomorrow / N Days, hero with best session, island map with spot markers, spot chart (wind, gust, best session, direction strip), stats, hourly table, kn/mph/km/h and °C/°F, phone tab bar. Gear badges dropped. Kahului Harbor and Keawakapu added. **Tides and waves (§8.8)** |
| M4 | NWS gridpoint, live observations, advisories, marine text, accuracy panel, **History page (forecast vs observed, §8.6)** |
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
6. **Data storage:** data force-pushed to an orphan `data` branch as one commit (no git history), not committed to `main`. Archive files accumulate inside that commit (§7.6). A periodic backup (e.g. a monthly zip as a GitHub Release asset) can be added if the archive becomes precious.
7. **Dark-only theme:** the Pacific design is dark by intent; the earlier light/dark switch was dropped.
