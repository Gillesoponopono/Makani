"""Sky per hour from the WRF model: sunny, partly cloudy, cloudy or rain.

WRF gives the solar radiation reaching the ground (`swrad`, W/m², instantaneous
at the hour) and the rain rate. In daylight, the share of a clear sky's sunshine
that gets through (`sun`, swrad over the Haurwitz clear-sky radiation for the
sun's height) tells how cloudy it is:
- `sun` >= 0.8: "sun", 0.5-0.8: "partly", below 0.5: "cloud";
- rain >= 0.25 mm/h: "rain", day or night.
With the sun under ~12° the ratio is unreliable: those daylight hours take the
nearest reliable hour's sky. Night hours without rain get no sky.

Each hour gets `"sky": "sun" | "partly" | "cloud" | "rain" | null` and
`"sun": 0.97 | null`.
"""

from __future__ import annotations

import math
from typing import Any

SUNNY = 0.8
PARTLY = 0.5
RAIN_MM_H = 0.25
MIN_COS_Z = 0.2  # sun ~11.5° up
SKIES = ("sun", "partly", "cloud", "rain")


def clear_sky_wm2(cos_z: float) -> float:
    """Haurwitz (1945) global horizontal irradiance under a clear sky."""
    return 1098.0 * cos_z * math.exp(-0.057 / cos_z) if cos_z > 0 else 0.0


def hour_sky(swrad: float | None, rain_mm_h: float | None, cos_z: float) -> tuple[str | None, float | None]:
    raining = rain_mm_h is not None and rain_mm_h >= RAIN_MM_H
    sun = None
    if swrad is not None and cos_z >= MIN_COS_Z:
        sun = round(max(0.0, swrad) / clear_sky_wm2(cos_z), 2)
    if raining:
        return "rain", sun
    if sun is None:
        return None, None
    return ("sun" if sun >= SUNNY else "partly" if sun >= PARTLY else "cloud"), sun


def fill_low_sun(hours: list[dict[str, Any]]) -> None:
    """Daylight hours with the sun too low to judge take the nearest judged hour of the same day."""
    for i, h in enumerate(hours):
        if not h["daylight"] or h.get("sky") is not None:
            continue
        day = h["t"][:10]
        for k in range(1, 4):
            for j in (i + k, i - k):
                if 0 <= j < len(hours) and hours[j]["t"][:10] == day and hours[j].get("sun") is not None:
                    h["sky"] = hours[j]["sky"] if hours[j]["sky"] != "rain" else (
                        "sun" if hours[j]["sun"] >= SUNNY else "partly" if hours[j]["sun"] >= PARTLY else "cloud")
                    break
            if h.get("sky") is not None:
                break
