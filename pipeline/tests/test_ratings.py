import math

import pytest

from makani.config import load_ratings, load_spots
from makani.ratings import (classify_sector, compass, display_kn, in_range, ms_to_kn,
                            sports_for, uv_to_speed_dir)

RATINGS = load_ratings()
SPOTS = {s["id"]: s for s in load_spots()["spots"]}


def test_ms_to_kn():
    assert ms_to_kn(10) == pytest.approx(19.43844)


@pytest.mark.parametrize("u,v,expected", [
    (0, -5, 0),     # air moving south -> wind from N
    (-5, 0, 90),    # air moving west  -> from E
    (0, 5, 180),    # air moving north -> from S
    (5, 0, 270),    # air moving east  -> from W
    (-5, -5, 45),   # from NE
])
def test_uv_to_direction_quadrants(u, v, expected):
    speed, deg = uv_to_speed_dir(u, v)
    assert deg == expected
    assert speed == pytest.approx(math.hypot(u, v))


def test_typical_trade_wind_is_ene():
    _, deg = uv_to_speed_dir(-9.216081, -1.8918515)  # recorded Kanaha cell value
    assert 70 <= deg <= 85
    assert compass(deg) in ("ENE", "E")


@pytest.mark.parametrize("deg,start,end,inside", [
    (50, 30, 100, True),
    (100, 30, 100, False),   # half-open
    (30, 30, 100, True),
    (350, 340, 30, True),    # wrap-around
    (0, 340, 30, True),
    (29.9, 340, 30, True),
    (30, 340, 30, False),
    (200, 340, 30, False),
    (360, 0, 30, True),      # 360 normalises to 0
])
def test_in_range(deg, start, end, inside):
    assert in_range(deg, start, end) is inside


def test_kanaha_sectors():
    s = SPOTS["kanaha"]["sectors"]
    assert classify_sector(70, s) == "good"
    assert classify_sector(10, s) == "ok"
    assert classify_sector(120, s) == "ok"
    assert classify_sector(140, s) == "poor"
    assert classify_sector(200, s) == "danger"


def test_maui_sunset_wraparound_and_offshore():
    s = SPOTS["maui-sunset"]["sectors"]
    assert classify_sector(10, s) == "good"
    assert classify_sector(350, s) == "good"
    assert classify_sector(320, s) == "ok"
    assert classify_sector(70, s) == "danger"   # ENE trades are offshore in Kihei
    assert classify_sector(250, s) == "poor"


def test_danger_wins_over_overlaps():
    sectors = {"good": [[0, 360]], "danger": [[90, 100]]}
    assert classify_sector(95, sectors) == "danger"


@pytest.mark.parametrize("kn,expected", [
    (8, []),
    (10, ["foil_wing"]),
    (16, ["foil_wing", "directional"]),
    (19, ["foil_wing", "directional", "twintip"]),
    (20, ["directional", "twintip"]),
    (26, ["twintip"]),
    (30, ["expert"]),
    (45, ["expert"]),
])
def test_overlapping_sport_bands(kn, expected):
    assert sports_for(kn, "good", RATINGS) == expected
    assert sports_for(kn, "ok", RATINGS) == expected


# 10.45 is stored as the float 10.4499..., published as 10.4, so the site shows 10.
@pytest.mark.parametrize("kn,shown", [(9.6, 10), (9.44, 9), (10.45, 10), (10.5, 11), (12.5, 13), (29.96, 30)])
def test_display_kn_matches_js_rounding(kn, shown):
    assert display_kn(kn) == shown


def test_no_sports_in_danger_or_poor():
    assert sports_for(20, "danger", RATINGS) == []
    assert sports_for(20, "poor", RATINGS) == []


def test_compass_points():
    assert compass(0) == "N"
    assert compass(359) == "N"
    assert compass(67.5) == "ENE"
    assert compass(225) == "SW"
