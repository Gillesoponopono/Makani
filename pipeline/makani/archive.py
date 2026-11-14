"""Forecast archive: keep every WRF run as it was issued.

The ERDDAP "best" time series replaces past hours with the newest run's
analysis, so a forecast that was shown two days ago can't be fetched again
later. To compare "what we forecast" with "what happened", each run is saved
here the moment it's first published.

Layout (under the data dir, published on the `data` branch):
    archive/forecast/<run>.json     one small file per run, all spots
    archive/obs/<station>/<YYYY-MM>.json   hourly observations (see obs.py)
    archive/index.json              what's available, for the site
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json_atomic

ARCHIVE_DIR = "archive"


def run_id(coverage_end: str) -> str:
    """'2026-11-18T00:00:00Z' -> '2026-11-18T00Z' (one WRF run per coverage end)."""
    return coverage_end[:13] + "Z"


def forecast_record(meta: dict[str, Any], docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact per-run record: hourly wind (kn, 1 decimal) and direction per spot.

    `fetchedAt` is when we first saw the run. Hours before it were already past
    (analysis), hours after it were genuine forecasts; lead time = t - fetchedAt.
    """
    return {
        "run": run_id(meta["wrf"]["coverageEnd"]),
        "coverageEnd": meta["wrf"]["coverageEnd"],
        "fetchedAt": meta["generatedAt"],
        "start": docs[0]["hours"][0]["t"],
        "hours": len(docs[0]["hours"]),
        "spots": {
            d["id"]: {
                "kn": [h["wrf"]["kn"] for h in d["hours"]],
                "dir": [h["wrf"]["dir"] for h in d["hours"]],
            }
            for d in docs
        },
    }


def save_forecast(out_dir: Path, meta: dict[str, Any], docs: list[dict[str, Any]]) -> Path:
    """Write the run's record. A run is archived once: re-fetches of the same run
    (e.g. --force) keep the original fetchedAt so lead times stay honest."""
    rec = forecast_record(meta, docs)
    path = out_dir / ARCHIVE_DIR / "forecast" / f"{rec['run']}.json"
    existing = read_json(path)
    if existing and existing.get("fetchedAt"):
        rec["fetchedAt"] = existing["fetchedAt"]
    write_json_atomic(path, rec)
    return path


def write_index(out_dir: Path, obs_status: dict[str, Any] | None = None,
                now: datetime | None = None) -> dict[str, Any]:
    """Rebuild archive/index.json from what's on disk.

    obs_status (from obs.update_obs) is merged into the previous status so a
    station that wasn't fetched this time keeps its last known state.
    """
    root = out_dir / ARCHIVE_DIR
    runs = []
    for p in sorted((root / "forecast").glob("*.json")):
        rec = read_json(p)
        if rec:
            runs.append({"run": rec["run"], "fetchedAt": rec["fetchedAt"],
                         "start": rec["start"], "hours": rec["hours"]})
    obs: dict[str, list[str]] = {}
    for station_dir in sorted((root / "obs").glob("*")):
        if station_dir.is_dir():
            obs[station_dir.name] = sorted(p.stem for p in station_dir.glob("*.json"))
    status = (read_json(root / "index.json") or {}).get("obsStatus", {})
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for sid, st in (obs_status or {}).items():
        prev = status.get(sid, {})
        status[sid] = {**st, "checkedAt": stamp,
                       "lastOkAt": stamp if st.get("status") == "ok" else prev.get("lastOkAt")}
    index = {"forecastRuns": runs, "obs": obs, "obsStatus": status}
    write_json_atomic(root / "index.json", index)
    return index


def count_files(out_dir: Path) -> int:
    root = out_dir / ARCHIVE_DIR
    return sum(1 for p in root.rglob("*.json") if p.name != "index.json") if root.exists() else 0

