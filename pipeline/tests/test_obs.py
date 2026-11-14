import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from makani import obs
from makani.net import FetchError

FIXTURES = Path(__file__).parent / "fixtures"
HST = timezone(timedelta(hours=-10))
COOPS = {"id": "1615680", "source": "coops"}
NWS = {"id": "PHOG", "source": "nws"}


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


# ---------------------------------------------------------------- parsing

def test_parse_recorded_coops_fixture():
    samples = obs.parse_coops((FIXTURES / "coops_wind.json").read_bytes())
    assert len(samples) == 11  # 6-minute data, 10:00-11:00 inclusive
    assert samples[0] == obs.Sample(utc(2026, 11, 13, 10, 0), 12.44, 16.13, 75.0)


def test_parse_coops_no_data_is_empty_and_other_errors_raise():
    assert obs.parse_coops(b'{"error": {"message": "No data was found. This product may not be offered"}}') == []
    with pytest.raises(FetchError):
        obs.parse_coops(b'{"error": {"message": "Range Limit Exceeded"}}')


def test_parse_coops_drops_flagged_and_blank_values():
    raw = json.dumps({"data": [
        {"t": "2026-11-13 10:00", "s": "12.0", "d": "70.0", "g": "15.0", "f": "1,0"},
        {"t": "2026-11-13 10:06", "s": "", "d": "", "g": "", "f": "0,0"},
    ]}).encode()
    samples = obs.parse_coops(raw)
    assert samples == [obs.Sample(utc(2026, 11, 13, 10, 6), None, None, None)]


def test_parse_recorded_nws_fixture_reads_raw_metar():
    samples = obs.parse_nws((FIXTURES / "nws_obs.json").read_bytes())
    by_t = {s.t: s for s in samples}
    # Parsed windSpeed is null here, but the METAR says 06016G29KT.
    assert by_t[utc(2026, 11, 13, 21, 54)] == obs.Sample(utc(2026, 11, 13, 21, 54), 16.0, 29.0, 60.0)
    # Where both exist they agree: 24.12 km/h = 13.0 kn, METAR 04013G18KT.
    assert by_t[utc(2026, 11, 13, 9, 54)].kn == 13.0
    assert 24.12 / 1.852 == pytest.approx(13.0, abs=0.05)
    # No raw message: falls back to the parsed field (16.56 km/h).
    assert by_t[utc(2026, 11, 13, 15, 54)].kn == pytest.approx(16.56 / 1.852)
    # Neither: kept as an empty sample (ignored when binning).
    assert by_t[utc(2026, 11, 13, 11, 54)].kn is None
    assert sum(1 for s in samples if s.kn is not None) == 13


@pytest.mark.parametrize("raw,expected", [
    ("PHOG 132254Z 05020G32KT 10SM FEW030 RMK AO2 PK WND 05032/2210", (20.0, 32.0, 50.0)),
    ("PHOG 131354Z AUTO 05007G19KT 10SM CLR", (7.0, 19.0, 50.0)),
    ("PHOG 131054Z 02012KT 10SM", (12.0, None, 20.0)),
    ("PHOG 130554Z VRB03KT 10SM", (3.0, None, None)),
    ("PHOG 130454Z 00000KT 10SM", (0.0, None, None)),
    ("PHOG 130354Z 360105G120KT", (105.0, 120.0, 360.0)),
    ("PHOG 130254Z AUTO 10SM CLR", None),
    ("", None),
])
def test_parse_metar_wind(raw, expected):
    assert obs.parse_metar_wind(raw) == expected


def test_parse_nws_rejects_qc_x_and_unknown_units():
    feat = {"properties": {"timestamp": "2026-11-13T09:54:00+00:00", "rawMessage": "",
                           "windSpeed": {"unitCode": "wmoUnit:km_h-1", "value": 30, "qualityControl": "X"},
                           "windGust": {"unitCode": "wmoUnit:km_h-1", "value": None},
                           "windDirection": {"unitCode": "wmoUnit:degree_(angle)", "value": 60}}}
    assert obs.parse_nws(json.dumps({"features": [feat]}).encode())[0].kn is None
    feat["properties"]["windSpeed"] = {"unitCode": "wmoUnit:mph", "value": 10, "qualityControl": "V"}
    with pytest.raises(FetchError):
        obs.parse_nws(json.dumps({"features": [feat]}).encode())


def test_coops_requests_are_chunked_under_31_days():
    urls = obs.coops_urls("1615680", utc(2026, 1, 1), utc(2026, 3, 15))
    assert len(urls) == 3
    ranges = []
    for u in urls:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
        b = datetime.strptime(q["begin_date"][0], "%Y%m%d %H:%M")
        e = datetime.strptime(q["end_date"][0], "%Y%m%d %H:%M")
        assert e - b <= timedelta(days=31)
        assert q["units"] == ["english"] and q["time_zone"] == ["gmt"]
        ranges.append((b, e))
    assert ranges[0][0] == datetime(2026, 1, 1) and ranges[-1][1] == datetime(2026, 3, 15)
    assert all(ranges[i][1] == ranges[i + 1][0] for i in range(len(ranges) - 1))


def test_nws_window_is_capped_at_7_days():
    seen = []
    obs.fetch_samples(NWS, utc(2025, 1, 1), utc(2026, 11, 13, 12), lambda u: seen.append(u) or b'{"features": []}')
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)
    assert q["start"] == ["2026-11-06T12:00:00Z"]


# ---------------------------------------------------------------- binning

def test_hour_bins_are_centred_and_local():
    # 23:54Z is 13:54 HST -> belongs to the 14:00 HST hour; 00:29Z -> still 14:00
    assert obs.hour_key(utc(2026, 11, 13, 23, 54), HST) == "2026-11-13T14"
    assert obs.hour_key(utc(2026, 11, 14, 0, 29), HST) == "2026-11-13T14"
    assert obs.hour_key(utc(2026, 11, 14, 0, 30), HST) == "2026-11-13T15"


def test_aggregate_mean_max_and_vector_direction():
    samples = [
        obs.Sample(utc(2026, 11, 13, 23, 36), 10.0, 14.0, 350.0),
        obs.Sample(utc(2026, 11, 13, 23, 42), 20.0, 26.0, 10.0),
        obs.Sample(utc(2026, 11, 13, 23, 48), None, None, None),  # blank: ignored
        obs.Sample(utc(2026, 11, 13, 23, 54), 12.0, None, 2.0),
    ]
    rec = obs.aggregate(samples, HST)["2026-11-13T14"]
    assert rec["kn"] == pytest.approx(14.0)
    assert rec["gust"] == 26.0
    assert rec["dir"] in (3, 4, 5)  # wraps around north instead of averaging to ~120°
    assert rec["n"] == 3


def test_aggregate_without_gusts_or_direction():
    rec = obs.aggregate([obs.Sample(utc(2026, 11, 13, 20, 0), 0.0, None, None)], HST)["2026-11-13T10"]
    assert rec == {"kn": 0.0, "gust": None, "dir": None, "n": 1}


# ---------------------------------------------------------------- merging

def test_merge_keeps_complete_bins_and_accepts_fills(tmp_path):
    full = {"2026-11-13T14": {"kn": 14.0, "gust": 20.0, "dir": 70, "n": 10}}
    assert obs.merge(tmp_path, COOPS, full) == 1
    partial = {"2026-11-13T14": {"kn": 9.0, "gust": 11.0, "dir": 70, "n": 3}}
    assert obs.merge(tmp_path, COOPS, partial) == 0  # edge-of-window bin never overwrites
    corrected = {"2026-11-13T14": {"kn": 14.2, "gust": 20.0, "dir": 71, "n": 10}}
    assert obs.merge(tmp_path, COOPS, corrected) == 1
    assert obs.merge(tmp_path, COOPS, corrected) == 0  # idempotent
    doc = json.loads((tmp_path / "2026-11.json").read_text())
    assert doc["station"] == "1615680" and doc["month"] == "2026-11"
    assert doc["hours"]["2026-11-13T14"]["kn"] == 14.2


def test_merge_splits_months(tmp_path):
    recs = {"2026-10-31T23": {"kn": 5.0, "gust": None, "dir": 90, "n": 1},
            "2026-11-01T00": {"kn": 6.0, "gust": None, "dir": 90, "n": 1}}
    assert obs.merge(tmp_path, NWS, recs) == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-10.json", "2026-11.json"]


def test_update_obs_isolates_station_failures(tmp_path):
    def fetch(url):
        if "weather.gov" in url:
            raise FetchError("NWS down")
        return (FIXTURES / "coops_wind.json").read_bytes()

    status = obs.update_obs(tmp_path, [NWS, COOPS], HST, utc(2026, 11, 13, 11), days=1, fetch=fetch)
    assert status["PHOG"]["status"] == "error"
    assert status["1615680"]["status"] == "ok"
    assert (tmp_path / "archive" / "obs" / "1615680" / "2026-11.json").exists()
