"""Unit conversions, wind direction, sector and sport-band classification.

This module is the single implementation of rating logic: the site only
displays what it computes, and alerts (M5) will reuse it.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

MS_TO_KN = 1.943844

SECTOR_PRIORITY = ("danger", "good", "ok")  # anything else is "poor"


def ms_to_kn(ms: float) -> float:
    return ms * MS_TO_KN


def display_kn(kn: float) -> int:
    """Whole knots exactly as the site shows them (JS Math.round of the 1-decimal value).

    Ratings use this so a row reading "10" never says "too light". Python's round()
    is banker's rounding, hence floor(x + 0.5).
    """
    return math.floor(round(kn, 1) + 0.5)


def uv_to_speed_dir(u: float, v: float) -> tuple[float, int]:
    """Return (speed m/s, meteorological 'from' direction in whole degrees 0-359)."""
    speed = math.hypot(u, v)
    direction = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
    deg = int(round(direction)) % 360
    return speed, deg


def in_range(deg: float, start: float, end: float) -> bool:
    """Half-open [start, end) on the compass; wraps when start > end (e.g. 340->30)."""
    deg %= 360
    if start <= end:
        return start <= deg < end
    return deg >= start or deg < end


def classify_sector(deg: float, sectors: dict[str, Sequence[Sequence[float]]]) -> str:
    for name in SECTOR_PRIORITY:
        for start, end in sectors.get(name, []):
            if in_range(deg, start, end):
                return name
    return "poor"


def sports_for(kn: float, sector: str, ratings: dict[str, Any]) -> list[str]:
    """Sport ids whose band contains kn. Bands are [min, max); max None = open-ended.

    Only good/ok directions get sports; danger and poor get none.
    """
    if sector not in ("good", "ok"):
        return []
    out = []
    for band in ratings["sports"]:
        lo, hi = band["minKn"], band["maxKn"]
        if kn >= lo and (hi is None or kn < hi):
            out.append(band["id"])
    return out


def compass(deg: float) -> str:
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((deg % 360) / 22.5 + 0.5) % 16]
