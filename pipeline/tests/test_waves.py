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
