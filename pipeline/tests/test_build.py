import json
from datetime import datetime, timedelta, timezone

import pytest

from makani import build as build_mod
from makani.validate import ValidationError

NOW = datetime(2026, 11, 14, 0, 30, tzinfo=timezone.utc)  # 2026-11-13 14:30 HST
START = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)  # 2026-11-13 00:00 HST


def info_csv(end: str) -> bytes:
    return f"Row Type,Variable Name,Attribute Name,Data Type,Value\nattribute,NC_GLOBAL,time_coverage_end,String,{end}\n".encode()


def table(n_hours: int, u: float = -9.5, v: float = -3.5) -> bytes:
    rows = []
    for i in range(n_hours):
        t = (START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append([t, 20.92, -156.44, u, v, 25.0, 1e-4 if i == 5 else 0.0])
    return json.dumps({"table": {
        "columnNames": ["time", "latitude", "longitude", "Uwind", "Vwind", "Tair", "rain"],
        "rows": rows}}).encode()


def box_table(n_hours: int, u: float = -9.5, v: float = -3.5) -> bytes:
    """Stride-2 Maui box: 17 lats x 20 lons, like the real map query."""
    lats = [round(20.506 + 0.036 * i, 3) for i in range(17)]
    lons = [round(-156.72 + 0.04 * j, 2) for j in range(20)]
    rows = []
    for i in range(n_hours):
        t = (START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows += [[t, la, lo, u, v] for la in lats for lo in lons]
    return json.dumps({"table": {"columnNames": ["time", "latitude", "longitude", "Uwind", "Vwind"],
                                 "rows": rows}}).encode()


class FakeFetch:
    def __init__(self, end="2026-11-18T00:00:00Z", n_hours=98, **kw):
        self.end, self.n_hours, self.kw, self.urls = end, n_hours, kw, []

    def __call__(self, url):
        self.urls.append(url)
        if "/info/" in url:
            return info_csv(self.end)
        if ":2:" in url:  # stride-2 box = map query
            return box_table(self.n_hours, **self.kw)
        return table(self.n_hours, **self.kw)


def test_build_writes_spots_and_meta(tmp_path):
    fetch = FakeFetch()
    assert build_mod.build(tmp_path, now=NOW, fetch=fetch) is True

    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["wrf"]["coverageEnd"] == "2026-11-18T00:00:00Z"
    assert meta["wrf"]["hours"] == 98
    assert [s["id"] for s in meta["spots"]] == ["kanaha", "sprecks", "maui-sunset"]
    # Query starts at local midnight (10:00Z).
    assert "2026-11-13T10:00:00Z" in fetch.urls[1]

    kanaha = json.loads((tmp_path / "spots" / "kanaha.json").read_text())
    h0 = kanaha["hours"][0]
    assert h0["t"] == "2026-11-13T00:00:00-10:00"
    assert h0["wrf"]["kn"] == pytest.approx(19.7, abs=0.1)
    assert 65 <= h0["wrf"]["dir"] <= 75
    assert h0["wrf"]["gustEst"] == pytest.approx(h0["wrf"]["kn"] * 1.3, abs=0.1)
    assert h0["sector"] == "good"
    # 19.7 kn is shown as "20", and foil/wing is [10, 20), so it drops out.
    assert h0["sports"] == ["directional", "twintip"]
    assert h0["daylight"] is False                     # midnight
    assert kanaha["hours"][12]["daylight"] is True     # noon
    assert kanaha["hours"][5]["wrf"]["rainMmH"] == pytest.approx(0.36)
    assert kanaha["sun"][0]["date"] == "2026-11-13"

    frames = json.loads((tmp_path / "map" / "frames.json").read_text())
    assert (len(frames["lats"]), len(frames["lons"])) == (17, 20)
    assert len(frames["times"]) == len(frames["kn10"]) == 98
    assert frames["times"][0] == "2026-11-13T00:00:00-10:00"
    assert frames["kn10"][0][0] == round(h0["wrf"]["kn"] * 10)
    assert frames["daylight"][0] is False and frames["daylight"][12] is True
    assert meta["map"] == {"file": "map/frames.json", "hours": 98, "grid": [17, 20]}

    # ENE trades are offshore at Kihei: no sports, danger sector.
    sunset = json.loads((tmp_path / "spots" / "maui-sunset.json").read_text())
    assert sunset["hours"][0]["sector"] == "danger"
    assert sunset["hours"][0]["sports"] == []


def test_unchanged_run_is_skipped_and_force_rebuilds(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    fetch = FakeFetch()
    assert build_mod.build(tmp_path, now=NOW, fetch=fetch) is False
    assert len(fetch.urls) == 1  # only the info request
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(), force=True) is True
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(end="2026-11-19T00:00:00Z")) is True


def test_bad_data_publishes_nothing(tmp_path):
    with pytest.raises(ValidationError):
        build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(n_hours=10))
    assert not (tmp_path / "meta.json").exists()


def test_failed_rebuild_keeps_previous_files(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    before = (tmp_path / "meta.json").read_text()
    with pytest.raises(ValidationError):
        build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(end="2026-11-19T00:00:00Z", n_hours=3))
    assert (tmp_path / "meta.json").read_text() == before


def test_missing_values_are_skipped():
    spot = {"id": "x", "name": "X", "beach": {"lat": 20.9, "lon": -156.4},
            "sectors": {"good": [[0, 360]]}}
    rows = [
        {"time": "2026-11-13T10:00:00Z", "latitude": 20.9, "longitude": -156.4,
         "Uwind": None, "Vwind": None, "Tair": None, "rain": None},
        {"time": "2026-11-13T11:00:00Z", "latitude": 20.9, "longitude": -156.4,
         "Uwind": -5.0, "Vwind": 0.0, "Tair": None, "rain": None},
    ]
    ratings = {"gustFactor": 1.3, "sports": []}
    doc = build_mod.build_spot(spot, rows, ratings, timezone(timedelta(hours=-10)))
    assert len(doc["hours"]) == 1
    assert doc["hours"][0]["wrf"]["tairC"] is None
    assert doc["hours"][0]["wrf"]["rainMmH"] is None

