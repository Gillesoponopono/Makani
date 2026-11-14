from datetime import date, datetime, timedelta, timezone

from makani.sun import sun_times

HST = timezone(timedelta(hours=-10))
KAHULUI = (20.899, -156.447)


def _minutes(dt: datetime) -> int:
    local = dt.astimezone(HST)
    return local.hour * 60 + local.minute


def test_kahului_mid_november():
    # Hand-derived reference (decl -18.0°, EoT +15.8 min, zenith 90.833°): rise 06:35, set 17:45 HST.
    rise, sset = sun_times(date(2026, 11, 13), *KAHULUI)
    assert rise.astimezone(HST).date() == date(2026, 11, 13)
    assert sset.astimezone(HST).date() == date(2026, 11, 13)
    assert abs(_minutes(rise) - (6 * 60 + 35)) <= 3
    assert abs(_minutes(sset) - (17 * 60 + 45)) <= 3


def test_kahului_june_solstice():
    # Hand-derived reference (decl +23.44°, EoT -1.8 min): rise 05:46, set 19:10 HST.
    rise, sset = sun_times(date(2026, 6, 21), *KAHULUI)
    assert abs(_minutes(rise) - (5 * 60 + 46)) <= 3
    assert abs(_minutes(sset) - (19 * 60 + 10)) <= 3
