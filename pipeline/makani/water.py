"""Sea surface temperature at each spot, from the PacIOOS ROMS Hawaii ocean model.

`roms_hiig` is on the same ERDDAP server as the wind: a ~4 km grid, a forecast
every 3 hours, `temp` in °C at a 0.25 m top level. Land and the shallows right
at the beach are masked, so each spot reads a cell picked by hand just offshore
(config `water`). Hourly values are interpolated between the 3-hour steps.

Each hour gets `"waterC": 25.6` (or null), and the spot document a
`"water": {"status": "ok" | "error" | "none", "cell": {...}}` block.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import erddap
from .net import FetchError, Fetcher, http_get

ROMS = "roms_hiig"
DEPTH = 0.25
STEP = timedelta(hours=3)


def _parse_z(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def series(cell: dict[str, float], start: str, fetch: Fetcher = http_get
           ) -> tuple[list[tuple[datetime, float]], dict[str, float]]:
    """(time, °C) points for the cell nearest `cell`, from 3 h before `start` so the
    first hours can be interpolated, plus the cell actually used."""
    begin = _iso_z(_parse_z(start) - STEP)
    rows = erddap.point_series(cell["lat"], cell["lon"], begin, ("temp",), fetch,
                               dataset=ROMS, depth=DEPTH)
    pts = []
    for r in rows:
        v = r.get("temp")
        if isinstance(v, (int, float)) and v == v:  # NaN is a masked (land) cell
            pts.append((_parse_z(r["time"]), float(v)))
    first = rows[0] if rows else {}
    return pts, {"lat": first.get("latitude"), "lon": first.get("longitude")}


def value_at(pts: list[tuple[datetime, float]], t: datetime) -> float | None:
    """Linear between the two steps around `t`; None outside the series or across a gap."""
    for tk, vk in pts:
        if tk == t:
            return vk
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 < t < t1:
            return None if t1 - t0 > STEP else v0 + (v1 - v0) * ((t - t0) / (t1 - t0))
    return None


class WaterSource:
    """Fetches each model cell once per build (nearby spots can share one)."""

    def __init__(self, start: str, fetch: Fetcher = http_get):
        self.start, self.fetch = start, fetch
        self._cache: dict[tuple[float, float], tuple[list[tuple[datetime, float]], dict[str, float]]] = {}

    def apply(self, spot: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
        """Add `waterC` to each hour of `doc` and return the doc-level `water` block."""
        cell = spot.get("water")
        if not cell:
            return {"status": "none"}
        key = (cell["lat"], cell["lon"])
        try:
            if key not in self._cache:
                self._cache[key] = series(cell, self.start, self.fetch)
            pts, used = self._cache[key]
        except (FetchError, KeyError, ValueError) as exc:
            print(f"::warning::water temperature for {spot['id']} not available: {exc}")
            for h in doc["hours"]:
                h["waterC"] = None
            return {"status": "error"}
        n = 0
        for h in doc["hours"]:
            v = value_at(pts, datetime.fromisoformat(h["t"]))
            h["waterC"] = None if v is None else round(v, 1)
            n += v is not None
        print(f"{spot['id']}: water temperature for {n} of {len(doc['hours'])} hours")
        return {"status": "ok" if n else "error", "cell": used}
