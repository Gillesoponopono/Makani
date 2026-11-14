"""Observed wind archive: what the wind actually did.

Sources (both free, no key):
- NOAA CO-OPS Kahului Harbor (1615680): waterfront anemometer, 6-minute data,
  years of history (31-day limit per request). Speeds in knots with units=english.
- NWS Kahului Airport (PHOG) via api.weather.gov: ASOS, ~hourly at :54. The API
  only keeps ~7 days, so every run re-reads the full 7-day window. Wind is read
  from the raw METAR text (the parsed fields are often null until QC runs).

Samples are binned to the hour they're centred on ([H-30 min, H+30 min)), which
matches WRF's instantaneous hourly values: wind = mean, gust = max, direction =
speed-weighted vector mean. Stored per station and HST month:

    archive/obs/<station>/<YYYY-MM>.json
    {"station", "source", "month", "hours": {"2026-11-13T14": {"kn", "gust", "dir", "n"}}}
"""

from __future__ import annotations

import json
import math
import re
import urllib.parse
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, NamedTuple

from .jsonio import read_json, write_json_atomic
from .net import FetchError, Fetcher, http_get

NWS_BASE = "https://api.weather.gov"
COOPS_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NWS_MAX_DAYS = 7
COOPS_CHUNK_DAYS = 30  # API limit is 31 days for 6-minute products

UNIT_TO_KN = {
    "wmoUnit:km_h-1": 1 / 1.852,
    "wmoUnit:m_s-1": 1.943844,
    "wmoUnit:kn": 1.0,
}


class Sample(NamedTuple):
    t: datetime  # aware, UTC
    kn: float | None
    gust: float | None
    dir: float | None


# ---------------------------------------------------------------- parsing

def nws_url(station: str, start: datetime, end: datetime) -> str:
    q = urllib.parse.urlencode({"start": _iso(start), "end": _iso(end), "limit": 500})
    return f"{NWS_BASE}/stations/{urllib.parse.quote(station)}/observations?{q}"


# METAR surface wind group, e.g. "05020G32KT" (050° true, 20 kt, gusts 32), "VRB03KT", "00000KT".
METAR_WIND = re.compile(r"\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT\b")


def parse_metar_wind(raw_message: str) -> tuple[float, float | None, float | None] | None:
    """(kn, gust, dir) from the METAR wind group, or None if there isn't one.

    The NWS API's parsed windSpeed is often null for hours until QC runs (checked
    2026-11-13: 32 of 40 recent PHOG obs), while the raw METAR always has the wind,
    already in knots. So the raw text is the primary source.
    """
    m = METAR_WIND.search(raw_message or "")
    if not m:
        return None
    kn = float(m.group(2))
    gust = float(m.group(3)) if m.group(3) else None
    direction = None if m.group(1) == "VRB" or kn == 0 else float(m.group(1))
    return kn, gust, direction


def parse_nws(raw: bytes) -> list[Sample]:
    doc = json.loads(raw)
    out = []
    for feat in doc.get("features", []):
        p = feat["properties"]
        t = datetime.fromisoformat(p["timestamp"]).astimezone(timezone.utc)
        metar = parse_metar_wind(p.get("rawMessage") or "")
        if metar:
            out.append(Sample(t, *metar))
            continue

        def value(key: str, speed: bool) -> float | None:
            v = p.get(key) or {}
            if v.get("value") is None or v.get("qualityControl") == "X":  # X = rejected by QC
                return None
            if not speed:
                return float(v["value"])
            factor = UNIT_TO_KN.get(v.get("unitCode", ""))
            if factor is None:
                raise FetchError(f"unexpected NWS unit {v.get('unitCode')!r} for {key}")
            return float(v["value"]) * factor

        out.append(Sample(t, value("windSpeed", True), value("windGust", True),
                          value("windDirection", False)))
    return out


def coops_urls(station: str, start: datetime, end: datetime) -> list[str]:
    """One URL per <=30-day chunk (the 6-minute wind product is capped at 31 days)."""
    urls = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=COOPS_CHUNK_DAYS), end)
        q = urllib.parse.urlencode({
            "product": "wind", "station": station,
            "begin_date": chunk_start.strftime("%Y%m%d %H:%M"),
            "end_date": chunk_end.strftime("%Y%m%d %H:%M"),
            "units": "english", "time_zone": "gmt", "format": "json",
            "application": "Makani",
        })
        urls.append(f"{COOPS_URL}?{q}")
        chunk_start = chunk_end
    return urls


def _num(s: Any) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_coops(raw: bytes) -> list[Sample]:
    doc = json.loads(raw)
    if "error" in doc:
        msg = str(doc["error"].get("message", ""))
        if "no data" in msg.lower():
            return []  # station outage for that range
        raise FetchError(f"CO-OPS error: {msg.strip()}")
    out = []
    for row in doc.get("data", []):
        # f = "X,R" flags: max-exceeded, rate-of-change exceeded. Drop flagged samples.
        if "1" in str(row.get("f", "")).split(","):
            continue
        t = datetime.strptime(row["t"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        out.append(Sample(t, _num(row.get("s")), _num(row.get("g")), _num(row.get("d"))))
    return out


# ---------------------------------------------------------------- binning

def hour_key(t: datetime, tz: tzinfo) -> str:
    """Centred hourly bin in local time: 13:30 <= t < 14:30 -> '...T14'."""
    centred = (t + timedelta(minutes=30)).astimezone(tz)
    return centred.strftime("%Y-%m-%dT%H")


def aggregate(samples: list[Sample], tz: tzinfo) -> dict[str, dict[str, Any]]:
    bins: dict[str, list[Sample]] = {}
    for s in samples:
        if s.kn is not None:
            bins.setdefault(hour_key(s.t, tz), []).append(s)
    out = {}
    for key, ss in sorted(bins.items()):
        kn = sum(s.kn for s in ss) / len(ss)  # type: ignore[misc]
        gusts = [s.gust for s in ss if s.gust is not None]
        u = sum(s.kn * math.sin(math.radians(s.dir)) for s in ss if s.dir is not None)  # type: ignore[operator]
        v = sum(s.kn * math.cos(math.radians(s.dir)) for s in ss if s.dir is not None)  # type: ignore[operator]
        direction = None if (u == 0 and v == 0) else int(round(math.degrees(math.atan2(u, v)))) % 360
        out[key] = {
            "kn": round(kn, 1),
            "gust": round(max(gusts), 1) if gusts else None,
            "dir": direction,
            "n": len(ss),
        }
    return out


def merge(station_dir: Path, station: dict[str, Any], records: dict[str, dict[str, Any]]) -> int:
    """Merge hourly records into monthly files. Returns how many hours were added or updated.

    A stored hour is replaced only by a record built from at least as many samples,
    so a partial bin at the edge of a fetch window never overwrites a complete one,
    while late QC fills and corrections still get in.
    """
    by_month: dict[str, dict[str, dict[str, Any]]] = {}
    for key, rec in records.items():
        by_month.setdefault(key[:7], {})[key] = rec
    updated = 0
    for month, recs in sorted(by_month.items()):
        path = station_dir / f"{month}.json"
        doc = read_json(path) or {"station": station["id"], "source": station["source"],
                                  "month": month, "hours": {}}
        hours = doc["hours"]
        n_before = updated
        for key, rec in recs.items():
            old = hours.get(key)
            if old is None or (rec["n"] >= old["n"] and rec != old):
                hours[key] = rec
                updated += 1
        if updated > n_before:
            doc["hours"] = dict(sorted(hours.items()))
            write_json_atomic(path, doc)
    return updated


# ---------------------------------------------------------------- driver

def fetch_samples(station: dict[str, Any], start: datetime, end: datetime,
                  fetch: Fetcher = http_get) -> list[Sample]:
    if station["source"] == "nws":
        start = max(start, end - timedelta(days=NWS_MAX_DAYS))
        return parse_nws(fetch(nws_url(station["id"], start, end)))
    if station["source"] == "coops":
        samples: list[Sample] = []
        for url in coops_urls(station["id"], start, end):
            samples.extend(parse_coops(fetch(url)))
        return samples
    raise ValueError(f"unknown observation source {station['source']!r}")


def update_obs(out_dir: Path, stations: list[dict[str, Any]], tz: tzinfo, now: datetime,
               days: float = NWS_MAX_DAYS, fetch: Fetcher = http_get) -> dict[str, dict[str, Any]]:
    """Fetch the last `days` of observations for each station and merge them into the archive.

    One station failing never stops the others (or the forecast); the error is
    reported in the returned status.
    """
    status: dict[str, dict[str, Any]] = {}
    start = now - timedelta(days=days)
    for st in stations:
        try:
            samples = fetch_samples(st, start, now, fetch)
            records = aggregate(samples, tz)
            updated = merge(out_dir / "archive" / "obs" / st["id"], st, records)
            status[st["id"]] = {"status": "ok", "samples": len(samples), "hours": len(records),
                                "updated": updated}
            print(f"obs {st['id']}: {len(samples)} samples -> {len(records)} hours, {updated} new/updated")
        except (FetchError, ValueError, KeyError) as exc:
            status[st["id"]] = {"status": "error", "error": str(exc)[:300]}
            print(f"::warning::observations {st['id']} failed: {exc}")
    return status


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
