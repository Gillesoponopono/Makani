import json
import math
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
        hst = (i + START.hour - 10) % 24  # START is local midnight
        swrad = max(0.0, 800 * math.sin(math.pi * (hst - 6.6) / 11.2)) * (0.3 if 24 + 13 <= i <= 24 + 15 else 1)
        rows.append([t, 20.92, -156.44, u, v, 25.0, 1e-4 if i == 5 else 0.0, swrad])
    return json.dumps({"table": {
        "columnNames": ["time", "latitude", "longitude", "Uwind", "Vwind", "Tair", "rain", "swrad"],
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


def wave_table(n_hours: int, cols: list[str], values: list[float]) -> bytes:
    rows = [[(START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"), 0, 20.9, 203.55, *values]
            for i in range(n_hours)]
    return json.dumps({"table": {"columnNames": ["time", "depth", "latitude", "longitude", *cols],
                                 "rows": rows}}).encode()


def roms_table(n_hours: int) -> bytes:
    """Sea temperature every 3 h from 3 h before the start, warming 0.1 °C per step."""
    rows = [[(START + timedelta(hours=3 * i - 3)).strftime("%Y-%m-%dT%H:%M:%SZ"), 0.25, 20.931, -156.444,
             25.5 + 0.1 * i] for i in range(n_hours // 3 + 2)]
    return json.dumps({"table": {"columnNames": ["time", "depth", "latitude", "longitude", "temp"],
                                 "rows": rows}}).encode()


def tide_json(url: str) -> bytes:
    """Highs and lows every ~6 h 12 min, or an hourly curve, over the requested days."""
    q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
    d0 = datetime.strptime(q["begin_date"], "%Y%m%d")
    d1 = datetime.strptime(q["end_date"], "%Y%m%d") + timedelta(days=1)
    preds, t, high = [], d0, True
    step = timedelta(hours=1) if q["interval"] == "h" else timedelta(hours=6, minutes=12)
    while t < d1:
        p = {"t": t.strftime("%Y-%m-%d %H:%M"), "v": "2.1" if high else "0.3"}
        if q["interval"] == "hilo":
            p["type"] = "H" if high else "L"
        preds.append(p)
        t, high = t + step, not high
    return json.dumps({"predictions": preds}).encode()


def nws_json(down: bool = False) -> bytes:
    """18.52 km/h (10 kn) for the first 12 hours, then 37.04 km/h (20 kn); gusts on the first run only."""
    t0 = START.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    t1 = (START + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return json.dumps({"properties": {
        "updateTime": "2026-11-13T21:05:00+00:00",
        "windSpeed": {"uom": "wmoUnit:km_h-1", "values": [{"validTime": f"{t0}/PT12H", "value": 18.52},
                                                           {"validTime": f"{t1}/P1DT6H", "value": 37.04}]},
        "windGust": {"uom": "wmoUnit:km_h-1", "values": [{"validTime": f"{t0}/PT12H", "value": 27.78}]},
        "windDirection": {"uom": "wmoUnit:degree_(angle)", "values": [{"validTime": f"{t0}/P2D", "value": 70}]},
    }}).encode()


class FakeFetch:
    def __init__(self, end="2026-11-18T00:00:00Z", n_hours=98, tides_down=False, nws_down=False,
                 latest="20261111", **kw):
        self.end, self.n_hours, self.kw, self.urls = end, n_hours, kw, []
        self.tides_down, self.nws_down, self.latest = tides_down, nws_down, latest

    def __call__(self, url):
        self.urls.append(url)
        if "tidesandcurrents" in url:
            if self.tides_down:
                raise build_mod.FetchError("NOAA down")
            return tide_json(url)
        if url.endswith("/latest.xml"):
            if self.latest is None:
                raise build_mod.FetchError("THREDDS down")
            return f'<dataset urlPath="wrf_mo/files/2026/wrf_mo_{self.latest}.nc"/>'.encode()
        if "api.weather.gov" in url:
            if self.nws_down:
                raise build_mod.FetchError("HTTP 500 for api.weather.gov")
            return nws_json()
        if "/swan_maui." in url:
            return wave_table(self.n_hours, ["shgt", "pper", "pdir"], [1.2, 14.7, 345])
        if "/ww3_hawaii." in url:
            return wave_table(self.n_hours, ["whgt", "wper", "wdir", "shgt", "sper", "sdir"],
                              [1.5, 6.9, 61, 1.3, 14.9, 340])
        if "/roms_hiig." in url:
            return roms_table(self.n_hours)
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
    assert [s["id"] for s in meta["spots"]] == ["kanaha", "sprecks", "harbor", "hookipa", "maui-sunset", "keawakapu"]
    # Query starts at local midnight (10:00Z).
    assert "2026-11-13T10:00:00Z" in fetch.urls[2]  # after the info request and the latest-run catalog

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


def test_build_adds_waves_water_and_tides(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["schemaVersion"] == 6
    assert meta["water"] == {"dataset": "roms_hiig", "spots": {s: "ok" for s in
                             ["kanaha", "sprecks", "harbor", "hookipa", "maui-sunset", "keawakapu"]}}
    assert meta["tides"]["stations"] == {"1615202": "ok", "1615680": "ok"}
    assert meta["waves"]["spots"]["harbor"] == "sheltered"

    kanaha = json.loads((tmp_path / "spots" / "kanaha.json").read_text())
    w = kanaha["hours"][0]["wave"]
    assert (w["m"], w["per"], w["dir"], w["type"]) == (1.2, 14.7, 345, "mixed")
    assert kanaha["waves"]["status"] == "ok"
    # Midnight sits 3 h after the first ROMS step (25.5) at the second one (25.6); 1 AM is a third of the way on.
    assert [h["waterC"] for h in kanaha["hours"][:2]] == [25.6, 25.6]
    assert kanaha["hours"][3]["waterC"] == 25.7
    assert kanaha["water"]["status"] == "ok"
    tide = kanaha["tide"]
    assert tide["station"] == "1615680" and tide["kind"] == "harmonic"
    assert tide["curve"]["start"] == "2026-11-13T00:00:00-10:00"
    assert len(tide["curve"]["ft"]) == 5 * 24 + 1   # 98 hours from midnight span 5 local days
    assert {e["type"] for e in tide["extremes"]} == {"H", "L"}

    sunset = json.loads((tmp_path / "spots" / "maui-sunset.json").read_text())
    assert sunset["tide"]["station"] == "1615202" and sunset["tide"]["kind"] == "subordinate"
    assert sunset["hours"][0]["wave"]["chop"] is None   # trade-wind chop heads out to sea there
    assert sunset["hours"][0]["wave"]["type"] == "swell"

    harbor = json.loads((tmp_path / "spots" / "harbor.json").read_text())
    assert harbor["waves"] == {"status": "sheltered"}
    assert harbor["hours"][0]["wave"] is None


def test_tides_down_keeps_the_published_tides_and_still_publishes(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    before = json.loads((tmp_path / "spots" / "kanaha.json").read_text())["tide"]
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(end="2026-11-19T00:00:00Z", tides_down=True))
    after = json.loads((tmp_path / "spots" / "kanaha.json").read_text())
    assert after["tide"] == before
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["wrf"]["coverageEnd"] == "2026-11-19T00:00:00Z"
    assert meta["tides"]["stations"]["1615680"] == "kept"


def test_unchanged_run_is_skipped_and_force_rebuilds(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    fetch = FakeFetch()
    assert build_mod.build(tmp_path, now=NOW, fetch=fetch) is False
    assert len(fetch.urls) == 2  # only the info request and the latest-run catalog
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(), force=True) is True
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(end="2026-11-19T00:00:00Z")) is True


def test_unchanged_run_is_refreshed_every_refresh_hours(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    fetch = FakeFetch()
    assert build_mod.build(tmp_path, now=NOW + timedelta(hours=5), fetch=fetch, refresh_hours=6) is False
    assert len(fetch.urls) == 2  # only the info request and the latest-run catalog
    later = NOW + timedelta(hours=6)
    assert build_mod.build(tmp_path, now=later, fetch=FakeFetch(), refresh_hours=6) is True
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["generatedAt"] == later.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert meta["wrf"]["coverageEnd"] == "2026-11-18T00:00:00Z"


def test_meta_records_the_model_run(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["wrf"]["run"] == "2026-11-11T00:00:00Z"


def test_a_new_run_still_arriving_triggers_a_rebuild(tmp_path):
    # Coverage end only moves once the new run passes the previous one's end; the
    # latest-file catalog names it as soon as its first hours are up.
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(latest="20261113")) is True
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta["wrf"]["run"] == "2026-11-13T00:00:00Z"
    assert meta["wrf"]["coverageEnd"] == "2026-11-18T00:00:00Z"


def test_latest_catalog_down_keeps_the_known_run(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(latest="20261113"))
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(latest=None)) is False  # no flip back
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(latest=None), force=True)
    assert json.loads((tmp_path / "meta.json").read_text())["wrf"]["run"] == "2026-11-13T00:00:00Z"
    # a new coverage end without the catalog: coverage end - 168 h
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(end="2026-11-21T00:00:00Z", latest=None))
    assert json.loads((tmp_path / "meta.json").read_text())["wrf"]["run"] == "2026-11-14T00:00:00Z"


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



def test_build_adds_the_sky(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    hours = json.loads((tmp_path / "spots" / "kanaha.json").read_text())["hours"]
    by_t = {h["t"][:13]: h for h in hours}
    assert by_t["2026-11-13T12"]["sky"] == "sun" and by_t["2026-11-13T12"]["sun"] > 0.8
    assert by_t["2026-11-14T14"]["sky"] == "cloud"           # the fake model's cloudy afternoon
    assert by_t["2026-11-13T05"]["sky"] == "rain"            # 0.36 mm/h before dawn
    assert by_t["2026-11-13T22"]["sky"] is None              # night
    assert by_t["2026-11-13T07"]["sky"] is not None          # low sun: borrowed from a later hour


def test_build_adds_the_nws_forecast(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    doc = json.loads((tmp_path / "spots" / "kanaha.json").read_text())
    assert doc["nws"] == {"status": "ok", "gridpoint": "HFO/213,126", "updated": "2026-11-13T21:05:00Z"}
    by_t = {h["t"][:13]: h for h in doc["hours"]}
    assert by_t["2026-11-13T00"]["nws"] == {"kn": 10.0, "gust": 15.0, "dir": 70}
    assert by_t["2026-11-13T12"]["nws"] == {"kn": 20.0, "gust": None, "dir": 70}
    assert by_t["2026-11-15T12"]["nws"] is None              # past the NWS runs
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert set(meta["nws"]["spots"].values()) == {"ok"}


def test_nws_outage_never_blocks_the_wind(tmp_path):
    assert build_mod.build(tmp_path, now=NOW, fetch=FakeFetch(nws_down=True)) is True
    doc = json.loads((tmp_path / "spots" / "kanaha.json").read_text())
    assert doc["nws"]["status"] == "error"
    assert all(h["nws"] is None for h in doc["hours"])


def test_build_adds_the_adjusted_wind_where_calibrated(tmp_path):
    build_mod.build(tmp_path, now=NOW, fetch=FakeFetch())
    kanaha = json.loads((tmp_path / "spots" / "kanaha.json").read_text())
    assert kanaha["adjusted"]["reference"].startswith("mean of the Kahului Harbor")
    h = kanaha["hours"][14]
    assert 0 < h["wrf"]["knAdj"] < h["wrf"]["kn"]          # the model reads high near Kahului
    hookipa = json.loads((tmp_path / "spots" / "hookipa.json").read_text())
    assert hookipa["adjusted"]["transferredFrom"] == "sprecks"     # no anemometer: Sprecks' correction
    assert hookipa["adjusted"]["maeAdj"] is None and hookipa["hours"][14]["wrf"]["knAdj"] > 0
    sunset = json.loads((tmp_path / "spots" / "maui-sunset.json").read_text())
    assert sunset["adjusted"]["reference"].startswith("Kealia Pond")
