"""Sunrise/sunset from the NOAA solar position equations (accurate to ~1 min)."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone


def _julian_day(d: date) -> float:
    return d.toordinal() + 1721424.5


def sun_times(d: date, lat: float, lon: float) -> tuple[datetime, datetime]:
    """Return (sunrise, sunset) as aware UTC datetimes for the given date and place.

    lon is degrees east (negative for Hawaii). Uses the official zenith 90.833°.
    """
    jd = _julian_day(d) + 0.5  # noon UTC
    t = (jd - 2451545.0) / 36525.0

    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t)
         + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))

    y = math.tan(math.radians(eps / 2)) ** 2
    l0r = math.radians(l0)
    eq_time = 4 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr)
    )  # minutes

    latr, declr = math.radians(lat), math.radians(decl)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(latr) * math.cos(declr))
              - math.tan(latr) * math.tan(declr))
    ha = math.degrees(math.acos(max(-1.0, min(1.0, cos_ha))))

    solar_noon = 720 - 4 * lon - eq_time  # minutes after 00:00 UTC
    midnight = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return (midnight + timedelta(minutes=solar_noon - 4 * ha),
            midnight + timedelta(minutes=solar_noon + 4 * ha))
