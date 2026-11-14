"""Archive used to compare forecasts with what actually happened.

Layout (under the data dir, published on the `data` branch):
    archive/forecast/<run>.json            every WRF run as issued (see thredds.py)
    archive/obs/<station>/<YYYY-MM>.json   hourly observed wind (see obs.py)
    archive/index.json                     what's available + source status, for the site
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json_atomic

ARCHIVE_DIR = "archive"


def migrate_legacy(out_dir: Path) -> int:
    """Remove forecast records in the M1 format (named by ERDDAP coverage end,
    no `init`), superseded by THREDDS runs named by init time. Returns files removed."""
    removed = 0
    for p in (out_dir / ARCHIVE_DIR / "forecast").glob("*.json"):
        rec = read_json(p)
        if not rec or "init" not in rec:
            p.unlink()
            removed += 1
    return removed


def _stamp(now: datetime | None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_index(out_dir: Path, obs_status: dict[str, Any] | None = None,
                forecast_status: dict[str, Any] | None = None,
                now: datetime | None = None) -> dict[str, Any]:
    """Rebuild archive/index.json from what's on disk.

    Status passed in is merged over the previous index, so a source that wasn't
    checked this time keeps its last known state.
    """
    root = out_dir / ARCHIVE_DIR
    prev = read_json(root / "index.json") or {}
    stamp = _stamp(now)

    runs = []
    for p in sorted((root / "forecast").glob("*.json")):
        rec = read_json(p)
        if rec and "init" in rec:
            runs.append({"run": rec["run"], "init": rec["init"], "start": rec["start"],
                         "hours": rec["hours"]})
    obs: dict[str, list[str]] = {}
    for station_dir in sorted((root / "obs").glob("*")):
        if station_dir.is_dir():
            obs[station_dir.name] = sorted(p.stem for p in station_dir.glob("*.json"))

    obs_st = prev.get("obsStatus", {})
    for sid, st in (obs_status or {}).items():
        obs_st[sid] = {**st, "checkedAt": stamp,
                       "lastOkAt": stamp if st.get("status") == "ok" else obs_st.get(sid, {}).get("lastOkAt")}
    fc_st = prev.get("forecastStatus")
    if forecast_status is not None:
        fc_st = {**forecast_status, "checkedAt": stamp,
                 "lastOkAt": stamp if forecast_status.get("status") == "ok" else (fc_st or {}).get("lastOkAt")}

    index = {"forecastRuns": runs, "obs": obs, "obsStatus": obs_st, "forecastStatus": fc_st}
    write_json_atomic(root / "index.json", index)
    return index


def obs_checked_hours_ago(out_dir: Path, now: datetime) -> float | None:
    """Hours since the stations were last checked (the oldest station counts)."""
    st = (read_json(out_dir / ARCHIVE_DIR / "index.json") or {}).get("obsStatus", {})
    stamps = [v.get("checkedAt") for v in st.values() if v.get("checkedAt")]
    if not stamps:
        return None
    oldest = min(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) for s in stamps)
    return (now - oldest).total_seconds() / 3600


def count_files(out_dir: Path) -> int:
    root = out_dir / ARCHIVE_DIR
    return sum(1 for p in root.rglob("*.json") if p.name != "index.json") if root.exists() else 0
