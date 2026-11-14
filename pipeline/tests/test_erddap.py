from pathlib import Path

import pytest

from makani import erddap

FIXTURES = Path(__file__).parent / "fixtures"


def test_griddap_url_shape():
    url = erddap.griddap_url(["Uwind", "Vwind"], "2026-11-14T10:00:00Z", (20.92, 20.92), (-156.44, -156.44))
    assert url.startswith("https://pae-paha.pacioos.hawaii.edu/erddap/griddap/wrf_mo.json?")
    query = url.split("?", 1)[1]
    assert query.count("%5B") == 6 and query.count("%5D") == 6
    assert "Uwind%5B(2026-11-14T10:00:00Z):1:(last)%5D%5B(20.92):1:(20.92)%5D%5B(-156.44):1:(-156.44)%5D" in query
    assert ",Vwind%5B" in query


def test_parse_recorded_point():
    rows = erddap.parse_table((FIXTURES / "erddap_point.json").read_bytes())
    assert len(rows) == 6
    assert rows[0]["time"] == "2026-11-14T10:00:00Z"
    assert set(rows[0]) == {"time", "latitude", "longitude", "Uwind", "Vwind", "Tair", "rain"}


def test_html_proxy_error_raises():
    with pytest.raises(erddap.ErddapError):
        erddap.parse_table(b"<html><h1>Proxy Error</h1></html>")


def test_coverage_end_from_info():
    csv = (FIXTURES / "info_index.csv").read_bytes()
    assert erddap.coverage_end(lambda url: csv) == "2026-11-18T00:00:00Z"


def test_coverage_end_missing():
    with pytest.raises(erddap.ErddapError):
        erddap.coverage_end(lambda url: b"Row Type,Variable Name\n")
