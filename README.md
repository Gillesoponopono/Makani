# Makani

Free kitesurf wind forecast for Maui (Kanaha, Spreckelsville, Maui Sunset), built on the PacIOOS WRF `wrf_mo` model and NWS data. Static site on GitHub Pages, refreshed by GitHub Actions.

See [SPEC.md](SPEC.md) for the full specification.

## Layout

| Path | What |
|---|---|
| `config/` | Spots (coordinates, model cell, direction sectors) and sport bands, shared by everything |
| `pipeline/` | Python (stdlib only) that fetches WRF from ERDDAP and writes the site's JSON |
| `web/` | Svelte + Vite site |
| `.github/workflows/` | `ci.yml` tests, `forecast.yml` data every 6 h, `deploy.yml` Pages deploy |

Forecast JSON is not committed to `main`. `forecast.yml` force-pushes it to the orphan `data` branch (one commit, no history), and `deploy.yml` copies it into the site at build time.

The `data` branch also holds the **archive** used to compare forecasts with what actually happened:
- `archive/forecast/<run>.json`: every WRF run as it was first published (it can't be re-fetched later).
- `archive/obs/<station>/<YYYY-MM>.json`: hourly observed wind from Kahului Harbor (NOAA CO-OPS `1615680`) and Kahului Airport (NWS `PHOG`).

Each run restores the previous `data` branch first, so archive files accumulate. The workflow refuses to publish if the archive would shrink.

## Local development

```bash
python3 -m venv .venv && .venv/bin/pip install -r pipeline/requirements-dev.txt
```

```bash
cd pipeline && ../.venv/bin/python -m pytest -q
```

Fetch live data into the dev site (add `--force` to rebuild an unchanged model run, `--obs-days 30` to pull more observations, `--skip-obs` to skip them):

```bash
cd pipeline && ../.venv/bin/python -m makani.build --out ../web/public/data
```

```bash
cd web && npm install && npm run dev
```

## One-time GitHub setup

1. Settings → Pages → Source: **GitHub Actions**.
2. Actions → **Forecast data** → Run workflow (creates the `data` branch and deploys).
3. Optional, once: run **Forecast data** again with `obs_days` = 400 to backfill about a year of Kahului Harbor observations. The airport (PHOG) only keeps 7 days.
