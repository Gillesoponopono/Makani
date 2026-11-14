"""Structural checks run before anything is published.

Never publish partial or garbage data: any failure here aborts the run and the
previously published files stay in place.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

SECTORS = {"good", "ok", "poor", "danger"}
MIN_HOURS = 24


class ValidationError(ValueError):
    pass


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def validate_spot(doc: dict[str, Any], sport_ids: set[str]) -> None:
    sid = doc.get("id", "?")
    hours = doc.get("hours")
    _check(isinstance(hours, list) and len(hours) >= MIN_HOURS,
           f"{sid}: expected >= {MIN_HOURS} hours, got {len(hours or [])}")
    prev = None
    for h in hours:
        t = datetime.fromisoformat(h["t"])
        _check(t.utcoffset() is not None, f"{sid}: naive timestamp {h['t']}")
        if prev is not None:
            _check(t - prev == timedelta(hours=1), f"{sid}: non-hourly step {prev} -> {t}")
        prev = t
        w = h["wrf"]
        _check(0 <= w["kn"] < 120, f"{sid}: implausible wind {w['kn']} kn at {h['t']}")
        _check(0 <= w["dir"] < 360, f"{sid}: bad direction {w['dir']} at {h['t']}")
        _check(w["gustEst"] >= w["kn"], f"{sid}: gust below sustained at {h['t']}")
        _check(h["sector"] in SECTORS, f"{sid}: bad sector {h['sector']}")
        _check(set(h["sports"]) <= sport_ids, f"{sid}: unknown sport in {h['sports']}")
        _check(isinstance(h["daylight"], bool), f"{sid}: daylight must be bool")
    _check(len(doc.get("sun", [])) >= 1, f"{sid}: missing sun times")


def validate_meta(meta: dict[str, Any], spot_ids: list[str]) -> None:
    _check([s["id"] for s in meta["spots"]] == spot_ids, "meta spots do not match spot files")
    _check(meta["wrf"]["status"] == "ok", "wrf status not ok")
    _check(meta["wrf"]["hours"] >= MIN_HOURS, "too few WRF hours")
