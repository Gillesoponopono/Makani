"""Forecast archive from PacIOOS THREDDS: every WRF run, exactly as issued.

THREDDS keeps each individual run of wrf_mo since 2010-05-14 (5,578 runs on
2026-11-13), one per day initialised at 00Z (14:00 HST the day before), each
running to init + 168 h. Unlike the ERDDAP "best" series, a run never changes
once complete, so lead time is exact: valid time - init time.

Runs land slowly (the 2026-11-12 run had 67 of 163 hours online after ~48 h),
so a run is archived only once complete, or once it's old enough that it
clearly never will be.

Per run and spot, one small NetCDF Subset Service (NCSS) point request in CSV:
~1 s and ~12 KB. A year of backfill for 3 spots is ~1,100 requests.

    archive/forecast/<YYYY-MM-DDTHHZ>.json
    {"run", "init", "source": "thredds", "start" (HST), "hours",
     "spots": {id: {"kn": [...], "dir": [...]}}}   # hourly from start, null for gaps
"""

from __future__ import annotations

import csv
import io
import re
import time
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, Callable

from .jsonio import write_json_atomic
from .net import FetchError, Fetcher, http_get
from .ratings import ms_to_kn, uv_to_speed_dir

BASE = "https://pae-paha.pacioos.hawaii.edu/thredds"
CATALOG_URL = f"{BASE}/catalog/wrf_mo/runs/catalog.xml"
RUN_PREFIX = "WRF_Maui-Oahu_Regional_Atmospheric_Model_RUN_"
RUN_LENGTH = timedelta(hours=168)
GIVE_UP_AFTER = timedelta(days=3)  # archive an incomplete run once it's this old
MAX_CONSECUTIVE_ERRORS = 5          # server down: stop and retry next time

_RUN_RE = re.compile(re.escape(RUN_PREFIX) + r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)")


def _parse_z(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def run_id(init: datetime) -> str:
    """2026-11-11T00:00Z -> '2026-11-11T00Z' (also the archive file name)."""
    return init.astimezone(timezone.utc).strftime("%Y-%m-%dT%HZ")


def list_runs(fetch: Fetcher = http_get) -> list[datetime]:
    """Init times of all runs in the THREDDS catalog, oldest first."""
    raw = fetch(CATALOG_URL).decode("utf-8", "replace")
    return sorted({_parse_z(m) for m in _RUN_RE.findall(raw)})


def point_url(init: datetime, lat: float, lon: float) -> str:
    name = RUN_PREFIX + init.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"{BASE}/ncss/grid/wrf_mo/runs/{name}"
            f"?var=Uwind&var=Vwind&latitude={lat:g}&longitude={lon:g}&temporal=all&accept=csv")


def _float(s: str) -> float | None:
    try:
        v = float(s)
    except ValueError:
        return None
    return None if v != v else v  # NaN


def parse_point_csv(raw: bytes) -> list[tuple[datetime, float | None, float | None]]:
    """NCSS CSV -> [(valid time UTC, u, v)]. Columns look like 'Uwind[unit="meter second-1"]'."""
    text = raw.decode("utf-8", "replace")
    if not text.startswith("time"):
        raise FetchError(f"unexpected NCSS response: {text[:200]!r}")
    reader = csv.reader(io.StringIO(text))
    header = [h.split("[", 1)[0] for h in next(reader)]
    try:
        it, iu, iv = header.index("time"), header.index("Uwind"), header.index("Vwind")
    except ValueError as exc:
        raise FetchError(f"NCSS CSV missing columns: {header}") from exc
    return [(_parse_z(row[it]), _float(row[iu]), _float(row[iv])) for row in reader if row]


def build_record(init: datetime, series: dict[str, list[tuple[datetime, float | None, float | None]]],
                 tz: tzinfo) -> dict[str, Any]:
    """Compact run record on a shared hourly axis (null where a spot has no value)."""
    times = sorted({t for rows in series.values() for t, _, _ in rows})
    start, end = times[0], times[-1]
    n = int((end - start).total_seconds() // 3600) + 1
    spots = {}
    for sid, rows in series.items():
        kn: list[float | None] = [None] * n
        dirs: list[int | None] = [None] * n
        for t, u, v in rows:
            if u is None or v is None:
                continue
            i = int((t - start).total_seconds() // 3600)
            ms, deg = uv_to_speed_dir(u, v)
            kn[i], dirs[i] = round(ms_to_kn(ms), 1), deg
        spots[sid] = {"kn": kn, "dir": dirs}
    return {
        "run": run_id(init),
        "init": init.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "thredds",
        "start": start.astimezone(tz).isoformat(),
        "end": end.astimezone(tz).isoformat(),
        "hours": n,
        "spots": spots,
    }


def is_complete(init: datetime, last_valid: datetime, now: datetime) -> bool:
    return last_valid >= init + RUN_LENGTH or now - init >= GIVE_UP_AFTER


def update_forecast_archive(out_dir: Path, spots: list[dict[str, Any]], tz: tzinfo, now: datetime,
                            days: float = 10, fetch: Fetcher = http_get, pause: float = 0.2,
                            sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    """Archive every complete run from the last `days` that isn't archived yet.

    Archived runs are immutable and never re-fetched. Errors on one run don't stop
    the others; several in a row (server down) stop the pass, and the next pass
    picks up where this one left off.
    """
    folder = out_dir / "archive" / "forecast"
    since = now - timedelta(days=days)
    added, pending, errors = [], [], 0
    consecutive = 0
    for init in list_runs(fetch):
        if init < since or (folder / f"{run_id(init)}.json").exists():
            continue
        try:
            series = {}
            for spot in spots:
                cell = spot["wrfCell"]
                series[spot["id"]] = parse_point_csv(fetch(point_url(init, cell["lat"], cell["lon"])))
                if pause:
                    sleep(pause)
            if not any(series.values()):
                raise FetchError("run has no data")
            rec = build_record(init, series, tz)
            if not is_complete(init, _parse_z_any(rec["end"]), now):
                pending.append(f"{run_id(init)} ({rec['hours']} h so far)")
                consecutive = 0
                continue
            write_json_atomic(folder / f"{rec['run']}.json", rec)
            added.append(rec["run"])
            consecutive = 0
        except FetchError as exc:
            errors += 1
            consecutive += 1
            print(f"::warning::forecast run {run_id(init)}: {exc}")
            if consecutive >= MAX_CONSECUTIVE_ERRORS:
                print("::warning::too many THREDDS errors in a row; stopping this pass")
                break
    print(f"forecast archive: {len(added)} runs added"
          + (f" ({added[0]} … {added[-1]})" if added else "")
          + (f"; waiting for {', '.join(pending)}" if pending else "")
          + (f"; {errors} errors" if errors else ""))
    return {"status": "ok" if not errors else "partial", "added": len(added), "pending": pending,
            "errors": errors}


def _parse_z_any(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(timezone.utc)
