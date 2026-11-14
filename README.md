# Makani

Free kitesurf wind forecast for Maui (Kanaha, Spreckelsville, Kahului Harbor, Hoʻokipa, Maui Sunset, Keawakapu), built on the PacIOOS WRF `wrf_mo` model and NWS data, with waves (PacIOOS SWAN Maui and WaveWatch III), sea temperature (PacIOOS ROMS) and tides (NOAA CO-OPS predictions). Static site on GitHub Pages, refreshed by GitHub Actions.

See [SPEC.md](SPEC.md) for the full specification.

## Layout

| Path | What |
|---|---|
| `config/` | Spots (coordinates, model cell, direction sectors) and sport bands, shared by everything |
| `pipeline/` | Python (stdlib only) that fetches WRF wind, SWAN/WW3 waves and ROMS sea temperature from ERDDAP and NOAA tide predictions, and writes the site's JSON |
| `web/` | Svelte + Vite site; `web/scripts/` builds the coastline and places the spots on the island picture (run once, outputs committed) |
| `.github/workflows/` | `ci.yml` tests, `forecast.yml` hourly light check (full fetch only for a new run, observations every ~6 h), `deploy.yml` Pages deploy |

Forecast JSON is not committed to `main`. `forecast.yml` force-pushes it to the orphan `data` branch (one commit, no history), and `deploy.yml` copies it into the site at build time.

The `data` branch also holds the **archive** used to compare forecasts with what actually happened:
- `archive/forecast/<run>.json`: every WRF run exactly as issued, from PacIOOS THREDDS (which keeps all runs since 2010), named by init time.
- `archive/obs/<station>/<YYYY-MM>.json`: hourly observed wind from Kahului Harbor (NOAA CO-OPS `1615680`) and Kahului Airport (NWS `PHOG`).

Each run restores the previous `data` branch first, so archive files accumulate. The workflow refuses to publish if the archive would shrink.

## Local development

```bash
python3 -m venv .venv && .venv/bin/pip install -r pipeline/requirements-dev.txt
```

```bash
cd pipeline && ../.venv/bin/python -m pytest -q
```

Fetch live data into the dev site (add `--force` to rebuild an unchanged model run, `--forecast-days 30` / `--obs-days 30` to archive more history, `--skip-obs` to skip observations):

```bash
cd pipeline && ../.venv/bin/python -m makani.build --out ../web/public/data
```

Forecast-error analysis (forecast vs the Kahului Harbor and Airport anemometers, broken down by direction, strength, month, hour, air temperature and cloud cover; downloads and caches its public data):

```bash
cd pipeline && python3 tools/error_factors.py --work /tmp/makani-errors --csv
```

Refit the adjusted forecast (writes `config/calibration.json`, same cache):

```bash
cd pipeline && python3 tools/calibrate.py --work /tmp/makani-errors
```

```bash
cd web && npm install && npm run dev
```

## One-time GitHub setup

1. Settings → Pages → Source: **GitHub Actions**.
2. Actions → **Forecast data** → Run workflow (creates the `data` branch and deploys).
3. Optional, once: run **Forecast data** again with `forecast_days` = 400 and `obs_days` = 400 to backfill about a year of forecast runs and Kahului Harbor observations (~20 min). The airport (PHOG) only keeps 7 days.
