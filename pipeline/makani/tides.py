"""Tide predictions from NOAA CO-OPS (free, no key), in feet above MLLW.

Per station (config `tideStations`):
- `interval=hilo` gives the high and low tide times and heights (the H/L marks);
- `interval=h` gives an hourly curve, but only for harmonic stations. Subordinate
  stations (Makena) only have high/low times, offset from a reference station,
  so their curve is a cosine fit between consecutive highs and lows, the usual
  way to sketch a tide between its extremes.

Times come in local standard time (`time_zone=lst`); Hawaii has no DST.
Predictions are deterministic, so when NOAA is unreachable the build keeps the
previously published block.

Published block, per spot (`tide` in spots/{id}.json):
    {"station", "name", "kind", "datum": "MLLW", "units": "ft",
     "curve": {"start": "<local midnight ISO>", "stepMinutes": 60, "ft": [...]},
     "extremes": [{"t": "<ISO>", "ft": 2.31, "type": "H"}, ...]}
"""

from __future__ import annotations

import json
import math
import urllib.parse
from datetime import date, datetime, timedelta, tzinfo
from typing import Any

from .net import FetchError, Fetcher, http_get

COOPS_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


class TideError(FetchError):
    pass


def predictions_url(station: str, begin: date, end: date, interval: str) -> str:
    q = urllib.parse.urlencode({
        "product": "predictions",
        "station": station,
        "begin_date": begin.strftime("%Y%m%d"),
        "end_date": end.strftime("%Y%m%d"),
        "datum": "MLLW",
        "units": "english",
        "time_zone": "lst",
        "interval": interval,
        "format": "json",
        "application": "Makani",
    })
    return f"{COOPS_URL}?{q}"


def parse_predictions(raw: bytes, tz: tzinfo) -> list[tuple[datetime, float, str | None]]:
    """(local time, feet, "H"/"L"/None) rows; NOAA reports errors as JSON with HTTP 200."""
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        raise TideError(f"non-JSON tide response: {raw[:200]!r}") from exc
    if "error" in doc:
        raise TideError(f"NOAA tides: {doc['error'].get('message', doc['error'])}")
    out = []
    for p in doc.get("predictions", []):
        t = datetime.strptime(p["t"], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        out.append((t, float(p["v"]), p.get("type")))
    if not out:
        raise TideError("NOAA tides: empty prediction list")
    return out


def cosine_value(extremes: list[tuple[datetime, float, str | None]], t: datetime) -> float | None:
    """Tide height at t by cosine interpolation between the surrounding extremes."""
    for (t0, h0, _), (t1, h1, _) in zip(extremes, extremes[1:]):
        if t0 <= t <= t1:
            f = (1 - math.cos(math.pi * (t - t0) / (t1 - t0))) / 2
            return h0 + (h1 - h0) * f
    return None


def station_block(station: dict[str, Any], begin: date, end: date, tz: tzinfo,
                  fetch: Fetcher = http_get) -> dict[str, Any]:
    """Curve from local midnight of `begin` to midnight after `end`, with the
    highs and lows from the day before to the day after (for "next tide")."""
    sid = station["id"]
    extremes = parse_predictions(fetch(predictions_url(sid, begin - timedelta(days=1),
                                                       end + timedelta(days=1), "hilo")), tz)
    extremes = [e for e in extremes if e[2] in ("H", "L")]
    start = datetime(begin.year, begin.month, begin.day, tzinfo=tz)
    n = ((end - begin).days + 1) * 24 + 1
    times = [start + timedelta(hours=i) for i in range(n)]

    if station.get("kind") == "harmonic":
        hourly = parse_predictions(fetch(predictions_url(sid, begin, end + timedelta(days=1), "h")), tz)
        by_time = {t: v for t, v, _ in hourly}
        values = [by_time.get(t) for t in times]
    else:
        values = [cosine_value(extremes, t) for t in times]

    return {
        "station": sid,
        "name": station.get("name", sid),
        "kind": station.get("kind", "harmonic"),
        "datum": "MLLW",
        "units": "ft",
        "curve": {"start": start.isoformat(), "stepMinutes": 60,
                  "ft": [None if v is None else round(v, 2) for v in values]},
        "extremes": [{"t": t.isoformat(), "ft": round(v, 2), "type": k} for t, v, k in extremes],
    }


def fetch_blocks(stations: list[dict[str, Any]], wanted: set[str], begin: date, end: date,
                 tz: tzinfo, fetch: Fetcher = http_get) -> dict[str, dict[str, Any] | None]:
    """One block per wanted station id; None (with a warning) when it can't be fetched."""
    by_id = {s["id"]: s for s in stations}
    out: dict[str, dict[str, Any] | None] = {}
    for sid in sorted(wanted):
        station = by_id.get(sid, {"id": sid, "kind": "harmonic"})
        try:
            out[sid] = station_block(station, begin, end, tz, fetch)
            print(f"tides {sid}: {len(out[sid]['extremes'])} highs/lows")
        except (FetchError, KeyError, ValueError) as exc:
            out[sid] = None
            print(f"::warning::tides for {sid} not updated: {exc}")
    return out
