from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from makani import tides

FIXTURES = Path(__file__).parent / "fixtures"
HST = timezone(timedelta(hours=-10), "HST")
BEGIN, END = date(2026, 11, 13), date(2026, 11, 14)


def recorded(url: str) -> bytes:
    station = "1615202" if "station=1615202" in url else "1615680"
    interval = "hilo" if "interval=hilo" in url else "h"
    return (FIXTURES / f"tide_{station}_{interval}.json").read_bytes()


def test_url_asks_for_feet_above_mllw_in_local_time():
    url = tides.predictions_url("1615680", BEGIN, END, "hilo")
    assert url.startswith("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?")
    for part in ("product=predictions", "station=1615680", "begin_date=20261113", "end_date=20261114",
                 "datum=MLLW", "units=english", "time_zone=lst", "interval=hilo"):
        assert part in url


def test_parse_highs_and_lows():
    rows = tides.parse_predictions(recorded("station=1615680&interval=hilo"), HST)
    assert rows[4] == (datetime(2026, 11, 13, 5, 10, tzinfo=HST), 2.309, "H")
    assert {k for _, _, k in rows} == {"H", "L"}


def test_noaa_error_message_raises():
    with pytest.raises(tides.TideError, match="No Predictions"):
        tides.parse_predictions(b'{"error": {"message": "No Predictions data was found."}}', HST)
    with pytest.raises(tides.TideError):
        tides.parse_predictions(b"<html>502</html>", HST)


def test_harmonic_station_uses_the_hourly_curve():
    block = tides.station_block({"id": "1615680", "name": "Kahului Harbor", "kind": "harmonic"},
                                BEGIN, END, HST, recorded)
    assert block["curve"]["start"] == "2026-11-13T00:00:00-10:00"
    ft = block["curve"]["ft"]
    assert len(ft) == 2 * 24 + 1           # two days, both midnights included
    assert ft[0] == pytest.approx(0.59, abs=0.01)
    assert ft[5] == pytest.approx(2.31, abs=0.01)  # the 5:10 AM high
    assert all(v is not None for v in ft)
    # Marks from the day before to the day after, for "next tide" at the edges.
    assert block["extremes"][0]["t"].startswith("2026-11-12")
    assert block["extremes"][-1]["t"].startswith("2026-11-15")
    assert block["extremes"][4] == {"t": "2026-11-13T05:10:00-10:00", "ft": 2.31, "type": "H"}


def test_subordinate_station_gets_a_cosine_curve_through_its_highs_and_lows():
    block = tides.station_block({"id": "1615202", "name": "Makena", "kind": "subordinate"},
                                BEGIN, END, HST, recorded)
    ft = block["curve"]["ft"]
    assert len(ft) == 49 and all(v is not None for v in ft)
    # Between the 1:38 PM low (0.637) and the 3:40 PM high (0.88).
    assert 0.637 <= ft[14] <= 0.88
    # Never beyond the extremes it interpolates.
    assert max(ft) <= 1.791 and min(ft) >= -0.045


def test_cosine_value_hits_the_extremes_and_the_midpoint():
    t0 = datetime(2026, 11, 13, 0, tzinfo=HST)
    ext = [(t0, 0.0, "L"), (t0 + timedelta(hours=6), 2.0, "H")]
    assert tides.cosine_value(ext, t0) == pytest.approx(0.0)
    assert tides.cosine_value(ext, t0 + timedelta(hours=3)) == pytest.approx(1.0)
    assert tides.cosine_value(ext, t0 + timedelta(hours=6)) == pytest.approx(2.0)
    assert tides.cosine_value(ext, t0 + timedelta(hours=7)) is None


def test_failures_become_none():
    def down(url):
        raise tides.FetchError("timeout")
    out = tides.fetch_blocks([{"id": "1615680", "kind": "harmonic"}], {"1615680"}, BEGIN, END, HST, down)
    assert out == {"1615680": None}
