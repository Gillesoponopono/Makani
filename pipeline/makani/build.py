"""Build the static forecast JSON consumed by the site.

Usage:
    python -m makani.build --out web/public/data [--force]
        [--forecast-days N] [--obs-days N] [--obs-every-hours H] [--skip-obs]

Designed to run hourly as a cheap check:
1. Site forecast (ERDDAP): one ~13 KB request reads the dataset's coverage end;
   the spot JSON is rebuilt only when it changes, i.e. a new run is complete.
2. Forecast archive (THREDDS): when a new run is out (or with --force, or a
   non-default --forecast-days for backfill), every complete run of the last
   N days that isn't archived yet is saved exactly as issued.
3. Observations: the last N days are merged into archive/obs/, at most every
   H hours (--obs-every-hours; 0 = every time). A large --obs-days backfills
   Kahului Harbor history (NWS keeps only 7 days).

Exits 0 when the site forecast is fine (archive and observation failures are
warnings); writes `changed=true|false` to $GITHUB_OUTPUT when set.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timezone, tzinfo
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, archive, erddap, mapframes, obs, thredds
from .config import load_map, load_ratings, load_spots, local_tz
from .jsonio import read_json, write_json_atomic
from .net import FetchError
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

    map_cfg = load_map(config_dir)
    map_rows = erddap.box_series(map_cfg["bbox"], map_cfg["gridStride"], start, ("Uwind", "Vwind"), fetch)
    beach0 = spots_cfg["spots"][0]["beach"]
    frames = mapframes.build_frames(map_rows, map_cfg["bbox"], map_cfg["gridStride"], tz,
                                    (beach0["lat"], beach0["lon"]))
    mapframes.validate_frames(frames)
    print(f"map: {len(frames['lats'])}x{len(frames['lons'])} grid, {len(frames['times'])} hours")

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
        "spots": [{"id": d["id"], "name": d["name"], "displayName": d["displayName"],
                   "beach": d["beach"]} for d in docs],
        "map": {"file": "map/frames.json", "hours": len(frames["times"]),
                "grid": [len(frames["lats"]), len(frames["lons"])]},
    }
    validate_meta(meta, [d["id"] for d in docs])

    # Data files first, meta last, so meta never references data that isn't there.
    for doc in docs:
        write_json_atomic(out_dir / "spots" / f"{doc['id']}.json", doc)
    write_json_atomic(out_dir / "map" / "frames.json", frames)
    write_json_atomic(out_dir / "meta.json", meta)
    print(f"Wrote {len(docs)} spots, {meta['wrf']['hours']} hours, run ends {cov_end}.")
    return True


DEFAULT_FORECAST_DAYS = 10
STALE_HOURS = 24  # fail the job only when the published forecast is older than this


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True, help="output directory (e.g. web/public/data)")
    ap.add_argument("--force", action="store_true", help="rebuild even if the model run is unchanged")
    ap.add_argument("--forecast-days", type=float, default=DEFAULT_FORECAST_DAYS,
                    help="archive missing THREDDS runs from the last N days (e.g. 400 to backfill)")
    ap.add_argument("--obs-days", type=float, default=obs.NWS_MAX_DAYS,
                    help="days of observations to (re)fetch; large values backfill CO-OPS history")
    ap.add_argument("--obs-every-hours", type=float, default=0,
                    help="skip observations if they were checked less than H hours ago (0 = always)")
    ap.add_argument("--skip-obs", action="store_true", help="don't fetch observations")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    spots_cfg = load_spots()
    tz = local_tz(spots_cfg)

    # 1. Site forecast (cheap check; full fetch only for a new run).
    # PacIOOS is sometimes unreachable from some GitHub runners (seen 2026-11-14):
    # keep the published site as is, still update observations, and only fail the
    # job once the site's data is more than STALE_HOURS old.
    forecast_error = None
    try:
        forecast_changed = build(args.out, force=args.force, now=now)
    except FetchError as exc:
        forecast_changed, forecast_error = False, str(exc)
        print(f"::warning::site forecast not updated, PacIOOS ERDDAP unreachable: {exc}")

    # 2. Forecast archive.
    migrated = archive.migrate_legacy(args.out)
    if migrated:
        print(f"Removed {migrated} legacy forecast archive file(s)")
    fc_status = None
    no_runs_yet = not any((args.out / "archive" / "forecast").glob("*.json"))
    scan = forecast_changed or args.force or args.forecast_days != DEFAULT_FORECAST_DAYS or no_runs_yet
    if scan and not forecast_error:
        try:
            fc_status = thredds.update_forecast_archive(args.out, spots_cfg["spots"], tz, now,
                                                        days=args.forecast_days)
        except FetchError as exc:
            fc_status = {"status": "error", "error": str(exc)[:300], "added": 0}
            print(f"::warning::forecast archive failed: {exc}")

    # 3. Observations.
    obs_updated = 0
    obs_status: dict[str, Any] = {}
    ago = archive.obs_checked_hours_ago(args.out, now)
    due = args.obs_every_hours <= 0 or ago is None or ago >= args.obs_every_hours - 0.5
    if args.skip_obs:
        pass
    elif not due:
        print(f"Observations checked {ago:.1f} h ago; next check after {args.obs_every_hours:g} h.")
    else:
        obs_status = obs.update_obs(args.out, spots_cfg.get("observationStations", []),
                                    tz, now, days=args.obs_days)
        obs_updated = sum(s.get("updated", 0) for s in obs_status.values())

    index = archive.write_index(args.out, obs_status=obs_status, forecast_status=fc_status, now=now)
    print(f"Archive: {len(index['forecastRuns'])} forecast runs, "
          f"obs months {', '.join(f'{k}: {len(v)}' for k, v in index['obs'].items()) or 'none'}")

    runs_added = (fc_status or {}).get("added", 0)
    changed = forecast_changed or runs_added > 0 or migrated > 0 or obs_updated > 0
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")

    if forecast_error:
        meta = read_json(args.out / "meta.json") or {}
        generated = meta.get("generatedAt")
        age = ((now - datetime.strptime(generated, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))
               .total_seconds() / 3600) if generated else None
        if age is None or age > STALE_HOURS:
            print(f"::error::site forecast is {'missing' if age is None else f'{age:.0f} h old'} "
                  f"and PacIOOS is unreachable")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
