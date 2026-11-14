"""Build the static forecast JSON consumed by the site.

Usage:
    python -m makani.build --out web/public/data [--force] [--obs-days N | --skip-obs]

1. WRF forecast: rebuilt only when a new model run is out; each run is also
   archived (archive/forecast/<run>.json).
2. Observations: last N days (default 7) merged into archive/obs/ every time.
   Use a large N once to backfill Kahului Harbor history (NWS keeps 7 days).

Exits 0 when the forecast is fine (an observation source failing is only a
warning); writes `changed=true|false` to $GITHUB_OUTPUT when set.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone, tzinfo
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, archive, erddap, obs
from .config import load_ratings, load_spots, local_tz
from .jsonio import read_json, write_json_atomic
from .ratings import classify_sector, display_kn, ms_to_kn, sports_for, uv_to_speed_dir
from .sun import sun_times
from .validate import validate_meta, validate_spot

WRF_VARIABLES = ("Uwind", "Vwind", "Tair", "rain")


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_z(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _round(x: float | None, nd: int) -> float | None:
    return None if x is None else round(x, nd)


def build_spot(spot: dict[str, Any], rows: list[dict[str, Any]], ratings: dict[str, Any],
               tz: tzinfo) -> dict[str, Any]:
    """Turn raw ERDDAP rows for one grid cell into the published spot document."""
    beach = spot["beach"]
    sun_cache: dict[date, tuple[datetime, datetime]] = {}
    hours = []
    for r in rows:
        u, v = r.get("Uwind"), r.get("Vwind")
        if u is None or v is None:
            continue
        t_utc = _parse_z(r["time"])
        t_loc = t_utc.astimezone(tz)
        d = t_loc.date()
        if d not in sun_cache:
            sun_cache[d] = sun_times(d, beach["lat"], beach["lon"])
        rise, sset = sun_cache[d]

        ms, deg = uv_to_speed_dir(u, v)
        kn = ms_to_kn(ms)
        sector = classify_sector(deg, spot["sectors"])
        rain = r.get("rain")
        hours.append({
            "t": t_loc.isoformat(),
            "wrf": {
                "kn": round(kn, 1),
                "dir": deg,
                "gustEst": round(kn * ratings["gustFactor"], 1),
                "tairC": _round(r.get("Tair"), 1),
                "rainMmH": None if rain is None else round(max(rain, 0.0) * 3600.0, 2),
            },
            "sector": sector,
            "sports": sports_for(display_kn(kn), sector, ratings),
            "daylight": rise <= t_utc <= sset,
        })

    first = rows[0] if rows else {}
    return {
        "id": spot["id"],
        "name": spot["name"],
        "displayName": spot.get("displayName", spot["name"]),
        "beach": beach,
        "wrfCell": {"lat": first.get("latitude"), "lon": first.get("longitude")},
        "sectors": spot["sectors"],
        "hours": hours,
        "sun": [
            {"date": d.isoformat(),
             "rise": rs[0].astimezone(tz).strftime("%H:%M"),
             "set": rs[1].astimezone(tz).strftime("%H:%M")}
            for d, rs in sorted(sun_cache.items())
        ],
    }


def build(out_dir: Path, *, force: bool = False, now: datetime | None = None,
          fetch: erddap.Fetcher = erddap.http_get, config_dir: Path | None = None) -> bool:
    """Fetch and write all files. Returns False when the model run is unchanged."""
    spots_cfg = load_spots(config_dir)
    ratings = load_ratings(config_dir)
    tz = local_tz(spots_cfg)
    now = now or datetime.now(timezone.utc)

    cov_end = erddap.coverage_end(fetch)
    prev = read_json(out_dir / "meta.json")
    if (not force and prev and prev.get("schemaVersion") == SCHEMA_VERSION
            and prev.get("wrf", {}).get("coverageEnd") == cov_end):
        print(f"WRF run unchanged (coverage end {cov_end}); nothing to do.")
        return False

    # Start at local midnight so "today" shows all 24 hours (past hours come from analysis).
    midnight_local = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start = _iso_z(midnight_local)

    docs = []
    for spot in spots_cfg["spots"]:
        cell = spot["wrfCell"]
        rows = erddap.point_series(cell["lat"], cell["lon"], start, WRF_VARIABLES, fetch)
        doc = build_spot(spot, rows, ratings, tz)
        print(f"{spot['id']}: {len(doc['hours'])} hours from cell "
              f"{doc['wrfCell']['lat']}, {doc['wrfCell']['lon']}")
        docs.append(doc)

    sport_ids = {b["id"] for b in ratings["sports"]}
    for doc in docs:
        validate_spot(doc, sport_ids)

    hours0 = docs[0]["hours"]
    meta = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": _iso_z(now),
        "timezone": spots_cfg["timezone"],
        "utcOffsetHours": spots_cfg["utcOffsetHours"],
        "wrf": {
            "dataset": erddap.DATASET,
            "coverageEnd": cov_end,
            "start": hours0[0]["t"],
            "end": hours0[-1]["t"],
            "hours": len(hours0),
            "status": "ok",
        },
        "ratings": ratings,
        "spots": [{"id": d["id"], "name": d["name"], "displayName": d["displayName"]} for d in docs],
    }
    validate_meta(meta, [d["id"] for d in docs])

    # Archive first (it's the one thing we can never re-fetch), then spot files,
    # meta last so meta never references data that isn't there.
    archive.save_forecast(out_dir, meta, docs)
    for doc in docs:
        write_json_atomic(out_dir / "spots" / f"{doc['id']}.json", doc)
    write_json_atomic(out_dir / "meta.json", meta)
    print(f"Wrote {len(docs)} spots, {meta['wrf']['hours']} hours, run ends {cov_end}.")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="output directory (e.g. web/public/data)")
    ap.add_argument("--force", action="store_true", help="rebuild even if the model run is unchanged")
    ap.add_argument("--obs-days", type=float, default=obs.NWS_MAX_DAYS,
                    help="days of observations to (re)fetch; large values backfill CO-OPS history")
    ap.add_argument("--skip-obs", action="store_true", help="don't fetch observations")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    forecast_changed = build(args.out, force=args.force, now=now)

    obs_updated = 0
    obs_status: dict[str, Any] = {}
    if not args.skip_obs:
        spots_cfg = load_spots()
        obs_status = obs.update_obs(args.out, spots_cfg.get("observationStations", []),
                                    local_tz(spots_cfg), now, days=args.obs_days)
        obs_updated = sum(s.get("updated", 0) for s in obs_status.values())
    index = archive.write_index(args.out, obs_status=obs_status, now=now)
    print(f"Archive: {len(index['forecastRuns'])} forecast runs, "
          f"obs months {', '.join(f'{k}: {len(v)}' for k, v in index['obs'].items()) or 'none'}")

    changed = forecast_changed or obs_updated > 0
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
