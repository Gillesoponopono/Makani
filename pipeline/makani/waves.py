"""Waves at each spot, from two PacIOOS models on the same ERDDAP server as the wind.

- SWAN Maui (`swan_maui`, ~500 m grid): the sea just off the beach, at a cell
  picked by hand per spot (config `waves.swan`): significant height `shgt` (m),
  peak period `pper` (s) and peak direction `pdir` (coming from, degrees).
- WaveWatch III Hawaii (`ww3_hawaii`, ~5 km grid): the sea offshore (config
  `waves.ww3`), split into wind waves (`whgt`, `wper`, `wdir`) and swell
  (`shgt`, `sper`, `sdir`). This is what tells chop from swell.

Both use 0-360 longitudes and a single depth level. Spots with
`waves.sheltered` (Kahului Harbor: SWAN doesn't resolve the basin) get no
numbers, just that status.

Wave type per hour:
- `flat` when the beach cell is under 0.3 m (1 ft);
- otherwise from the offshore energy split (height squared): swell share
  >= 65 % is `swell`, <= 35 % is `chop`, else `mixed`. Wind waves coming from the
  spot's offshore ("danger") sector travel out to sea, so they don't count and
  aren't shown (trade-wind chop off Kīhei never reaches the beach);
- without WW3, from SWAN's peak period: >= 10 s swell, else chop.

Cold starts: when PacIOOS restarts its wave models from rest (18 Nov 2026 at 06Z,
after an outage), heights at the beach fall to almost nothing within an hour,
then grow back over days as the swell comes in from offshore (WW3 had no swell
at all for 3 days). Those hours aren't the sea, so a drop from >= 0.1 m to under
1 cm within one hour blanks the waves from that hour for SPINUP (96 h). The
series is fetched from SPINUP before the first hour so a restart is still seen
after it has left the forecast window. Heights under 1 cm are never shown.

Each hour gets
    "wave": {"m", "per", "dir", "type",
             "swell": {"m", "per", "dir"} | null, "chop": {"m", "per", "dir"} | null}
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import erddap
from .net import FetchError, Fetcher, http_get
from .ratings import classify_sector

SWAN = "swan_maui"
WW3 = "ww3_hawaii"
SWAN_VARS = ("shgt", "pper", "pdir")
WW3_VARS = ("whgt", "wper", "wdir", "shgt", "sper", "sdir")
FLAT_M = 0.3
MIN_M = 0.01  # under 1 cm is model noise (a cold start), not a sea state
RESTART_FROM_M = 0.1
SPINUP = timedelta(hours=96)
SWELL_SHARE = 0.65
CHOP_SHARE = 0.35


def _hour_key(t: str) -> str:
    """UTC hour key, rounding ERDDAP times that are a few seconds off the hour."""
    dt = datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    dt = (dt + timedelta(minutes=30)).replace(minute=0, second=0)
    return dt.strftime("%Y-%m-%dT%H")


def _num(x: Any) -> float | None:
    if x is None or isinstance(x, str):
        return None
    x = float(x)
    return None if x != x else x  # NaN


def _part(m: Any, per: Any, d: Any) -> dict[str, Any] | None:
    m, per, d = _num(m), _num(per), _num(d)
    if m is None or m < MIN_M or per is None:
        return None
    return {"m": round(m, 2), "per": round(per, 1), "dir": None if d is None else round(d) % 360}


def series(dataset: str, cell: dict[str, float], start: str, variables: tuple[str, ...],
           fetch: Fetcher = http_get) -> tuple[dict[str, dict[str, Any]], dict[str, float]]:
    """Rows by UTC hour key for the cell nearest `cell`, plus the cell actually used."""
    rows = erddap.point_series(cell["lat"], cell["lon"] % 360, start, variables, fetch,
                               dataset=dataset, depth=0.0)
    by_hour = {_hour_key(r["time"]): r for r in rows}
    first = rows[0] if rows else {}
    lon = first.get("longitude")
    used = {"lat": first.get("latitude"), "lon": None if lon is None else round(lon - 360 if lon > 180 else lon, 3)}
    return by_hour, used


def wave_type(m: float, swell: dict[str, Any] | None, chop: dict[str, Any] | None,
              peak_period: float | None) -> str:
    if m < FLAT_M:
        return "flat"
    es = swell["m"] ** 2 if swell else 0.0
    ew = chop["m"] ** 2 if chop else 0.0
    if es + ew == 0:
        return "swell" if (peak_period or 0) >= 10 else "chop"
    share = es / (es + ew)
    if share >= SWELL_SHARE:
        return "swell"
    if share <= CHOP_SHARE:
        return "chop"
    return "mixed"


def hour_wave(swan: dict[str, Any] | None, ww3: dict[str, Any] | None,
              sectors: dict[str, Any]) -> dict[str, Any] | None:
    """The `wave` record for one hour, or None without a usable SWAN value."""
    if not swan:
        return None
    m, per, d = _num(swan.get("shgt")), _num(swan.get("pper")), _num(swan.get("pdir"))
    if m is None or m < MIN_M:
        return None
    swell = chop = None
    if ww3:
        swell = _part(ww3.get("shgt"), ww3.get("sper"), ww3.get("sdir"))
        chop = _part(ww3.get("whgt"), ww3.get("wper"), ww3.get("wdir"))
        if chop and chop["dir"] is not None and classify_sector(chop["dir"], sectors) == "danger":
            chop = None  # blown out to sea, away from this beach
    return {
        "m": round(m, 2),
        "per": None if per is None else round(per, 1),
        "dir": None if d is None else round(d) % 360,
        "type": wave_type(m, swell, chop, per),
        "swell": swell,
        "chop": chop,
    }


def _key_time(key: str) -> datetime:
    return datetime.strptime(key, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def restart(by_hour: dict[str, dict[str, Any]]) -> datetime | None:
    """The hour of the last cold start in a SWAN series: height >= 0.1 m, then under 1 cm."""
    found, prev = None, None
    for key in sorted(by_hour):
        m = _num(by_hour[key].get("shgt"))
        if m is not None:
            if prev is not None and prev >= RESTART_FROM_M and m < MIN_M:
                found = _key_time(key)
            prev = m
    return found


def _lookback(start: str) -> str:
    try:
        t = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return start
    return (t - SPINUP).strftime("%Y-%m-%dT%H:%M:%SZ")


class WaveSource:
    """Fetches each model cell once per build (several spots share a WW3 cell)."""

    def __init__(self, start: str, fetch: Fetcher = http_get):
        self.start, self.fetch = _lookback(start), fetch
        self._cache: dict[tuple[str, float, float], tuple[dict[str, dict[str, Any]], dict[str, float]]] = {}

    def get(self, dataset: str, cell: dict[str, float], variables: tuple[str, ...]):
        key = (dataset, cell["lat"], cell["lon"])
        if key not in self._cache:
            self._cache[key] = series(dataset, cell, self.start, variables, self.fetch)
        return self._cache[key]

    def apply(self, spot: dict[str, Any], doc: dict[str, Any]) -> dict[str, Any]:
        """Add `wave` to each hour of `doc` and return the doc-level `waves` block."""
        cfg = spot.get("waves") or {}
        if cfg.get("sheltered"):
            for h in doc["hours"]:
                h["wave"] = None
            return {"status": "sheltered"}
        if "swan" not in cfg:
            return {"status": "none"}
        try:
            swan, swan_cell = self.get(SWAN, cfg["swan"], SWAN_VARS)
        except (FetchError, KeyError, ValueError) as exc:
            print(f"::warning::waves for {spot['id']} not available: {exc}")
            for h in doc["hours"]:
                h["wave"] = None
            return {"status": "error"}
        ww3: dict[str, dict[str, Any]] = {}
        ww3_cell = None
        if "ww3" in cfg:
            try:
                ww3, ww3_cell = self.get(WW3, cfg["ww3"], WW3_VARS)
            except (FetchError, KeyError, ValueError) as exc:
                print(f"::warning::wave split (WW3) for {spot['id']} not available: {exc}")
        cold = restart(swan)
        blank_until = cold + SPINUP if cold else None
        if cold:
            print(f"::warning::{spot['id']}: wave model restarted at {cold:%Y-%m-%d %H}Z; "
                  f"no waves until {blank_until:%Y-%m-%d %H}Z")
        n = 0
        for h in doc["hours"]:
            t = datetime.fromisoformat(h["t"]).astimezone(timezone.utc)
            if cold and cold <= t < blank_until:
                h["wave"] = None
                continue
            key = t.strftime("%Y-%m-%dT%H")
            h["wave"] = hour_wave(swan.get(key), ww3.get(key), spot["sectors"])
            n += h["wave"] is not None
        print(f"{spot['id']}: waves for {n} of {len(doc['hours'])} hours")
        block = {"status": "ok" if n else "error", "swanCell": swan_cell, "ww3Cell": ww3_cell}
        if cold:
            block["restart"] = cold.strftime("%Y-%m-%dT%H:%M:%SZ")
            block["blankUntil"] = blank_until.strftime("%Y-%m-%dT%H:%M:%SZ")
        return block
