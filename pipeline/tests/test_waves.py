import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from makani import waves

FIXTURES = Path(__file__).parent / "fixtures"
NORTH = {"good": [[30, 100]], "ok": [[0, 30], [100, 130]], "danger": [[150, 270]]}
KIHEI = {"good": [[340, 30]], "ok": [[300, 340], [30, 50]], "danger": [[50, 160]]}


def recorded(url: str) -> bytes:
    return (FIXTURES / ("swan_point.json" if "/swan_maui." in url else "ww3_point.json")).read_bytes()


def test_series_queries_0_360_longitudes_with_a_depth_axis():
    urls = []
    def fetch(url):
        urls.append(url)
        return recorded(url)
    by_hour, cell = waves.series(waves.SWAN, {"lat": 20.905, "lon": -156.445}, "2026-11-15T00:00:00Z",
                                 waves.SWAN_VARS, fetch)
    assert "/griddap/swan_maui.json?" in urls[0]
    assert "%5B(0)%5D%5B(20.905):1:(20.905)%5D%5B(203.555):1:(203.555)%5D" in urls[0]
    assert cell == {"lat": pytest.approx(20.905, abs=1e-4), "lon": -156.445}
    assert set(by_hour) == {f"2026-11-15T0{i}" for i in range(6)}


def test_hour_wave_from_recorded_kanaha_data():
    swan, _ = waves.series(waves.SWAN, {"lat": 20.905, "lon": -156.445}, "x", waves.SWAN_VARS, recorded)
    ww3, _ = waves.series(waves.WW3, {"lat": 20.95, "lon": -156.45}, "x", waves.WW3_VARS, recorded)
    w = waves.hour_wave(swan["2026-11-15T00"], ww3["2026-11-15T00"], NORTH)
    assert w["m"] == pytest.approx(1.18, abs=0.01)
    assert w["per"] == pytest.approx(14.7, abs=0.1)
    assert w["dir"] == 345
    # Offshore: ~1.5 m of 7 s trade-wind chop and ~1.2 m of 14 s NNW swell.
    assert w["chop"]["per"] < 8 and w["swell"]["per"] > 13
    assert w["type"] == "mixed"


def test_types():
    swell = {"m": 1.2, "per": 15.0, "dir": 340}
    chop = {"m": 1.5, "per": 7.0, "dir": 60}
    small = {"m": 0.3, "per": 6.0, "dir": 60}
    assert waves.wave_type(0.2, swell, chop, 15) == "flat"
    assert waves.wave_type(1.0, swell, small, 15) == "swell"
    assert waves.wave_type(1.0, small, chop, 7) == "chop"
    assert waves.wave_type(1.0, swell, chop, 15) == "mixed"
    assert waves.wave_type(1.0, None, None, 14) == "swell"   # no WW3: SWAN's peak period
    assert waves.wave_type(1.0, None, None, 6) == "chop"


def test_chop_blowing_out_to_sea_is_ignored():
    swan = {"shgt": 0.5, "pper": 15.7, "pdir": 205}
    ww3 = {"whgt": 0.6, "wper": 3.1, "wdir": 100, "shgt": 0.2, "sper": 11.6, "sdir": 179}
    w = waves.hour_wave(swan, ww3, KIHEI)   # ENE trades are offshore at Kihei
    assert w["chop"] is None
    assert w["type"] == "swell"
    assert waves.hour_wave(swan, ww3, NORTH)["type"] == "chop"


def test_masked_cells_give_no_wave():
    assert waves.hour_wave({"shgt": None, "pper": None, "pdir": None}, None, NORTH) is None
    assert waves.hour_wave({"shgt": 0.0, "pper": 0.0, "pdir": 0.0}, None, NORTH) is None
    assert waves.hour_wave(None, None, NORTH) is None


def test_apply_fills_hours_and_shares_cells():
    urls = []
    def fetch(url):
        urls.append(url)
        return recorded(url)
    src = waves.WaveSource("2026-11-15T00:00:00Z", fetch)
    def doc():
        return {"hours": [{"t": "2026-11-14T14:00:00-10:00"}, {"t": "2026-11-14T15:00:00-10:00"},
                          {"t": "2026-11-15T09:00:00-10:00"}]}
    spot = {"id": "kanaha", "sectors": NORTH,
            "waves": {"swan": {"lat": 20.905, "lon": -156.445}, "ww3": {"lat": 20.95, "lon": -156.45}}}
    d1 = doc()
    block = src.apply(spot, d1)
    assert block["status"] == "ok"
    assert d1["hours"][0]["wave"]["type"] == "mixed"
    assert d1["hours"][2]["wave"] is None          # beyond the recorded hours
    src.apply({**spot, "id": "kanaha2"}, doc())
    assert len(urls) == 2                          # one SWAN + one WW3 request in all

    harbor = doc()
    assert src.apply({"id": "harbor", "sectors": NORTH, "waves": {"sheltered": True}}, harbor) == {"status": "sheltered"}
    assert harbor["hours"][0]["wave"] is None


def test_apply_survives_a_failed_fetch():
    def down(url):
        raise waves.FetchError("Proxy Error")
    d = {"hours": [{"t": "2026-11-14T14:00:00-10:00"}]}
    spot = {"id": "kanaha", "sectors": NORTH, "waves": {"swan": {"lat": 20.905, "lon": -156.445}}}
    assert waves.WaveSource("x", down).apply(spot, d) == {"status": "error"}
    assert d["hours"][0]["wave"] is None


def swan_table(heights: dict[str, float]) -> bytes:
    """An ERDDAP SWAN point table: UTC hour "2026-11-18T05" -> height (m)."""
    rows = [[f"{k}:00:00Z", 0, 20.904999, 203.55501, m, 9.0, 30.0] for k, m in sorted(heights.items())]
    return json.dumps({"table": {"columnNames": ["time", "depth", "latitude", "longitude", "shgt", "pper", "pdir"],
                                 "rows": rows}}).encode()


def test_heights_under_a_centimetre_are_noise():
    # Real values from the 18 Nov 2026 cold start at Kanahā.
    assert waves.hour_wave({"shgt": 2.8646468e-07, "pper": 2.9993868, "pdir": 15}, None, NORTH) is None
    assert waves.hour_wave({"shgt": 0.0018078685, "pper": 3.66, "pdir": 15}, None, NORTH) is None
    assert waves.hour_wave({"shgt": 0.023159375, "pper": 3.66, "pdir": 15}, None, NORTH)["m"] == 0.02
    assert waves._part(0.004, 8.0, 40) is None


def test_restart_is_a_collapse_within_one_hour():
    assert waves.restart({"2026-11-18T05": {"shgt": 1.18}, "2026-11-18T06": {"shgt": 2.9e-07},
                          "2026-11-18T07": {"shgt": 0.002}}) == datetime(2026, 11, 18, 6, tzinfo=timezone.utc)
    # A calm sea that stays calm, or falls gradually, is not a restart.
    assert waves.restart({"2026-11-18T05": {"shgt": 0.05}, "2026-11-18T06": {"shgt": 0.005}}) is None
    assert waves.restart({"2026-11-18T05": {"shgt": 0.4}, "2026-11-18T06": {"shgt": 0.3}}) is None
    assert waves.restart({"2026-11-18T05": {"shgt": None}, "2026-11-18T06": {"shgt": 0.0}}) is None


def test_cold_start_blanks_the_spin_up_and_is_seen_from_before_the_window():
    restart = datetime(2026, 11, 18, 6, tzinfo=timezone.utc)
    heights = {}
    for i in range(-30, 130):
        t = restart + timedelta(hours=i)
        heights[t.strftime("%Y-%m-%dT%H")] = 1.2 if i < 0 else 0.005 * (i + 1)
    urls = []
    def fetch(url):
        urls.append(url)
        return swan_table(heights)
    # Forecast starts a day after the restart: the query reaches 96 h further back.
    src = waves.WaveSource("2026-11-19T10:00:00Z", fetch)
    hours = [restart + timedelta(hours=i) for i in (28, 95, 96, 100)]
    doc = {"hours": [{"t": t.isoformat()} for t in hours]}
    spot = {"id": "kanaha", "sectors": NORTH, "waves": {"swan": {"lat": 20.905, "lon": -156.445}}}
    block = src.apply(spot, doc)
    assert "(2026-11-15T10:00:00Z)" in urls[0]
    assert [h["wave"] is None for h in doc["hours"]] == [True, True, False, False]
    assert block["status"] == "ok"
    assert block["restart"] == "2026-11-18T06:00:00Z"
    assert block["blankUntil"] == "2026-11-22T06:00:00Z"
