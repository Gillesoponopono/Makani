import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from makani import thredds
from makani.config import load_spots
from makani.net import FetchError

FIXTURES = Path(__file__).parent / "fixtures"
HST = timezone(timedelta(hours=-10))
SPOTS = load_spots()["spots"]


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def csv_for(init, hours=range(6, 169), u=-9.0, v=-3.0, nan_at=()):
    lines = ['time,latitude[unit="degrees_north"],longitude[unit="degrees_east"],'
             'Uwind[unit="meter second-1"],Vwind[unit="meter second-1"]']
    for h in hours:
        t = (init + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
        uu = "NaN" if h in nan_at else u
        lines.append(f"{t},20.92,-156.44,{uu},{v}")
    return ("\n".join(lines) + "\n").encode()


def catalog_for(inits):
    body = "".join(
        f'<dataset name="{thredds.RUN_PREFIX}{i:%Y-%m-%dT%H:%M:%SZ}" '
        f'urlPath="wrf_mo/runs/{thredds.RUN_PREFIX}{i:%Y-%m-%dT%H:%M:%SZ}"></dataset>' for i in inits)
    return f"<catalog>{body}</catalog>".encode()


class FakeThredds:
    """Serves a catalog of runs; `hours` maps init -> range of lead hours available."""

    def __init__(self, hours, fail=()):
        self.hours, self.fail, self.urls = hours, set(fail), []

    def __call__(self, url):
        self.urls.append(url)
        if url == thredds.CATALOG_URL:
            return catalog_for(sorted(self.hours))
        for init, rng in self.hours.items():
            if f"RUN_{init:%Y-%m-%dT%H:%M:%SZ}" in url:
                if init in self.fail:
                    raise FetchError("boom")
                return csv_for(init, rng)
        raise AssertionError(url)


# ---------------------------------------------------------------- parsing

def test_list_runs_from_recorded_catalog():
    raw = (FIXTURES / "thredds_runs_catalog.xml").read_bytes()
    runs = thredds.list_runs(lambda url: raw)
    assert runs == sorted(runs)
    assert runs[0] == utc(2010, 5, 14) and runs[-1] == utc(2026, 11, 12)
    assert len(runs) == 4


def test_point_url():
    url = thredds.point_url(utc(2025, 11, 10), 20.92, -156.44)
    assert url == ("https://pae-paha.pacioos.hawaii.edu/thredds/ncss/grid/wrf_mo/runs/"
                   "WRF_Maui-Oahu_Regional_Atmospheric_Model_RUN_2025-11-10T00:00:00Z"
                   "?var=Uwind&var=Vwind&latitude=20.92&longitude=-156.44&temporal=all&accept=csv")


def test_parse_recorded_point_csv():
    rows = thredds.parse_point_csv((FIXTURES / "ncss_point.csv").read_bytes())
    assert rows[0][0] == utc(2026, 11, 10, 6)
    assert rows[0][1] == pytest.approx(-8.935519218444824)
    assert len(rows) == 7


def test_parse_point_csv_rejects_error_pages_and_handles_nan():
    with pytest.raises(FetchError):
        thredds.parse_point_csv(b"<html>Error 400: no such dataset</html>")
    rows = thredds.parse_point_csv(csv_for(utc(2026, 1, 1), range(6, 8), nan_at={7}))
    assert rows[1][1] is None


# ---------------------------------------------------------------- records

def test_build_record_shared_axis_and_gaps():
    init = utc(2026, 11, 10)
    series = {
        "kanaha": thredds.parse_point_csv(csv_for(init, range(6, 10), nan_at={8})),
        "sprecks": thredds.parse_point_csv(csv_for(init, [6, 9])),  # missing 7, 8
    }
    rec = thredds.build_record(init, series, HST)
    assert rec["run"] == "2026-11-10T00Z" and rec["init"] == "2026-11-10T00:00:00Z"
    assert rec["start"] == "2026-11-09T20:00:00-10:00"
    assert rec["hours"] == 4
    assert rec["spots"]["kanaha"]["kn"][2] is None
    assert rec["spots"]["sprecks"]["kn"][1:3] == [None, None]
    assert rec["spots"]["kanaha"]["kn"][0] == pytest.approx(18.4, abs=0.1)
    assert 70 <= rec["spots"]["kanaha"]["dir"][0] <= 73


def test_is_complete():
    init = utc(2026, 11, 12)
    assert thredds.is_complete(init, init + timedelta(hours=168), init + timedelta(days=1))
    assert not thredds.is_complete(init, init + timedelta(hours=72), init + timedelta(days=2))
    assert thredds.is_complete(init, init + timedelta(hours=72), init + timedelta(days=3))  # gave up


# ---------------------------------------------------------------- archive pass

def test_archives_complete_runs_waits_for_partial_and_never_refetches(tmp_path):
    now = utc(2026, 11, 14, 1)
    runs = {
        utc(2026, 11, 1): range(6, 169),     # older than the window
        utc(2026, 11, 10): range(6, 169),
        utc(2026, 11, 11): range(6, 169),
        utc(2026, 11, 12): range(6, 73),     # still landing
    }
    fetch = FakeThredds(runs)
    st = thredds.update_forecast_archive(tmp_path, SPOTS, HST, now, days=10, fetch=fetch, pause=0)
    assert st["added"] == 2 and st["errors"] == 0
    assert st["pending"] == ["2026-11-12T00Z (67 h so far)"]
    files = sorted(p.name for p in (tmp_path / "archive" / "forecast").iterdir())
    assert files == ["2026-11-10T00Z.json", "2026-11-11T00Z.json"]
    rec = json.loads((tmp_path / "archive" / "forecast" / "2026-11-11T00Z.json").read_text())
    assert rec["hours"] == 163 and set(rec["spots"]) == {"kanaha", "sprecks", "harbor", "maui-sunset", "keawakapu"}
    assert len(fetch.urls) == 1 + 3 * len(SPOTS)  # catalog + 3 runs x every spot

    # Next pass: archived runs aren't fetched again; the partial one is retried.
    fetch2 = FakeThredds({**runs, utc(2026, 11, 12): range(6, 169)})
    st = thredds.update_forecast_archive(tmp_path, SPOTS, HST, now, days=10, fetch=fetch2, pause=0)
    assert st["added"] == 1
    assert len(fetch2.urls) == 1 + len(SPOTS)


def test_errors_are_isolated_and_a_failing_server_stops_the_pass(tmp_path):
    now = utc(2026, 11, 14)
    good = {utc(2026, 11, d): range(6, 169) for d in range(1, 13)}
    st = thredds.update_forecast_archive(tmp_path, SPOTS, HST, now, days=20,
                                         fetch=FakeThredds(good, fail={utc(2026, 11, 3)}), pause=0)
    assert st["added"] == 11 and st["errors"] == 1 and st["status"] == "partial"

    many_fail = set(good)
    st = thredds.update_forecast_archive(tmp_path / "x", SPOTS, HST, now, days=20,
                                         fetch=FakeThredds(good, fail=many_fail), pause=0)
    assert st["added"] == 0 and st["errors"] == thredds.MAX_CONSECUTIVE_ERRORS
