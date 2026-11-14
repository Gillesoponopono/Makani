import copy
from datetime import timedelta, timezone

import pytest

from makani import mapframes
from makani.validate import ValidationError

HST = timezone(timedelta(hours=-10))
BBOX = {"latMin": 20.5, "latMax": 21.1, "lonMin": -156.72, "lonMax": -155.95}
LATS = [20.506 + 0.036 * i for i in range(10)]
LONS = [-156.72 + 0.04 * j for j in range(10)]


def rows(hours=30, missing=()):
    out = []
    for h in range(hours):
        t = f"2026-11-{13 + (10 + h) // 24:02d}T{(10 + h) % 24:02d}:00:00Z"
        for i, la in enumerate(LATS):
            for j, lo in enumerate(LONS):
                u = None if (h, i, j) in missing else -5.0 - i  # speed grows with latitude
                out.append({"time": t, "latitude": la, "longitude": lo, "Uwind": u, "Vwind": 0.0})
    return out


def test_frames_are_row_major_quantized_and_local():
    doc = mapframes.build_frames(rows(), BBOX, 2, HST, (20.9, -156.45))
    assert len(doc["lats"]) == 10 and len(doc["lons"]) == 10
    assert doc["times"][0] == "2026-11-13T00:00:00-10:00"
    f0 = doc["kn10"][0]
    assert f0[0] == round(5.0 * 1.943844 * 10)          # lat 0, lon 0
    assert f0[3 * 10 + 7] == round(8.0 * 1.943844 * 10)  # lat 3, lon 7
    assert doc["dir"][0][0] == 90                        # u<0, v=0: wind from the east
    assert doc["daylight"][0] is False and doc["daylight"][12] is True
    mapframes.validate_frames(doc)


def test_missing_values_become_null():
    doc = mapframes.build_frames(rows(missing={(0, 2, 2)}), BBOX, 2, HST, (20.9, -156.45))
    assert doc["kn10"][0][2 * 10 + 2] is None and doc["dir"][0][2 * 10 + 2] is None
    mapframes.validate_frames(doc)


def test_validation_rejects_bad_frames():
    good = mapframes.build_frames(rows(), BBOX, 2, HST, (20.9, -156.45))
    with pytest.raises(ValidationError):
        mapframes.validate_frames(mapframes.build_frames(rows(hours=10), BBOX, 2, HST, (20.9, -156.45)))
    bad = copy.deepcopy(good)
    bad["kn10"][3] = bad["kn10"][3][:-1]
    with pytest.raises(ValidationError):
        mapframes.validate_frames(bad)
    bad = copy.deepcopy(good)
    bad["times"][5] = bad["times"][6]
    with pytest.raises(ValidationError):
        mapframes.validate_frames(bad)
    bad = copy.deepcopy(good)
    for fr in bad["kn10"][:10]:
        fr[:] = [None] * len(fr)
    with pytest.raises(ValidationError):
        mapframes.validate_frames(bad)
