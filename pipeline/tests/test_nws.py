import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from makani import nws
from makani.net import FetchError

RAW = (Path(__file__).parent / "fixtures" / "nws_gridpoint.json").read_bytes()
SPOT = {"id": "kanaha", "nws": {"gridpoint": "HFO/213,126"}}


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def doc_from(first_utc, n):
    hst = timezone(timedelta(hours=-10))
    return {"hours": [{"t": (first_utc + timedelta(hours=i)).astimezone(hst).isoformat()} for i in range(n)]}


@pytest.mark.parametrize("s, hours", [("PT1H", 1), ("PT15H", 15), ("P1D", 24), ("P1DT6H", 30), ("P8DT6H", 198)])
def test_parse_duration(s, hours):
    assert nws.parse_duration(s) == timedelta(hours=hours)


def test_parse_duration_rejects_garbage():
    with pytest.raises(ValueError):
        nws.parse_duration("P")


def test_runs_are_spread_over_their_hours_in_knots():
    hours, updated = nws.parse(RAW)
    assert updated == "2026-11-17T17:37:08Z"
    assert hours[utc(2026, 11, 17, 11)]["kn"] == pytest.approx(12.0)      # 22.224 km/h, PT1H
    assert hours[utc(2026, 11, 17, 12)]["kn"] == pytest.approx(11.0)      # 20.372 km/h, PT15H
    assert hours[utc(2026, 11, 18, 2)]["kn"] == pytest.approx(11.0)       # last hour of that run
    assert hours[utc(2026, 11, 18, 3)]["kn"] == pytest.approx(12.0)       # next run
    assert hours[utc(2026, 11, 17, 12)]["gust"] == pytest.approx(15.0)    # 27.78 km/h
    assert hours[utc(2026, 11, 17, 20)]["dir"] == 80 and hours[utc(2026, 11, 17, 21)]["dir"] == 70


def test_unknown_unit_is_refused():
    p = json.loads(RAW)
    p["properties"]["windSpeed"]["uom"] = "wmoUnit:furlong"
    with pytest.raises(ValueError):
        nws.parse(json.dumps(p).encode())


def test_apply_fills_the_hours_it_covers():
    calls = []

    def fetch(url):
        calls.append(url)
        return RAW

    src = nws.NwsSource(fetch)
    doc = doc_from(utc(2026, 11, 17, 9), 5)                 # 9Z, 10Z: before the NWS series
    block = src.apply(SPOT, doc)
    assert block == {"status": "ok", "gridpoint": "HFO/213,126", "updated": "2026-11-17T17:37:08Z"}
    assert [h["nws"] and h["nws"]["kn"] for h in doc["hours"]] == [None, None, 12.0, 11.0, 11.0]
    assert doc["hours"][3]["nws"] == {"kn": 11.0, "gust": 15.0, "dir": 80}
    src.apply(SPOT, doc_from(utc(2026, 11, 17, 9), 2))      # same gridpoint: fetched once
    assert calls == ["https://api.weather.gov/gridpoints/HFO/213,126"]


def test_apply_survives_an_outage():
    def fetch(url):
        raise FetchError("HTTP 503")

    doc = doc_from(utc(2026, 11, 17, 11), 3)
    assert nws.NwsSource(fetch).apply(SPOT, doc) == {"status": "error", "gridpoint": "HFO/213,126"}
    assert all(h["nws"] is None for h in doc["hours"])


def test_spot_without_gridpoint():
    assert nws.NwsSource(lambda u: RAW).apply({"id": "x"}, doc_from(utc(2026, 11, 17, 11), 1)) == {"status": "none"}
