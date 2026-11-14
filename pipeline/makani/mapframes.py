"""Wind grid for the SVG map: one quantized frame per hour.

    map/frames.json
    {
      "bbox", "stride", "lats": [...], "lons": [...],      # grid point coordinates (ascending)
      "times": ["2026-11-13T00:00:00-10:00", ...],         # HST, same hours as the spot files
      "daylight": [true, ...],                             # at Kahului, for slider shading
      "kn10": [[...], ...],   # per hour, row-major (lat index * len(lons) + lon index),
      "dir":  [[...], ...]    # wind speed in tenths of a knot / "from" direction in degrees; null = missing
    }
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any

from .ratings import ms_to_kn, uv_to_speed_dir
from .sun import sun_times
from .validate import ValidationError

MAX_BYTES_HINT = 400_000  # SPEC §7.5 budget for the raw JSON


def _parse_z(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def build_frames(rows: list[dict[str, Any]], bbox: dict[str, float], stride: int, tz: tzinfo,
                 sun_at: tuple[float, float]) -> dict[str, Any]:
    lats = sorted({round(r["latitude"], 4) for r in rows})
    lons = sorted({round(r["longitude"], 4) for r in rows})
    times = sorted({r["time"] for r in rows})
    ilat = {v: i for i, v in enumerate(lats)}
    ilon = {v: i for i, v in enumerate(lons)}
    itime = {v: i for i, v in enumerate(times)}
    n = len(lats) * len(lons)
    kn10: list[list[int | None]] = [[None] * n for _ in times]
    dirs: list[list[int | None]] = [[None] * n for _ in times]
    for r in rows:
        u, v = r.get("Uwind"), r.get("Vwind")
        if u is None or v is None:
            continue
        k = ilat[round(r["latitude"], 4)] * len(lons) + ilon[round(r["longitude"], 4)]
        ms, deg = uv_to_speed_dir(u, v)
        t = itime[r["time"]]
        kn10[t][k] = int(round(ms_to_kn(ms) * 10))
        dirs[t][k] = deg

    sun_cache: dict[date, tuple[datetime, datetime]] = {}
    local_times, daylight = [], []
    for s in times:
        t_utc = _parse_z(s)
        d = t_utc.astimezone(tz).date()
        if d not in sun_cache:
            sun_cache[d] = sun_times(d, *sun_at)
        rise, sset = sun_cache[d]
        local_times.append(t_utc.astimezone(tz).isoformat())
        daylight.append(rise <= t_utc <= sset)

    return {"bbox": bbox, "stride": stride, "lats": lats, "lons": lons, "times": local_times,
            "daylight": daylight, "kn10": kn10, "dir": dirs}


def validate_frames(doc: dict[str, Any], min_hours: int = 24) -> None:
    n = len(doc["lats"]) * len(doc["lons"])
    times = doc["times"]
    if len(times) < min_hours:
        raise ValidationError(f"map: expected >= {min_hours} hours, got {len(times)}")
    if n < 50:
        raise ValidationError(f"map: grid too small ({n} points)")
    for a, b in zip(times, times[1:]):
        if datetime.fromisoformat(b) - datetime.fromisoformat(a) != timedelta(hours=1):
            raise ValidationError(f"map: non-hourly step {a} -> {b}")
    for name in ("kn10", "dir"):
        if len(doc[name]) != len(times) or any(len(fr) != n for fr in doc[name]):
            raise ValidationError(f"map: {name} has the wrong shape")
    filled = sum(1 for fr in doc["kn10"] for x in fr if x is not None)
    if filled < 0.9 * n * len(times):
        raise ValidationError(f"map: too many missing values ({filled} of {n * len(times)})")
    if any(x is not None and not 0 <= x < 1200 for fr in doc["kn10"] for x in fr):
        raise ValidationError("map: implausible wind speed")
