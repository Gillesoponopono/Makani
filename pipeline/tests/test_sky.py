from datetime import datetime, timedelta, timezone

import pytest

from makani import sky
from makani.sun import cos_zenith

HST = timezone(timedelta(hours=-10))
KANAHA = (20.899, -156.447)


def test_sun_height_at_kanaha_mid_november():
    # Solar noon ~12:10 HST; declination ~ -18.3°, so the zenith is ~39° there.
    noon = cos_zenith(datetime(2026, 11, 14, 12, 10, tzinfo=HST), *KANAHA)
    assert noon == pytest.approx(0.776, abs=0.01)
    assert cos_zenith(datetime(2026, 11, 14, 0, 0, tzinfo=HST), *KANAHA) < 0
    assert cos_zenith(datetime(2026, 11, 14, 9, 0, tzinfo=HST), *KANAHA) < noon


def test_categories():
    cz = 0.776
    clear = sky.clear_sky_wm2(cz)
    assert 760 < clear < 820                      # WRF gave 820 W/m² at noon on a clear day
    assert sky.hour_sky(820, 0.0, cz) == ("sun", pytest.approx(1.04, abs=0.03))
    assert sky.hour_sky(0.6 * clear, 0.0, cz)[0] == "partly"
    assert sky.hour_sky(0.3 * clear, 0.0, cz)[0] == "cloud"
    assert sky.hour_sky(0.3 * clear, 1.2, cz)[0] == "rain"
    assert sky.hour_sky(None, 0.5, -0.3) == ("rain", None)  # rain at night
    assert sky.hour_sky(0.0, 0.0, -0.3) == (None, None)     # plain night
    assert sky.hour_sky(40, 0.0, 0.05) == (None, None)      # sun too low to judge


def test_low_sun_hours_borrow_the_nearest_judged_hour():
    hours = [
        {"t": "2026-11-14T06:00:00-10:00", "daylight": False, "sky": None, "sun": None},
        {"t": "2026-11-14T07:00:00-10:00", "daylight": True, "sky": None, "sun": None},
        {"t": "2026-11-14T08:00:00-10:00", "daylight": True, "sky": "rain", "sun": 0.62},
        {"t": "2026-11-14T09:00:00-10:00", "daylight": True, "sky": "sun", "sun": 0.95},
    ]
    sky.fill_low_sun(hours)
    assert hours[0]["sky"] is None
    assert hours[1]["sky"] == "partly"   # from 8 AM's sunshine, not its rain
