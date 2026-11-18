"""The National Weather Service forecast at each spot: a second opinion beside WRF.

`api.weather.gov/gridpoints/HFO/x,y` is the Honolulu office's forecast grid
(2.5 km). Forecasters edit it and it's updated several times a day, so it keeps
coming when PacIOOS skips a WRF run. It has real gusts (WRF has none). Each
layer is a list of `start/duration` runs (`2026-11-17T12:00:00+00:00/PT15H`):
one value often spans 6 to 24 hours, so the line is coarser than WRF.

Each hour gets `"nws": {"kn": 18.0, "gust": 24.0, "dir": 70}` (or null), and the
spot document an `"nws": {"status": "ok" | "error" | "none", "gridpoint":
"HFO/213,126", "updated": "2026-11-17T17:37:08Z"}` block.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .net import FetchError, Fetcher, http_get

URL = "https://api.weather.gov/gridpoints/{gridpoint}"
SOURCE = "NWS Honolulu forecast grid (api.weather.gov)"
TO_KN = {"wmoUnit:km_h-1": 1 / 1.852, "wmoUnit:m_s-1": 3600 / 1852, "wmoUnit:kn": 1.0}
_DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")
HOUR = timedelta(hours=1)


def parse_duration(s: str) -> timedelta:
    """ISO 8601 durations as the NWS writes them: PT1H, PT15H, P1D, P1DT6H."""
    m = _DURATION.match(s)
    if not m or not any(m.groups()):
        raise ValueError(f"bad duration {s!r}")
    d, h, mi = (int(g or 0) for g in m.groups())
    return timedelta(days=d, hours=h, minutes=mi)


def hourly(layer: dict[str, Any], factor: float = 1.0) -> dict[datetime, float]:
    """UTC hour -> value (times `factor`), each run spread over the hours it covers."""
    out: dict[datetime, float] = {}
    for v in layer.get("values", []):
        if v.get("value") is None:
            continue
        start_s, dur_s = v["validTime"].split("/")
        start = datetime.fromisoformat(start_s).astimezone(timezone.utc).replace(minute=0, second=0)
        n = max(1, round(parse_duration(dur_s) / HOUR))
        for i in range(n):
            out[start + i * HOUR] = v["value"] * factor
    return out


def _factor(layer: dict[str, Any]) -> float:
    uom = layer.get("uom", "")
    if uom not in TO_KN:
        raise ValueError(f"unknown wind unit {uom!r}")
    return TO_KN[uom]


def parse(raw: bytes) -> tuple[dict[datetime, dict[str, float | None]], str | None]:
    """(UTC hour -> {"kn", "gust", "dir"}, update time) from a gridpoint response."""
    p = json.loads(raw)["properties"]
    speed = hourly(p["windSpeed"], _factor(p["windSpeed"]))
    gust = hourly(p["windGust"], _factor(p["windGust"])) if "windGust" in p else {}
    direction = hourly(p["windDirection"]) if "windDirection" in p else {}
    hours = {t: {"kn": kn, "gust": gust.get(t), "dir": direction.get(t)} for t, kn in speed.items()}
    updated = p.get("updateTime")
    if updated:
        updated = datetime.fromisoformat(updated).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return hours, updated


class NwsSource:
    """Fetches each forecast gridpoint once per build."""

    def __init__(self, fetch: Fetcher = http_get):
        self.fetch = fetch
        self._cache: dict[str, tuple[dict[datetime, dict[str, float | None]], str | None]] = {}

    def apply(self, spot: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
        """Add `nws` to each hour of `doc` and return the doc-level `nws` block."""
        gridpoint = (spot.get("nws") or {}).get("gridpoint")
        if not gridpoint:
            return {"status": "none"}
        try:
            if gridpoint not in self._cache:
                self._cache[gridpoint] = parse(self.fetch(URL.format(gridpoint=gridpoint)))
            hours, updated = self._cache[gridpoint]
        except (FetchError, KeyError, ValueError, TypeError) as exc:
            print(f"::warning::NWS forecast for {spot['id']} not available: {exc}")
            for h in doc["hours"]:
                h["nws"] = None
            return {"status": "error", "gridpoint": gridpoint}
        n = 0
        for h in doc["hours"]:
            v = hours.get(datetime.fromisoformat(h["t"]).astimezone(timezone.utc))
            if v is None:
                h["nws"] = None
                continue
            h["nws"] = {
                "kn": round(v["kn"], 1),
                "gust": None if v["gust"] is None else round(v["gust"], 1),
                "dir": None if v["dir"] is None else round(v["dir"]) % 360,
            }
            n += 1
        print(f"{spot['id']}: NWS forecast for {n} of {len(doc['hours'])} hours ({gridpoint}, updated {updated})")
        return {"status": "ok" if n else "error", "gridpoint": gridpoint, "updated": updated}
