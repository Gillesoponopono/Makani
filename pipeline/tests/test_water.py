from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from makani import water

FIXTURES = Path(__file__).parent / "fixtures"
HST = timezone(timedelta(hours=-10))


def recorded(url: str) -> bytes:
    return (FIXTURES / "roms_point.json").read_bytes()


def test_series_asks_roms_for_the_top_level_from_3_hours_earlier():
    urls = []
    def fetch(url):
        urls.append(url)
        return recorded(url)
    pts, cell = water.series({"lat": 20.931, "lon": -156.444}, "2026-11-14T12:00:00Z", fetch)
    assert "/griddap/roms_hiig.json?temp" in urls[0]
    assert "%5B(2026-11-14T09:00:00Z):1:(last)%5D%5B(0.25)%5D%5B(20.931):1:(20.931)%5D%5B(-156.444)" in urls[0]
    assert cell == {"lat": pytest.approx(20.9312, abs=1e-4), "lon": pytest.approx(-156.4437, abs=1e-4)}
    assert len(pts) == 5 and pts[0][1] == pytest.approx(25.63, abs=0.01)


def test_value_at_interpolates_between_steps():
    t0 = datetime(2026, 11, 14, 0, tzinfo=timezone.utc)
    pts = [(t0, 25.0), (t0 + timedelta(hours=3), 25.3), (t0 + timedelta(hours=9), 26.0)]
    assert water.value_at(pts, t0) == 25.0
    assert water.value_at(pts, t0 + timedelta(hours=1)) == pytest.approx(25.1)
    assert water.value_at(pts, t0 + timedelta(hours=3)) == pytest.approx(25.3)
    assert water.value_at(pts, t0 + timedelta(hours=5)) is None    # across a 6 h gap
    assert water.value_at(pts, t0 + timedelta(hours=9)) == 26.0
    assert water.value_at(pts, t0 - timedelta(hours=1)) is None
    assert water.value_at([], t0) is None


def test_apply_fills_hours_and_shares_cells():
    urls = []
    def fetch(url):
        urls.append(url)
        return recorded(url)
    src = water.WaterSource("2026-11-14T12:00:00Z", fetch)
    doc = {"hours": [{"t": "2026-11-13T23:00:00-10:00"}, {"t": "2026-11-14T03:00:00-10:00"},
                     {"t": "2026-11-15T03:00:00-10:00"}]}
    spot = {"id": "kanaha", "water": {"lat": 20.931, "lon": -156.444}}
    block = src.apply(spot, doc)
    assert block["status"] == "ok" and block["cell"]["lat"] == pytest.approx(20.931, abs=1e-3)
    # 09Z is a model step; 13Z is a third of the way from 12Z to 15Z; the next day is past the fixture.
    assert [h["waterC"] for h in doc["hours"]] == [25.6, 25.6, None]
    src.apply({**spot, "id": "kanaha2"}, {"hours": []})
    assert len(urls) == 1
    assert src.apply({"id": "x"}, {"hours": []}) == {"status": "none"}


def test_masked_cells_and_failures_give_no_values():
    land = b'{"table": {"columnNames": ["time","depth","latitude","longitude","temp"], "rows": [' \
           b'["2026-11-14T09:00:00Z", 0.25, 20.9, -156.4, null], ["2026-11-14T12:00:00Z", 0.25, 20.9, -156.4, null]]}}'
    doc = {"hours": [{"t": "2026-11-14T00:00:00-10:00"}]}
    spot = {"id": "inland", "water": {"lat": 20.9, "lon": -156.4}}
    assert water.WaterSource("2026-11-14T12:00:00Z", lambda u: land).apply(spot, doc)["status"] == "error"
    assert doc["hours"][0]["waterC"] is None

    def down(url):
        raise water.FetchError("Proxy Error")
    assert water.WaterSource("2026-11-14T12:00:00Z", down).apply(spot, doc) == {"status": "error"}
